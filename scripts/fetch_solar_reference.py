#!/usr/bin/env python3
"""Download hourly ERA5 solar radiation at the station from the Open-Meteo archive API.

The response is saved exactly as received, for `python -m joto_guard calibrate-light`.
No key is needed. Open-Meteo data is licensed CC BY 4.0; ERA5 contains modified
Copernicus Climate Change Service information. ERA5 runs about five days behind real time.

NASA POWER, the reference in the build plan, had no hourly solar values yet for
28 Aug to 15 Sep 2026 when checked on 18 Sep 2026 (every hour was the fill value -999).

    python scripts/fetch_solar_reference.py --start 2026-08-28 --end 2026-09-15
"""

import argparse
import json
import sys
import urllib.parse
import urllib.request
from datetime import date
from pathlib import Path

ARCHIVE_URL = "https://archive-api.open-meteo.com/v1/archive"
STATION = {"latitude": -1.099736, "longitude": 37.014528}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--start", type=date.fromisoformat, required=True)
    parser.add_argument("--end", type=date.fromisoformat, required=True)
    parser.add_argument("--latitude", type=float, default=STATION["latitude"])
    parser.add_argument("--longitude", type=float, default=STATION["longitude"])
    parser.add_argument("--out", type=Path, default=Path("data/reference"))
    args = parser.parse_args()

    query = urllib.parse.urlencode(
        {
            "latitude": args.latitude,
            "longitude": args.longitude,
            "start_date": args.start.isoformat(),
            "end_date": args.end.isoformat(),
            "hourly": "shortwave_radiation,direct_radiation,diffuse_radiation,cloud_cover",
            "models": "era5",
            "timezone": "GMT",
        }
    )
    with urllib.request.urlopen(f"{ARCHIVE_URL}?{query}", timeout=90) as response:
        body = response.read()

    payload = json.loads(body)
    if "hourly" not in payload:
        print(f"error: {payload.get('reason', 'no hourly data in the response')}", file=sys.stderr)
        return 1

    args.out.mkdir(parents=True, exist_ok=True)
    path = args.out / f"open_meteo_era5_{args.start}_{args.end}.json"
    path.write_bytes(body)

    values = payload["hourly"]["shortwave_radiation"]
    filled = [t for t, v in zip(payload["hourly"]["time"], values, strict=True) if v is not None]
    last = filled[-1] if filled else "none"
    print(f"wrote {path}: {len(filled)} of {len(values)} hours have values (last {last})")
    print(f"grid point {payload['latitude']}, {payload['longitude']}, {payload['elevation']} m")
    return 0


if __name__ == "__main__":
    sys.exit(main())
