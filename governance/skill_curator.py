#!/usr/bin/env python3
"""
Skill-curator: flaggar skills som bara är prosa.

Varje skill ska bära en kontrollerbar regel i en sektion `## Kontrollregel`
med minst ett `kommando:` eller en `sökväg:` i backticks, samt en mänsklig
granskare (`granskad_av:`). Curatorn läser bara; den kör inga kommandon och
skriver aldrig i SKILL.md.

Användning:
    python governance/skill_curator.py scan <rot> [--json ut.json] [--strict]
    python governance/skill_curator.py propose <telemetri.jsonl> [--root R] [--tak 1] [--min 3] [--out D]
    python governance/skill_curator.py retire <SKILL.md> --regel-id ID --korning REF [--orsak TEXT] [--out D]
    python governance/skill_curator.py overhead <matningar.jsonl> [--root R] [--min-vinst 0.2] [--foljd 0.5] [--out D]

Alla tre skriver bara förslag (status `proposed`) i proposals/. Ingen körning
skriver i SKILL.md. Tillägg, ersättning och avveckling passerar samma
mänskliga grind: en människa för in eller stryker regeln och fyller i
`granskad_av`.

Tak: en skill får högst `--tak` kontrollregler. Ett nytt förslag till en skill
som redan är vid taket blir `ersätt`, inte `lägg till`. Regler som mätningar
visar redan följs eller ignoreras blir `stryk` respektive `ersätt`
(arXiv:2610.04832 §6.1.2).
"""
from __future__ import annotations

import argparse
import hashlib
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
    status: str  # OK | PROSE_ONLY | TOKEN_ONLY | UNREVIEWED
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


def rule_sections(text: str) -> list[tuple[str, dict[str, list[str]]]]:
    """Alla Kontrollregel-sektioner som (sektionstext, fält)."""
    out = []
    for m in SECTION_RE.finditer(text):
        rest = text[m.end():]
        nxt = NEXT_SECTION_RE.search(rest)
        end = m.end() + (nxt.start() if nxt else len(rest))
        out.append((text[m.start():end].rstrip() + "\n", parse_rule_section(text[m.start():end]) or {}))
    return out


def find_skill(root: Path, name: str) -> Path | None:
    for p in root.rglob("*"):
        if p.is_file() and p.name.lower() == "skill.md" and p.parent.name == name:
            return p
    return None


def _sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _guard_out(out: Path) -> None:
    """Förslag får aldrig hamna i en skill-katalog (ingen skrivning i skills)."""
    for d in [out.resolve(), *out.resolve().parents]:
        try:
            has_skill = d.is_dir() and any(c.is_file() and c.name.lower() == "skill.md" for c in d.iterdir())
        except PermissionError:
            continue
        if has_skill:
            raise SystemExit(f"FEL: --out {out} ligger i skill-katalogen {d}; förslag skrivs bara utanför skills")


def write_proposal(out: Path, slug: str, header: dict[str, str], body: str) -> Path | None:
    _guard_out(out)
    out.mkdir(parents=True, exist_ok=True)
    slug = re.sub(r"[^\w-]+", "-", slug)[:80].strip("-")
    target = out / f"{date.today().isoformat()}_{slug}.md"
    if target.exists():
        return None
    head = "".join(f"{k}: {v}\n" for k, v in {"status": "proposed", **header}.items())
    target.write_text(f"---\n{head}---\n{body}", encoding="utf-8")
    print(f"förslag: {target}")
    return target


def retire_body(skill_md: Path, section: str, rule_id: str, korning: str, orsak: str) -> str:
    return (
        f"## Avveckling av {rule_id} (FÖRSLAG – ej genomförd)\n"
        f"- skill: `{skill_md}`\n"
        f"- regel: `{rule_id}`\n"
        f"- motiverande körning: `{korning}`\n"
        f"- orsak: {orsak}\n"
        f"- granskad_av: <tomt tills en människa godkänt>\n\n"
        f"### Återställning\n"
        f"Vid avslag ändras ingenting; regeln står kvar. Om strykningen redan är genomförd och ska ångras "
        f"återinförs sektionen nedan ordagrant (sha256 `{_sha(section)}`, "
        f"SKILL.md vid förslaget sha256 `{_sha(skill_md.read_text(encoding='utf-8'))}`).\n\n"
        f"```markdown\n{section}```\n"
    )


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
    if not fields.get("regel"):
        # Att formulera regeln ger mer än att bara nämna kommandot/sökvägen
        # (arXiv:2610.04832 §5.1.2: +0.15 utöver enbart token).
        res.status = "TOKEN_ONLY"
        res.warnings.append("kommando/sökväg utan formulerad regel (regel:)")
        return res
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
    if args.strict and any(counts[k] for k in ("PROSE_ONLY", "TOKEN_ONLY", "UNREVIEWED")):
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
    root = Path(args.root) if args.root else None
    written = 0
    for (skill, kind, value), n in sorted(counter.items()):
        if n < args.min:
            continue
        label = "kommando" if kind == "kommando" else "sökväg"
        skill_md = find_skill(root, skill) if root else None
        existing = rule_sections(skill_md.read_text(encoding="utf-8")) if skill_md else []
        header = {"skill": skill, "kalla": "meta-agent", "underlag": f"{n} granskade händelser"}
        restore = ""
        if root is None or skill_md is None:
            header["typ"] = "lägg till"
            header["tak"] = "okontrollerat (skill ej hittad under --root)"
            print(f"VARNING: tak okontrollerat för {skill}")
        elif len(existing) >= args.tak:
            ids = [(f.get("id") or ["<utan id>"])[0] for _, f in existing]
            header["typ"] = "ersätt"
            header["ersatter"] = ", ".join(ids)
            header["tak"] = f"TAK: {len(existing)} av {args.tak} regler; ny regel måste ersätta, inte läggas till"
            restore = ("\n### Återställning\nVid avslag står befintliga regler kvar. Ersatt text, ordagrant:\n\n"
                       + "".join(f"```markdown\n{sec}```\n" for sec, _ in existing))
            print(f"TAK: {skill} har redan {len(existing)} regel/regler – förslaget blir ersätt")
        else:
            header["typ"] = "lägg till"
            header["tak"] = f"{len(existing)} av {args.tak}"
        body = (
            f"## Kontrollregel (FÖRSLAG – ej införd)\n"
            f"- id: <sätts av granskare>\n"
            f"- regel: <formuleras av granskare>\n"
            f"- {label}: `{value}`\n"
            f"- källa: meta-agent\n"
            f"- granskad_av: <tomt tills en människa godkänt>\n" + restore
        )
        if write_proposal(out, f"{skill}-{kind}-{value}", header, body):
            written += 1
    print(f"{written} förslag skrivna till {out} (inga SKILL.md ändrade)")
    return 0


def cmd_retire(args: argparse.Namespace) -> int:
    """Avveckling som egen operation: pekar på regeln, körningen och återställningen."""
    skill_md = Path(args.skill_md)
    for sec, f in rule_sections(skill_md.read_text(encoding="utf-8")):
        if (f.get("id") or [None])[0] == args.regel_id:
            header = {"typ": "avveckling", "skill": str(skill_md), "regel_id": args.regel_id, "korning": args.korning}
            write_proposal(Path(args.out), f"avveckling-{skill_md.parent.name}-{args.regel_id}", header,
                           retire_body(skill_md, sec, args.regel_id, args.korning, args.orsak))
            print("inga SKILL.md ändrade")
            return 0
    print(f"FEL: regel-id {args.regel_id} finns inte i {skill_md}", file=sys.stderr)
    return 2


def classify_pairs(rows: list[dict], min_gain: float, followed: float) -> dict[tuple[str, str], dict]:
    """Klassa regel–modell-par enligt arXiv:2610.04832 §6.1.2.

    Par utan vinst (med − utan < min_gain) är overhead. En regel flaggas när
    minst hälften av modellerna klassar den som overhead. Medelföljsamhet utan
    regeln >= followed: redan följd (pröva borttagning). Annars: verkningslös
    (skriv om).
    """
    by_rule: dict[tuple[str, str], list[dict]] = {}
    for r in rows:
        by_rule.setdefault((r["skill"], r["regel_id"]), []).append(r)
    result = {}
    for key, rs in by_rule.items():
        over = [r for r in rs if r["foljsamhet_med"] - r["foljsamhet_utan"] < min_gain]
        if not rs or len(over) * 2 < len(rs):
            continue
        mean_utan = sum(r["foljsamhet_utan"] for r in rs) / len(rs)
        result[key] = {"klass": "redan_foljd" if mean_utan >= followed else "verkningslos",
                       "overhead": len(over), "modeller": len(rs), "medel_utan": round(mean_utan, 3)}
    return result


def cmd_overhead(args: argparse.Namespace) -> int:
    rows = [json.loads(l) for l in Path(args.matningar).read_text(encoding="utf-8").splitlines() if l.strip()]
    flagged = classify_pairs(rows, args.min_vinst, args.foljd)
    root = Path(args.root) if args.root else None
    for (skill, rid), c in sorted(flagged.items()):
        korning = f"{args.matningar} ({c['overhead']}/{c['modeller']} modeller utan vinst, medel utan regel {c['medel_utan']})"
        typ, orsak = (("stryk", "redan följd utan regeln – pröva borttagning kontrollerat innan strykning")
                      if c["klass"] == "redan_foljd" else
                      ("ersätt", "verkningslös – ignoreras med och utan regeln; skriv om"))
        print(f"[{c['klass'].upper()}] {skill}/{rid}: {c['overhead']}/{c['modeller']} modeller → {typ}")
        skill_md = find_skill(root, skill) if root else None
        sec = next((s for s, f in rule_sections(skill_md.read_text(encoding="utf-8"))
                    if (f.get("id") or [None])[0] == rid), None) if skill_md else None
        header = {"typ": typ, "skill": skill, "regel_id": rid, "korning": korning, "kalla": "meta-agent"}
        if sec is None:
            body = (f"## {typ.capitalize()} {rid} (FÖRSLAG)\n- orsak: {orsak}\n- motiverande körning: `{korning}`\n"
                    f"- återställning: regeltexten hittades inte under --root; hämta den innan beslut\n"
                    f"- granskad_av: <tomt tills en människa godkänt>\n")
        else:
            body = retire_body(skill_md, sec, rid, korning, orsak)
            if typ == "ersätt":
                body = body.replace("## Avveckling av", "## Ersättning av", 1) + "\n### Ny formulering\n<skrivs av granskare>\n"
        write_proposal(Path(args.out), f"{typ}-{skill}-{rid}", header, body)
    print(f"{len(flagged)} regler flaggade (inga SKILL.md ändrade)")
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
    p.add_argument("--root")
    p.add_argument("--tak", type=int, default=1)
    p.add_argument("--out", default=str(Path(__file__).parent / "proposals"))
    p.set_defaults(func=cmd_propose)
    r = sub.add_parser("retire")
    r.add_argument("skill_md")
    r.add_argument("--regel-id", required=True)
    r.add_argument("--korning", required=True)
    r.add_argument("--orsak", default="<anges av förslagsställaren>")
    r.add_argument("--out", default=str(Path(__file__).parent / "proposals"))
    r.set_defaults(func=cmd_retire)
    o = sub.add_parser("overhead")
    o.add_argument("matningar")
    o.add_argument("--root")
    o.add_argument("--min-vinst", type=float, default=0.2)
    o.add_argument("--foljd", type=float, default=0.5)
    o.add_argument("--out", default=str(Path(__file__).parent / "proposals"))
    o.set_defaults(func=cmd_overhead)
    args = ap.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
