import re
import unittest
from pathlib import Path

AVVISAT = Path(__file__).resolve().parents[1] / "avvisat.md"
ENTRY_RE = re.compile(r"^## (A-\d{2}) .+$", re.MULTILINE)
REQUIRED = ("utfall", "datum", "beslutat_av", "lösning", "skäl", "ändras om")


class AvvisatTest(unittest.TestCase):
    def test_entries_complete(self):
        text = AVVISAT.read_text(encoding="utf-8")
        heads = list(ENTRY_RE.finditer(text))
        self.assertTrue(heads)
        ids = [m.group(1) for m in heads]
        self.assertEqual(len(ids), len(set(ids)), "id förekommer flera gånger")
        self.assertEqual(ids, sorted(ids), "nya poster läggs sist")
        for i, m in enumerate(heads):
            end = heads[i + 1].start() if i + 1 < len(heads) else len(text)
            body = text[m.end():end]
            fields = dict(re.findall(r"^- ([\wåäö ]+): (.+)$", body, re.MULTILINE))
            for k in REQUIRED:
                self.assertTrue(fields.get(k, "").strip(), f"{m.group(1)} saknar {k}")
            self.assertIn(fields["utfall"], ("avvisat", "uppskjutet"), m.group(1))
            self.assertRegex(fields["datum"], r"^\d{4}-\d{2}-\d{2}$")
            for ref in re.findall(r"A-\d{2}", fields.get("ersatter", "")):
                self.assertIn(ref, ids[:i], f"{m.group(1)} ersätter okänd eller senare post {ref}")


if __name__ == "__main__":
    unittest.main()
