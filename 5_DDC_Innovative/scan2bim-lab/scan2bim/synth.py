"""Syntetiskt teknikrum med känt facit.

Rum 6 x 4 x 3 m med rör i olika dimensioner, en böj, två rör på samma linje,
ett skåp (störobjekt) och slumpbrus. Punkter tas bara med där ytan är vänd mot
någon skannerposition (enkel synlighet; skuggning mellan föremål modelleras
inte, se METOD.md). Brus läggs på i alla riktningar.
"""
from __future__ import annotations

import numpy as np

from .dimensions import STEEL_OD_MM
from .geometry import orthonormal_basis

ROOM = (6.0, 4.0, 3.0)


def _r(dn):
    return STEEL_OD_MM[dn] / 2000.0


DEFAULT_PIPES = [
    {"id": "P1", "dn": "DN100", "start": [0.3, 0.4, 2.6], "end": [5.5, 0.4, 2.6]},
    {"id": "P2", "dn": "DN50", "start": [0.3, 0.8, 2.6], "end": [5.5, 0.8, 2.6]},
    {"id": "P3", "dn": "DN25", "start": [0.5, 1.1, 2.65], "end": [4.0, 1.1, 2.65]},
    {"id": "P4", "dn": "DN150", "start": [5.6, 3.5, 0.1], "end": [5.6, 3.5, 2.9]},
    {"id": "P5", "dn": "DN80", "start": [2.0, 1.5, 2.3], "end": [2.0, 3.55, 2.3]},
    {"id": "P6", "dn": "DN80", "start": [2.0, 3.7, 0.3], "end": [2.0, 3.7, 2.15]},
    {"id": "P7", "dn": "DN32", "start": [4.5, 0.5, 2.4], "end": [4.5, 3.5, 2.4]},
    {"id": "P8a", "dn": "DN65", "start": [0.3, 2.5, 2.0], "end": [2.5, 2.5, 2.0]},
    {"id": "P8b", "dn": "DN65", "start": [3.0, 2.5, 2.0], "end": [5.5, 2.5, 2.0]},
]
DEFAULT_CONNECTIONS = [("P5", "P6", "böj")]
DEFAULT_SCANNERS = [[3.0, 2.0, 1.5], [1.2, 3.0, 1.4]]


def _rect(origin, e1, e2, spacing, rng):
    origin, e1, e2 = map(np.asarray, (origin, e1, e2))
    area = np.linalg.norm(e1) * np.linalg.norm(e2)
    n = int(area / spacing ** 2)
    a, b = rng.random(n), rng.random(n)
    pts = origin + np.outer(a, e1) + np.outer(b, e2)
    normal = np.cross(e1, e2)
    normal /= np.linalg.norm(normal)
    return pts, np.tile(normal, (n, 1))


def _cylinder(start, end, r, spacing, rng):
    start, end = np.asarray(start, float), np.asarray(end, float)
    axis = end - start
    L = np.linalg.norm(axis)
    axis /= L
    u, v = orthonormal_basis(axis)
    n = int(2 * np.pi * r * L / spacing ** 2)
    t = rng.random(n) * L
    th = rng.random(n) * 2 * np.pi
    radial = np.outer(np.cos(th), u) + np.outer(np.sin(th), v)
    return start + np.outer(t, axis) + r * radial, radial


def _visible(pts, nrm, scanners):
    vis = np.zeros(len(pts), dtype=bool)
    for s in scanners:
        to_s = np.asarray(s) - pts
        # ytor räknas synliga oavsett normalens tecken för plana ytor (rummets
        # insida); för rör används utåtriktad normal
        vis |= np.einsum("ij,ij->i", nrm, to_s) > 0
    return vis


def make_scene(seed=0, spacing=0.006, noise=0.002, pipes=None, scanners=None,
               clutter_points=3000):
    rng = np.random.default_rng(seed)
    pipes = pipes or DEFAULT_PIPES
    scanners = scanners or DEFAULT_SCANNERS
    X, Y, Z = ROOM
    room_spacing = spacing * 2.5                 # rummets ytor glesare än rören
    chunks = []
    # Normaler riktade in i rummet så att synlighetstestet fungerar.
    surfaces = [
        ([0, 0, 0], [X, 0, 0], [0, Y, 0], "golv"),
        ([0, Y, Z], [X, 0, 0], [0, -Y, 0], "tak"),
        ([0, 0, 0], [0, 0, Z], [X, 0, 0], "vägg y=0"),
        ([0, Y, 0], [X, 0, 0], [0, 0, Z], "vägg y=4"),
        ([0, 0, 0], [0, Y, 0], [0, 0, Z], "vägg x=0"),
        ([X, 0, 0], [0, 0, Z], [0, Y, 0], "vägg x=6"),
    ]
    gt_planes = []
    for o, e1, e2, name in surfaces:
        p, n = _rect(o, e1, e2, room_spacing, rng)
        chunks.append(p[_visible(p, n, scanners)])
        n0 = n[0]
        gt_planes.append({"namn": name, "normal": n0.tolist(),
                          "d": float(-n0 @ np.asarray(o, float))})
    # Skåp som störobjekt (räknas inte i facit)
    cab_o, cab = np.array([0.1, 3.2, 0.0]), np.array([0.6, 0.6, 1.8])
    for o, e1, e2 in [
        (cab_o + [cab[0], 0, 0], [0, cab[1], 0], [0, 0, cab[2]]),
        (cab_o, [cab[0], 0, 0], [0, 0, cab[2]]),
        (cab_o + [0, 0, cab[2]], [cab[0], 0, 0], [0, cab[1], 0]),
    ]:
        p, n = _rect(o, e1, e2, room_spacing, rng)
        chunks.append(p[_visible(p, n, scanners)])
    gt_pipes = []
    for pd in pipes:
        r = _r(pd["dn"])
        p, n = _cylinder(pd["start"], pd["end"], r, spacing, rng)
        chunks.append(p[_visible(p, n, scanners)])
        gt_pipes.append({**pd, "radius_mm": round(r * 1000, 2)})
    # Slumpmässigt skräp (kablar, smuts, reflexer)
    if clutter_points:
        chunks.append(rng.random((clutter_points, 3)) * [X, Y, Z])
    pts = np.vstack(chunks)
    pts += rng.normal(0, noise, pts.shape)
    truth = {"planes": gt_planes, "pipes": gt_pipes,
             "connections": [list(c) for c in DEFAULT_CONNECTIONS],
             "params": {"seed": seed, "spacing": spacing, "noise": noise,
                        "scanners": scanners, "room": list(ROOM)}}
    return pts, truth
