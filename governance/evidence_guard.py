#!/usr/bin/env python3
"""
Styrningsblock efter leverans: tidigare bevis ogiltigförklaras om avtal,
lydelse, preskription eller K21-bas har rört sig.

Bevisloggen är append-only (JSONL). En post ändras aldrig. Ogiltigförklaring
skrivs som en ny post och är bestående: ett ogiltigt bevis blir giltigt igen
bara genom en ny, omverifierad bevispost med nytt id.

Beroendetyper: avtal, lydelse, preskription, k21_bas.
Varje beroende har `ref` plus de fält som ska jämföras, t.ex.
    {"ref": "Kontrakt 2026-114", "fil": "avtal/kontrakt.pdf", "sha256": "..."}
    {"ref": "AB 04 kap 6 § 19", "version": "AB 04"}
    {"ref": "Slutfaktura projekt X", "datum": "2027-03-01"}
    {"ref": "K21 bas projekt X", "period": "2025-03", "varde": "123.4"}
En ny bevispost kan ange `ersatter: [id, ...]`. Ersättning gäller bara via
denna uttryckliga relation, aldrig via tidsordning (jfr MemTrace, ekv. 2).
Ett ersatt bevis är historik: status ERSATT, får inte återanvändas.
Har beroendet `fil` räknas sha256 om från filen. Annars jämförs mot
aktuellt tillstånd (state-fil). Saknas aktuellt värde: OKÄNT, fail-closed.

Användning:
    python governance/evidence_guard.py fingerprint <fil>
    python governance/evidence_guard.py record --ledger L --entry post.json
    python governance/evidence_guard.py check --ledger L --state S [--id ID ...] [--append] [--today YYYY-MM-DD]
    python governance/evidence_guard.py block --ledger L --state S --id ID [--today YYYY-MM-DD]
Exitkod för check: 0 alla giltiga, 1 något OGILTIGT eller OKÄNT.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import date
from pathlib import Path

KINDS = ("avtal", "lydelse", "preskription", "k21_bas")
LABEL = {"avtal": "Avtal", "lydelse": "Lydelse", "preskription": "Preskription", "k21_bas": "K21-bas"}


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def read_ledger(path: Path) -> list[dict]:
    if not path.exists():
        return []
    return [json.loads(l) for l in path.read_text(encoding="utf-8").splitlines() if l.strip()]


def append_ledger(path: Path, record: dict) -> None:
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n")


def validate_entry(entry: dict) -> list[str]:
    errs = []
    for k in ("id", "leverans", "datum", "pastaende", "beroenden"):
        if not entry.get(k):
            errs.append(f"saknar fält: {k}")
    deps = entry.get("beroenden") or {}
    if not deps:
        errs.append("minst ett beroende krävs")
    for kind, dep in deps.items():
        if kind not in KINDS:
            errs.append(f"okänd beroendetyp: {kind} (tillåtna: {', '.join(KINDS)})")
        elif not isinstance(dep, dict) or not dep.get("ref"):
            errs.append(f"{kind}: saknar ref")
        elif len([k for k in dep if k != "ref"]) == 0:
            errs.append(f"{kind}: inget jämförbart fält utöver ref")
    return errs


def evaluate(entry: dict, state: dict, base: Path, today: date) -> tuple[str, list[str]]:
    """Returnerar (status, orsaker). status: GILTIGT | OGILTIGT | OKÄNT."""
    reasons, unknown = [], []
    for kind, dep in entry["beroenden"].items():
        ref = dep["ref"]
        if "fil" in dep:
            p = Path(dep["fil"])
            p = p if p.is_absolute() else base / p
            if not p.exists():
                unknown.append(f"{LABEL[kind]} '{ref}': fil saknas ({dep['fil']})")
                continue
            cur = {"sha256": sha256_file(p)}
        else:
            cur = (state.get(kind) or {}).get(ref)
            if cur is None:
                unknown.append(f"{LABEL[kind]} '{ref}': aktuellt tillstånd saknas")
                continue
        for field, then in dep.items():
            if field in ("ref", "fil"):
                continue
            now = cur.get(field)
            if now is None:
                unknown.append(f"{LABEL[kind]} '{ref}': fält '{field}' saknas i aktuellt tillstånd")
            elif str(now) != str(then):
                reasons.append(f"{LABEL[kind]} '{ref}': {field} {then} → {now}")
        if kind == "preskription":
            d = cur.get("datum", dep.get("datum"))
            try:
                if d and date.fromisoformat(str(d)) < today:
                    reasons.append(f"Preskription '{ref}': datum {d} har passerats")
            except ValueError:
                unknown.append(f"Preskription '{ref}': ogiltigt datum {d}")
    if reasons:
        return "OGILTIGT", reasons + unknown
    if unknown:
        return "OKÄNT", unknown
    return "GILTIGT", []


def current_status(records: list[dict], state: dict, base: Path, today: date, ids: list[str] | None):
    invalidated = {r["bevis_id"]: r for r in records if r.get("typ") == "ogiltigforklaring"}
    superseded = {old: r["id"] for r in records if r.get("typ") == "bevis" for old in r.get("ersatter", [])}
    out = []
    for r in records:
        if r.get("typ") != "bevis" or (ids and r["id"] not in ids):
            continue
        if r["id"] in superseded:
            out.append((r, "ERSATT", [f"ersatt av {superseded[r['id']]} (historik, återanvänds inte)"], True))
            continue
        if r["id"] in invalidated:
            prev = invalidated[r["id"]]
            out.append((r, "OGILTIGT", [f"ogiltigförklarat {prev['datum']}: " + "; ".join(prev["orsaker"])], True))
            continue
        status, reasons = evaluate(r, state, base, today)
        out.append((r, status, reasons, False))
    if ids:
        missing = set(ids) - {r["id"] for r, *_ in out}
        for m in sorted(missing):
            out.append(({"id": m, "leverans": "?"}, "OKÄNT", ["bevis-id finns inte i loggen"], False))
    return out


def _load_state(path: str | None) -> dict:
    return json.loads(Path(path).read_text(encoding="utf-8")) if path else {}


def _today(s: str | None) -> date:
    return date.fromisoformat(s) if s else date.today()


def cmd_fingerprint(a) -> int:
    print(sha256_file(Path(a.file)))
    return 0


def cmd_record(a) -> int:
    ledger = Path(a.ledger)
    entry = json.loads(Path(a.entry).read_text(encoding="utf-8"))
    entry["typ"] = "bevis"
    errs = validate_entry(entry)
    known = {r.get("id") for r in read_ledger(ledger) if r.get("typ") == "bevis"}
    if entry.get("id") in known:
        errs.append(f"id {entry['id']} finns redan; loggen är append-only, använd nytt id")
    ers = entry.get("ersatter", [])
    if not isinstance(ers, list):
        errs.append("ersatter måste vara en lista av bevis-id")
    else:
        errs += [f"ersatter: okänt bevis-id {x}" for x in ers if x not in known]
    if errs:
        print("\n".join(f"FEL: {e}" for e in errs), file=sys.stderr)
        return 2
    append_ledger(ledger, entry)
    print(f"registrerat: {entry['id']}")
    return 0


def cmd_check(a) -> int:
    ledger = Path(a.ledger)
    today = _today(a.today)
    rows = current_status(read_ledger(ledger), _load_state(a.state), ledger.parent, today, a.id)
    bad = 0
    for r, status, reasons, sticky in rows:
        print(f"[{status}] {r['id']} ({r.get('leverans', '')})")
        for x in reasons:
            print(f"    - {x}")
        if status in ("OGILTIGT", "OKÄNT") or (status == "ERSATT" and a.id):
            bad += 1
        if a.append and status == "OGILTIGT" and not sticky:
            append_ledger(ledger, {"typ": "ogiltigforklaring", "bevis_id": r["id"],
                                   "datum": today.isoformat(), "orsaker": reasons})
    return 1 if bad else 0


def cmd_block(a) -> int:
    ledger = Path(a.ledger)
    today = _today(a.today)
    rows = current_status(read_ledger(ledger), _load_state(a.state), ledger.parent, today, [a.id])
    r, status, reasons, _ = rows[0]
    lines = [
        "---",
        "### Styrningsblock",
        f"- Bevis: `{r['id']}`, leverans: {r.get('leverans', '?')}, registrerat {r.get('datum', '?')}",
        f"- Status {today.isoformat()}: **{status}**",
    ]
    for kind, dep in (r.get("beroenden") or {}).items():
        vals = ", ".join(f"{k}={v}" for k, v in dep.items() if k != "ref")
        lines.append(f"- Bundet till {LABEL[kind]}: {dep['ref']} ({vals})")
    for x in reasons:
        lines.append(f"- Orsak: {x}")
    lines.append(
        "- Beviset får inte återanvändas om avtal, lydelse, preskription eller K21-bas har ändrats. "
        f"Kontrollera före återanvändning: `python governance/evidence_guard.py check --ledger {a.ledger} "
        f"--state {a.state} --id {r['id']}`"
    )
    print("\n".join(lines))
    return 0 if status == "GILTIGT" else 1


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    f = sub.add_parser("fingerprint"); f.add_argument("file"); f.set_defaults(func=cmd_fingerprint)
    r = sub.add_parser("record"); r.add_argument("--ledger", required=True); r.add_argument("--entry", required=True)
    r.set_defaults(func=cmd_record)
    for name, fn in (("check", cmd_check), ("block", cmd_block)):
        c = sub.add_parser(name)
        c.add_argument("--ledger", required=True)
        c.add_argument("--state")
        c.add_argument("--today")
        if name == "check":
            c.add_argument("--id", nargs="*")
            c.add_argument("--append", action="store_true")
        else:
            c.add_argument("--id", required=True)
        c.set_defaults(func=fn)
    a = ap.parse_args(argv)
    return a.func(a)


if __name__ == "__main__":
    sys.exit(main())
