"""Kommandorad.

  python -m scan2bim.cli info   <fil>
  python -m scan2bim.cli detect <fil> [--voxel 0.008] [--bbox x0 y0 z0 x1 y1 z1] --out resultat.json
  python -m scan2bim.cli bench  [--seeds 0 1 2] [--noise 0.002] [--out rapport.json] [--krav]

`bench` bygger syntetiska teknikrum med känt facit, kör hela kedjan och mäter.
Med --krav ger kommandot exitkod 1 om kraven i KRAV inte uppfylls.
"""
from __future__ import annotations

import argparse
import json
import sys

import numpy as np

from . import pc_io, pipeline
from .evaluate import evaluate_connections, evaluate_pipes, evaluate_planes
from .synth import DEFAULT_SCANNERS, make_scene

# Krav för syntetisk benchmark (kontrollregel). Ändras bara av människa.
KRAV = {
    "plan_andel_hittade": 1.0,       # alla sex rumsytor
    "ror_andel_hittade": 0.85,
    "max_abs_radiefel_mm": 3.0,
    "max_axelfel_mm": 10.0,
    "dn_andel_ratt": 0.85,
}


def _bench(args):
    runs, ok_all = [], True
    for seed in args.seeds:
        scanners = DEFAULT_SCANNERS[:args.skannrar]
        pts, truth = make_scene(seed=seed, noise=args.noise, spacing=args.spacing,
                                scanners=scanners)
        res = pipeline.run(pts, voxel=args.voxel, noise=args.noise, seed=seed)
        pe = evaluate_planes(res["planes"], truth["planes"])
        re = evaluate_pipes(res["pipes"], truth["pipes"])
        ce = evaluate_connections(res["connections"], res["pipes"], truth["pipes"],
                                  truth["connections"], re)
        hits = max(re["hittade"], 1)
        check = {
            "plan_andel_hittade": pe["hittade"] / pe["antal_facit"],
            "ror_andel_hittade": re["hittade"] / re["antal_facit"],
            "max_abs_radiefel_mm": re["max_abs_radiefel_mm"],
            "max_axelfel_mm": re["max_axelfel_mm"],
            "dn_andel_ratt": re["dn_ratt"] / hits,
        }
        passed = {
            k: (v is not None and (v >= KRAV[k] if "andel" in k else v <= KRAV[k]))
            for k, v in check.items()
        }
        ok_all &= all(passed.values())
        runs.append({"seed": seed, "statistik": res["stats"], "plan": pe, "ror": re,
                     "kopplingar": ce, "kontroll": check, "godkand": passed})
        print(f"seed {seed}: plan {pe['hittade']}/{pe['antal_facit']} (+{pe['extra']} extra) | "
              f"rör {re['hittade']}/{re['antal_facit']} (+{re['extra']} extra), "
              f"DN rätt {re['dn_ratt']}, max radiefel {re['max_abs_radiefel_mm']} mm, "
              f"max axelfel {re['max_axelfel_mm']} mm | kopplingar "
              f"{ce['hittade']}/{ce['antal_facit']} ({ce['kandidater_totalt']} kandidater) | "
              f"{res['stats']['tid_normaler_s'] + res['stats']['tid_plan_s'] + res['stats']['tid_ror_s']:.1f} s")
        if args.verbose:
            for r in re["rader"]:
                print("   ", r)
    report = {"krav": KRAV, "parametrar": {"noise": args.noise, "spacing": args.spacing, "voxel": args.voxel, "skannrar": args.skannrar}, "korningar": runs, "alla_krav_uppfyllda": bool(ok_all)}
    if args.out:
        with open(args.out, "w", encoding="utf-8") as f:
            json.dump(report, f, ensure_ascii=False, indent=2)
    print("ALLA KRAV UPPFYLLDA" if ok_all else "KRAV EJ UPPFYLLDA")
    return 0 if (ok_all or not args.krav) else 1


def main(argv=None):
    ap = argparse.ArgumentParser(prog="scan2bim")
    sub = ap.add_subparsers(dest="cmd", required=True)

    a = sub.add_parser("info")
    a.add_argument("fil")

    d = sub.add_parser("detect")
    d.add_argument("fil")
    d.add_argument("--voxel", type=float, default=0.008)
    d.add_argument("--noise", type=float, default=0.002)
    d.add_argument("--bbox", type=float, nargs=6)
    d.add_argument("--max-points", type=int, default=3_000_000)
    d.add_argument("--out", required=True)

    b = sub.add_parser("bench")
    b.add_argument("--seeds", type=int, nargs="+", default=[0, 1, 2])
    b.add_argument("--noise", type=float, default=0.002)
    b.add_argument("--spacing", type=float, default=0.006)
    b.add_argument("--voxel", type=float, default=0.008)
    b.add_argument("--skannrar", type=int, default=2, help="antal skannerpositioner (1-2)")
    b.add_argument("--out")
    b.add_argument("--krav", action="store_true")
    b.add_argument("-v", "--verbose", action="store_true")

    args = ap.parse_args(argv)
    if args.cmd == "info":
        print(json.dumps(pc_io.describe(args.fil), ensure_ascii=False, indent=2))
        return 0
    if args.cmd == "detect":
        pts = pc_io.load_points(args.fil, voxel=args.voxel / 2, bbox=args.bbox,
                                max_points=args.max_points)
        res = pipeline.run(pts, voxel=args.voxel, noise=args.noise)
        out = pipeline.to_json(res)
        with open(args.out, "w", encoding="utf-8") as f:
            json.dump(out, f, ensure_ascii=False, indent=2)
        s = res["stats"]
        print(f"{len(res['planes'])} plan, {len(res['pipes'])} rör, "
              f"{len(res['connections'])} kopplingskandidater ({s['punkter_efter_voxel']} punkter)")
        return 0
    return _bench(args)


if __name__ == "__main__":
    sys.exit(main())
