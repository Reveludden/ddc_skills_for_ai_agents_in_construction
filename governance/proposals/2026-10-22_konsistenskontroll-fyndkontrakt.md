---
status: proposed
skill: konsistenskontroll
kalla: claude (session), metod från cloudflare/security-audit-skill (MIT)
typ: lägg till
tak: ej satt (--tak är en flagga; overhead är bromsen). Skillen har ingen Kontrollregel i dag
grund_skill_version: 1.7.2
grund_skill_sha256: f7beaffa5c0dc4ca57651032c9f83d4386e530131e4f5de51d4b31640578e734
---
## Kontrollregel (FÖRSLAG – ej införd)
- id: SFV-KONS-01
- regel: Varje avvikelse i passen 0–5b redovisas i fynd.json. Bara bekräftade avvikelser får betydelse; [ICKE-VERIFIERBART] blir behover_verifiering med exakt saknat faktum; en brist som redan bärs av en annan kontroll blir notering. GODKÄND FÖR LEVERANS kräver exitkod 0.
- kommando: `python governance/findings_guard.py rapport --fynd fynd.json --granskning`
- källa: claude (session 2026-10-22)
- granskad_av: <tomt tills en människa godkänt>

## Föreslagna textändringar (FÖRSLAG – ej införda)

### 1. Pass 5b: utfallen knyts till kontraktet
Ändring i steg 4 och 5 i Pass 5b:

| Pass 5b i dag | Utfall i fynd.json |
|---|---|
| [BEKRÄFTAT] | påståendet står, inget fynd |
| [KONFLIKT] | `bekraftad`, med verifieringssvaret som `kallspar` och den isolerade instansen som `verifierad_av` |
| [ICKE-VERIFIERBART] | `behover_verifiering` med `saknat_faktum` (exakt vilken uppgift) och `verifieringsplan` (vem, var) |

Det ersätter "omklassificera påståendet till [H]". [H] säger att något är obekräftat; `saknat_faktum` säger vad som behövs för att avgöra det.

### 2. Djupförsvar är inte en avvikelse
Tillägg under "Grundregel":

> En brist som inte kan påverka slutsatsen, därför att en annan del av dokumentet redan bär den, är en `notering`, inte en avvikelse. Ange i `befintligt_skydd` vad som bär slutsatsen. Noteringar räknas inte i "TOTALT: N avvikelser kräver åtgärd". Exempel: ett datum saknar källhänvisning i bakgrunden, men samma datum är styrkt med källa i analysen.

### 3. Betydelse bara för bekräftade avvikelser
Tillägg i Slutrapport:

> Varje bekräftad avvikelse får betydelse `avgorande` (ändrar slutsatsen), `vasentlig` (en bärande del måste rättas) eller `begransad`. Bara `avgorande` och `vasentlig` samt `behover_verifiering` blockerar GODKÄND FÖR LEVERANS. Skriv ut tabellen från `findings_guard.py rapport --granskning` sist i slutrapporten.

## Varför
- I dag räknas alla avvikelser lika i "TOTALT". En formfråga och ett fel som vänder slutsatsen väger lika tungt, och dokument kan stoppas av brister som inte påverkar något.
- [ICKE-VERIFIERBART] → [H] tappar informationen om vad som behövs. Kontraktet kräver den.
- Veto-regeln i Pass 5 och kravet på isolerad kontext i Pass 5b står kvar oförändrade. Förslaget gör dem kontrollerbara: `findings_guard.py` vägrar en `bekraftad` där `verifierad_av` är samma som `hittad_av`.

## Återställning
Vid avslag ändras ingenting. Om förslaget införts och ska ångras stryks sektionen `## Kontrollregel` med id SFV-KONS-01 och textändringarna 1–3.
