"""Mätrigg: jämför detekterade element med facit.

Alla mått i facit och resultat i meter, utom där fältnamnet säger _mm.
Matchning:
- Plan: vinkel mellan normaler < 5 grader och avstånd mellan planen < 5 cm.
- Rör: vinkel mellan axlar < 5 grader och avstånd mellan axellinjerna
  < max(2 r, 3 cm), samt överlapp längs axeln.
"""
from __future__ import annotations

import numpy as np


def _angle(a, b):
    a, b = np.asarray(a, float), np.asarray(b, float)
    c = abs(a @ b) / (np.linalg.norm(a) * np.linalg.norm(b))
    return float(np.degrees(np.arccos(min(1.0, c))))


def evaluate_planes(detected, truth, max_angle=5.0, max_offset=0.05):
    rows, used = [], set()
    for gt in truth:
        n_gt = np.asarray(gt["normal"], float)
        best = None
        for i, p in enumerate(detected):
            if i in used:
                continue
            ang = _angle(p.normal, n_gt)
            if ang > max_angle:
                continue
            # avstånd: projicera detekterat plans centrum på facitplanet
            off = abs(np.asarray(p.center) @ n_gt + gt["d"])
            if off <= max_offset and (best is None or off < best[1]):
                best = (i, off, ang)
        if best:
            used.add(best[0])
            rows.append({"facit": gt["namn"], "hittad": True,
                         "avstand_mm": round(best[1] * 1000, 1),
                         "vinkel_deg": round(best[2], 2)})
        else:
            rows.append({"facit": gt["namn"], "hittad": False})
    found = sum(r["hittad"] for r in rows)
    return {"antal_facit": len(truth), "hittade": found,
            "extra": len(detected) - len(used), "rader": rows}


def _line_distance(p_a, a, p_b):
    w = np.asarray(p_b) - np.asarray(p_a)
    return float(np.linalg.norm(w - (w @ a) * a))


def evaluate_pipes(detected, truth, max_angle=5.0):
    rows, used = [], set()
    for gt in truth:
        s, e = np.asarray(gt["start"], float), np.asarray(gt["end"], float)
        L = np.linalg.norm(e - s)
        a = (e - s) / L
        r = gt["radius_mm"] / 1000
        best = None
        for i, p in enumerate(detected):
            if i in used or _angle(p.axis, a) > max_angle:
                continue
            mid = (np.asarray(p.start) + np.asarray(p.end)) / 2
            dist = _line_distance(s, a, mid)
            if dist > max(2 * r, 0.03):
                continue
            t0, t1 = sorted([(np.asarray(p.start) - s) @ a, (np.asarray(p.end) - s) @ a])
            overlap = min(t1, L) - max(t0, 0)
            if overlap <= 0.1 * L:
                continue
            if best is None or dist < best[1]:
                best = (i, dist, overlap)
        if best:
            i, dist, overlap = best
            p = detected[i]
            used.add(i)
            rows.append({
                "facit": gt["id"], "dn_facit": gt["dn"], "hittad": True,
                "dn_hittad": p.dn, "dn_ratt": p.dn == gt["dn"],
                "radiefel_mm": round(float(p.radius_mm - gt["radius_mm"]), 2),
                "axelfel_mm": round(dist * 1000, 1),
                "langd_facit_m": round(float(L), 3),
                "langdfel_m": round(p.length_m - float(L), 3),
                "tackning_langd": round(float(overlap / L), 3),
                "synlig_omkrets_deg": p.coverage_deg})
        else:
            rows.append({"facit": gt["id"], "dn_facit": gt["dn"], "hittad": False})
    hits = [r for r in rows if r["hittad"]]
    summary = {
        "antal_facit": len(truth), "hittade": len(hits),
        "extra": len(detected) - len(used),
        "dn_ratt": sum(r["dn_ratt"] for r in hits),
        "max_abs_radiefel_mm": max((abs(r["radiefel_mm"]) for r in hits), default=None),
        "medel_abs_radiefel_mm": round(float(np.mean([abs(r["radiefel_mm"]) for r in hits])), 2) if hits else None,
        "max_axelfel_mm": max((r["axelfel_mm"] for r in hits), default=None),
    }
    return {**summary, "rader": rows}


def evaluate_connections(candidates, detected_pipes, truth_pipes, truth_connections,
                         pipe_eval):
    """Hittades facitets kopplingar bland kandidaterna?"""
    gt_to_det = {}
    for row, gt in zip(pipe_eval["rader"], truth_pipes):
        if not row["hittad"]:
            continue
        # leta upp det detekterade röret igen via axelns närhet
        s = np.asarray(gt["start"], float)
        a = np.asarray(gt["end"], float) - s
        a /= np.linalg.norm(a)
        for i, p in enumerate(detected_pipes):
            mid = (np.asarray(p.start) + np.asarray(p.end)) / 2
            if _angle(p.axis, a) < 5 and _line_distance(s, a, mid) < 0.05:
                gt_to_det.setdefault(gt["id"], i)
    pairs = {(c["ror_a"], c["ror_b"]) for c in candidates}
    rows = []
    for a, b, kind in truth_connections:
        ia, ib = gt_to_det.get(a), gt_to_det.get(b)
        ok = ia is not None and ib is not None and (min(ia, ib), max(ia, ib)) in pairs
        rows.append({"facit": f"{a}-{b}", "typ": kind, "hittad": bool(ok)})
    return {"antal_facit": len(rows), "hittade": sum(r["hittad"] for r in rows),
            "kandidater_totalt": len(candidates), "rader": rows}
