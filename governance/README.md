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
- **Ersättning måste anges uttryckligen.** Ett nytt bevis kan ange `"ersatter": ["E-..."]`. Det gamla beviset får då status `ERSATT`, finns kvar som historik och återanvänds inte. Ett senare bevis utan `ersatter` ersätter ingenting.
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

**Xu m.fl., *MemTrace: State-Consistent Memory for Long-Horizon Coding Agents*.** Kontrollerat mot artikeltexten. Att den har arXiv-nummer 2610.04838 bygger på användarens uppgift.
- **Samma princip som här:**
  - Spår ändras aldrig efter att de skrivits (§3.1).
  - Ett spår återanvänds bara om det fortfarande stämmer med aktuellt tillstånd och inte är ersatt (ekv. 2).
  - Om förutsättningarna har ändrats, eller inte går att kontrollera, återanvänds spåret inte automatiskt.
- **Ersättning kräver en uttrycklig relation.** Tidsordning räcker inte. Det är därifrån fältet `ersatter` kommer.
- **Lagring räcker inte.** Med bara lagrade spår, utan relationerna mellan dem, blev resultatet på DeepSWE 32,1 % mot 35,4 % utan något minne alls. Med relationerna blev det 44,2 %, och med hela systemet 56,6 % (tab. 3).
- **Mycket bevis blir inaktuellt.** 57 % av spåren fick en senare ändring i någon fil de var kopplade till. Efter ungefär 1 000 händelsesteg var sannolikheten att filerna var oförändrade ungefär 0,50 (§4.3).
- **Begränsningar:**
  - En enda modell och bara kodningsuppgifter.
  - Längre körtid i vissa fall, till exempel 30 → 82 minuter per uppgift på SWE-EVO med Codex CLI (tab. 6).
  - Antalet ogiltigförklaringar mäter vad ogiltigförklaringsregeln utlöser, inte verifierade fel (bil. A.3).

**Motposition: Ye m.fl., *Meta Context Engineering via Agentic Skill Evolution* (ICML 2026, PMLR 306).** Hela artikeln är läst.
- **Metod:** en meta-agent ändrar skills på egen hand. Den utgår från historiken av skills, körningar och utvärderingar, och optimerar mot poäng på ett valideringsset (ekv. 3). Resultatet blev 5,6–53,8 % relativ förbättring mot de bästa befintliga metoderna, i snitt 16,9 %.
- **Alla fem domäner har ett facit:** FiNER (finans), USPTO-50k (kemi), Symptom2Disease (medicin), LawBench (juridik) och AEGIS2 (AI-säkerhet).
  - Juridiken gäller bara deluppgiften att förutsäga brottsrubricering i kinesisk straffrätt, mätt i micro-F1. Det är en klassificering, inte en bedömning (bil. A).
- **Begränsningar enligt författarna:**
  - Fördelen gäller kunskapsinhämtning och mönstermatchning, och kanske inte resonemangstunga uppgifter.
  - Metoden kan ha svårt med långa, komplexa förlopp (§5).
  - Effekten av att skills utvecklas, utöver en fast skill, är liten. Den mättes bara på FiNER: 75 mot 71 % offline (tab. 3).
  - Bara delmängder av data användes, och studien bygger på en huvudmodell (DeepSeek V3.1).
- **Följd för SFV:** juridiska bedömningar, som preskription, ÄTA eller avtalstolkning, är resonemangstunga och saknar facit som kan räknas fram. Därför står spärren kvar: meta-agenten föreslår men skriver inte in. Förslagen kan rangordnas efter historiken, men en människa avgör. Autonom utveckling kan prövas där facit finns, till exempel i scan2bim-mätningar.

**Chen, Liang och Xie, *TagGraph: Tag-Augmented Graphs for Graph Retrieval of Agent Persistent Histories* (arXiv:2609.38353v2, workshoppapper vid COLM 2026).** Kontrollerat mot artikeltexten. Artikeln gäller idégrafen, som ännu inte är byggd.
- **Ingen grafvariant vinner överallt.** På LongMemEval-S var den bästa grafvarianten 0,844 MRR, BM25 på samma anteckningar 0,867 och OpenClaw 0,880. På ATANT Core var lokal graftraversering bäst, ungefär 0,70, före BM25 (ungefär 0,64) och spridning med PageRank (ungefär 0,55). I stressrundorna ledde BM25 (tab. 1).
- **Det mesta av styrkan är lexikal.** Att ta bort den direkta lexikala vägen till filerna (TF-IDF) kostade 0,119 MRR, medan själva spridningen bidrog med 0,020. På ATANT Core gav det +0,158 att ta bort spridningen (tab. 3).
- **Taggarna avgör.** Valet av extraktionsmodell gav 0,290 MRR i skillnad. Det är mer än alla förbättringar av traverseringen tillsammans, som gav 0,132. 651 av 658 missade rätta anteckningar saknade en användbar tagg med minst en extraktionsmodell (§5.3, §5.5).
- **Begränsningar:**
  - Bara rangordning mäts, svarskvaliteten kontrolleras bara översiktligt.
  - Små extraktionsmodeller användes.
  - Orsaken till att spridningen gav sämre resultat är inte fastställd.
- **Följd för SFV:** idégrafen väntar tills frågorna finns. När den byggs gäller tre villkor:
  - Den ska jämföras mot BM25 på samma anteckningar och bara behållas om den slår BM25.
  - Taggarna ska komma ur ett fast ordförråd som inte går att avvika från, till exempel AB 04-kapitel och paragraf, diarienummer och fastighetsbeteckning, och inte bara föreslås i en prompt.
  - Lokal traversering, där vägen till svaret går att följa, ska väljas före spridning, eftersom spridning med PageRank är svårare att spåra (§6.3).

**Övriga källor är inte verifierade:** arXiv:2607.18235 och 2608.03392 samt LeadDev 2026-10-05. Idégrafen och flera parallella körningar är medvetet inte byggda.
