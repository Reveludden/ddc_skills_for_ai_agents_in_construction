#!/usr/bin/env python3
"""
Fyndkontrakt: varje fynd i en granskning har ett av fyra utfall, och den som
hittade fyndet får inte vara den som bekräftar det.

Metoden är hämtad från cloudflare/security-audit-skill (MIT), översatt från
kodsårbarheter till SFV-granskningar (ÄTA, konsistenskontroll, ekonomi).

Utfall:
    bekraftad            källspår + oberoende verifierare; bara här sätts `betydelse`
    behover_verifiering  exakt `saknat_faktum` + `verifieringsplan`; ingen betydelse
    avvisad              prövad och motbevisad; `skal` + oberoende verifierare
    notering             förbättring utan påverkan; `befintligt_skydd` anger vad
                         som redan bär slutsatsen (djupförsvar är inte en avvikelse)

Betydelse (bara bekraftad): avgorande | vasentlig | begransad
    avgorande  ändrar slutsatsen eller ståndpunkten
    vasentlig  slutsatsen står, men en bärande del måste rättas
    begransad  rättas, påverkar inte slutsatsen

Källspår: lista av {"kalla", "stalle", "citat"} med valfri "fil". Har posten
`fil` och `citat` kontrolleras att citatet finns ordagrant i filen (blanksteg
normaliseras). Går filen inte att läsa som text blir det en varning, inte ett
godkännande: citatet räknas som ej maskinkontrollerat.

Användning:
    python governance/findings_guard.py check  --fynd fynd.json
    python governance/findings_guard.py rapport --fynd fynd.json
    python governance/findings_guard.py rapport --fynd fynd.json --granskning
Exitkod: 0 kontraktet håller, 2 kontraktsbrott. `rapport` ger dessutom 1 när
leveransen inte är klar: något fynd är behover_verifiering. Med `--granskning`
är fynden fel i ett dokument (konsistenskontroll), och då blockerar även
bekraftad med betydelse avgorande eller vasentlig. Utan flaggan är fynden
grunder i en bedömning (ÄTA), och en bekräftad grund är slutsatsen, inte ett fel.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

UTFALL = ("bekraftad", "behover_verifiering", "avvisad", "notering")
BETYDELSE = ("avgorande", "vasentlig", "begransad")
REQUIRED = {
    "bekraftad": ("kallspar", "verifierad_av", "betydelse", "atgard"),
    "behover_verifiering": ("saknat_faktum", "verifieringsplan"),
    "avvisad": ("skal", "verifierad_av"),
    "notering": ("befintligt_skydd",),
}
FORBIDDEN = {
    "behover_verifiering": ("betydelse",),
    "avvisad": ("betydelse", "atgard"),
    "notering": ("betydelse",),
}
LABEL = {
    "bekraftad": "Bekräftad",
    "behover_verifiering": "Behöver verifiering",
    "avvisad": "Avvisad",
    "notering": "Förbättringsnotering",
}


def _norm(s: str) -> str:
    return " ".join(str(s).split())


def _blank(v) -> bool:
    return v is None or (isinstance(v, str) and not v.strip()) or (isinstance(v, (list, dict)) and not v)


def check_trace(item: dict, base: Path, where: str) -> tuple[list[str], list[str]]:
    errs, warns = [], []
    if not isinstance(item, dict):
        return [f"{where}: källspår måste vara ett objekt"], []
    for k in ("kalla", "stalle", "citat"):
        if _blank(item.get(k)):
            errs.append(f"{where}: saknar {k}")
    fil, citat = item.get("fil"), item.get("citat")
    if fil and not _blank(citat):
        p = Path(fil)
        p = p if p.is_absolute() else base / p
        try:
            text = p.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            warns.append(f"{where}: {fil} kunde inte läsas som text; citatet är ej maskinkontrollerat")
        else:
            if _norm(citat) not in _norm(text):
                errs.append(f"{where}: citatet finns inte ordagrant i {fil}")
    return errs, warns


def validate(fynd: list, base: Path) -> tuple[list[str], list[str]]:
    errs, warns = [], []
    if not isinstance(fynd, list):
        return ["fyndfilen måste vara en JSON-lista"], []
    seen = set()
    for i, f in enumerate(fynd):
        if not isinstance(f, dict):
            errs.append(f"post {i}: måste vara ett objekt")
            continue
        fid = f.get("id") or f"post {i}"
        for k in ("id", "pastaende", "utfall", "hittad_av"):
            if _blank(f.get(k)):
                errs.append(f"{fid}: saknar {k}")
        if f.get("id") in seen:
            errs.append(f"{fid}: id förekommer flera gånger")
        seen.add(f.get("id"))
        u = f.get("utfall")
        if u not in UTFALL:
            errs.append(f"{fid}: okänt utfall {u!r} (tillåtna: {', '.join(UTFALL)})")
            continue
        for k in REQUIRED[u]:
            if _blank(f.get(k)):
                errs.append(f"{fid}: {u} kräver {k}")
        for k in FORBIDDEN.get(u, ()):
            if k in f:
                errs.append(f"{fid}: {u} får inte ha {k}")
        if u in ("bekraftad", "avvisad"):
            finder = _norm(f.get("hittad_av") or "").lower()
            verifier = _norm(f.get("verifierad_av") or "").lower()
            if finder and verifier and finder == verifier:
                errs.append(f"{fid}: verifierad_av måste vara en annan än hittad_av (oberoende prövning)")
        if u == "bekraftad":
            if f.get("betydelse") not in BETYDELSE and not _blank(f.get("betydelse")):
                errs.append(f"{fid}: okänd betydelse {f.get('betydelse')!r} (tillåtna: {', '.join(BETYDELSE)})")
            spar = f.get("kallspar")
            if spar is not None and not isinstance(spar, list):
                errs.append(f"{fid}: kallspar måste vara en lista")
            elif spar:
                for j, item in enumerate(spar):
                    e, w = check_trace(item, base, f"{fid} källspår {j + 1}")
                    errs += e
                    warns += w
    return errs, warns


def _load(path: str) -> list:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def cmd_check(a) -> int:
    p = Path(a.fynd)
    errs, warns = validate(_load(a.fynd), p.parent)
    for w in warns:
        print(f"VARNING: {w}")
    for e in errs:
        print(f"FEL: {e}", file=sys.stderr)
    if errs:
        return 2
    print("Fyndkontraktet håller.")
    return 0


def cmd_rapport(a) -> int:
    p = Path(a.fynd)
    fynd = _load(a.fynd)
    errs, warns = validate(fynd, p.parent)
    if errs:
        for e in errs:
            print(f"FEL: {e}", file=sys.stderr)
        return 2
    by = {u: [f for f in fynd if f["utfall"] == u] for u in UTFALL}
    order = {b: i for i, b in enumerate(BETYDELSE)}
    lines = ["### Fyndredovisning", ""]
    lines.append("| Utfall | Antal |")
    lines.append("|---|---|")
    for u in UTFALL:
        lines.append(f"| {LABEL[u]} | {len(by[u])} |")
    if by["bekraftad"]:
        lines += ["", "**Bekräftade avvikelser**" if a.granskning else "**Bekräftade fynd**", ""]
        for f in sorted(by["bekraftad"], key=lambda f: order[f["betydelse"]]):
            kallor = "; ".join(f"{t['kalla']}, {t['stalle']}" for t in f["kallspar"])
            lines.append(f"- `{f['id']}` ({f['betydelse']}): {f['pastaende']} Källa: {kallor}. Åtgärd: {f['atgard']}")
    if by["behover_verifiering"]:
        lines += ["", "**Behöver verifiering** (ingen bedömning görs förrän faktum finns)", ""]
        for f in by["behover_verifiering"]:
            lines.append(f"- `{f['id']}`: {f['pastaende']} Saknas: {f['saknat_faktum']} Plan: {f['verifieringsplan']}")
    if by["notering"]:
        lines += ["", "**Förbättringsnoteringar** (påverkar inte slutsatsen)", ""]
        for f in by["notering"]:
            lines.append(f"- `{f['id']}`: {f['pastaende']} Bärs redan av: {f['befintligt_skydd']}")
    if by["avvisad"]:
        lines += ["", "**Avvisade** (prövade och motbevisade)", ""]
        for f in by["avvisad"]:
            lines.append(f"- `{f['id']}`: {f['pastaende']} Skäl: {f['skal']}")
    blocking = list(by["behover_verifiering"])
    if a.granskning:
        blocking += [f for f in by["bekraftad"] if f["betydelse"] in ("avgorande", "vasentlig")]
    lines += ["", f"Leveransstatus: **{'EJ KLAR' if blocking else 'KLAR'}**"
              + (f" ({len(blocking)} fynd kräver åtgärd eller verifiering)" if blocking else "")]
    if warns:
        lines.append(f"Ej maskinkontrollerade citat: {len(warns)}")
    print("\n".join(lines))
    return 1 if blocking else 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    for name, fn in (("check", cmd_check), ("rapport", cmd_rapport)):
        c = sub.add_parser(name)
        c.add_argument("--fynd", required=True)
        if name == "rapport":
            c.add_argument("--granskning", action="store_true")
        c.set_defaults(func=fn)
    a = ap.parse_args(argv)
    return a.func(a)


if __name__ == "__main__":
    sys.exit(main())
