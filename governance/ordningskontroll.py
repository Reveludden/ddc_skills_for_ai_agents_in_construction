#!/usr/bin/env python3
"""
Ordningskontroll: en agents körlogg prövas mot regler om stegens ordning.

Det här är förkontrollen före en AI-domare. Regler om ordning och närvaro har
ett exakt svar och kontrolleras med kod. En AI-domare kan missa ett steg som
saknas helt och ändå vara säker på att körningen var korrekt.

Körloggen är JSONL, en händelse per rad, i den ordning agenten utförde dem:
    {"korning": "K-1", "steg": "preskription_kontroll", "status": "ok"}
    {"korning": "K-1", "steg": "sakbedomning", "status": "ok"}
Bara `status: "ok"` räknas som lyckat. Fel, timeout och saknad status räknas
inte som att steget är utfört.

Reglerna är en JSON-lista. Två typer:
    {"id": "SFV-ATA-01", "fore": ["preskription_kontroll", "sakbedomning"]}
        Varje gång steg B förekommer måste ett lyckat steg A ha kommit tidigare.
        Förekommer B inte alls är regeln uppfylld.
    {"id": "SFV-ATA-02", "kravs": "avtal_hamtat", "om": "citat_avtal"}
        Steget måste förekomma lyckat i körningen. Med `om` gäller kravet bara
        om det steget förekommer.

Status per körning:
    OK      alla regler uppfyllda
    BRUTEN  minst en regel bruten
    OKÄNT   körningen saknar händelser eller har händelser utan `steg`
            (fail-closed: körningen får inte godkännas)

Användning:
    python governance/ordningskontroll.py check --logg korlogg.jsonl --regler regler.json [--korning ID ...] [--json ut.json]
Exitkod: 0 alla OK, 1 någon BRUTEN eller OKÄNT, 2 felaktiga regler.
Sammanfattningen per regel anger k/n, alltså följsamhet med antal körningar.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def validate_rules(rules: list) -> list[str]:
    errs = []
    seen = set()
    if not isinstance(rules, list):
        return ["reglerna måste vara en JSON-lista"]
    for i, r in enumerate(rules):
        rid = r.get("id") if isinstance(r, dict) else None
        if not rid:
            errs.append(f"regel {i}: id saknas")
            continue
        if rid in seen:
            errs.append(f"{rid}: id förekommer flera gånger")
        seen.add(rid)
        has_fore, has_kravs = "fore" in r, "kravs" in r
        if has_fore == has_kravs:
            errs.append(f"{rid}: ange exakt en av `fore` och `kravs`")
        elif has_fore and not (isinstance(r["fore"], list) and len(r["fore"]) == 2 and all(r["fore"])):
            errs.append(f"{rid}: `fore` ska vara [A, B]")
        elif has_kravs and not r["kravs"]:
            errs.append(f"{rid}: `kravs` saknar steg")
        if "om" in r and not has_kravs:
            errs.append(f"{rid}: `om` gäller bara `kravs`")
    return errs


def read_log(path: Path) -> dict[str, list[dict]]:
    runs: dict[str, list[dict]] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            e = json.loads(line)
            runs.setdefault(str(e.get("korning", "")), []).append(e)
    return runs


def check_rule(rule: dict, events: list[dict]) -> str | None:
    """Returnerar en orsak om regeln är bruten, annars None."""
    if "fore" in rule:
        a, b = rule["fore"]
        a_done = False
        for i, e in enumerate(events):
            if e["steg"] == b and not a_done:
                if any(x["steg"] == a for x in events[:i]):
                    return f"{b} (händelse {i + 1}) efter misslyckat {a}"
                return f"{b} (händelse {i + 1}) utan {a} före"
            if e["steg"] == a and e.get("status") == "ok":
                a_done = True
        return None
    step, cond = rule["kravs"], rule.get("om")
    if cond and not any(e["steg"] == cond for e in events):
        return None
    if any(e["steg"] == step and e.get("status") == "ok" for e in events):
        return None
    if any(e["steg"] == step for e in events):
        return f"{step} förekommer men lyckades inte" + (f" (krävs när {cond} förekommer)" if cond else "")
    return f"{step} saknas" + (f" (krävs när {cond} förekommer)" if cond else "")


def check_run(rules: list[dict], events: list[dict]) -> tuple[str, list[tuple[str, str]]]:
    if not events:
        return "OKÄNT", [("-", "inga händelser")]
    if any(not e.get("steg") for e in events):
        return "OKÄNT", [("-", "händelse utan `steg`")]
    broken = [(r["id"], why) for r in rules if (why := check_rule(r, events))]
    return ("BRUTEN" if broken else "OK"), broken


def cmd_check(a) -> int:
    rules = json.loads(Path(a.regler).read_text(encoding="utf-8"))
    errs = validate_rules(rules)
    if errs:
        print("\n".join(f"FEL: {e}" for e in errs), file=sys.stderr)
        return 2
    runs = read_log(Path(a.logg))
    for k in a.korning or []:
        runs.setdefault(k, [])  # efterfrågad körning utan händelser blir OKÄNT
    ids = a.korning or sorted(runs)
    report, bad = [], 0
    kept = {r["id"]: 0 for r in rules}
    for k in ids:
        status, broken = check_run(rules, runs[k])
        print(f"[{status}] {k}")
        for rid, why in broken:
            print(f"    - {rid}: {why}")
        bad += status != "OK"
        if status != "OKÄNT":
            for r in rules:
                kept[r["id"]] += all(rid != r["id"] for rid, _ in broken)
        report.append({"korning": k, "status": status, "brutna": [{"regel_id": rid, "orsak": w} for rid, w in broken]})
    n = sum(1 for x in report if x["status"] != "OKÄNT")
    print(f"Sammanfattning ({n} körningar med känd status):")
    for rid, k in kept.items():
        print(f"    {rid}: {k}/{n} uppfyllda")
    if a.json:
        Path(a.json).write_text(json.dumps({"korningar": report, "per_regel": {rid: {"uppfyllda": k, "n": n}
                                            for rid, k in kept.items()}}, ensure_ascii=False, indent=2),
                                encoding="utf-8")
    return 1 if bad else 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    c = sub.add_parser("check")
    c.add_argument("--logg", required=True)
    c.add_argument("--regler", required=True)
    c.add_argument("--korning", nargs="*")
    c.add_argument("--json")
    c.set_defaults(func=cmd_check)
    a = ap.parse_args(argv)
    return a.func(a)


if __name__ == "__main__":
    sys.exit(main())
