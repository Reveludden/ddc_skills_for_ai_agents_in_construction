"""Provsvit: kedjan mot facit, och matinstrumenten mot kanda fel.

Kor:  python prov.py [utdatakatalog]
Varje prov rapporterar forvantat, uppmatt och GODKAND/UNDERKAND.
Exitkod 0 = alla godkanda, 1 = minst ett underkant.
"""
import json
import os
import sys
import time

import numpy as np
import ifcopenshell
import ifcopenshell.geom

import ifc_export as X
import s2b
import syntetisk as S

UT = sys.argv[1] if len(sys.argv) > 1 else "utdata"
os.makedirs(UT, exist_ok=True)
RESULTAT = []


def prov(id_, namn, ok, forvantat, uppmatt):
    RESULTAT.append(dict(id=id_, namn=namn, godkand=bool(ok), forvantat=forvantat, uppmatt=uppmatt))
    print(f"{'GODKAND ' if ok else 'UNDERKAND'} {id_:4} {namn}: forvantat {forvantat} | uppmatt {uppmatt}")


def vagg_for(res, facitvagg):
    nf = S.VAGGAR[facitvagg]["n"]
    return next((w for w in res["vaggar"] if np.array(w["nh"]) @ nf > 0.99), None)


def i_facit(w, facitvagg, u):
    eu, ef = np.array(w["eu"]), S.VAGGAR[facitvagg]["eu"]
    return u * (eu @ ef) - S.VAGGAR[facitvagg]["origo"] @ ef


def matcha(res, o):
    """Kandidat pa ratt vagg vars u-intervall overlappar facit. Returnerar (kandidat, fel i mm)."""
    w = vagg_for(res, o["vagg"])
    if w is None:
        return None, None
    for k in w["kandidater"]:
        a, b = sorted([i_facit(w, o["vagg"], k["u_vanster"]), i_facit(w, o["vagg"], k["u_hoger"])])
        if b > o["u0"] and a < o["u1"]:
            fel = dict(vanster=1e3 * (a - o["u0"]), hoger=1e3 * (b - o["u1"]),
                       nedre=1e3 * (k["v_nedre"] - o["v0"]), ovre=1e3 * (k["v_ovre"] - o["v1"]),
                       bredd=1e3 * (k["bredd_m"] - (o["u1"] - o["u0"])),
                       hojd=1e3 * (k["hojd_m"] - (o["v1"] - o["v0"])))
            return k, fel
    return None, None


def r1(x):
    return round(float(x), 1)


t0 = time.time()

# ---------- A. Basrummet ----------
P, F = S.rum(seed=1)
res = s2b.kor(P)
prov("A1", "fyra vaggar, golv och tak", len(res["vaggar"]) == 4 and abs(res["hojd"] - 3.0) < 0.005,
     "4 vaggar, hojd 3000 mm", f"{len(res['vaggar'])} vaggar, hojd {r1(1e3 * res['hojd'])} mm")

typnamn = {"dorroppning": "dorroppning", "fonsteroppning": "fonsteroppning", "stangd_dorr": "stangd_dorr_kandidat"}
for id_, o in (("A2", F["oppningar"][0]), ("A3", F["oppningar"][1]), ("A4", F["stangda"][0])):
    k, fel = matcha(res, o)
    ok = k is not None and k["typ"] == typnamn[o["typ"]] and max(abs(v) for v in fel.values()) <= 20
    prov(id_, f"{o['typ']} pa vagg {o['vagg']} hittad, kanter inom 20 mm", ok,
         f"typ {typnamn[o['typ']]}, |fel| <= 20 mm",
         "ej hittad" if k is None else f"typ {k['typ']}, fel mm " + str({a: r1(b) for a, b in fel.items()}))

flagg = {v: vagg_for(res, v)["plan_otillrackligt"] for v in "SONV"}
prov("A5", "plan otillrackligt endast for den bojda vaggen N", flagg == dict(S=False, O=False, N=True, V=False),
     "N=True, ovriga False", str(flagg))

lut = {v: r1(vagg_for(res, v)["lutning_mm_per_m"]) for v in "SONV"}
prov("A6", "lutning: N 5 mm/m (15 mm pa 3 m), ovriga 0", abs(lut["N"] - 5.0) <= 0.5 and
     all(abs(lut[v]) <= 0.5 for v in "SOV"), "N 5,0 +-0,5; ovriga |l| <= 0,5", str(lut))

tj = vagg_for(res, "S")["tjocklek"]
prov("A7", "vaggtjocklek S observerad i dorrsmyg", tj["kalla"] == "observerad" and abs(tj["varde_m"] - 0.45) <= 0.01,
     "observerad, 450 +-10 mm", f"{tj['kalla']}, {r1(1e3 * tj['varde_m'])} mm")
tjo = {v: vagg_for(res, v)["tjocklek"]["kalla"] for v in "ONV"}
prov("A8", "tjocklek utan dorrsmyg markeras antagen", all(x == "antagen" for x in tjo.values()),
     "O, N, V = antagen", str(tjo))

lang = {v: r1(1e3 * vagg_for(res, v)["langd_m"]) for v in "SONV"}
prov("A9", "vagglangd ur horn (S, N 5000; O, V 4000 mm), inom 20 mm",
     all(abs(lang[v] - 1e3 * S.VAGGAR[v]["L"]) <= 20 for v in "SONV"), "|fel| <= 20 mm", str(lang))

ifcfil = os.path.join(UT, "modell.ifc")
X.skriv(res, ifcfil)
fel, tal = X.kontrollera(ifcfil)
prov("A10", "IFC: schema + relationer + kallsparning", not fel and tal == dict(IfcWall=4, IfcOpeningElement=3, IfcDoor=2, IfcWindow=1),
     "0 fel; 4 vaggar, 3 oppningar, 2 dorrar, 1 fonster", f"{len(fel)} fel; {tal}")

# A11: IFC-geometrin tur och retur - oppningarnas lage i varldskoordinater ska motsvara pipelinen
ins = ifcopenshell.geom.settings()
ins.set("use-world-coords", True)
m = ifcopenshell.open(ifcfil)
maxfel = 0.0
for el in m.by_type("IfcOpeningElement"):
    v = np.array(ifcopenshell.geom.create_shape(ins, el).geometry.verts).reshape(-1, 3)
    vagg = el.VoidsElements[0].RelatingBuildingElement
    w = next(w for w in res["vaggar"] if X.stabil_guid(w["nyckel"]) == vagg.GlobalId)
    k = next(k for k in w["kandidater"] if k["typ"] in el.Name)
    u = v @ np.array(w["eu"])
    z = v[:, 2] - res["golv_z"]
    maxfel = max(maxfel, abs(u.min() - k["u_vanster"]), abs(u.max() - k["u_hoger"]),
                 abs(z.min() - k["v_nedre"]), abs(z.max() - k["v_ovre"]))
prov("A11", "IFC-oppningarnas varldslage = uppmatt lage", maxfel <= 0.001, "<= 1 mm", f"{r1(1e3 * maxfel)} mm")

# A12: IFC-vaggens inre yta mot de uppmatta punkterna (inte mot pipelinens egna tal).
# For parametriska vaggar: avstand fran ytans horn till punkterna nara hornen.
from scipy.spatial import cKDTree
trad = cKDTree(P)
vfel = {}
for el in m.by_type("IfcWall"):
    w = next(w for w in res["vaggar"] if X.stabil_guid(w["nyckel"]) == el.GlobalId)
    if w["plan_otillrackligt"]:
        continue
    v = np.array(ifcopenshell.geom.create_shape(ins, el).geometry.verts).reshape(-1, 3)
    n, d0 = np.array(w["n"]), w["d0"]
    inre = v[np.abs(v @ n + d0) < 0.2]            # hornen pa rumssidan
    sond = inre + 0.0
    sond[:, 2] = np.clip(sond[:, 2], res["golv_z"] + 0.3, res["tak_z"] - 0.3)
    lok = []
    for p in sond:
        idx = trad.query_ball_point(p, 0.25)
        q = P[idx]
        q = q[np.abs(q @ n + d0) < 0.03]
        if len(q):
            lok.append(abs(np.median(q @ n + d0) - (p @ n + d0)))
    vfel[el.Name.split()[-1]] = r1(1e3 * max(lok)) if lok else None
prov("A12", "IFC-vaggens inre yta vid hornen mot punktmolnet", all(x is not None and x <= 3 for x in vfel.values()),
     "<= 3 mm", str(vfel))

# ---------- B. Forstorelseprov: kand forskjutning 14 mm ----------
patch = dict(vagg="O", u0=3.0, u1=3.8, v0=0.5, v1=1.5, d=0.014)
Pb, _ = S.rum(seed=1, patch=patch)
rb = s2b.kor(Pb)
w = vagg_for(rb, "O")
n, d0, eu = np.array(w["n"]), w["d0"], np.array(w["eu"])
u = Pb @ eu
uf = u * (eu @ S.VAGGAR["O"]["eu"]) - S.VAGGAR["O"]["origo"] @ S.VAGGAR["O"]["eu"]
v = Pb[:, 2] - rb["golv_z"]
d = Pb @ n + d0
inne = (uf > 3.1) & (uf < 3.7) & (v > 0.6) & (v < 1.4) & (np.abs(d) < 0.05)
plan_mm = 1e3 * np.median(d[inne])
yta_mm = 1e3 * np.median(d[inne] - w["_poly"](u[inne], v[inne]))
prov("B1", "kand utbuktning 14 mm uppmatt mot planet", abs(plan_mm - 14) <= 2, "14 +-2 mm", f"{r1(plan_mm)} mm")
prov("B2", "kand utbuktning 14 mm uppmatt mot ytmodellen", abs(yta_mm - 14) <= 2, "14 +-2 mm", f"{r1(yta_mm)} mm")

# ---------- C. Forstorelseprov for IFC-kontrollen ----------
m = ifcopenshell.open(ifcfil)
m.remove(m.by_type("IfcRelFillsElement")[0])
m.remove(m.by_type("IfcRelVoidsElement")[0])
skadad = os.path.join(UT, "skadad.ifc")
m.write(skadad)
fel_c, _ = X.kontrollera(skadad)
prov("C1", "IFC-kontrollen hittar borttagna void/fill-relationer", len(fel_c) >= 2,
     ">= 2 fel", f"{len(fel_c)} fel: " + "; ".join(fel_c[:3]))
m = ifcopenshell.open(ifcfil)
rel = m.by_type("IfcRelDefinesByProperties")[0]
rel.RelatingPropertyDefinition = None
m.write(skadad)
fel_c2, _ = X.kontrollera(skadad)
prov("C2", "IFC-kontrollen hittar brutet obligatoriskt attribut (schema)", any(f.startswith("schema") for f in fel_c2),
     ">= 1 schemafel", f"{len(fel_c2)} fel: " + "; ".join(fel_c2[:2]))
os.remove(skadad)

# ---------- D. Negativ kontroll: rum utan oppningar, rak vagg ----------
Pd, _ = S.rum(seed=3, dorr=False, fonster=False, stangd_djup=None, bukt=0.0, lutning=0.0)
rd = s2b.kor(Pd)
nk = sum(len(w["kandidater"]) for w in rd["vaggar"])
no = sum(w["plan_otillrackligt"] for w in rd["vaggar"])
prov("D1", "inga oppningar i ett rum utan oppningar", nk == 0, "0 kandidater", f"{nk}")
prov("D2", "ingen vagg flaggas skev i ett rakt rum", no == 0, "0 flaggade", f"{no}")

# ---------- E. Stangd dorr i liv med vaggen (5 mm) ----------
Pe, _ = S.rum(seed=1, stangd_djup=0.005)
re_ = s2b.kor(Pe)
kv = vagg_for(re_, "V")["kandidater"]
prov("E1", "stangd dorr 5 mm i liv: ingen dorr pastas", len(kv) == 0,
     "0 kandidater (kanda granser: ej detekterbar)", f"{len(kv)}: {[k['typ'] for k in kv]}")

# ---------- F. Svarare data: brus 5 mm, halv tathet ----------
Pf, Ff = S.rum(seed=4, sigma=0.005, tathet=1250)
rf = s2b.kor(Pf)
for id_, o in (("F1", Ff["oppningar"][0]), ("F2", Ff["oppningar"][1]), ("F3", Ff["stangda"][0])):
    k, fel = matcha(rf, o)
    ok = k is not None and k["typ"] == typnamn[o["typ"]] and max(abs(v) for v in fel.values()) <= 20
    prov(id_, f"sigma 5 mm, halv tathet: {o['typ']}", ok, "hittad, |fel| <= 20 mm",
         "ej hittad" if k is None else f"typ {k['typ']}, max |fel| {r1(max(abs(v) for v in fel.values()))} mm")
fl = {v: vagg_for(rf, v)["plan_otillrackligt"] for v in "SONV"}
prov("F4", "sigma 5 mm: bara N flaggas skev", fl == dict(S=False, O=False, N=True, V=False), "N=True", str(fl))

# ---------- G. Stabila GUID vid omkorning med nytt brus ----------
def guider(r):
    g = set()
    for w in r["vaggar"]:
        g.add(X.stabil_guid(w["nyckel"]))
        for k in w["kandidater"]:
            g.add(f"{w['nyckel']}:{k['typ']}:{round(k['u_vanster'], 1) + 0.0}:{round(k['v_nedre'], 1) + 0.0}")
    return g
P2, _ = S.rum(seed=2)
g1, g2 = guider(res), guider(s2b.kor(P2))
prov("G1", "samma identiteter efter omkorning (nytt brus)", g1 == g2, f"{len(g1)} lika", f"{len(g1 & g2)} av {len(g1 | g2)} lika")

# ---------- H. Upprepning: 10 slumpfro, precision och recall ----------
traff, saknade, falska, fel_alla = 0, 0, 0, {t: [] for t in typnamn}
for seed in range(10, 20):
    Ph, Fh = S.rum(seed=seed)
    rh = s2b.kor(Ph)
    facit = Fh["oppningar"] + Fh["stangda"]
    anv = set()
    for o in facit:
        k, fel = matcha(rh, o)
        if k is not None and k["typ"] == typnamn[o["typ"]]:
            traff += 1
            anv.add(id(k))
            fel_alla[o["typ"]] += [abs(fel["bredd"]), abs(fel["hojd"]), abs(fel["vanster"]), abs(fel["nedre"])]
        else:
            saknade += 1
    falska += sum(1 for w in rh["vaggar"] for k in w["kandidater"] if id(k) not in anv)
prec = traff / max(traff + falska, 1)
rec = traff / max(traff + saknade, 1)
mae = {t: r1(np.mean(v)) if v else None for t, v in fel_alla.items()}
prov("H1", "precision over 10 rum (30 oppningar)", prec >= 0.95, ">= 0,95", f"{prec:.3f} ({traff} ratt, {falska} falska)")
prov("H2", "recall over 10 rum (30 oppningar)", rec >= 0.90, ">= 0,90", f"{rec:.3f} ({saknade} missade)")
prov("H3", "MAE matt per oppningstyp", all(v is not None and v <= 20 for v in mae.values()), "<= 20 mm", str(mae))

tid = time.time() - t0
ok = all(r["godkand"] for r in RESULTAT)
sammanf = dict(godkanda=sum(r["godkand"] for r in RESULTAT), totalt=len(RESULTAT), tid_s=round(tid, 1),
               versioner=dict(numpy=np.__version__, ifcopenshell=ifcopenshell.version))
print(f"\n{sammanf['godkanda']}/{sammanf['totalt']} godkanda, {sammanf['tid_s']} s")


def rent(o):
    if isinstance(o, dict):
        return {k: rent(v) for k, v in o.items() if not k.startswith("_")}
    if isinstance(o, (list, tuple)):
        return [rent(v) for v in o]
    if isinstance(o, (np.floating, np.integer, np.bool_)):
        return o.item()
    return o


with open(os.path.join(UT, "rapport.json"), "w", encoding="utf-8") as f:
    json.dump(dict(sammanfattning=sammanf, prov=RESULTAT, basrum=rent(res)), f, ensure_ascii=False, indent=1)
sys.exit(0 if ok else 1)
