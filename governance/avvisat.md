# Avvisat och uppskjutet

Den här filen samlar lösningar som utretts tillräckligt för att kostnad och nytta gick att väga, och som sedan avvisades eller sköts upp. Syftet är att nästa läsare inte ska behöva föra samma resonemang igen.

**Vad som hör hit:** en lösning som utretts, beslutet, skälet och vad som skulle ändra beslutet. Inget annat. Inga planer, ingen status och inga hänvisningar till filrader, eftersom sådant blir inaktuellt.

**Hur filen ändras:**
- Nya poster läggs till sist. En befintlig post ändras aldrig.
- Den som vill pröva en fråga på nytt lägger till en ny post med `ersatter: A-NN`. Den nya posten ska förklara varför skälet inte längre gäller.
- `beslutat_av` anger vem som fattat beslutet. Saknas ett mänskligt beslut står `ej beslutat`. Då är posten en rekommendation och inget beslut.

Idén till filen kommer från `spec/rejected.md` i itai-gendler/pdd-kit (MIT).

---

## A-01 Meta-agent som ändrar skills på egen hand
- utfall: avvisat
- datum: 2026-10-08
- beslutat_av: Bengt Skoglund. Beslutet är dokumenterat i governance/README.md och fördes in i main genom PR #1. Där beskrivs det som "ett SFV-beslut"; om det är fattat på SFV-nivå är inte kontrollerat.
- lösning: En meta-agent skriver in, ersätter och stryker regler i SKILL.md utifrån körhistorik och utvärderingar, enligt Ye m.fl., ICML 2026.
- skäl: Alla domäner där metoden visat effekt har ett facit som kan räknas fram. Juridiska bedömningar, som preskription, ÄTA eller avtalstolkning, är resonemangstunga och saknar sådant facit. Översikten Zhou m.fl. stöder inte heller kravet på mänsklig granskning, så spärren är ett eget SFV-beslut och följer inte av litteraturen.
- i stället: Meta-agenten föreslår (`status: proposed`) och en människa för in regeln och fyller i `granskad_av`.
- ändras om: Ett område med beräkningsbart facit blir aktuellt, till exempel scan2bim-mätningar. Där kan autonom utveckling prövas utan att spärren hävs för juridiska skills.

## A-02 Idégraf över agenthistorik
- utfall: uppskjutet
- datum: 2026-10-08
- beslutat_av: Bengt Skoglund. Beslutet är dokumenterat i governance/README.md och fördes in i main genom PR #1.
- lösning: En graf med taggar över tidigare körningar och anteckningar, som hämtas med traversering enligt Chen, Liang och Xie (TagGraph).
- skäl: Ingen grafvariant vann överallt. Det mesta av styrkan var lexikal, och BM25 eller sökning i råtext slog ofta grafen. Valet av taggar betydde mer än traverseringen.
- ändras om: Riktiga SFV-frågor finns och en graf passerar tre grindar:
  1. Den slår sökning i originaltexten och BM25 på extrakten.
  2. Den använder ett fast ordförråd i koden, till exempel lagrum, diarienummer, fastighetsbeteckning och K21-period.
  3. Den använder lokal traversering utan PageRank.

## A-03 Flera parallella agentkörningar
- utfall: uppskjutet
- datum: 2026-10-08
- beslutat_av: Bengt Skoglund. Beslutet är dokumenterat i governance/README.md och fördes in i main genom PR #1.
- lösning: Starta flera agentramverk eller körningar parallellt, avbryt de svaga och flytta budget till de starka (arXiv:2607.18235).
- skäl: Inget behov är ännu formulerat som motiverar kostnaden.
- ändras om: En återkommande uppgift visar stor spridning mellan körningar och resultatet går att mäta tidigt.

## A-04 Tak på antal regler som standard
- utfall: uppskjutet
- datum: 2026-10-08
- beslutat_av: ej beslutat (governance/README.md: "Beslutet är Bengts")
- lösning: Att `--tak` har ett standardvärde, så att en ny regel automatiskt blir en ersättning när en skill har N regler.
- skäl: Bromsen i normalfallet är `overhead`, som bygger på mätningar. Ett fast tak utan mätning riskerar att tränga ut regler som gör nytta.
- ändras om: Antalet regler per skill växer utan att `overhead` flaggar något. Om ett standardvärde införs är förslaget 3, inte 1.

## A-05 Installera cloudflare/security-audit-skill
- utfall: avvisat
- datum: 2026-10-22
- beslutat_av: Bengt Skoglund (valde att arbeta in metoden i stället, session 2026-10-22)
- lösning: Installera skillen och köra full revision av repot.
- skäl: Skillen granskar programkod, medan repot främst består av markdown och JSON. En full revision kör många underagenter i flera omgångar, vilket inte står i proportion till sex skript.
- i stället: Metoden fördes in som fyndkontrakt (`findings_guard.py`) med oberoende verifiering. Skripten granskades i vägledningsläge.
- ändras om: Repot får körbar kod som hanterar indata från tredje part i större omfattning.

## A-06 Härdning av update_all_skills.py och publish_*.ps1
- utfall: uppskjutet
- datum: 2026-10-22
- beslutat_av: Bengt Skoglund (godkände README-raden i stället för kodändring, session 2026-10-22)
- lösning: Lägga in skydd mot symlänkar vid skrivning av SKILL.md, claw.json och instructions.md.
- skäl: Skripten kommer från det ursprungliga repot, har upphovspersonens sökväg hårdkodad och anropas inte av något i governance/. Att härda kod som inte körs ger inget skydd.
- i stället: En varning i governance/README.md, avsnitt Kända begränsningar.
- ändras om: Skripten börjar köras på skill-kataloger med innehåll från tredje part.

## A-07 Installera pdd-kit
- utfall: avvisat
- datum: 2026-10-23
- beslutat_av: Bengt Skoglund (valde att föra över idéerna som förslag, session 2026-10-23)
- lösning: Installera pdd-toolkit och dess skills (map, ideate, verify).
- skäl: Verktyget är byggt för mjukvaruprodukter, och varken SFV-ärenden eller detta repo är en sådan produkt. Det kräver Node och npm, och skillen hämtar CLI:t från npm vid varje körning, med `@latest` som reserv.
- i stället: Tre idéer fördes över. Två är förslag till skills: måttstock före klassificering i ata-hindersanalys och omgörningstestet i fu-entreprenad. Den tredje är den här filen.
- ändras om: Ett mjukvaruprojekt med egen produktbeskrivning blir aktuellt.
