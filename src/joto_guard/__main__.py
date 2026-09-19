"""Command line.

python -m joto_guard calibrate-light --reference <file>
python -m joto_guard wbgt
python -m joto_guard fit-correction --past-forecasts <file>
python -m joto_guard forecast
"""

import argparse
import json
import sys
from collections.abc import Sequence
from datetime import UTC, datetime
from pathlib import Path

import pandas as pd

from conduit_sentinel.audit import is_night
from conduit_sentinel.config import load_config
from conduit_sentinel.pipeline import csv_ready

from . import bands, bias, verify
from .forecast import (
    DEFAULT_MODEL,
    FORECAST_URL,
    fetch_json,
    forecast_wbgt,
    request_params,
    variable_name,
)
from .guidance import forecast_guidance
from .solar_calibration import calibrate, ghi_hourly, load, reference_from_open_meteo, save
from .station_wbgt import firmware_by_local_hour, mean_difference, wbgt_hourly
from .wbgt import REFERENCE_HEIGHT_M

DEFAULT_REFERENCE_NAME = "ERA5 hourly shortwave radiation, Open-Meteo archive API (models=era5)"

# Local hours summarised as "midday" in the firmware comparison.
MIDDAY_HOURS = range(10, 16)

# Local days with fewer forecast hours than this are not summarised.
MIN_HOURS_PER_DAY = 12

PROCESSED_HELP = "Sentinel's obs_hourly.csv and report.json (default: data/processed)"


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="joto-guard")
    commands = parser.add_subparsers(dest="command", required=True)

    light = commands.add_parser(
        "calibrate-light",
        help="fit the light-sensor calibration against a solar reference",
        description="Fit counts-to-GHI for the SI1145 light sensor and write the estimates.",
    )
    light.add_argument(
        "--processed", type=Path, default=Path("data/processed"), help=PROCESSED_HELP
    )
    light.add_argument(
        "--reference",
        type=Path,
        required=True,
        help="Open-Meteo archive response saved by scripts/fetch_solar_reference.py",
    )
    light.add_argument("--reference-name", default=DEFAULT_REFERENCE_NAME)
    light.add_argument("--out", type=Path, default=Path("config/solar_calibration.json"))
    light.set_defaults(handler=calibrate_light)

    wbgt = commands.add_parser(
        "wbgt",
        help="compute the station's hourly WBGT (Liljegren et al. 2008)",
        description="Hourly WBGT from the Sentinel outputs and the light calibration, "
        "compared with the firmware's WBGT column.",
    )
    wbgt.add_argument("--processed", type=Path, default=Path("data/processed"), help=PROCESSED_HELP)
    wbgt.add_argument("--calibration", type=Path, default=Path("config/solar_calibration.json"))
    wbgt.add_argument(
        "--config",
        type=Path,
        default=Path("config/qc_rules.yaml"),
        help="Sentinel configuration, for the local time zone and night hours",
    )
    wbgt.add_argument(
        "--wind-height",
        type=float,
        default=REFERENCE_HEIGHT_M,
        help="anemometer height in metres (default 2, which needs no adjustment)",
    )
    wbgt.set_defaults(handler=station_wbgt)

    forecast = commands.add_parser(
        "forecast",
        help="forecast hourly WBGT at the station from Open-Meteo",
        description="Fetch an hourly weather forecast for the station and compute its WBGT "
        "the same way as the station's.",
    )
    forecast.add_argument(
        "--processed", type=Path, default=Path("data/processed"), help=PROCESSED_HELP
    )
    forecast.add_argument("--days", type=int, default=3, help="days ahead, 1 to 16 (default 3)")
    forecast.add_argument(
        "--model", default=DEFAULT_MODEL, help=f"Open-Meteo model (default {DEFAULT_MODEL})"
    )
    forecast.add_argument(
        "--payload",
        type=Path,
        help="compute from a saved Open-Meteo response instead of fetching a new one",
    )
    forecast.add_argument(
        "--config",
        type=Path,
        default=Path("config/qc_rules.yaml"),
        help="Sentinel configuration, for the local time zone",
    )
    forecast.add_argument(
        "--raw-dir",
        type=Path,
        default=Path("data/reference"),
        help="where a fetched response is saved (default: data/reference)",
    )
    forecast.add_argument(
        "--correction",
        type=Path,
        default=Path("config/forecast_correction.json"),
        help="correction towards the station, from fit-correction (skipped if the file is absent)",
    )
    forecast.add_argument(
        "--guidance",
        type=Path,
        default=Path("config/heat_guidance.yaml"),
        help="heat limits and advice by type of work (default: config/heat_guidance.yaml)",
    )
    forecast.set_defaults(handler=station_forecast)

    correction = commands.add_parser(
        "fit-correction",
        help="fit the forecast's correction towards the station, by hour of day",
        description="Compare past forecasts with the station's WBGT (wbgt_hourly.csv) and save "
        "the hourly offsets and uncertainty band.",
    )
    correction.add_argument(
        "--processed", type=Path, default=Path("data/processed"), help=PROCESSED_HELP
    )
    correction.add_argument(
        "--past-forecasts",
        type=Path,
        required=True,
        help="Open-Meteo response saved by scripts/fetch_past_forecasts.py",
    )
    correction.add_argument("--model", default=DEFAULT_MODEL)
    correction.add_argument(
        "--config",
        type=Path,
        default=Path("config/qc_rules.yaml"),
        help="Sentinel configuration, for the local time zone",
    )
    correction.add_argument("--out", type=Path, default=Path("config/forecast_correction.json"))
    correction.set_defaults(handler=fit_correction)

    check = commands.add_parser(
        "verify",
        help="check the forecast against the station at the level, not just the temperature",
        description="Score the corrected forecast on days left out of its fit: the error, how "
        "often the level it implies matches the one the station justified, and how often it "
        "said an hour was safer than it was.",
    )
    check.add_argument(
        "--processed", type=Path, default=Path("data/processed"), help=PROCESSED_HELP
    )
    check.add_argument(
        "--past-forecasts",
        type=Path,
        required=True,
        help="Open-Meteo response saved by scripts/fetch_past_forecasts.py",
    )
    check.add_argument(
        "--config",
        type=Path,
        default=Path("config/qc_rules.yaml"),
        help="Sentinel configuration, for the local time zone",
    )
    check.add_argument("--guidance", type=Path, default=Path("config/heat_guidance.yaml"))
    check.add_argument("--out", type=Path, default=Path("data/processed/verification.json"))
    check.set_defaults(handler=run_verify)

    args = parser.parse_args(argv)
    try:
        return args.handler(args)
    except (OSError, KeyError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1


def calibrate_light(args: argparse.Namespace) -> int:
    report = json.loads((args.processed / "report.json").read_text(encoding="utf-8"))
    hourly = pd.read_csv(args.processed / "obs_hourly.csv")
    payload = json.loads(args.reference.read_text(encoding="utf-8"))

    station = report["station"]
    latitude, longitude = station["latitude"], station["longitude"]
    dark_floor = report["light"]["night_counts"]["light_ir_counts"]["median"]
    reference_name = f"{args.reference_name}, grid {payload['latitude']}, {payload['longitude']}"

    calibration = calibrate(
        hourly,
        reference_from_open_meteo(payload),
        latitude,
        longitude,
        dark_floor,
        reference_name,
    )
    args.out.parent.mkdir(parents=True, exist_ok=True)
    save(calibration, args.out)

    estimates = ghi_hourly(hourly, calibration, latitude, longitude)
    estimates_path = args.processed / "ghi_hourly.csv"
    csv_ready(estimates).to_csv(estimates_path, index=False)

    daylight, high_sun = calibration.held_out["daylight"], calibration.held_out["high_sun"]
    print(
        f"Fitted on {calibration.n_days} days ({calibration.first_day} to {calibration.last_day}), "
        f"{calibration.n_hours} daylight hours"
    )
    print(
        f"GHI = (IR - {calibration.dark_floor_counts:g}) x "
        f"({calibration.a:.5f} + {calibration.b:.5f} x (1 - mu))"
    )
    print(
        f"Days left out of the fit: RMSE {daylight['rmse_wm2']:g} W/m2 over daylight, "
        f"{high_sun['rmse_wm2']:g} W/m2 with the sun above 30 degrees"
    )
    clear = calibration.held_out.get("clear_reference_sky")
    if clear:
        print(
            f"Under a clear reference sky ({clear['n_hours']} hours): "
            f"RMSE {clear['rmse_wm2']:g} W/m2, R2 {clear['r2']:g}"
        )
    print(f"Wrote {args.out} and {estimates_path}")
    return 0


def station_wbgt(args: argparse.Namespace) -> int:
    report = json.loads((args.processed / "report.json").read_text(encoding="utf-8"))
    hourly = pd.read_csv(args.processed / "obs_hourly.csv")
    hourly["hour_utc"] = pd.to_datetime(hourly["hour_utc"], utc=True)
    calibration = load(args.calibration)
    config = load_config(args.config)
    timezone = config.station.display_timezone

    station = report["station"]
    table = wbgt_hourly(
        hourly, calibration, station["latitude"], station["longitude"], args.wind_height
    )
    by_hour = firmware_by_local_hour(table, timezone)

    table_path = args.processed / "wbgt_hourly.csv"
    by_hour_path = args.processed / "wbgt_firmware_by_hour.csv"
    csv_ready(table).to_csv(table_path, index=False)
    by_hour.to_csv(by_hour_path, index=False)

    computed = table.dropna(subset=["wbgt_c"])
    print(
        f"WBGT for {len(computed)} of {len(table)} station hours "
        "(the others lack a quality-controlled input)"
    )
    if not computed.empty:
        peak = computed.loc[computed["wbgt_c"].idxmax()]
        local = peak["hour_utc"].tz_convert(timezone)
        print(f"Highest hour: {peak['wbgt_c']:.1f} degC at {local:%Y-%m-%d %H:%M} local time")
    night_hours = by_hour["local_hour"][
        is_night(by_hour["local_hour"], config.audit.night_start_hour, config.audit.night_end_hour)
    ]
    print(
        "Firmware WBGT minus this model: "
        f"{mean_difference(by_hour, MIDDAY_HOURS):+.1f} degC from 10:00 to 15:59, "
        f"{mean_difference(by_hour, night_hours):+.1f} degC at night"
    )
    print(f"Wrote {table_path} and {by_hour_path}")
    return 0


def station_forecast(args: argparse.Namespace) -> int:
    report = json.loads((args.processed / "report.json").read_text(encoding="utf-8"))
    station = report["station"]
    latitude, longitude = station["latitude"], station["longitude"]

    if args.payload:
        payload = json.loads(args.payload.read_text(encoding="utf-8"))
        source = args.payload
    else:
        if not 1 <= args.days <= 16:
            raise ValueError("--days must be from 1 to 16")
        params = request_params(
            latitude, longitude, station["elevation_m"], args.model, forecast_days=args.days
        )
        payload = fetch_json(FORECAST_URL, params)
        fetched = datetime.now(UTC)
        args.raw_dir.mkdir(parents=True, exist_ok=True)
        source = args.raw_dir / f"open_meteo_{args.model}_forecast_{fetched:%Y%m%dT%H%MZ}.json"
        source.write_text(json.dumps(payload), encoding="utf-8")

    table = forecast_wbgt(payload, latitude, longitude)
    correction = bias.load(args.correction) if args.correction.exists() else None
    if correction is not None:
        table = bias.apply(table, correction)
    out = args.processed / "wbgt_forecast.csv"
    csv_ready(table).to_csv(out, index=False)

    timezone = load_config(args.config).station.display_timezone
    document = forecast_guidance(
        table,
        bands.load_guidance(args.guidance),
        {
            key: station[key]
            for key in ("name", "latitude", "longitude", "elevation_m")
            if key in station
        },
        timezone,
        args.model,
        datetime.now(UTC),
    )
    guidance_path = args.processed / "heat_guidance.json"
    guidance_path.write_text(json.dumps(document, indent=1) + "\n", encoding="utf-8")
    local = table["hour_utc"].dt.tz_convert(timezone)
    column = "wbgt_c" if correction is None else "wbgt_corrected_c"
    print(f"Forecast from {source}: {len(table)} hours")
    for day, hours in table.groupby(local.dt.date):
        if len(hours) < MIN_HOURS_PER_DAY:
            continue
        peak = hours.loc[hours[column].idxmax()]
        band = (
            ""
            if correction is None
            else f" (likely {peak['wbgt_low_c']:.1f} to {peak['wbgt_high_c']:.1f})"
        )
        print(
            f"  {day}: highest WBGT {peak[column]:.1f} degC{band} at "
            f"{peak['hour_utc'].tz_convert(timezone):%H:%M} ({len(hours)} hours)"
        )
    if correction is None:
        print(f"Raw model output: no correction at {args.correction}")
    else:
        print(f"Corrected towards the station with {args.correction}")
    for day in document["days"]:
        heavy = day["by_work_type"].get("heavy")
        if heavy and heavy["limited_from"]:
            print(
                f"  {day['date']}: heavy work needs work/rest from {heavy['limited_from']} "
                f"to {heavy['limited_until']}"
            )
    print(f"Wrote {out} and {guidance_path}")
    return 0


def _pairs_from(args: argparse.Namespace) -> tuple[pd.DataFrame, str, list[int]]:
    """Station hours paired with the archived forecasts made 0 to 3 days before them."""
    report = json.loads((args.processed / "report.json").read_text(encoding="utf-8"))
    station = pd.read_csv(args.processed / "wbgt_hourly.csv")
    station["hour_utc"] = pd.to_datetime(station["hour_utc"], utc=True)
    payload = json.loads(args.past_forecasts.read_text(encoding="utf-8"))
    timezone = load_config(args.config).station.display_timezone

    latitude, longitude = report["station"]["latitude"], report["station"]["longitude"]
    leads = [day for day in range(8) if variable_name("temperature_2m", day) in payload["hourly"]]
    forecasts = {day: forecast_wbgt(payload, latitude, longitude, day) for day in leads}
    return bias.pair_forecasts(station, forecasts, timezone), timezone, leads


def run_verify(args: argparse.Namespace) -> int:
    pairs, _, leads = _pairs_from(args)
    guidance = bands.load_guidance(args.guidance)
    result = verify.verify(pairs, guidance)

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")

    error = result["error_c"]
    print(
        f"{result['n_hours']} hours over {result['n_days']} days, forecasts made "
        f"{leads[0]} to {leads[-1]} days ahead, each day left out of the fit"
    )
    print(
        f"WBGT error: mean absolute {error['mae']:g}, RMSE {error['rmse']:g}, "
        f"bias {error['bias']:+g}, 90th percentile {error['p90_abs']:g}, "
        f"worst {error['worst_abs']:g} degC"
    )
    print("\nDoes it get the level right?")
    print(f"{'work type':12s} {'exact':>7s} {'said safer':>11s} {'said worse':>11s}")
    for work_type, row in result["levels"].items():
        print(
            f"{work_type:12s} {row['exact_pct']:6.1f}% {row['under_warned_pct']:10.1f}% "
            f"{row['over_warned_pct']:10.1f}%"
        )
    print("\nIf the band's upper edge were the warning instead of the central value")
    for work_type, row in result["levels_from_band_top"].items():
        print(
            f"{work_type:12s} {row['exact_pct']:6.1f}% {row['under_warned_pct']:10.1f}% "
            f"{row['over_warned_pct']:10.1f}%"
        )
    print(f"\nWrote {args.out}")
    return 0


def fit_correction(args: argparse.Namespace) -> int:
    pairs, timezone, leads = _pairs_from(args)
    correction = bias.fit(pairs, args.model, timezone)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    bias.save(correction, args.out)

    overall = correction.held_out["all"]
    print(
        f"Fitted on {correction.n_days} days ({correction.first_day} to {correction.last_day}), "
        f"forecasts made {leads[0]} to {leads[-1]} days ahead, {correction.n_pairs} pairs"
    )
    print(
        "Mean absolute error on days left out: "
        f"raw {overall['raw']['mae_c']:g} degC, corrected {overall['corrected']['mae_c']:g} degC, "
        f"the station's usual value for the hour {overall['station_usual']['mae_c']:g} degC"
    )
    print(
        f"The 80 % band held the station value {correction.held_out['band_held_station_pct']:g} % "
        "of the time"
    )
    print(f"Wrote {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
