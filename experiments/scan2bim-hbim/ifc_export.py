"""IFC4-export av scan2bim-resultat med kallsparning per objekt.

Varje objekt far Pset `SFV_Scan2BIM` med Kalla (observerad | harledd | antagen),
metod och residualer. Dorr/fonster kopplas via IfcRelVoidsElement och
IfcRelFillsElement. GUID harleds ur geometrin (uuid5) for att overleva omkorning.
"""
import numpy as np
import ifcopenshell
import ifcopenshell.api as api
import ifcopenshell.api.aggregate
import ifcopenshell.api.context
import ifcopenshell.api.feature
import ifcopenshell.api.geometry
import ifcopenshell.api.project
import ifcopenshell.api.pset
import ifcopenshell.api.root
import ifcopenshell.api.spatial
import ifcopenshell.api.unit
import ifcopenshell.validate

from s2b import Z, stabil_guid


def _matris(origo, eu, nh):
    M = np.eye(4)
    M[:3, 0], M[:3, 1], M[:3, 2], M[:3, 3] = eu, -nh, Z, origo
    return M


def _pset(m, el, props):
    ps = api.pset.add_pset(m, product=el, name="SFV_Scan2BIM")
    api.pset.edit_pset(m, pset=ps, properties={k: v for k, v in props.items() if v is not None})


def skriv(res, sokvag, namn="Scan2BIM syntetiskt rum"):
    m = api.project.create_file(version="IFC4")
    proj = api.root.create_entity(m, ifc_class="IfcProject", name=namn)
    api.unit.assign_unit(m, length={"is_metric": True, "raw": "METERS"})
    modell = api.context.add_context(m, context_type="Model")
    kropp = api.context.add_context(m, context_type="Model", context_identifier="Body",
                                    target_view="MODEL_VIEW", parent=modell)
    site = api.root.create_entity(m, ifc_class="IfcSite", name="Plats")
    bygg = api.root.create_entity(m, ifc_class="IfcBuilding", name="Byggnad")
    plan = api.root.create_entity(m, ifc_class="IfcBuildingStorey", name="Plan 1")
    api.aggregate.assign_object(m, products=[site], relating_object=proj)
    api.aggregate.assign_object(m, products=[bygg], relating_object=site)
    api.aggregate.assign_object(m, products=[plan], relating_object=bygg)

    golv_z, hojd = res["golv_z"], res["hojd"]
    for w in res["vaggar"]:
        n, d0 = np.array(w["n"]), w["d0"]
        nh, eu = np.array(w["nh"]), np.array(w["eu"])

        def pa_planet(u, v):
            q = eu * u + Z * (golv_z + v)
            return q - nh * (q @ n + d0) / (n @ nh)

        origo = pa_planet(w["umin"], 0.0)
        M = _matris(origo, eu, nh)
        vagg = api.root.create_entity(m, ifc_class="IfcWall", name=f"Vagg {w['nyckel']}")
        vagg.GlobalId = stabil_guid(w["nyckel"])
        if w["plan_otillrackligt"]:
            # Skev/bojd vagg: inre vaggytan som triangulerad yta ur ytmodellen
            uu = np.linspace(w["umin"], w["umax"], 21)
            vv = np.linspace(0.0, hojd, 13)
            Ug, Vg = np.meshgrid(uu, vv, indexing="ij")
            d = w["_poly"](Ug.ravel(), Vg.ravel())
            pts = np.array([pa_planet(a, b) for a, b in zip(Ug.ravel(), Vg.ravel())]) + np.outer(d, n)
            lok = (pts - origo) @ np.column_stack([eu, -nh, Z])
            ni, nj = len(uu), len(vv)
            faces = []
            for i in range(ni - 1):
                for j in range(nj - 1):
                    a, b, c, e = i * nj + j, (i + 1) * nj + j, (i + 1) * nj + j + 1, i * nj + j + 1
                    faces += [[a, b, c], [a, c, e]]
            rep = api.geometry.add_mesh_representation(m, context=kropp, vertices=[lok.tolist()],
                                                       faces=[faces])
            geom = "yta (inre vaggliv ur robust ytmodell); tjocklek ej modellerad"
        else:
            rep = api.geometry.add_wall_representation(m, context=kropp, length=w["langd_m"],
                                                       height=hojd, thickness=w["tjocklek"]["varde_m"])
            geom = "parametrisk (plan + extrudering)"
        api.geometry.assign_representation(m, product=vagg, representation=rep)
        api.geometry.edit_object_placement(m, product=vagg, matrix=M)
        api.spatial.assign_container(m, products=[vagg], relating_structure=plan)
        _pset(m, vagg, dict(
            Kalla="observerad", Geometri=geom,
            ResidualPlanMedianMm=round(w["plan"]["median_abs_mm"], 2),
            ResidualPlanP95Mm=round(w["plan"]["p95_abs_mm"], 2),
            ResidualYtmodellP95Mm=round(w["ytmodell"]["p95_abs_mm"], 2),
            PlanOtillrackligt=w["plan_otillrackligt"],
            LutningMmPerM=round(w["lutning_mm_per_m"], 2),
            Tackning=round(w["tackning"], 3),
            Tjocklek=w["tjocklek"]["varde_m"], TjocklekKalla=w["tjocklek"]["kalla"],
            TjocklekMetod=w["tjocklek"]["metod"],
            LangdKalla="; ".join(f"{k}={v}" for k, v in w["kant"].items())))

        for k in w["kandidater"]:
            if k["typ"] not in ("dorroppning", "fonsteroppning", "stangd_dorr_kandidat"):
                continue
            nyckel = f"{w['nyckel']}:{k['typ']}:{round(k['u_vanster'], 1) + 0.0}:{round(k['v_nedre'], 1) + 0.0}"
            x0 = k["u_vanster"] - w["umin"]
            t = w["tjocklek"]["varde_m"]
            Mo = M.copy()
            Mo[:3, 3] = origo + eu * x0 + Z * k["v_nedre"] + nh * 0.05
            opp = api.root.create_entity(m, ifc_class="IfcOpeningElement", name=f"Oppning {k['typ']}")
            opp.GlobalId = stabil_guid(nyckel + ":oppning")
            rep = api.geometry.add_wall_representation(m, context=kropp, length=k["bredd_m"],
                                                       height=k["hojd_m"], thickness=t + 0.10)
            api.geometry.assign_representation(m, product=opp, representation=rep)
            api.geometry.edit_object_placement(m, product=opp, matrix=Mo)
            api.feature.add_feature(m, feature=opp, element=vagg)
            _pset(m, opp, dict(Kalla=k["kalla"], Metod=k["skal"],
                               BreddMm=round(1e3 * k["bredd_m"], 1), HojdMm=round(1e3 * k["hojd_m"], 1)))

            klass = "IfcWindow" if k["typ"] == "fonsteroppning" else "IfcDoor"
            fyll = api.root.create_entity(m, ifc_class=klass, name=k["typ"])
            fyll.GlobalId = stabil_guid(nyckel + ":fyllnad")
            fyll.OverallWidth, fyll.OverallHeight = k["bredd_m"], k["hojd_m"]
            Mf = M.copy()
            Mf[:3, 3] = origo + eu * x0 + Z * k["v_nedre"] - nh * (t / 2 - 0.025)
            rep = api.geometry.add_wall_representation(m, context=kropp, length=k["bredd_m"],
                                                       height=k["hojd_m"], thickness=0.05)
            api.geometry.assign_representation(m, product=fyll, representation=rep)
            api.geometry.edit_object_placement(m, product=fyll, matrix=Mf)
            api.feature.add_filling(m, opening=opp, element=fyll)
            api.spatial.assign_container(m, products=[fyll], relating_structure=plan)
            _pset(m, fyll, dict(
                Kalla="harledd", Metod=k["skal"],
                Sakerhet="medel" if k["typ"] == "stangd_dorr_kandidat" else "hog",
                DorrbladObserverat=False if klass == "IfcDoor" else None))

    m.write(sokvag)
    return m


def kontrollera(sokvag):
    """Schemavalidering + egna relationstester. Returnerar lista med fel."""
    m = ifcopenshell.open(sokvag)
    logg = ifcopenshell.validate.json_logger()
    ifcopenshell.validate.validate(m, logg)
    fel = [f"schema: {s.get('message', s)}" for s in logg.statements]
    for el in m.by_type("IfcDoor") + m.by_type("IfcWindow"):
        if not el.FillsVoids:
            fel.append(f"{el.is_a()} {el.GlobalId} saknar IfcRelFillsElement")
        else:
            opp = el.FillsVoids[0].RelatingOpeningElement
            if not opp.VoidsElements:
                fel.append(f"oppning {opp.GlobalId} saknar IfcRelVoidsElement")
    for el in m.by_type("IfcElement"):
        if not any(p.Name == "SFV_Scan2BIM" for r in el.IsDefinedBy
                   for p in [getattr(r, "RelatingPropertyDefinition", None)] if p):
            fel.append(f"{el.is_a()} {el.GlobalId} saknar SFV_Scan2BIM")
    tal = {t: len(m.by_type(t)) for t in ("IfcWall", "IfcOpeningElement", "IfcDoor", "IfcWindow")}
    return fel, tal
