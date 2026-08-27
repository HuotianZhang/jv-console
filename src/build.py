#!/usr/bin/env python3
"""Build a self-contained index.html from the app template.

The template carries a single placeholder, /*__DATA__*/, where a JSON dataset is
injected. With no --data argument an empty dataset is written, so the page opens
as an empty folder and you load your own scans through "Import files…" or by
dropping .dat files onto the left pane.

    python3 src/build.py                       # empty app -> index.html
    python3 src/build.py --data my_data.json   # pre-loaded app
    python3 src/build.py --data my.json -o demo.html

Produce a dataset with tools/parse_dat.py.
"""
from __future__ import annotations

import argparse
import json
import pathlib
import sys

HERE = pathlib.Path(__file__).resolve().parent
ROOT = HERE.parent
TEMPLATE = HERE / "app.template.html"
PLACEHOLDER = "/*__DATA__*/"

EMPTY = {"folder": "", "pixels": list("abcdef"), "scans": []}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--data", type=pathlib.Path,
                    help="dataset JSON from tools/parse_dat.py (default: an empty dataset)")
    ap.add_argument("-o", "--out", type=pathlib.Path, default=ROOT / "index.html",
                    help="output HTML file (default: index.html at the repo root)")
    args = ap.parse_args(argv)

    template = TEMPLATE.read_text(encoding="utf-8")
    if PLACEHOLDER not in template:
        print(f"error: {TEMPLATE} has no {PLACEHOLDER} placeholder", file=sys.stderr)
        return 1

    if args.data:
        payload = json.loads(args.data.read_text(encoding="utf-8"))
        for key in ("pixels", "scans"):
            if key not in payload:
                print(f"error: {args.data} has no '{key}' key", file=sys.stderr)
                return 1
        label = f"{len(payload['scans'])} scan(s) from {args.data}"
    else:
        payload = EMPTY
        label = "empty dataset"

    out = template.replace(PLACEHOLDER, json.dumps(payload, separators=(",", ":")))
    args.out.write_text(out, encoding="utf-8")
    print(f"wrote {args.out}  ({len(out) / 1024:.0f} kB, {label})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
