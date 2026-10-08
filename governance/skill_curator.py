#!/usr/bin/env python3
"""
Skill-curator: flaggar skills som bara är prosa.

Varje skill ska bära en kontrollerbar regel i en sektion `## Kontrollregel`
med minst ett `kommando:` eller en `sökväg:` i backticks, samt en mänsklig
granskare (`granskad_av:`). Curatorn läser bara; den kör inga kommandon och
skriver aldrig i SKILL.md.

Användning:
    python governance/skill_curator.py scan <rot> [--json ut.json] [--strict]
    python governance/skill_curator.py propose <telemetri.jsonl> [--min 3] [--out governance/proposals]

`propose` är meta-agentens enda skrivväg: den lägger förslag i proposals/
med status `proposed`. Ett förslag blir regel först när en människa för in
det i SKILL.md och fyller i `granskad_av`.
"""
from __future__ import annotations

import argparse
import json
import re
import shutil
import sys
from collections import Counter
from dataclasses import asdict, dataclass, field
from datetime import date
from pathlib import Path

SECTION_RE = re.compile(r"^##\s+(Kontrollregel|Check rule)\s*$", re.IGNORECASE | re.MULTILINE)
NEXT_SECTION_RE = re.compile(r"^##\s+", re.MULTILINE)
FIELD_RE = re.compile(r"^\s*[-*]?\s*([\wåäöÅÄÖ_]+)\s*:\s*(.+?)\s*$", re.MULTILINE)
BACKTICK_RE = re.compile(r"`([^`]+)`")

ALIASES = {
    "kommando": "kommando", "command": "kommando",
    "sökväg": "sokvag", "sokvag": "sokvag", "path": "sokvag",
    "regel": "regel", "rule": "regel",
    "id": "id",
    "granskad_av": "granskad_av", "reviewed_by": "granskad_av",
    "granskad": "granskad", "reviewed": "granskad",
    "källa": "kalla", "kalla": "kalla", "source": "kalla",
}

WINDOWS_PATH_RE = re.compile(r"^([A-Za-z]:[\\/]|\\\\)")


@dataclass
class SkillResult:
    path: str
    status: str  # OK | PROSE_ONLY | UNREVIEWED
    rule_id: str | None = None
    kommando: list[str] = field(default_factory=list)
    sokvag: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


def parse_rule_section(text: str) -> dict[str, list[str]] | None:
    m = SECTION_RE.search(text)
    if not m:
        return None
    body = text[m.end():]
    nxt = NEXT_SECTION_RE.search(body)
    if nxt:
        body = body[: nxt.start()]
    fields: dict[str, list[str]] = {}
    for key, value in FIELD_RE.findall(body):
        canon = ALIASES.get(key.lower())
        if not canon:
            continue
        if canon in ("kommando", "sokvag"):
            vals = BACKTICK_RE.findall(value)  # bara backtickad text räknas
        else:
            vals = [value.strip("`")]
        fields.setdefault(canon, []).extend(v.strip() for v in vals if v.strip())
    return fields


def _check_path(p: str, skill_dir: Path) -> str | None:
    if WINDOWS_PATH_RE.match(p) and sys.platform != "win32":
        return f"sökväg ej kontrollerbar på denna plattform: {p}"
    cand = Path(p) if Path(p).is_absolute() else skill_dir / p
    if not cand.exists():
        return f"sökväg saknas: {p}"
    return None


def _check_command(cmd: str, skill_dir: Path) -> str | None:
    head = cmd.split()[0] if cmd.split() else ""
    if not head:
        return "tomt kommando"
    if shutil.which(head) or (skill_dir / head).exists():
        return None
    return f"kommandots program hittas inte i PATH: {head}"


def curate_file(skill_md: Path) -> SkillResult:
    text = skill_md.read_text(encoding="utf-8", errors="replace")
    res = SkillResult(path=str(skill_md), status="PROSE_ONLY")
    fields = parse_rule_section(text)
    if fields is None:
        res.warnings.append("saknar sektionen '## Kontrollregel'")
        return res
    res.rule_id = (fields.get("id") or [None])[0]
    res.kommando = fields.get("kommando", [])
    res.sokvag = fields.get("sokvag", [])
    if not res.kommando and not res.sokvag:
        res.warnings.append("Kontrollregel utan kommando eller sökväg i backticks")
        return res
    for p in res.sokvag:
        if (w := _check_path(p, skill_md.parent)):
            res.warnings.append(w)
    for c in res.kommando:
        if (w := _check_command(c, skill_md.parent)):
            res.warnings.append(w)
    if not fields.get("granskad_av"):
        res.status = "UNREVIEWED"
        res.warnings.append("regeln saknar granskad_av (mänsklig granskning)")
        return res
    res.status = "OK"
    return res


def scan(root: Path) -> list[SkillResult]:
    files = sorted(p for p in root.rglob("*") if p.is_file() and p.name.lower() == "skill.md")
    return [curate_file(f) for f in files]


def cmd_scan(args: argparse.Namespace) -> int:
    results = scan(Path(args.root))
    counts = Counter(r.status for r in results)
    for r in results:
        if r.status != "OK" or r.warnings:
            print(f"[{r.status}] {r.path}")
            for w in r.warnings:
                print(f"    - {w}")
    print(f"\nTotalt {len(results)} skills: " + ", ".join(f"{k}={v}" for k, v in sorted(counts.items())))
    if args.json:
        Path(args.json).write_text(json.dumps([asdict(r) for r in results], ensure_ascii=False, indent=2), encoding="utf-8")
    if args.strict and (counts["PROSE_ONLY"] or counts["UNREVIEWED"]):
        return 1
    return 0


def cmd_propose(args: argparse.Namespace) -> int:
    """Meta-agent: föreslå regler ur telemetri. Skriver aldrig i SKILL.md.

    Telemetri (JSONL), en händelse per rad:
        {"skill": "ata-hindersanalys", "kommando": "...", "utfall": "human_accepted"}
        {"skill": "...", "sokvag": "...", "utfall": "human_corrected"}
    Endast händelser med mänskligt granskat utfall räknas (human_accepted,
    human_corrected). Övriga ignoreras.
    """
    counter: Counter[tuple[str, str, str]] = Counter()
    for line in Path(args.telemetry).read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        ev = json.loads(line)
        if ev.get("utfall") not in ("human_accepted", "human_corrected"):
            continue
        for kind in ("kommando", "sokvag"):
            if ev.get(kind):
                counter[(ev["skill"], kind, ev[kind])] += 1
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    written = 0
    for (skill, kind, value), n in sorted(counter.items()):
        if n < args.min:
            continue
        slug = re.sub(r"[^\w-]+", "-", f"{skill}-{kind}-{value}")[:80].strip("-")
        target = out / f"{date.today().isoformat()}_{slug}.md"
        if target.exists():
            continue
        label = "kommando" if kind == "kommando" else "sökväg"
        target.write_text(
            f"---\nstatus: proposed\nskill: {skill}\nkalla: meta-agent\nunderlag: {n} granskade händelser\n---\n"
            f"## Kontrollregel (FÖRSLAG – ej införd)\n"
            f"- id: <sätts av granskare>\n"
            f"- regel: <formuleras av granskare>\n"
            f"- {label}: `{value}`\n"
            f"- källa: meta-agent\n"
            f"- granskad_av: <tomt tills en människa godkänt>\n",
            encoding="utf-8",
        )
        written += 1
        print(f"förslag: {target}")
    print(f"{written} förslag skrivna till {out} (inga SKILL.md ändrade)")
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("scan")
    s.add_argument("root")
    s.add_argument("--json")
    s.add_argument("--strict", action="store_true")
    s.set_defaults(func=cmd_scan)
    p = sub.add_parser("propose")
    p.add_argument("telemetry")
    p.add_argument("--min", type=int, default=3)
    p.add_argument("--out", default=str(Path(__file__).parent / "proposals"))
    p.set_defaults(func=cmd_propose)
    args = ap.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
