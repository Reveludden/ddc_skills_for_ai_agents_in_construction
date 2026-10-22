import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import findings_guard as fg  # noqa: E402

EXAMPLES = Path(__file__).resolve().parents[1] / "examples"


def confirmed(**kw):
    f = {
        "id": "F-1", "pastaende": "p", "utfall": "bekraftad", "hittad_av": "huvudsession",
        "verifierad_av": "verifierare-1", "betydelse": "avgorande", "atgard": "a",
        "kallspar": [{"kalla": "k", "stalle": "s", "citat": "c"}],
    }
    f.update(kw)
    return f


class FindingsGuardTest(unittest.TestCase):
    def _errs(self, fynd, base=Path(".")):
        return fg.validate(fynd, base)[0]

    def test_example_holds(self):
        fynd = json.loads((EXAMPLES / "fynd_exempel.json").read_text(encoding="utf-8"))
        self.assertEqual(fg.validate(fynd, EXAMPLES), ([], []))

    def test_finder_cannot_verify(self):
        errs = self._errs([confirmed(verifierad_av=" Huvudsession ")])
        self.assertTrue(any("oberoende" in e for e in errs))
        avv = {"id": "A", "pastaende": "p", "utfall": "avvisad", "hittad_av": "x", "verifierad_av": "X", "skal": "s"}
        self.assertTrue(any("oberoende" in e for e in self._errs([avv])))

    def test_confirmed_needs_trace_and_valid_weight(self):
        self.assertTrue(any("kallspar" in e for e in self._errs([confirmed(kallspar=[])])))
        self.assertTrue(any("saknar citat" in e for e in self._errs([confirmed(kallspar=[{"kalla": "k", "stalle": "s"}])])))
        self.assertTrue(any("okänd betydelse" in e for e in self._errs([confirmed(betydelse="hög")])))

    def test_unverified_has_exact_fact_and_no_weight(self):
        nv = {"id": "N", "pastaende": "p", "utfall": "behover_verifiering", "hittad_av": "x"}
        errs = self._errs([nv])
        self.assertTrue(any("saknat_faktum" in e for e in errs))
        self.assertTrue(any("verifieringsplan" in e for e in errs))
        nv.update(saknat_faktum="f", verifieringsplan="v", betydelse="begransad")
        self.assertEqual(self._errs([nv]), ["N: behover_verifiering får inte ha betydelse"])

    def test_note_requires_existing_control(self):
        note = {"id": "N", "pastaende": "p", "utfall": "notering", "hittad_av": "x"}
        self.assertTrue(any("befintligt_skydd" in e for e in self._errs([note])))

    def test_unknown_outcome_and_duplicate_id(self):
        errs = self._errs([confirmed(), confirmed(), {"id": "Z", "pastaende": "p", "utfall": "trolig", "hittad_av": "x"}])
        self.assertTrue(any("flera gånger" in e for e in errs))
        self.assertTrue(any("okänt utfall" in e for e in errs))

    def test_quote_checked_against_file(self):
        with tempfile.TemporaryDirectory() as t:
            base = Path(t)
            (base / "u.txt").write_text("Anspråk ska framställas\nskriftligen.", encoding="utf-8")
            ok = confirmed(kallspar=[{"kalla": "k", "stalle": "s", "citat": "framställas skriftligen.", "fil": "u.txt"}])
            self.assertEqual(fg.validate([ok], base), ([], []))
            bad = confirmed(kallspar=[{"kalla": "k", "stalle": "s", "citat": "muntligen", "fil": "u.txt"}])
            self.assertTrue(any("ordagrant" in e for e in self._errs([bad], base)))
            missing = confirmed(kallspar=[{"kalla": "k", "stalle": "s", "citat": "c", "fil": "saknas.pdf"}])
            errs, warns = fg.validate([missing], base)
            self.assertEqual(errs, [])
            self.assertTrue(any("ej maskinkontrollerat" in w for w in warns))

    def test_report_exit_codes(self):
        with tempfile.TemporaryDirectory() as t:
            p = Path(t) / "f.json"
            p.write_text(json.dumps([confirmed()]), encoding="utf-8")
            self.assertEqual(fg.main(["rapport", "--fynd", str(p)]), 0)
            self.assertEqual(fg.main(["rapport", "--fynd", str(p), "--granskning"]), 1)
            p.write_text(json.dumps([confirmed(betydelse="begransad")]), encoding="utf-8")
            self.assertEqual(fg.main(["rapport", "--fynd", str(p), "--granskning"]), 0)
            p.write_text(json.dumps([confirmed(verifierad_av="huvudsession")]), encoding="utf-8")
            self.assertEqual(fg.main(["check", "--fynd", str(p)]), 2)
            self.assertEqual(fg.main(["rapport", "--fynd", str(p)]), 2)


if __name__ == "__main__":
    unittest.main()
