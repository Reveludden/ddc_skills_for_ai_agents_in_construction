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
| `TOKEN_ONLY` | Kommando eller sökväg finns, men ingen formulerad `regel:` |
| `UNREVIEWED` | Regel med kommando eller sökväg finns, men ingen `granskad_av` |
| `OK` | Formulerad regel med kommando eller sökväg, granskad av en människa |

Varningar visas när en sökväg saknas eller ett programnamn inte finns i PATH. Curatorn kör aldrig kommandona. `--strict` ger exitkod 1 om någon skill har annan status än `OK`. Curatorn fungerar på vilken rot som helst, till exempel `N:\SKILLS`.

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

**Wang m.fl., *Agent Skill Evolution: How Revisions Affect Coding Agents* (okt 2026).** Siffrorna nedan är kontrollerade mot artikeltexten. Att texten hör till arXiv:2610.04832 bygger på användarens uppgift.

| Påstående | Artikeln |
|---|---|
| Följsamhet +0,41 | 16 öppna modeller, ett svar (tabell 3). Fem slutna modeller: +0,43 |
| Krävd handling +0,23 | Fyra agenter i sandlåda, spann +0,16 till +0,36 (tabell 4) |
| Korrekt slutresultat +0,10 | Tre agenter, blindbedömt (tabell 5). Sonnet 4.5 ensam: +0,06, ej signifikant |
| Vinsten sitter i kommando eller sökväg | Främst när kommandot eller sökvägen är **ny** för skillen (+0,51 till +0,66). Redan nämnd: +0,08. Att formulera regeln ger +0,15 utöver att bara nämna kommandot eller sökvägen (§5.1.2–5.1.3) |
| Revideringar som bara ändrar prosa | +0,017 (§5) |
| Hela skill-kroppen kostar +50 % | Genomsnitt per agentkörning, spann 37–57 % (§6.2.2). Själva revideringen ger ingen mätbar kostnad per körning |
| Laddning vid behov behåller ungefär halva vinsten | 51 % i genomsnitt (KI 28–75 %). Öppna modeller ungefär 38 %. Sonnet 4.5: hela vinsten (+0,19 i båda lägena) (§5.2.4) |

**Hur detta styr verktyget:**
- **`TOKEN_ONLY`:** att bara nämna kommandot eller sökvägen räcker inte. Regeln ska vara formulerad.
- **Strykningar är också en ändring.** Att ta bort en regel sänker följsamheten med ungefär tre fjärdedelar av vad det gav att lägga till den (§5.1.4). Därför går strykningar genom samma mänskliga granskning.
- **En regel kan kosta utan att göra nytta.** Var femte kombination av regel och modell gav fler tokens utan mätbar vinst (§6.1.2).

**Begränsningar i artikeln som påverkar SFV-skills:**
- Bara regler som kan kontrolleras mekaniskt med en strängjämförelse är testade. Förbud, villkorade regler och behörighetsspärrar är underrepresenterade, och bara 17 % av de möjliga reglerna kom med.
- Modellerna körde utan resonemangsläge. Uppgifterna gällde kodning.
- Effekterna gäller förfrågningar där regeln faktiskt behövs. Det var ungefär 25 % av senare commits (§7.2).

**Övriga källor är inte verifierade:** arXiv:2607.18235, 2610.04838 och 2608.03392 samt LeadDev 2026-10-05. Idégrafen och flera parallella körningar är medvetet inte byggda.
