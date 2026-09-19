"""Command line.

python -m joto_guard calibrate-light --reference <file>
python -m joto_guard wbgt
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

from .forecast import DEFAULT_MODEL, FORECAST_URL, fetch_json, forecast_wbgt, request_params
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
    forecast.set_defaults(handler=station_forecast)

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
    out = args.processed / "wbgt_forecast.csv"
    csv_ready(table).to_csv(out, index=False)

    timezone = load_config(args.config).station.display_timezone
    local = table["hour_utc"].dt.tz_convert(timezone)
    print(f"Forecast from {source}: {len(table)} hours")
    for day, hours in table.groupby(local.dt.date):
        if len(hours) < MIN_HOURS_PER_DAY:
            continue
        peak = hours.loc[hours["wbgt_c"].idxmax()]
        print(
            f"  {day}: highest WBGT {peak['wbgt_c']:.1f} degC at "
            f"{peak['hour_utc'].tz_convert(timezone):%H:%M} ({len(hours)} hours)"
        )
    print("Raw model output, not yet corrected to the station")
    print(f"Wrote {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
