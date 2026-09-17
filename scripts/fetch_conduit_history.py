#!/usr/bin/env python3
"""
fetch_conduit_history.py
------------------------
Data-preparation helper for Hack The Weather 2026.

Pulls the full observation history of one or more instruments from the UCAR
3D-PAWS FEWS NET CHORDS portal (3d-fewsnet.icdp.ucar.edu) in monthly chunks,
parses the GeoCSV comment header, and writes one CSV per chunk plus a single
concatenated file per instrument.

The Conduit@Empathy1 station at JKUAT is instrument 61.

Credentials: register at http://3d-fewsnet.icdp.ucar.edu/users/sign_up
(the portal is HTTP-only; use a throwaway password), then copy the API key
from your profile page and export:

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
                session: requests.Session, retries: int = 3) -> tuple[dict, pd.DataFrame]:
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
                return parse_geocsv(r.text)
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
        frames, meta_seen = [], {}
        for cs, ce in month_chunks(args.start, args.end):
            fn = args.out / f"instrument_{inst}_{cs.isoformat()}_{ce.isoformat()}.csv"
            if args.skip_existing and fn.exists():
                df = pd.read_csv(fn, parse_dates=["Time"])
                print(f"[{inst}] {cs} .. {ce}: cached {len(df):>7} rows")
                frames.append(df)
                continue
            meta, df = fetch_chunk(inst, cs, ce, email, api_key, session)
            meta_seen = meta or meta_seen
            print(f"[{inst}] {cs} .. {ce}: {len(df):>7} rows")
            if not df.empty:
                df.to_csv(fn, index=False)
                frames.append(df)
            time.sleep(args.sleep)

        if not frames:
            print(f"[{inst}] no data returned", file=sys.stderr)
            continue
        allv = (pd.concat(frames, ignore_index=True)
                  .drop_duplicates(subset="Time")
                  .sort_values("Time")
                  .reset_index(drop=True))
        out_all = args.out / f"instrument_{inst}_all.csv"
        allv.to_csv(out_all, index=False)
        (args.out / f"instrument_{inst}_meta.txt").write_text(
            "\n".join(f"{k}: {v}" for k, v in meta_seen.items()) + "\n")
        span = f"{allv['Time'].min()} -> {allv['Time'].max()}" if "Time" in allv else "n/a"
        print(f"[{inst}] wrote {out_all} ({len(allv):,} rows, {span})")
        if meta_seen:
            print(f"[{inst}] instrument: {meta_seen.get('instrument_name', '?')} "
                  f"lat {meta_seen.get('data collection latitude', '?')} "
                  f"lon {meta_seen.get('data collection longitude', '?')} "
                  f"elev {meta_seen.get('data collection elevation', '?')}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
