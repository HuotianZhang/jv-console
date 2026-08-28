#!/usr/bin/env python3
"""Parse LabVIEW solar-cell J(V) .dat files into the dataset the app consumes.

This is the reference implementation. The browser carries a JavaScript port
(see `parseDat` in src/app.template.html); the two are kept numerically
identical — see docs/labview-dat-format.md.

Nothing here is hardcoded to a particular sweep: the file is located by two
anchor tokens, `Pixel` and `Voltage`, each of which appears exactly once in
column one. Range, step, direction, point count and the pixel set are all read
from the file.

    python3 tools/parse_dat.py /path/to/measurement_folder -o data.json
    python3 src/build.py --data data.json          # -> a pre-loaded index.html
"""
from __future__ import annotations

import argparse
import glob
import io
import json
import os
import pathlib
import re
import sys

PIXELS = list("abcdef")

# QC bounds — a pixel outside any of these is flagged, never silently dropped.
QC = {"voc": (0.5, 1.3), "jsc": (1.0, 40.0), "ff": (0.20, 0.90), "pce": (0.5, 25.0)}

# Illumination is decided by the measured intensity, never by the column name or
# the filename: dark scans in the wild are labelled `_light`.
LIGHT_MIN = 10.0     # mW/cm^2
DARK_MAX = 1e-3


def sig(x, n=5):
    if x is None:
        return None
    x = float(x)
    if x != x or x in (float("inf"), float("-inf")):
        return None
    return float(f"%.{n}g" % x)


def classify(intensity: float) -> str:
    if intensity >= LIGHT_MIN:
        return "light"
    if intensity >= DARK_MAX:
        return "lowlight"
    return "dark"


def material_of(stem: str):
    m = re.match(r"^sample\d+_([A-Za-z0-9]+)", stem)
    if not m:
        return None
    tok = m.group(1)
    mm = re.match(r"^(PTQ10)(.+)$", tok)
    return f"{mm.group(1)}:{mm.group(2)}" if mm else tok


def lsq_slope(xs, ys):
    n = len(xs)
    if n < 4:
        return None
    sx = sum(xs); sy = sum(ys)
    sxx = sum(x * x for x in xs); sxy = sum(x * y for x, y in zip(xs, ys))
    d = n * sxx - sx * sx
    if abs(d) < 1e-12:
        return None
    return (n * sxy - sx * sy) / d


def slope_window(V, J, v0, half):
    """dV/dJ over a voltage window, converted from V/(mA cm^-2) to ohm cm^2."""
    xs = [j for v, j in zip(V, J) if v0 - half <= v <= v0 + half]
    ys = [v for v in V if v0 - half <= v <= v0 + half]
    a = lsq_slope(xs, ys)
    return None if a is None else a * 1000.0


def refine_mpp(V, J):
    """Parabolic interpolation of P(V) around the grid maximum.

    Removes the voltage-step quantisation visible in the file's own V_MMP.
    """
    P = [-v * j for v, j in zip(V, J)]
    k = max(range(len(P)), key=P.__getitem__)
    if k <= 0 or k >= len(V) - 1:
        return V[k], P[k]
    x0, x1, x2 = V[k - 1], V[k], V[k + 1]
    y0, y1, y2 = P[k - 1], P[k], P[k + 1]
    d1 = (y1 - y0) / (x1 - x0)
    d2 = (y2 - y1) / (x2 - x1)
    a = (d2 - d1) / (x2 - x0)
    if a == 0:
        return V[k], P[k]
    b = d1 - a * (x0 + x1)
    c = y0 - a * x0 * x0 - b * x0
    vm = -b / (2 * a)
    if not (x0 <= vm <= x2):
        return V[k], P[k]
    return vm, a * vm * vm + b * vm + c


def interp_at(xs, ys, x0):
    """y where the x series crosses x0, linearly interpolated; None if it never does."""
    for i in range(len(xs) - 1):
        a, b = xs[i], xs[i + 1]
        if (a - x0) * (b - x0) <= 0 and a != b:
            return ys[i] + (x0 - a) / (b - a) * (ys[i + 1] - ys[i])
    return None


def zero_cross(xs, ys):
    """x where the y series crosses zero; None if it never does."""
    for i in range(len(ys) - 1):
        if ys[i] * ys[i + 1] <= 0 and ys[i] != ys[i + 1]:
            return xs[i] - ys[i] * (xs[i + 1] - xs[i]) / (ys[i + 1] - ys[i])
    return None


def parse_file(path: str) -> dict:
    raw = io.open(path, encoding="iso-8859-1").read().replace("\r\n", "\n")
    rows = [ln.split("\t") for ln in raw.split("\n")]

    ip = iv = None
    for i, r in enumerate(rows):
        if r and r[0] == "Pixel" and ip is None:
            ip = i
        if r and r[0] == "Voltage" and iv is None:
            iv = i
    if ip is None or iv is None or iv <= ip:
        raise ValueError("no Pixel / Voltage anchor — not a LabVIEW JV file")

    names = [n for n in rows[ip][1:] if n]
    n = len(names)
    idx = {nm: i for i, nm in enumerate(names)}

    summary = {}
    for r in rows[ip + 1:iv]:
        if len(r) > 1 and r[0]:
            summary[r[0].split("[")[0].strip()] = [float(x) for x in r[1:1 + n]]

    meta = {}
    for r in rows[:ip]:
        t = r[0] if r else ""
        for key, pref in (("compliance", "Compliance"), ("stab", "Stab"),
                          ("averages", "Number of averages"),
                          ("cal", "Intensity calibration"), ("temp", "Temperature")):
            if t.startswith(pref):
                meta[key] = t.replace("\xb0", "°")

    V, cols = [], [[] for _ in range(n)]
    for r in rows[iv + 2:]:
        if len(r) < n + 1 or not r[0].strip():
            continue
        try:
            v = float(r[0])
        except ValueError:
            continue
        V.append(v)
        for c in range(n):
            cols[c].append(float(r[c + 1]))
    if len(V) < 5:
        raise ValueError("fewer than five sweep points")

    # A sweep run from positive to negative is stored descending. Turn it around so V always
    # ascends -- every consumer reconstructs voltage as vmin + i*vstep -- but remember which way
    # it was measured, because forward and reverse scans are not the same experiment.
    scan = "reverse" if V[-1] < V[0] else "forward"
    if scan == "reverse":
        V.reverse()
        for c in cols:
            c.reverse()

    steps = sorted(V[i] - V[i - 1] for i in range(1, len(V)))
    step = steps[len(steps) // 2]

    stem = pathlib.Path(path).stem
    channels = {}
    for p in PIXELS:
        li = idx.get(p + "_light")
        if li is None:
            continue
        INT = summary["INT"][li]
        mode = classify(INT)
        curve = cols[li]
        voc, jsc, ff = summary["V_OC"][li], summary["J_SC"][li], summary["FF"][li]
        area, ece = summary["A"][li], summary["ECE"][li]
        # On a reverse scan this LabVIEW writes V_OC and J_SC with inverted signs while V_MMP,
        # J_MMP and the curve keep the usual convention. Believe the curve, not the header, and
        # flip a header value only when it genuinely disagrees.
        if mode == "light":
            j0, vc = interp_at(V, curve, 0.0), zero_cross(V, curve)
            if j0 is not None and abs(j0) > 0.5 and jsc * j0 < 0:
                jsc = -jsc
            if vc is not None and abs(vc) > 0.05 and voc * vc < 0:
                voc = -voc
        rec = dict(
            mode=mode, INT=sig(INT), area=sig(area),
            voc=sig(voc), jsc=sig(jsc), ff=sig(ff * 100), pce=sig(ece * 100),
            vmpp=sig(summary["V_MMP"][li]), jmpp=sig(summary["J_MMP"][li]),
            jsc1sun=sig(jsc * 100.0 / INT) if INT > 1 else None,
            curve=[sig(x, 4) for x in curve],
        )
        if mode == "light":
            rec["rs"] = sig(slope_window(V, curve, voc, 0.08))
            rec["rsh"] = sig(slope_window(V, curve, 0.0, 0.15))
            vm, pm = refine_mpp(V, curve)
            rec["vmpp_fit"] = sig(vm)
            rec["ff_fit"] = sig(100.0 * pm / abs(voc * jsc)) if voc * jsc else None
            rec["pce_fit"] = sig(100.0 * pm / INT)
            bad = []
            if not QC["voc"][0] <= voc <= QC["voc"][1]:
                bad.append("Voc")
            if not QC["jsc"][0] <= abs(jsc) <= QC["jsc"][1]:
                bad.append("Jsc")
            if not QC["ff"][0] <= ff <= QC["ff"][1]:
                bad.append("FF")
            if not QC["pce"][0] <= ece * 100 <= QC["pce"][1]:
                bad.append("PCE")
            if bad:
                rec["qc"] = bad
        di = idx.get(p + "_dark")
        if di is not None:
            rec["dark"] = [sig(x, 4) for x in cols[di]]
        channels[p] = rec

    if not channels:
        raise ValueError("no pixel columns named a_light … f_light")

    sm = re.match(r"^(sample\d+)", stem)
    return dict(
        file=os.path.basename(path), name=stem,
        mtime=int(os.path.getmtime(path) * 1000),
        sample=sm.group(1) if sm else stem,
        material=material_of(stem), meta=meta,
        vmin=sig(V[0]), vmax=sig(V[-1]), vstep=sig(step), npts=len(V), scan=scan,
        nchan=n + 1, channels=channels,
    )


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("folder", help="folder containing the .dat files")
    ap.add_argument("-o", "--out", default="data.json", help="output JSON (default: data.json)")
    ap.add_argument("-q", "--quiet", action="store_true")
    args = ap.parse_args(argv)

    paths = sorted(glob.glob(os.path.join(args.folder, "*.dat")))
    if not paths:
        print(f"no .dat files in {args.folder}", file=sys.stderr)
        return 1

    scans, failed = [], []
    for path in paths:
        try:
            scans.append(parse_file(path))
        except Exception as exc:            # noqa: BLE001 — report and carry on
            failed.append(f"{os.path.basename(path)}: {exc}")

    scans.sort(key=lambda s: s["mtime"])
    payload = dict(folder=os.path.basename(os.path.normpath(args.folder)),
                   pixels=PIXELS, scans=scans)
    io.open(args.out, "w", encoding="utf-8").write(json.dumps(payload, separators=(",", ":")))

    if not args.quiet:
        for s in scans:
            lit = "".join(p for p, c in s["channels"].items() if c["mode"] == "light")
            flags = " ".join(f"{p}:{'/'.join(c['qc'])}"
                             for p, c in s["channels"].items() if c.get("qc"))
            print(f"  {s['name']:<42} {s['npts']:>4} pts  "
                  f"{s['vmin']}…{s['vmax']} V / {s['vstep']}  light={lit or '-':<7} {flags}")
        print(f"\n{len(scans)} scan(s) -> {args.out}"
              f" ({os.path.getsize(args.out) / 1024:.0f} kB)")
    for f in failed:
        print(f"skipped {f}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
