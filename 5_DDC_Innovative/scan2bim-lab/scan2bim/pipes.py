"""Rördetektering: raka cylindrar ur punktmoln.

Metod (egen formulering, se METOD.md):
- På en cylinder står ytnormalen vinkelrätt mot axeln. Två punkter med olika
  normaler ger därför axelriktningen som kryssprodukten av normalerna.
- Projicera de två punkterna och deras normaler på ett plan vinkelrätt mot
  axeln. Normallinjerna skär varandra i rörets centrum; avståndet ger radien.
- RANSAC: upprepa med punktpar ur samma närområde, räkna punkter som ligger
  på mantelytan och har normal vinkelrät mot axeln.
- Förfina: axel = riktningen med minst spridning bland inliers normaler;
  centrum och radie = geometrisk cirkelanpassning (Gauss-Newton) i snittet.
- Dela upp längs axeln där det finns glapp, så att två rör på samma linje
  blir två rör.
"""
from __future__ import annotations

from dataclasses import dataclass, asdict

import numpy as np
from scipy.spatial import cKDTree

from .dimensions import nearest_dn
from .geometry import orthonormal_basis


@dataclass
class Pipe:
    start: list
    end: list
    axis: list
    radius_mm: float
    diameter_mm: float
    dn: str | None
    dn_rel_error: float
    length_m: float
    n_points: int
    rms_mm: float
    coverage_deg: float      # hur stor del av omkretsen som syns i molnet
    orientering: str

    def to_dict(self):
        return asdict(self)


def _circle_fit(xy: np.ndarray, guess=None, iters=20):
    """Geometrisk cirkelanpassning. Startvärde från algebraisk (Kåsa) anpassning."""
    if guess is None:
        A = np.c_[2 * xy, np.ones(len(xy))]
        b = (xy ** 2).sum(axis=1)
        sol, *_ = np.linalg.lstsq(A, b, rcond=None)
        cx, cy = sol[:2]
        r = np.sqrt(max(sol[2] + cx * cx + cy * cy, 1e-12))
    else:
        cx, cy, r = guess
    for _ in range(iters):
        dx, dy = xy[:, 0] - cx, xy[:, 1] - cy
        dist = np.maximum(np.hypot(dx, dy), 1e-12)
        res = dist - r
        J = np.c_[-dx / dist, -dy / dist, -np.ones(len(xy))]
        step, *_ = np.linalg.lstsq(J, -res, rcond=None)
        cx, cy, r = cx + step[0], cy + step[1], r + step[2]
        if np.abs(step).max() < 1e-7:
            break
    return cx, cy, abs(r)


def _model_from_pair(p1, n1, p2, n2, r_min, r_max):
    a = np.cross(n1, n2)
    na = np.linalg.norm(a)
    if na < 0.25:                               # normalerna nästan parallella
        return None
    a /= na
    u, v = orthonormal_basis(a)
    q1, q2 = np.array([p1 @ u, p1 @ v]), np.array([p2 @ u, p2 @ v])
    m1, m2 = np.array([n1 @ u, n1 @ v]), np.array([n2 @ u, n2 @ v])
    M = np.c_[m1, -m2]
    if abs(np.linalg.det(M)) < 1e-6:
        return None
    t, s = np.linalg.solve(M, q2 - q1)
    c2 = q1 + t * m1
    r1, r2 = np.linalg.norm(q1 - c2), np.linalg.norm(q2 - c2)
    r = 0.5 * (r1 + r2)
    if not (r_min <= r <= r_max) or abs(r1 - r2) > 0.15 * r + 0.003:
        return None
    center = c2[0] * u + c2[1] * v              # punkt på axeln
    return center, a, r


def _inliers(P, N, center, axis, r, tol, cos_max):
    w = P - center
    perp = w - np.outer(w @ axis, axis)
    radial = np.linalg.norm(perp, axis=1)
    return (np.abs(radial - r) < tol) & (np.abs(N @ axis) < cos_max)


def _refine(P, N, center, axis, r, tol, cos_max, rounds=2):
    for _ in range(rounds):
        inl = _inliers(P, N, center, axis, r, tol, cos_max)
        if inl.sum() < 10:
            return None
        Ni = N[inl]
        evals, evecs = np.linalg.eigh(Ni.T @ Ni)
        new_axis = evecs[:, 0]
        if new_axis @ axis < 0:
            new_axis = -new_axis
        if new_axis @ axis > 0.98:              # godta bara små korrigeringar
            axis = new_axis
        u, v = orthonormal_basis(axis)
        Pi = P[inl]
        xy = np.c_[Pi @ u, Pi @ v]
        c_old = np.array([center @ u, center @ v])
        cx, cy, r = _circle_fit(xy, guess=(c_old[0], c_old[1], r))
        center = cx * u + cy * v
    inl = _inliers(P, N, center, axis, r, tol, cos_max)
    return center, axis, r, inl


def _coverage_deg(P, center, axis):
    u, v = orthonormal_basis(axis)
    w = P - center
    ang = np.degrees(np.arctan2(w @ v, w @ u)) % 360
    hist, _ = np.histogram(ang, bins=36, range=(0, 360))
    return float((hist > 0).sum() * 10)


def _orientation(axis):
    z = abs(axis[2])
    return "vertikal" if z > 0.95 else "horisontell" if z < 0.10 else "lutande"


def detect_pipes(points, normals, *, r_min=0.008, r_max=0.20, tol=None,
                 noise=0.002, min_points=60, min_length=0.25, gap=0.15,
                 neighborhood=0.25, iterations=3000, max_pipes=50, min_coverage=100.0,
                 min_density=0.0, seed=0):
    """Hitta raka rör bland `points`. Returnerar (pipes, used_mask)."""
    rng = np.random.default_rng(seed)
    tol = tol or max(0.004, 3 * noise)
    cos_max = 0.35
    n_all = len(points)
    used = np.zeros(n_all, dtype=bool)
    exhausted = np.zeros(n_all, dtype=bool)
    pipes: list[Pipe] = []
    failures = 0

    while len(pipes) < max_pipes and failures < 6:
        idx = np.flatnonzero(~used & ~exhausted)
        if len(idx) < min_points:
            break
        P, N = points[idx], normals[idx]
        tree = cKDTree(P)
        sub = rng.choice(len(P), min(len(P), 4000), replace=False)
        Ps, Ns = P[sub], N[sub]
        best, best_score = None, 0
        for _ in range(iterations):
            i = rng.integers(len(P))
            nb = tree.query_ball_point(P[i], neighborhood)
            if len(nb) < 5:
                continue
            j = nb[rng.integers(len(nb))]
            model = _model_from_pair(P[i], N[i], P[j], N[j], r_min, r_max)
            if model is None:
                continue
            score = int(_inliers(Ps, Ns, *model, tol, cos_max).sum())
            if score > best_score:
                best, best_score = model, score
        if best is None:
            break
        refined = _refine(P, N, *best, tol, cos_max)
        if refined is None:
            failures += 1
            continue
        center, axis, r, inl = refined
        if not (r_min <= r <= r_max):
            failures += 1
            continue
        found = _split_and_build(P, idx, inl, center, axis, r, gap, min_points,
                                 min_length, min_coverage, min_density)
        if not found:
            failures += 1
            # markera punkterna nära den bästa modellen som prövade
            exhausted[idx[inl]] = True
            continue
        failures = 0
        for pipe, members in found:
            pipes.append(pipe)
            used[members] = True
    return pipes, used


def _split_and_build(P, idx, inl, center, axis, r, gap, min_points, min_length,
                     min_coverage, min_density=0.0):
    Pi, gi = P[inl], idx[inl]
    t = (Pi - center) @ axis
    order = np.argsort(t)
    t_sorted = t[order]
    breaks = np.flatnonzero(np.diff(t_sorted) > gap)
    starts = np.r_[0, breaks + 1]
    ends = np.r_[breaks + 1, len(t_sorted)]
    out = []
    for s, e in zip(starts, ends):
        sel = order[s:e]
        if len(sel) < min_points:
            continue
        t0, t1 = t_sorted[s], t_sorted[e - 1]
        length = t1 - t0
        if length < min_length:
            continue
        seg = Pi[sel]
        w = seg - center
        radial = np.linalg.norm(w - np.outer(w @ axis, axis), axis=1)
        rms = float(np.sqrt(np.mean((radial - r) ** 2)) * 1000)
        coverage = _coverage_deg(seg, center, axis)
        if coverage < min_coverage:      # t.ex. hörn mellan vägg och golv
            continue
        # punkter per m2 synlig mantelyta; skräp i hörn och kanter är glest
        density = len(sel) / max(r * np.radians(coverage) * length, 1e-9)
        if density < min_density:
            continue
        d_mm = 2 * r * 1000
        dn, rel = nearest_dn(d_mm)
        out.append((Pipe(
            start=(center + t0 * axis).round(4).tolist(),
            end=(center + t1 * axis).round(4).tolist(),
            axis=axis.round(5).tolist(),
            radius_mm=round(r * 1000, 1), diameter_mm=round(d_mm, 1),
            dn=dn, dn_rel_error=rel, length_m=round(float(length), 3),
            n_points=int(len(sel)), rms_mm=round(rms, 2),
            coverage_deg=coverage,
            orientering=_orientation(axis)), gi[sel]))
    return out


def connection_candidates(pipes, max_gap=0.15, max_radius_ratio=1.25):
    """Rörändar som ligger nära varandra och har liknande dimension.

    Kandidater för böj/T-rör. Ska granskas av människa; inget kopplas ihop
    automatiskt.
    """
    out = []
    for i in range(len(pipes)):
        for j in range(i + 1, len(pipes)):
            a, b = pipes[i], pipes[j]
            ratio = max(a.radius_mm, b.radius_mm) / max(min(a.radius_mm, b.radius_mm), 1e-6)
            if ratio > max_radius_ratio:
                continue
            best = None
            for ea in (a.start, a.end):
                for eb in (b.start, b.end):
                    d = float(np.linalg.norm(np.subtract(ea, eb)))
                    if best is None or d < best[0]:
                        best = (d, ea, eb)
            gap_allowed = max_gap + 2 * max(a.radius_mm, b.radius_mm) / 1000
            if best[0] <= gap_allowed:
                angle = float(np.degrees(np.arccos(min(1.0, abs(np.dot(a.axis, b.axis))))))
                kind = "rak skarv" if angle < 10 else "böj" if angle > 60 else "vinklad skarv"
                out.append({"ror_a": i, "ror_b": j, "avstand_m": round(best[0], 3),
                            "vinkel_deg": round(angle, 1), "typ": kind})
    return out
