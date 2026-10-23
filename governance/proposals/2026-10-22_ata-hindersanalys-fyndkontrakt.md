---
status: proposed
skill: ata-hindersanalys
kalla: claude (session), metod från cloudflare/security-audit-skill (MIT)
typ: lägg till
tak: ej satt (--tak är en flagga; overhead är bromsen). Skillen har ingen Kontrollregel i dag
grund_skill_version: 3.5.1
grund_skill_sha256: 3b6dc5138edb3f0eafe75474f7f3448909ed0b6ca66ecc8acb2ba189a6883423
---
## Kontrollregel (FÖRSLAG – ej införd)
- id: SFV-ATA-02
- regel: Varje grund i bedömningen redovisas i fynd.json med utfall bekraftad, behover_verifiering, avvisad eller notering. Den som hittade grunden får inte bekräfta eller avvisa den; motståndstestet körs i en ny kontext. Leverans sker först när `rapport` ger exitkod 0.
- kommando: `python governance/findings_guard.py rapport --fynd fynd.json`
- källa: claude (session 2026-10-22)
- granskad_av: <tomt tills en människa godkänt>

## Föreslagna textändringar (FÖRSLAG – ej införda)

### 1. Motståndstest i ny kontext
I dag formulerar samma instans som skrev bedömningen motpartens starkaste invändning. Den instansen har redan bestämt sig.

Föreslagen lydelse, ersätter första stycket under "Motståndstest — OBLIGATORISKT INNAN LEVERANS":

> Motståndstestet görs av en ny instans (underagent eller separat session) som bara får anspråket, underlaget och de bekräftade grunderna, inte bedömningens slutsats. Uppdraget är att motbevisa varje grund. En grund som överlever blir `bekraftad` med `verifierad_av` satt till den nya instansen. En grund som motbevisas blir `avvisad` med `skal`. En invändning som inte kan avgöras ur underlaget blir `behover_verifiering` med exakt `saknat_faktum`.

### 2. Behöver verifiering har ingen ståndpunkt
Tillägg under "Typ A/B/C Fail-fast":

> En grund med utfallet `behover_verifiering` får inte bära SFV:s ståndpunkt och får ingen `betydelse`. Ange exakt vilket faktum som saknas och vem som kan ta fram det, till exempel "byggmötesprotokoll 6: medgav beställaren förlängd frist? Bengt kontrollerar". "Osäkert" räcker inte.

### 3. Grunder som inte påverkar slutsatsen
Tillägg i Steg 9:

> Om en bekräftad grund redan avgör ärendet, till exempel preskription, redovisas övriga brister som subsidiära grunder i svaret när de stärker SFV:s position. Brister utan självständig betydelse, till exempel saknad K21-indexering i ett preskriberat anspråk, blir `notering` med `befintligt_skydd` och räknas inte som avslagsgrund.

### 4. Kvalitetsdeklarationen
Tillägg i deklarationen sist i bedömningen:

```
Fyndredovisning: X bekräftade | Y behöver verifiering | Z avvisade | N noteringar. Oberoende prövning: ja.
```

## Varför
- Den som hittat ett fynd prövar det sämre än en ny instans. Det är samma princip som Pass 5b i konsistenskontroll (factored verifiering), som i dag inte används i ÄTA-flödet.
- `behover_verifiering` utan ståndpunkt hindrar att en obekräftad grund hamnar i svaret till entreprenören.
- `findings_guard.py` kontrollerar regeln mekaniskt: oberoende verifierare, exakt saknat faktum, citat som finns ordagrant i underlaget när `fil` anges.

## Återställning
Vid avslag ändras ingenting. Skillen har ingen Kontrollregel i dag; om förslaget införts och ska ångras stryks sektionen `## Kontrollregel` med id SFV-ATA-02 och textändringarna 1–4.
