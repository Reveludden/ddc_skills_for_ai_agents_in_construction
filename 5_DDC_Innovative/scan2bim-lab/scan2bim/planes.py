"""Plandetektering: golv, tak och väggar.

Metod (egen formulering, se METOD.md):
1. RANSAC: slumpa tre punkter -> plan; räkna punkter nära planet vars normal
   är parallell med planets normal. Bästa planet vinner.
2. Förfina planet med minsta kvadrat (PCA) på inliers.
3. Dela inliers i sammanhängande ytor; behåll bara ytor som är tillräckligt
   stora i båda riktningar (så att t.ex. ovansidan av ett rör inte blir ett plan).
4. Ta bort de godkända punkterna och upprepa.
"""
from __future__ import annotations

from dataclasses import dataclass, asdict

import numpy as np

from .geometry import components, orthonormal_basis


@dataclass
class Plane:
    normal: list
    d: float                 # normal . p + d = 0
    klass: str               # golv / tak / vägg / lutande
    n_points: int
    rms_mm: float
    extent_m: list           # utbredning i planets två riktningar
    center: list

    def to_dict(self):
        return asdict(self)


def _fit_plane(pts: np.ndarray):
    c = pts.mean(axis=0)
    _, _, vt = np.linalg.svd(pts - c, full_matrices=False)
    n = vt[2]
    return n, -float(n @ c), c


def _classify(normal, center, z_min, z_max):
    nz = abs(normal[2])
    if nz > 0.95:
        return "golv" if center[2] - z_min < (z_max - z_min) / 2 else "tak"
    if nz < 0.10:
        return "vägg"
    return "lutande"


def detect_planes(points, normals, *, dist_tol=0.015, angle_tol_deg=20,
                  min_points=500, min_extent=0.4, max_planes=30,
                  iterations=400, cluster_radius=0.06, seed=0):
    """Returnerar (planes, used_mask). used_mask markerar punkter som tillhör ett plan."""
    rng = np.random.default_rng(seed)
    n_all = len(points)
    used = np.zeros(n_all, dtype=bool)
    pool = np.ones(n_all, dtype=bool)            # kandidater för RANSAC
    cos_tol = np.cos(np.radians(angle_tol_deg))
    z_min, z_max = points[:, 2].min(), points[:, 2].max()
    planes: list[Plane] = []

    for _ in range(max_planes * 3):
        idx = np.flatnonzero(pool)
        if len(idx) < min_points or len(planes) >= max_planes:
            break
        P, N = points[idx], normals[idx]
        sub = idx if len(idx) <= 20000 else rng.choice(idx, 20000, replace=False)
        Ps, Ns = points[sub], normals[sub]
        best, best_score = None, 0
        for _ in range(iterations):
            s = Ps[rng.choice(len(Ps), 3, replace=False)]
            n = np.cross(s[1] - s[0], s[2] - s[0])
            norm = np.linalg.norm(n)
            if norm < 1e-9:
                continue
            n /= norm
            d = -n @ s[0]
            ok = (np.abs(Ps @ n + d) < dist_tol) & (np.abs(Ns @ n) > cos_tol)
            score = int(ok.sum())
            if score > best_score:
                best, best_score = (n, d), score
        if best is None:
            break
        n, d = best
        inl = (np.abs(P @ n + d) < dist_tol) & (np.abs(N @ n) > cos_tol)
        if inl.sum() < min_points:
            break
        n, d, _ = _fit_plane(P[inl])
        inl = (np.abs(P @ n + d) < dist_tol) & (np.abs(N @ n) > cos_tol)
        cand = idx[inl]
        labels = components(points[cand], cluster_radius)
        accepted_any = False
        for lab in np.unique(labels):
            member = cand[labels == lab]
            if len(member) < min_points:
                continue
            pts = points[member]
            nn, dd, c = _fit_plane(pts)
            u, v = orthonormal_basis(nn)
            ext = [float(np.ptp(pts @ u)), float(np.ptp(pts @ v))]
            if min(ext) < min_extent:
                continue
            rms = float(np.sqrt(np.mean((pts @ nn + dd) ** 2)) * 1000)
            planes.append(Plane(nn.round(5).tolist(), round(float(dd), 5),
                                _classify(nn, c, z_min, z_max), int(len(member)),
                                round(rms, 2), [round(e, 3) for e in ext],
                                c.round(4).tolist()))
            used[member] = True
            accepted_any = True
        pool[cand] = False                       # avvisade ytor prövas inte igen
        if not accepted_any and best_score < min_points:
            break
    return planes, used
