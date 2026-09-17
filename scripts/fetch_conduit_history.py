#!/usr/bin/env python3
"""
fetch_conduit_history.py
------------------------
Data-preparation helper for Hack The Weather 2026.

Pulls the full observation history of one or more instruments from the UCAR
3D-PAWS FEWS NET CHORDS portal (3d-fewsnet.icdp.ucar.edu) in monthly chunks and
saves each chunk as the portal sent it, GeoCSV header and all, so that
`python -m conduit_sentinel <folder>` can read the station metadata from it.

The Conduit@Empathy1 station at JKUAT is instrument 61.

Credentials: register at https://3d-fewsnet.icdp.ucar.edu/users/sign_up, then
copy the API key from your profile page and export it. New accounts start as
"guest": a portal admin has to grant "Registered User" and "Data Downloader"
first, or every request comes back as HTTP 406.

    export CHORDS_EMAIL="you@example.com"
    export CHORDS_API_KEY="xxxxxxxxxxxxxxxx"

Usage examples:

    python fetch_conduit_history.py --instrument 61 --start 2025-05-30 --end 2026-09-16
    python fetch_conduit_history.py --instrument 61 10 1 6 31 34 --start 2025-06-01 --end 2026-09-16 --out data/raw/portal

Requires: requests, pandas  (pip install requests pandas)
"""
from __future__ import annotations

import argparse
import io
import os
import sys
import time
from datetime import date, datetime, timedelta
from pathlib import Path

import pandas as pd
import requests

PORTAL_HOSTS = ["https://3d-fewsnet.icdp.ucar.edu", "http://3d-fewsnet.icdp.ucar.edu"]


def month_chunks(start: date, end: date):
    """Yield (chunk_start, chunk_end) date pairs, one per calendar month, end exclusive."""
    cur = start
    while cur < end:
        nxt = (cur.replace(day=1) + timedelta(days=32)).replace(day=1)
        yield cur, min(nxt, end)
        cur = nxt


def parse_geocsv(text: str) -> tuple[dict, pd.DataFrame]:
    """Split a CHORDS GeoCSV export into its comment metadata and a DataFrame."""
    meta, rows = {}, []
    for line in text.splitlines():
        if line.startswith("#"):
            body = line.lstrip("#").strip()
            if ":" in body:
                k, v = body.split(":", 1)
                meta[k.strip()] = v.strip()
        elif line.strip():
            rows.append(line)
    if not rows:
        return meta, pd.DataFrame()
    df = pd.read_csv(io.StringIO("\n".join(rows)))
    if "Time" in df.columns:
        df["Time"] = pd.to_datetime(df["Time"], utc=True, errors="coerce")
    return meta, df


def fetch_chunk(instrument: int, start: date, end: date, email: str, api_key: str,
                session: requests.Session, retries: int = 3) -> tuple[dict, pd.DataFrame, str]:
    params = {
        "start": f"{start.isoformat()}T00:00",
        "end": f"{end.isoformat()}T00:00",
        "email": email,
        "api_key": api_key,
    }
    last_err: Exception | None = None
    for host in PORTAL_HOSTS:
        url = f"{host}/instruments/{instrument}.csv"
        for attempt in range(1, retries + 1):
            try:
                r = session.get(url, params=params, timeout=120,
                                headers={"Accept": "text/csv, text/plain, */*"})
                if r.status_code == 406:
                    raise PermissionError(
                        "HTTP 406: the portal requires a valid email + api_key pair. "
                        "Check CHORDS_EMAIL / CHORDS_API_KEY.")
                r.raise_for_status()
                meta, df = parse_geocsv(r.text)
                return meta, df, r.text
            except PermissionError:
                raise
            except Exception as e:  # network or 5xx: back off and retry
                last_err = e
                time.sleep(2 * attempt)
        # try the next host
    raise RuntimeError(f"Failed to fetch instrument {instrument} {start}..{end}: {last_err}")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--instrument", type=int, nargs="+", default=[61], help="CHORDS instrument id(s); 61 = Conduit@Empathy1")
    ap.add_argument("--start", type=date.fromisoformat, default=date(2025, 5, 30))
    ap.add_argument("--end", type=date.fromisoformat, default=date.today() + timedelta(days=1), help="exclusive")
    ap.add_argument("--out", type=Path, default=Path("data/raw/portal"))
    ap.add_argument("--sleep", type=float, default=1.0, help="seconds between requests (be polite)")
    ap.add_argument("--skip-existing", action="store_true", help="do not re-download chunks already on disk")
    args = ap.parse_args()

    email, api_key = os.environ.get("CHORDS_EMAIL"), os.environ.get("CHORDS_API_KEY")
    if not email or not api_key:
        print("Set CHORDS_EMAIL and CHORDS_API_KEY in the environment first.", file=sys.stderr)
        return 2

    args.out.mkdir(parents=True, exist_ok=True)
    session = requests.Session()

    for inst in args.instrument:
        written, rows_total, meta_seen = [], 0, {}
        for cs, ce in month_chunks(args.start, args.end):
            fn = args.out / f"instrument_{inst}_{cs.isoformat()}_{ce.isoformat()}.csv"
            if args.skip_existing and fn.exists():
                meta, df = parse_geocsv(fn.read_text(encoding="utf-8"))
                print(f"[{inst}] {cs} .. {ce}: cached {len(df):>7} rows")
                meta_seen = meta or meta_seen
                written.append(fn)
                rows_total += len(df)
                continue
            meta, df, text = fetch_chunk(inst, cs, ce, email, api_key, session)
            meta_seen = meta or meta_seen
            print(f"[{inst}] {cs} .. {ce}: {len(df):>7} rows")
            if not df.empty:
                # Keep the GeoCSV exactly as the portal sent it: conduit_sentinel reads the
                # "# key: value" header for the station's id, position and measurement count.
                fn.write_text(text, encoding="utf-8")
                written.append(fn)
                rows_total += len(df)
            time.sleep(args.sleep)

        if not written:
            print(f"[{inst}] no data returned", file=sys.stderr)
            continue
        print(f"[{inst}] wrote {len(written)} files to {args.out} ({rows_total:,} rows in total)")
        print(f"[{inst}] quality-control them with: python -m conduit_sentinel {args.out}")
        if meta_seen:
            print(f"[{inst}] instrument: {meta_seen.get('instrument_name', '?')} "
                  f"lat {meta_seen.get('data collection latitude', '?')} "
                  f"lon {meta_seen.get('data collection longitude', '?')} "
                  f"elev {meta_seen.get('data collection elevation', '?')}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
