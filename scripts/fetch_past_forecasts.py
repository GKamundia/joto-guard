#!/usr/bin/env python3
"""Download the forecasts a weather model made for the station's past hours.

For every hour from --start to --end, Open-Meteo's Previous Runs API returns the value
forecast 0, 1, 2 ... days before that hour. Comparing them with the station's own WBGT
shows how the forecast errs at each lead time and hour of day, which the forecast
correction learns from. The decoded response is saved as JSON. No key is needed;
Open-Meteo data is licensed CC BY 4.0, and ECMWF IFS open data is CC BY 4.0. Archives
start in January 2024 for most models.

    python scripts/fetch_past_forecasts.py --start 2026-08-28 --end 2026-09-15
"""

import argparse
import json
import sys
from datetime import date
from pathlib import Path

from joto_guard.forecast import DEFAULT_MODEL, PAST_FORECASTS_URL, fetch_json, request_params

STATION = {"latitude": -1.099736, "longitude": 37.014528, "elevation_m": 1523.0}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--start", type=date.fromisoformat, required=True)
    parser.add_argument("--end", type=date.fromisoformat, required=True)
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument("--lead-days", type=int, nargs="+", default=[0, 1, 2, 3])
    parser.add_argument("--out", type=Path, default=Path("data/reference"))
    args = parser.parse_args()

    params = request_params(
        STATION["latitude"],
        STATION["longitude"],
        STATION["elevation_m"],
        args.model,
        tuple(args.lead_days),
        start_date=args.start.isoformat(),
        end_date=args.end.isoformat(),
    )
    try:
        payload = fetch_json(PAST_FORECASTS_URL, params, timeout_s=120)
    except (OSError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    args.out.mkdir(parents=True, exist_ok=True)
    path = args.out / f"open_meteo_{args.model}_past_forecasts_{args.start}_{args.end}.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    hours = len(payload["hourly"]["time"])
    print(f"wrote {path}: {hours} hours, lead days {', '.join(map(str, args.lead_days))}")
    print(f"grid point {payload['latitude']}, {payload['longitude']}, {payload['elevation']} m")
    return 0


if __name__ == "__main__":
    sys.exit(main())
