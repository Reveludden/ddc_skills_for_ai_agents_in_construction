"""Syntetiska punktmoln med exakt kant facit.

Inget riktigt punktmoln anvands. Facit ar kant ner till varje oppningskant,
sa att varje matt i pipelinen kan provas mot sanningen - aven matten sjalva.

Rummet: 5,0 x 4,0 m, hojd 3,0 m. Fyra vaggar (S, O, N, V):
  S  dorroppning 0,90 x 2,10 m, vaggtjocklek 0,45 m (smyg och overstycke skannade)
  O  fonsteroppning 1,20 x 1,30 m, brostning 0,90 m, karm 0,25 m in (glesa punkter)
  N  historisk vagg: buktning (sinus) och lutning
  V  stangd dorr 0,90 x 2,05 m, dorrbladet insankt `stangd_djup` m
"""
import numpy as np

LX, LY, H = 5.0, 4.0, 3.0
Z = np.array([0.0, 0.0, 1.0])

# Vaggarnas facitram: punkt = origo + u*eu + v*Z + d*n (d > 0 = in i rummet)
VAGGAR = {
    "S": dict(origo=(0, 0, 0), eu=(1, 0, 0), n=(0, 1, 0), L=LX),
    "O": dict(origo=(LX, 0, 0), eu=(0, 1, 0), n=(-1, 0, 0), L=LY),
    "N": dict(origo=(0, LY, 0), eu=(1, 0, 0), n=(0, -1, 0), L=LX),
    "V": dict(origo=(0, 0, 0), eu=(0, 1, 0), n=(1, 0, 0), L=LY),
}
for _v in VAGGAR.values():
    for _k in ("origo", "eu", "n"):
        _v[_k] = np.array(_v[_k], dtype=float)


def _yta(rng, tathet, u0, u1, v0, v1):
    n = rng.poisson(tathet * (u1 - u0) * (v1 - v0))
    return rng.uniform(u0, u1, n), rng.uniform(v0, v1, n)


def _till3d(vagg, u, v, d):
    w = VAGGAR[vagg]
    return w["origo"] + np.outer(u, w["eu"]) + np.outer(v, Z) + np.outer(d, w["n"])


def rum(seed=1, tathet=2500.0, sigma=0.002, dorr=True, fonster=True,
        stangd_djup=0.030, bukt=0.020, lutning=0.015, patch=None):
    """Returnerar (P [N,3], facit). `patch` = dict(vagg, u0, u1, v0, v1, d)."""
    rng = np.random.default_rng(seed)
    delar = []
    oppningar = []
    if dorr:
        oppningar.append(dict(vagg="S", typ="dorroppning", u0=1.0, u1=1.9, v0=0.0, v1=2.1, djup=0.45))
    if fonster:
        oppningar.append(dict(vagg="O", typ="fonsteroppning", u0=1.2, u1=2.4, v0=0.9, v1=2.2, djup=0.25))
    stangda = []
    if stangd_djup is not None:
        stangda.append(dict(vagg="V", typ="stangd_dorr", u0=2.5, u1=3.4, v0=0.0, v1=2.05, djup=stangd_djup))

    for namn, w in VAGGAR.items():
        u, v = _yta(rng, tathet, 0.0, w["L"], 0.0, H)
        d = np.zeros_like(u)
        for o in oppningar:
            if o["vagg"] == namn:
                inne = (u > o["u0"]) & (u < o["u1"]) & (v > o["v0"]) & (v < o["v1"])
                u, v, d = u[~inne], v[~inne], d[~inne]
        for s in stangda:
            if s["vagg"] == namn:
                inne = (u > s["u0"]) & (u < s["u1"]) & (v > s["v0"]) & (v < s["v1"])
                d[inne] -= s["djup"]
        if namn == "N":
            d += bukt * np.sin(np.pi * u / w["L"]) * np.sin(np.pi * v / H) + lutning * (v / H)
        if patch and patch["vagg"] == namn:
            inne = (u > patch["u0"]) & (u < patch["u1"]) & (v > patch["v0"]) & (v < patch["v1"])
            d[inne] += patch["d"]
        d = d + rng.normal(0.0, sigma, len(d))
        delar.append(_till3d(namn, u, v, d))

    # Smyg, overstycke, bakomliggande yta och karm for oppningarna
    for o in oppningar:
        t = o["djup"]
        for ukant in (o["u0"], o["u1"]):
            dd, vv = _yta(rng, tathet, -t, 0.0, o["v0"], o["v1"])
            delar.append(_till3d(o["vagg"], np.full_like(dd, ukant), vv, dd + rng.normal(0, sigma, len(dd))))
        uu, dd = _yta(rng, tathet, o["u0"], o["u1"], -t, 0.0)
        delar.append(_till3d(o["vagg"], uu, np.full_like(uu, o["v1"]), dd))
        if o["v0"] > 0:  # fonsterbank
            uu, dd = _yta(rng, tathet, o["u0"], o["u1"], -t, 0.0)
            delar.append(_till3d(o["vagg"], uu, np.full_like(uu, o["v0"]), dd))
        if o["typ"] == "dorroppning":  # korridorvagg 1,5 m bakom, golv i dorroppningen
            uu, vv = _yta(rng, tathet, o["u0"], o["u1"], o["v0"], o["v1"])
            delar.append(_till3d(o["vagg"], uu, vv, np.full_like(uu, -1.5)))
            uu, dd = _yta(rng, tathet, o["u0"], o["u1"], -t, 0.0)
            delar.append(_till3d(o["vagg"], uu, np.zeros_like(uu), dd))
        else:  # glas/karm: glesa returer
            uu, vv = _yta(rng, tathet * 0.1, o["u0"], o["u1"], o["v0"], o["v1"])
            delar.append(_till3d(o["vagg"], uu, vv, np.full_like(uu, -t)))

    # Golv och tak
    for z in (0.0, H):
        x, y = _yta(rng, tathet, 0.0, LX, 0.0, LY)
        delar.append(np.column_stack([x, y, np.full_like(x, z) + rng.normal(0, sigma, len(x))]))

    P = np.vstack(delar)
    facit = dict(oppningar=oppningar, stangda=stangda, bukt=bukt, lutning=lutning,
                 patch=patch, sigma=sigma, tathet=tathet, H=H, LX=LX, LY=LY)
    return P, facit


def facit_u(vagg, p):
    """u-koordinat i facitramen for en 3D-punkt."""
    w = VAGGAR[vagg]
    return float((np.asarray(p) - w["origo"]) @ w["eu"])
