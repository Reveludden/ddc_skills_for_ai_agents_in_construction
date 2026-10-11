"""Lokal scan2bim-kedja for HBIM - prototyp.

Princip: det som observerats i punktmolnet halls isar fran det som harletts
eller antagits. Varje resultat bar `kalla` = observerad | harledd | antagen.
Ingen data lamnar maskinen; bara numpy, scipy och IfcOpenShell anvands.
"""
import uuid

import numpy as np
from scipy import ndimage

Z = np.array([0.0, 0.0, 1.0])

TOL = dict(
    seg=0.04,          # RANSAC-troskel vid segmentering (rymmer buktning ~20 mm)
    band=0.10,         # punkter inom +-10 cm fran vaggplanet raknas till vaggen
    yta=0.012,         # |r| < 12 mm = punkten ligger i vaggytan
    insankt=0.012,     # r < -12 mm = punkten ligger bakom vaggytan
    cell=0.05,         # rutnat for oppningar
    marg=0.12,         # kantzon mot horn, golv och tak som inte anvands i statistik
    huber=0.005,       # Huber-grans for robust anpassning
    plan_sys=0.006,    # plan otillrackligt om ytmodellen avviker > 6 mm fran planet (P95 over vaggen)
    antagen_tjocklek=0.30,
    max_smyg=1.2,      # langre ned an sa letas inte smyg (korridorvagg 1,5 m bakom)
)
NS = uuid.UUID("6f1c2a52-3c1e-4d8e-9a57-2b0e5d3c9a11")


# ---------- grundgeometri ----------

def plan_svd(Q, w=None):
    w = np.ones(len(Q)) if w is None else w
    c = (w[:, None] * Q).sum(0) / w.sum()
    C = ((Q - c) * w[:, None]).T @ (Q - c)
    n = np.linalg.eigh(C)[1][:, 0]
    return n, -n @ c


def _vikter(e, delta, varv, iters):
    """Huber forst (stabil start), sedan Tukey biweight med c = 4,685 x robust sigma.

    Huber ensam ger avvikande punkter kvar vikt (delta/|e|). Ett lokalt utbuktat
    falt drar da referensytan till sig, och avvikelsen mats for liten
    (forstorelseprov B: 14 mm matt som 10,9 mm). Tukey ger dem vikt 0.
    """
    if varv < iters // 2:
        return np.where(np.abs(e) <= delta, 1.0, delta / np.maximum(np.abs(e), 1e-12))
    c = 4.685 * max(1.4826 * np.median(np.abs(e - np.median(e))), 1e-4)
    return np.where(np.abs(e) < c, (1 - (e / c) ** 2) ** 2, 0.0)


def huber_plan(Q, n, d0, delta, iters=20):
    for varv in range(iters):
        r = Q @ n + d0
        w = _vikter(r, delta, varv, iters)
        n2, d2 = plan_svd(Q, w)
        if n2 @ n < 0:
            n2, d2 = -n2, -d2
        n, d0 = n2, d2
    return n, d0


def huber_poly2(u, v, r, delta, iters=20):
    A = np.column_stack([np.ones_like(u), u, v, u * u, u * v, v * v])
    w = np.ones_like(r)
    for varv in range(iters):
        sw = np.sqrt(w)
        k = np.linalg.lstsq(A * sw[:, None], r * sw, rcond=None)[0]
        e = r - A @ k
        w = _vikter(e, delta, varv, iters)
    return lambda uu, vv: np.column_stack(
        [np.ones_like(uu), uu, vv, uu * uu, uu * vv, vv * vv]) @ k


def ransac(P, rng, tr, iters=300, prov=20000):
    S = P[rng.choice(len(P), min(prov, len(P)), replace=False)]
    bast, bastn = None, -1
    for _ in range(iters):
        a, b, c = S[rng.choice(len(S), 3, replace=False)]
        n = np.cross(b - a, c - a)
        nn = np.linalg.norm(n)
        if nn < 1e-9:
            continue
        n /= nn
        cnt = np.count_nonzero(np.abs(S @ n - n @ a) < tr)
        if cnt > bastn:
            bast, bastn = (n, -n @ a), cnt
    n, d0 = bast
    inl = np.abs(P @ n + d0) < tr
    n, d0 = plan_svd(P[inl])
    return n, d0, np.abs(P @ n + d0) < tr


def segmentera(P, rng, tr):
    plan, rest = [], np.arange(len(P))
    while len(rest) > 0.02 * len(P) and len(plan) < 25:
        n, d0, inl = ransac(P[rest], rng, tr)
        if inl.sum() < 800:
            break
        plan.append(dict(n=n, d0=d0, idx=rest[inl]))
        rest = rest[~inl]
    return plan


def stat(x):
    a = np.abs(x)
    return dict(median_abs_mm=1e3 * float(np.median(a)), p95_abs_mm=1e3 * float(np.percentile(a, 95)),
                medel_signerad_mm=1e3 * float(np.mean(x)), antal=int(len(x)))


def kte(x, k, storst=True):
    """k:te storsta/minsta - robust mot enstaka stroppunkter."""
    if len(x) == 0:
        return None
    x = np.sort(x)
    k = min(k, len(x))
    return float(x[-k] if storst else x[k - 1])


# ---------- kedjan ----------

def kor(P, seed=0, tol=TOL):
    rng = np.random.default_rng(seed)
    segment = segmentera(P, rng, tol["seg"])

    horis = [s for s in segment if abs(s["n"][2]) > 0.9]
    zz = [float(np.median(P[s["idx"], 2])) for s in horis]
    golv = horis[int(np.argmin(zz))]
    tak = horis[int(np.argmax(zz))]
    golv_z, tak_z = min(zz), max(zz)
    hojd = tak_z - golv_z
    centrum = np.median(P[golv["idx"]], axis=0)
    centrum[2] = golv_z + hojd / 2

    prel, ovriga = [], []
    for s in segment:
        if abs(s["n"][2]) > 0.15:
            continue
        Q = P[s["idx"]]
        n, d0 = s["n"].copy(), s["d0"]
        if (centrum @ n + d0) < 0:           # normalen ska peka in i rummet
            n, d0 = -n, -d0
        nh = n - (n @ Z) * Z
        nh /= np.linalg.norm(nh)
        eu = np.cross(Z, nh)
        u = Q @ eu
        ext_u = np.percentile(u, 99.5) - np.percentile(u, 0.5)
        ext_v = np.percentile(Q[:, 2], 99.5) - np.percentile(Q[:, 2], 0.5)
        if ext_u > 1.5 and ext_v > 1.5:
            prel.append(dict(seg=s, n=n, d0=d0, nh=nh, eu=eu,
                             umin=float(np.percentile(u, 0.5)), umax=float(np.percentile(u, 99.5))))
        else:
            ovriga.append(dict(antal=int(len(Q)), utstrackning_m=[round(float(ext_u), 2), round(float(ext_v), 2)]))

    # Varv A: robust anpassning med preliminar utstrackning. Hornen raknas forst
    # darefter - RANSAC-planet for en vagg med stangd dorr ligger annars ~1 cm fel.
    # Aven vaggens riktning (nh, eu) ska komma fran den robusta anpassningen:
    # RANSAC-normalen kan vara vriden 0,2 grader = 14 mm over 4 m (prov A12).
    for w, a in zip(prel, [analysera_vagg(P, w, golv_z, hojd, tol) for w in prel]):
        w["n"], w["d0"] = np.array(a["n"]), a["d0"]
        nh = w["n"] - (w["n"] @ Z) * Z
        w["nh"] = nh / np.linalg.norm(nh)
        w["eu"] = np.cross(Z, w["nh"])
        uu = P[w["seg"]["idx"]] @ w["eu"]
        w["umin"], w["umax"] = float(np.percentile(uu, 0.5)), float(np.percentile(uu, 99.5))
    # Vaggens langd: horn = skarning med grannvaggen (harledd), annars percentil (observerad)
    zm = golv_z + hojd / 2
    for w in prel:
        w["kant"] = {}
        for sida in ("umin", "umax"):
            bast = None
            for g in prel:
                if g is w or abs(w["nh"] @ g["nh"]) > 0.5:
                    continue
                A = np.array([w["n"][:2], g["n"][:2]])
                b = -np.array([w["d0"] + w["n"][2] * zm, g["d0"] + g["n"][2] * zm])
                xy = np.linalg.solve(A, b)
                uh = float(np.array([xy[0], xy[1], zm]) @ w["eu"])
                if abs(uh - w[sida]) < 0.3 and (bast is None or abs(uh - w[sida]) < abs(bast - w[sida])):
                    bast = uh
            if bast is not None:
                w[sida], w["kant"][sida] = bast, "harledd: horn mot grannvagg"
            else:
                w["kant"][sida] = "observerad: punktmolnets utstrackning (0,5-percentil)"

    vaggar = [analysera_vagg(P, w, golv_z, hojd, tol) for w in prel]

    golv_stat = stat(P[golv["idx"]] @ golv["n"] + golv["d0"])
    return dict(golv_z=golv_z, tak_z=tak_z, hojd=hojd, golv=golv_stat, vaggar=vaggar,
                ovriga_ytor=ovriga, antal_punkter=int(len(P)))


def analysera_vagg(P, w, golv_z, hojd, tol):
    n, d0, nh, eu = w["n"].copy(), w["d0"], w["nh"], w["eu"]
    umin, umax = w["umin"], w["umax"]
    u, v = P @ eu, P[:, 2] - golv_z
    ext = (u > umin) & (u < umax) & (v > 0) & (v < hojd)
    inre = ext & (u > umin + tol["marg"]) & (u < umax - tol["marg"]) & \
        (v > tol["marg"]) & (v < hojd - tol["marg"])
    utesluten = np.zeros(len(P), bool)
    for varv in (1, 2):
        # Varv 2: oppningar och insankta falt fran varv 1 utesluts ur anpassningen.
        # Annars drar en stangd dorr planet bakat och ger falsk lutning.
        d = P @ w["n"] + w["d0"]
        pass_ = inre & (np.abs(d) < 0.05) & ~utesluten
        n, d0 = huber_plan(P[pass_], w["n"].copy(), w["d0"], tol["huber"])
        d = P @ n + d0
        band = ext & (np.abs(d) < tol["band"])
        ub, vb, db = u[band], v[band], d[band]
        fit = pass_[band] & (np.abs(db) < 0.05)
        poly = huber_poly2(ub[fit], vb[fit], db[fit], tol["huber"])
        rb = db - poly(ub, vb)
        kandidater, tackning = rutnat(ub, vb, rb, umin, umax, hojd, P, n, d0, eu, golv_z, tol)
        utesluten[:] = False
        for k in kandidater:
            u0, u1, v0, v1 = k["box"]
            utesluten |= (u > u0 - 0.1) & (u < u1 + 0.1) & (v > v0 - 0.1) & (v < v1 + 0.1)

    plan_s, yta_s = stat(db[fit]), stat(rb[fit])
    # Kriteriet jamfor ytmodellen med planet, inte residualerna med varandra.
    # Residualkvoten (forsta versionen) foll under brus 5 mm: bruset dolde buktningen (prov F4).
    gu, gv = np.meshgrid(np.linspace(umin + tol["marg"], umax - tol["marg"], 40),
                         np.linspace(tol["marg"], hojd - tol["marg"], 30))
    sys_mm = 1e3 * float(np.percentile(np.abs(poly(gu.ravel(), gv.ravel())), 95))
    plan_otillr = sys_mm > 1e3 * tol["plan_sys"]
    lutning = -n[2] / np.sqrt(max(1 - n[2] ** 2, 1e-12)) * 1e3   # mm/m, + = overkant in mot rummet

    # Tjocklek: observerad i en dorroppnings smyg, annars nedre grans eller antagen
    tj = [k for k in kandidater if k["typ"] == "dorroppning" and k["smyg_m"]]
    lagsta = [k["smyg_m"] for k in kandidater if k["typ"] == "fonsteroppning" and k["smyg_m"]]
    if tj:
        tjocklek = dict(varde_m=round(tj[0]["smyg_m"], 3), kalla="observerad", metod="smyg i dorroppning")
    elif lagsta:
        tjocklek = dict(varde_m=tol["antagen_tjocklek"], kalla="antagen",
                        metod=f"minst {max(lagsta):.2f} m (karm i fonstersmyg); full tjocklek ej observerad")
    else:
        tjocklek = dict(varde_m=tol["antagen_tjocklek"], kalla="antagen", metod="ingen smyg observerad")

    azimut = float(np.degrees(np.arctan2(nh[1], nh[0])) % 360)
    offset = float(-(d0) / (n @ nh)) if abs(n @ nh) > 1e-9 else 0.0
    # + 0.0 tar bort tecknet pa noll: -0.0 och 0.0 gav olika GUID for samma vagg (prov G1)
    nyckel = f"vagg:{int(round(azimut / 5) * 5) % 360}:{round(offset, 1) + 0.0}"
    return dict(nyckel=nyckel, n=n.tolist(), d0=float(d0), nh=nh.tolist(), eu=eu.tolist(),
                umin=umin, umax=umax, langd_m=umax - umin, azimut_grader=azimut,
                plan=plan_s, ytmodell=yta_s, systematisk_avvikelse_mm=sys_mm, plan_otillrackligt=bool(plan_otillr),
                lutning_mm_per_m=float(lutning), tjocklek=tjocklek,
                tackning=tackning, kandidater=kandidater, kant=w.get("kant", {}),
                _poly=poly)


def rutnat(ub, vb, rb, umin, umax, hojd, P, n, d0, eu, golv_z, tol):
    # Rutnat: tom (inga punkter) eller insankt (punkterna ligger bakom ytan)
    c = tol["cell"]
    nu, nv = int(np.ceil((umax - umin) / c)), int(np.ceil(hojd / c))
    iu = np.clip(((ub - umin) / c).astype(int), 0, nu - 1)
    iv = np.clip((vb / c).astype(int), 0, nv - 1)
    alla = np.zeros((nu, nv), int)
    ytan = np.zeros((nu, nv), int)
    bakom = np.zeros((nu, nv), int)
    np.add.at(alla, (iu, iv), 1)
    np.add.at(ytan, (iu, iv), (np.abs(rb) < tol["yta"]).astype(int))
    np.add.at(bakom, (iu, iv), ((rb < -tol["insankt"]) & (rb > -tol["band"])).astype(int))

    F = np.abs(rb) < tol["yta"]
    Fu, Fv = ub[F], vb[F]
    kandidater = []
    for slag, mask in (("tom", alla == 0), ("insankt", (bakom > ytan) & (bakom >= 2))):
        lab, k = ndimage.label(mask)
        for i, sl in enumerate(ndimage.find_objects(lab), start=1):
            yta_m2 = (lab[sl] == i).sum() * c * c
            bu, bv = (sl[0].stop - sl[0].start) * c, (sl[1].stop - sl[1].start) * c
            if yta_m2 < 0.2 or bu < 0.3 or bv < 0.3 or sl[0].start == 0 or sl[0].stop == nu:
                continue
            box = (umin + sl[0].start * c, umin + sl[0].stop * c, sl[1].start * c, sl[1].stop * c)
            kandidater.append(klassa(slag, box, Fu, Fv, P, n, d0, eu, golv_z, tol))

    # Tackning: andel rutor utanfor oppningarna som har minst en punkt (matunderlag)
    fri = np.ones((nu, nv), bool)
    for k in kandidater:
        u0, u1, v0, v1 = k["box"]
        fri[int(round((u0 - umin) / c)):int(round((u1 - umin) / c)), int(round(v0 / c)):int(round(v1 / c))] = False
    tackning = float((alla[fri] > 0).mean()) if fri.any() else 0.0
    return kandidater, tackning


def klassa(slag, box, Fu, Fv, P, n, d0, eu, golv_z, tol):
    u0, u1, v0, v1 = box
    uc, vc = (u0 + u1) / 2, (v0 + v1) / 2
    rad = (Fv > max(v0, 0) + 0.10) & (Fv < v1 - 0.10)
    L = kte(Fu[rad & (Fu < uc) & (Fu > u0 - 0.2)], 3, True)
    R = kte(Fu[rad & (Fu > uc) & (Fu < u1 + 0.2)], 3, False)
    if L is None or R is None:
        return dict(slag=slag, typ="osaker", kalla="observerad", skal="kant saknas", box=box)
    kol = (Fu > L + 0.05) & (Fu < R - 0.05)
    T = kte(Fv[kol & (Fv > vc) & (Fv < v1 + 0.2)], 3, False)
    Bv = Fv[kol & (Fv < vc) & (Fv > v0 - 0.2)]
    B = kte(Bv, 3, True) if len(Bv) else 0.0
    W, Hh = R - L, (T - B) if T is not None else None

    dorrlik = Hh is not None and B < 0.15 and 0.6 <= W <= 1.6 and 1.8 <= Hh <= 2.6
    if slag == "tom" and dorrlik:
        typ, skal = "dorroppning", "hal i vaggen fran golv; dorrblad ej observerat"
    elif slag == "tom" and B >= 0.3 and Hh is not None:
        typ, skal = "fonsteroppning", "hal i vaggen med brostning; fonster harlett ur brostningen"
    elif slag == "insankt" and dorrlik:
        typ, skal = "stangd_dorr_kandidat", "rektangulart insankt falt fran golv; dorr harledd, inte observerad"
    else:
        typ, skal = "osaker", "geometrin raecker inte for att avgora"

    # Smygdjup: punkter bakom planet vid oppningens sidokanter
    smyg = None
    if slag == "tom" and Hh is not None:
        d = P @ n + d0
        u = P @ eu
        v = P[:, 2] - golv_z
        kant = ((np.abs(u - L) < 0.03) | (np.abs(u - R) < 0.03)) & (v > B + 0.2) & (v < T - 0.2) & \
            (d < -0.02) & (d > -tol["max_smyg"])
        if kant.sum() > 20:
            smyg = kte(-d[kant], 5, True)
    return dict(slag=slag, typ=typ, skal=skal, kalla="observerad" if slag == "tom" else "harledd",
                u_vanster=L, u_hoger=R, v_nedre=B, v_ovre=T, bredd_m=W, hojd_m=Hh, smyg_m=smyg, box=box)


def stabil_guid(nyckel):
    import ifcopenshell.guid
    return ifcopenshell.guid.compress(uuid.uuid5(NS, nyckel).hex)
