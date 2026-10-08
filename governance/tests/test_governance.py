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
RULE_UNREVIEWED = "# X\n\n## Kontrollregel\n- id: R1\n- kommando: `python3 -V`\n"
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
            ok = self._skill(root, "ok", RULE_OK)
            (ok / "data.txt").write_text("x")
            res = {Path(r.path).parent.name: r for r in sc.scan(root)}
            self.assertEqual(res["prosa"].status, "PROSE_ONLY")
            self.assertEqual(res["utan_kommando"].status, "PROSE_ONLY")
            self.assertEqual(res["ogranskad"].status, "UNREVIEWED")
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

    def test_duplicate_id_rejected(self):
        p = self.dir / "e.json"
        self.assertEqual(eg.main(["record", "--ledger", str(self.ledger), "--entry", str(p)]), 2)


if __name__ == "__main__":
    unittest.main()
