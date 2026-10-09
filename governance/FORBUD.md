# Gällande förbud i SFV-stacken

Samlade förbud och gränser för arbete med stacken. Filen lägger inte till nya regler. Varje punkt är beslutad av Bengt Skoglund under arbetet med PR #1 och efter sammanslagningen. Spalten **Spärr** anger om förbudet hålls av kod och test, eller bara av den här texten. Se även [README](README.md).

- **Kod** betyder att ett kommando vägrar eller att en status sätts, och att ett test täcker det.
- **Text** betyder att ingen kod hindrar överträdelse, så den som arbetar i stacken måste läsa och följa punkten.

Ändring av ett förbud sker genom Bengts beslut och en granskad ändring av den här filen. Det sker aldrig i samma körning som förbudet berör.

## 1. Stacken

| # | Förbud | Spärr |
|---|---|---|
| 1.1 | Bygg inte om stacken. Inget nytt kommando utan beslut. | Text |
| 1.2 | Ingen sammanslagning av skills. | Text |
| 1.3 | Ingen ny modell. | Text |
| 1.4 | Inga flera parallella körningar. | Text |
| 1.5 | Ingen sammanslagning av PR i en körning där Bengt har sagt att den inte ska slås ihop. | Text |

## 2. Regler i skills

| # | Förbud | Spärr |
|---|---|---|
| 2.1 | Ingen meta-agent skriver in en regel. Den får bara föreslå regler ur telemetri. | Kod: inget kommando i `skill_curator.py` skriver i en `SKILL.md`. Förslag får status `proposed`. |
| 2.2 | Förslag sparas aldrig i en skill-katalog. Det gäller även `scan --json`. | Kod: `_guard_out` |
| 2.3 | Tillägg, ersättning och strykning passerar samma mänskliga grind (`granskad_av`). Ingen skrivning sker i samma körning som förslaget. | Kod för att förslaget inte skrivs in. Text för själva grinden. |
| 2.4 | `overhead` får föreslå `stryk` eller `ersätt`, men får inte lägga in regeln. | Kod |
| 2.5 | Omkörning efter beslut: en ersatt regel ska ha skillnaden med minus utan ≥ 0,2 hos mer än hälften av modellerna. En struken regel ska ha följsamhet utan regeltext ≥ 0,5, annars återinförs regeln. Ingen verifieringsrad i förslaget. | Text |
| 2.6 | `--tak` är en flagga som är av som standard. Om ett standardvärde krävs är förslaget 3, inte 1. Beslutet är Bengts. | Kod: `default=None` |
| 2.7 | En skill som bara är prosa, eller som har kommando utan formulerad regel, godkänns inte. | Kod: `PROSE_ONLY`, `TOKEN_ONLY` |

## 3. Bevis och leverans

| # | Förbud | Spärr |
|---|---|---|
| 3.1 | Ett bevis återanvänds inte utan `check`. `block` läggs sist i leveransen. | Text för rutinen. Kod för utfallet: exitkod 1. |
| 3.2 | Ett bevis återanvänds inte om avtal, lydelse, preskription eller K21-bas har rört sig, eller om preskriptionsdatumet har passerats. | Kod: `OGILTIGT` |
| 3.3 | Ett bevis återanvänds inte om aktuellt tillstånd, en fil, den åberopade meningen eller lydelsetexten saknas. Det är fail-closed. | Kod: `OKÄNT` |
| 3.4 | En åberopad mening som inte finns i lydelsen ger ingen återanvändning. Att lagrummet finns räcker inte. | Kod: `OGILTIGT` (87dbcd8) |
| 3.5 | En bevispost ändras aldrig. En ogiltigförklaring är bestående och kräver ett nytt bevis med nytt id. | Kod |
| 3.6 | Ingen ersättning genom tidsordning, bara genom uttrycklig `ersatter`. Ett ersatt bevis återanvänds inte. | Kod: `ERSATT` |

## 4. Källor och märkning

| # | Förbud | Spärr |
|---|---|---|
| 4.1 | [V] sätts inte på en träff som saknar den åberopade meningen. | Text. Motsvarande kontroll för bevis finns i 3.4. |
| 4.2 | run-assert-eval förblir [O] i repot. | Text |
| 4.3 | Rättsläge, siffror, datum och versioner gissas inte. Osäkerhet anges i stället. | Text |
| 4.4 | A och B gissas inte och byggs inte. | Text |
| 4.5 | Mätningen av förfallna [VERIFIERA] och ADR med passerat datum byggs inte. Inget datumformat hittas på för den. | Text |

## 5. Idégraf

| # | Förbud | Spärr |
|---|---|---|
| 5.1 | Ingen idégraf förrän frågorna finns. | Text |
| 5.2 | Om en idégraf byggs gäller tre grindar. Den ska slå den starkaste av originaltextsökning och BM25 på extrakt. Taggarna ska komma ur ett fast ordförråd i koden, och en okänd tagg avvisas. Traverseringen ska vara lokal, utan PageRank. | Text |

## 6. Modell och kostnad

| # | Förbud | Spärr |
|---|---|---|
| 6.1 | Ingen modellväxling vid 300K. Byte sker i en ny session med överlämning av uppgift, fallerande kontroll och relevanta filer. | Text |
| 6.2 | Ingen modellväxling mitt i en PR. | Text |
| 6.3 | $/pass räknas med rätt läspris (cacheläsning): Sonnet 5.5 $0,10/M och Opus 5.5 $0,20/M enligt officiell prislista 2026-10-08. | Text |

## 7. Browser

| # | Förbud | Spärr |
|---|---|---|
| 7.1 | browser-use-sdk och computer-toolset läses inte in i stacken. | Text |
| 7.2 | En slängbrowser prövas bara efter sex steg: URL-policy, request-avlyssning, egress, instängda filer, confirm på `javascript_exec` och uppladdning, och container utan värdmontering. | Text |
| 7.3 | URL-policyn täcker inte klick eller redirect, så den får inte räknas som skydd för dem. `javascript:` i navigate körs även när `javascript_exec` är av. | Text |
| 7.4 | Ingen pekare mot NAS, skill-katalog eller ärendeportal. | Text |
| 7.5 | Ingen meta-agent skriver en browser-skill. | Text |

## 8. Data

| # | Förbud | Spärr |
|---|---|---|
| 8.1 | Ingen E57 och ingen IFC-write i packning av valv, fönster och innervägg. | Text |
