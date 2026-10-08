import json
import sys
import tempfile
import unittest
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import evidence_guard as eg  # noqa: E402
import skill_curator as sc  # noqa: E402

PROSE = "---\nname: x\n---\n# X\n\nBara beskrivande text.\n"
RULE_NO_CMD = "# X\n\n## Kontrollregel\n- regel: Var noggrann.\n- granskad_av: BS\n"
RULE_TOKEN_ONLY = "# X\n\n## Kontrollregel\n- id: R1\n- kommando: `python3 -V`\n- granskad_av: BS\n"
RULE_UNREVIEWED = "# X\n\n## Kontrollregel\n- id: R1\n- regel: Kör versionskontroll.\n- kommando: `python3 -V`\n"
RULE_OK = (
    "# X\n\n## Kontrollregel\n- id: R1\n- regel: Fil måste finnas.\n- sökväg: `data.txt`\n"
    "- kommando: `python3 -V`\n- granskad_av: Bengt Skoglund\n- granskad: 2026-10-08\n\n## Nästa\n- kommando: `ignoreras`\n"
)


class CuratorTest(unittest.TestCase):
    def _skill(self, root: Path, name: str, text: str) -> Path:
        d = root / name
        d.mkdir()
        (d / "SKILL.md").write_text(text, encoding="utf-8")
        return d

    def test_statuses(self):
        with tempfile.TemporaryDirectory() as t:
            root = Path(t)
            self._skill(root, "prosa", PROSE)
            self._skill(root, "utan_kommando", RULE_NO_CMD)
            self._skill(root, "ogranskad", RULE_UNREVIEWED)
            self._skill(root, "bara_token", RULE_TOKEN_ONLY)
            ok = self._skill(root, "ok", RULE_OK)
            (ok / "data.txt").write_text("x")
            res = {Path(r.path).parent.name: r for r in sc.scan(root)}
            self.assertEqual(res["prosa"].status, "PROSE_ONLY")
            self.assertEqual(res["utan_kommando"].status, "PROSE_ONLY")
            self.assertEqual(res["ogranskad"].status, "UNREVIEWED")
            self.assertEqual(res["bara_token"].status, "TOKEN_ONLY")
            self.assertEqual(res["ok"].status, "OK")
            self.assertEqual(res["ok"].warnings, [])
            self.assertNotIn("ignoreras", res["ok"].kommando)

    def test_missing_path_warns(self):
        with tempfile.TemporaryDirectory() as t:
            self._skill(Path(t), "ok", RULE_OK)
            (r,) = sc.scan(Path(t))
            self.assertEqual(r.status, "OK")
            self.assertTrue(any("saknas" in w for w in r.warnings))

    def test_strict_exit(self):
        with tempfile.TemporaryDirectory() as t:
            self._skill(Path(t), "prosa", PROSE)
            self.assertEqual(sc.main(["scan", t, "--strict"]), 1)
            self.assertEqual(sc.main(["scan", t]), 0)

    def test_propose_never_touches_skill(self):
        with tempfile.TemporaryDirectory() as t:
            root = Path(t)
            d = self._skill(root, "ata", PROSE)
            tel = root / "tel.jsonl"
            evs = [{"skill": "ata", "kommando": "python x.py --k21", "utfall": "human_accepted"}] * 3
            evs += [{"skill": "ata", "kommando": "rm -rf /", "utfall": "agent_only"}] * 5
            tel.write_text("\n".join(json.dumps(e) for e in evs))
            out = root / "prop"
            sc.main(["propose", str(tel), "--min", "3", "--out", str(out)])
            files = list(out.glob("*.md"))
            self.assertEqual(len(files), 1)
            body = files[0].read_text(encoding="utf-8")
            self.assertIn("status: proposed", body)
            self.assertNotIn("rm -rf", body)
            self.assertEqual((d / "SKILL.md").read_text(encoding="utf-8"), PROSE)


class CuratorProposalTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name) / "skills"
        self.out = Path(self.tmp.name) / "prop"
        d = self.root / "ata"
        d.mkdir(parents=True)
        self.skill = d / "SKILL.md"
        self.skill.write_text(RULE_OK, encoding="utf-8")
        (self.root / "tom").mkdir()
        (self.root / "tom" / "SKILL.md").write_text(PROSE, encoding="utf-8")

    def tearDown(self):
        self.tmp.cleanup()

    def _props(self):
        return {f.name: f.read_text(encoding="utf-8") for f in self.out.glob("*.md")}

    def test_retire_is_own_operation_and_restorable(self):
        before = self.skill.read_bytes()
        self.assertEqual(sc.main(["retire", str(self.skill), "--regel-id", "R1",
                                  "--korning", "run-42", "--out", str(self.out)]), 0)
        (body,) = self._props().values()
        self.assertIn("typ: avveckling", body)
        self.assertIn("run-42", body)
        self.assertIn("- sökväg: `data.txt`", body)          # regeltexten ordagrant
        self.assertIn("Vid avslag ändras ingenting", body)
        self.assertEqual(self.skill.read_bytes(), before)
        self.assertEqual(sc.main(["retire", str(self.skill), "--regel-id", "X9",
                                  "--korning", "r", "--out", str(self.out)]), 2)

    def test_no_proposal_inside_skill_dir(self):
        with self.assertRaises(SystemExit):
            sc.main(["retire", str(self.skill), "--regel-id", "R1", "--korning", "r",
                     "--out", str(self.skill.parent / "prop")])

    def test_cap_turns_add_into_replace(self):
        tel = Path(self.tmp.name) / "tel.jsonl"
        evs = [{"skill": s, "kommando": "python k21.py", "utfall": "human_accepted"}
               for s in ("ata", "tom") for _ in range(3)]
        tel.write_text("\n".join(json.dumps(e) for e in evs))
        sc.main(["propose", str(tel), "--root", str(self.root), "--out", str(self.out)])
        props = self._props()
        ata = next(v for k, v in props.items() if "ata" in k)
        tom = next(v for k, v in props.items() if "tom" in k)
        self.assertIn("typ: ersätt", ata)
        self.assertIn("ersatter: R1", ata)
        self.assertIn("TAK:", ata)
        self.assertIn("- sökväg: `data.txt`", ata)           # ersatt text för återställning
        self.assertIn("typ: lägg till", tom)
        self.assertEqual(self.skill.read_text(encoding="utf-8"), RULE_OK)

    def test_cap_unchecked_without_root(self):
        tel = Path(self.tmp.name) / "tel.jsonl"
        tel.write_text("\n".join(json.dumps({"skill": "ata", "sokvag": "x.md", "utfall": "human_corrected"})
                                 for _ in range(3)))
        sc.main(["propose", str(tel), "--out", str(self.out)])
        (body,) = self._props().values()
        self.assertIn("tak: okontrollerat", body)

    def test_overhead_followed_vs_ineffective(self):
        def row(rid, m, utan, med):
            return {"skill": "ata", "regel_id": rid, "modell": m, "foljsamhet_utan": utan, "foljsamhet_med": med}
        rows = [row("R1", "a", 0.8, 0.8), row("R1", "b", 0.6, 0.8),      # redan följd
                row("R2", "a", 0.0, 0.0), row("R2", "b", 0.2, 0.2),      # verkningslös
                row("R3", "a", 0.0, 0.6), row("R3", "b", 0.2, 0.8),      # effektiv
                row("R4", "a", 0.0, 0.6), row("R4", "b", 0.2, 0.2)]      # hälften overhead
        c = sc.classify_pairs(rows, 0.2, 0.5)
        self.assertEqual(c[("ata", "R1")]["klass"], "redan_foljd")
        self.assertEqual(c[("ata", "R2")]["klass"], "verkningslos")
        self.assertNotIn(("ata", "R3"), c)
        self.assertIn(("ata", "R4"), c)
        m = Path(self.tmp.name) / "m.jsonl"
        m.write_text("\n".join(json.dumps(r) for r in rows))
        before = self.skill.read_bytes()
        sc.main(["overhead", str(m), "--root", str(self.root), "--out", str(self.out)])
        props = self._props()
        r1 = next(v for k, v in props.items() if "R1" in k)
        r2 = next(v for k, v in props.items() if "R2" in k)
        self.assertIn("typ: stryk", r1)
        self.assertIn("- sökväg: `data.txt`", r1)            # återställningstext
        self.assertIn("typ: ersätt", r2)
        self.assertFalse(any("R3" in k for k in props))
        self.assertEqual(self.skill.read_bytes(), before)


class EvidenceGuardTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)
        self.avtal = self.dir / "kontrakt.txt"
        self.avtal.write_text("kontrakt v1")
        self.ledger = self.dir / "bevis.jsonl"
        self.entry = {
            "id": "E-1", "leverans": "PM ÄTA 12", "datum": "2026-10-01", "pastaende": "Anspråket är preskriberat.",
            "beroenden": {
                "avtal": {"ref": "Kontrakt", "fil": "kontrakt.txt", "sha256": eg.sha256_file(self.avtal)},
                "lydelse": {"ref": "AB 04 kap 6 § 19", "version": "AB 04"},
                "preskription": {"ref": "Slutbesiktning", "datum": "2027-03-01"},
                "k21_bas": {"ref": "K21 projekt", "period": "2025-03", "varde": "100.0"},
            },
        }
        self.state = {
            "lydelse": {"AB 04 kap 6 § 19": {"version": "AB 04"}},
            "preskription": {"Slutbesiktning": {"datum": "2027-03-01"}},
            "k21_bas": {"K21 projekt": {"period": "2025-03", "varde": "100.0"}},
        }
        p = self.dir / "e.json"
        p.write_text(json.dumps(self.entry, ensure_ascii=False))
        self.assertEqual(eg.main(["record", "--ledger", str(self.ledger), "--entry", str(p)]), 0)

    def tearDown(self):
        self.tmp.cleanup()

    def _eval(self, today=date(2026, 10, 8)):
        (rec,) = [r for r in eg.read_ledger(self.ledger) if r["typ"] == "bevis"]
        return eg.evaluate(rec, self.state, self.dir, today)

    def test_valid(self):
        self.assertEqual(self._eval()[0], "GILTIGT")

    def test_each_kind_moves(self):
        for kind, mutate in [
            ("avtal", lambda: self.avtal.write_text("kontrakt v2")),
            ("lydelse", lambda: self.state["lydelse"]["AB 04 kap 6 § 19"].update(version="AB 27")),
            ("preskription", lambda: self.state["preskription"]["Slutbesiktning"].update(datum="2027-09-01")),
            ("k21_bas", lambda: self.state["k21_bas"]["K21 projekt"].update(varde="104.2")),
        ]:
            with self.subTest(kind=kind):
                self.tearDown()
                self.setUp()
                mutate()
                status, reasons = self._eval()
                self.assertEqual(status, "OGILTIGT")
                self.assertTrue(any(eg.LABEL[kind] in r for r in reasons))

    def test_preskription_passed(self):
        self.assertEqual(self._eval(today=date(2027, 3, 2))[0], "OGILTIGT")

    def test_missing_state_fails_closed(self):
        del self.state["k21_bas"]
        self.assertEqual(self._eval()[0], "OKÄNT")

    def test_invalidation_is_append_only_and_sticky(self):
        sp = self.dir / "s.json"
        self.state["k21_bas"]["K21 projekt"]["varde"] = "104.2"
        sp.write_text(json.dumps(self.state, ensure_ascii=False))
        before = self.ledger.read_text(encoding="utf-8")
        self.assertEqual(eg.main(["check", "--ledger", str(self.ledger), "--state", str(sp),
                                  "--append", "--today", "2026-10-08"]), 1)
        after = self.ledger.read_text(encoding="utf-8")
        self.assertTrue(after.startswith(before))
        self.assertIn("ogiltigforklaring", after)
        # Tillståndet går tillbaka – beviset förblir ogiltigt.
        self.state["k21_bas"]["K21 projekt"]["varde"] = "100.0"
        sp.write_text(json.dumps(self.state, ensure_ascii=False))
        self.assertEqual(eg.main(["check", "--ledger", str(self.ledger), "--state", str(sp),
                                  "--id", "E-1", "--today", "2026-10-08"]), 1)

    def test_supersede_is_explicit(self):
        new = dict(self.entry, id="E-2", ersatter=["E-1"])
        p2 = self.dir / "e2.json"
        p2.write_text(json.dumps(new, ensure_ascii=False))
        self.assertEqual(eg.main(["record", "--ledger", str(self.ledger), "--entry", str(p2)]), 0)
        sp = self.dir / "s.json"
        sp.write_text(json.dumps(self.state, ensure_ascii=False))
        rows = {r["id"]: st for r, st, *_ in eg.current_status(
            eg.read_ledger(self.ledger), self.state, self.dir, date(2026, 10, 8), None)}
        self.assertEqual(rows, {"E-1": "ERSATT", "E-2": "GILTIGT"})
        base = ["check", "--ledger", str(self.ledger), "--state", str(sp), "--today", "2026-10-08"]
        self.assertEqual(eg.main(base), 0)               # översikt: historik fäller inte
        self.assertEqual(eg.main(base + ["--id", "E-1"]), 1)  # återanvändning av ersatt: nej
        # Senare post utan ersatter ersätter inte (tidsordning räcker inte).
        p3 = self.dir / "e3.json"
        p3.write_text(json.dumps(dict(self.entry, id="E-3"), ensure_ascii=False))
        eg.main(["record", "--ledger", str(self.ledger), "--entry", str(p3)])
        self.assertEqual(eg.main(base + ["--id", "E-2"]), 0)

    def test_supersede_unknown_id_rejected(self):
        p2 = self.dir / "e2.json"
        p2.write_text(json.dumps(dict(self.entry, id="E-2", ersatter=["E-99"]), ensure_ascii=False))
        self.assertEqual(eg.main(["record", "--ledger", str(self.ledger), "--entry", str(p2)]), 2)

    def test_duplicate_id_rejected(self):
        p = self.dir / "e.json"
        self.assertEqual(eg.main(["record", "--ledger", str(self.ledger), "--entry", str(p)]), 2)


if __name__ == "__main__":
    unittest.main()
