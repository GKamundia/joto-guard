"""Command line: python -m joto_guard calibrate-light --reference <file>"""

import argparse
import json
import sys
from collections.abc import Sequence
from pathlib import Path

import pandas as pd

from conduit_sentinel.pipeline import csv_ready

from .solar_calibration import calibrate, ghi_hourly, reference_from_open_meteo, save

DEFAULT_REFERENCE_NAME = "ERA5 hourly shortwave radiation, Open-Meteo archive API (models=era5)"


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="joto-guard")
    commands = parser.add_subparsers(dest="command", required=True)

    light = commands.add_parser(
        "calibrate-light",
        help="fit the light-sensor calibration against a solar reference",
        description="Fit counts-to-GHI for the SI1145 light sensor and write the estimates.",
    )
    light.add_argument(
        "--processed",
        type=Path,
        default=Path("data/processed"),
        help="Sentinel outputs holding obs_hourly.csv and report.json (default: data/processed)",
    )
    light.add_argument(
        "--reference",
        type=Path,
        required=True,
        help="Open-Meteo archive response saved by scripts/fetch_solar_reference.py",
    )
    light.add_argument("--reference-name", default=DEFAULT_REFERENCE_NAME)
    light.add_argument("--out", type=Path, default=Path("config/solar_calibration.json"))

    args = parser.parse_args(argv)
    try:
        return calibrate_light(args)
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


if __name__ == "__main__":
    sys.exit(main())
