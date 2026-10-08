# Styrning av skills och bevis

Två tillägg. Befintliga skills och verktyg ändras inte. Allt är Python-standardbibliotek.

## 1. Kontrollregel per skill och skill-curator

Varje `SKILL.md` ska ha en sektion som pekar på något som går att kontrollera, alltså ett kommando eller en sökväg. Prosa räcker inte.

```markdown
## Kontrollregel
- id: SFV-ATA-01
- regel: Preskription kontrolleras innan anspråket bedöms i sak.
- kommando: `python governance/evidence_guard.py check --ledger bevis.jsonl --state aktuellt.json`
- sökväg: `mallar/ata_svar.docx`
- granskad_av: Bengt Skoglund
- granskad: 2026-10-08
- källa: människa
```

Bara text inom backticks räknas som kommando eller sökväg. Engelska nycklar (`command`, `path`, `reviewed_by`) godtas också.

```bash
python governance/skill_curator.py scan <rot> [--json rapport.json] [--strict]
```

| Status | Betydelse |
|---|---|
| `PROSE_ONLY` | Sektionen saknas, eller den saknar kommando och sökväg |
| `UNREVIEWED` | Kommando eller sökväg finns, men ingen `granskad_av` |
| `OK` | Kommando eller sökväg finns och en människa har granskat |

Varningar visas när en sökväg saknas eller ett programnamn inte finns i PATH. Curatorn kör aldrig kommandona. `--strict` ger exitkod 1 om någon skill har status `PROSE_ONLY` eller `UNREVIEWED`. Curatorn fungerar på vilken rot som helst, till exempel `N:\SKILLS`.

### Meta-agenten föreslår men skriver inte in

```bash
python governance/skill_curator.py propose telemetri.jsonl --min 3
```

- Underlaget är bara händelser vars utfall en människa har granskat (`human_accepted`, `human_corrected`). Det som agenten gjort på egen hand ignoreras.
- Ett kommando eller en sökväg som förekommer minst `--min` gånger blir ett förslag i `governance/proposals/` med `status: proposed`.
- `SKILL.md` ändras aldrig. En regel räknas först när en människa har fört in den och fyllt i `granskad_av`.

## 2. Styrningsblock efter leverans: ogiltigförklaring av bevis

Ett bevis är ett påstående som ingår i en leverans och är bundet till ett eller flera beroenden:

| Beroende | Exempel på fält |
|---|---|
| `avtal` | `fil` och `sha256` (räknas om från filen) |
| `lydelse` | `version` eller `sha256` |
| `preskription` | `datum` (passerat datum ger också ogiltigt) |
| `k21_bas` | `period`, `varde` |

```bash
python governance/evidence_guard.py fingerprint avtal/kontrakt.pdf
python governance/evidence_guard.py record --ledger bevis.jsonl --entry post.json
python governance/evidence_guard.py check  --ledger bevis.jsonl --state aktuellt.json [--id E-..] [--append]
python governance/evidence_guard.py block  --ledger bevis.jsonl --state aktuellt.json --id E-..
```

- **Bevisloggen är append-only.** En post ändras aldrig. Med `check --append` skrivs ogiltigförklaringen som en ny post.
- **Ogiltigförklaringen är bestående.** Även om tillståndet återgår krävs ett nytt, omverifierat bevis med nytt id.
- **Fail-closed.** Saknas aktuellt tillstånd eller fil blir status `OKÄNT`, och beviset får då inte återanvändas.
- **`block` skriver styrningsblocket** som läggs sist i leveransen, med status, beroenden och kontrollkommandot.

Exempel finns i `examples/`. Tester:

```bash
python -m unittest discover -s governance/tests
```

## Underlag

Upplägget bygger på användarens sammanfattning av arXiv:2610.04832, 2610.04838 och 2608.03392 samt en artikel i LeadDev 2026-10-05. Källorna är inte verifierade. arXiv gick inte att nå från körmiljön där detta byggdes. Idégrafen och flera parallella körningar (arXiv:2607.18235) är medvetet inte byggda.
