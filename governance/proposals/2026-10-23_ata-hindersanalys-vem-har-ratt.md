---
status: proposed
skill: ata-hindersanalys
kalla: claude (session), idé från itai-gendler/pdd-kit (MIT), pdd-verify/references/verification-rubric.md
typ: lägg till (textändring, ingen Kontrollregel)
tak: ej satt (--tak är en flagga; overhead är bromsen)
grund_skill_version: 3.5.1
grund_skill_sha256: 3b6dc5138edb3f0eafe75474f7f3448909ed0b6ca66ecc8acb2ba189a6883423
---
## Steg 0.9 — Vem har rätt: handlingarna eller utförandet? (FÖRSLAG – ej infört)

Placeras mellan Steg 0.7 och Del A. Steget avgör vilken sida som är måttstocken innan anspråket klassificeras. Det ersätter inte Steg 1 eller A–J; det styr vilka av dem som bär bedömningen.

Ställ handlingarna (kontraktshandlingar i rangordning enligt Steg 4) mot det som utförts eller krävs på plats. Välj ett av tre utfall:

| Utfall | Innebörd | Följd i flödet |
|---|---|---|
| **Handlingarna har rätt** | Arbetet ryms i kontraktshandlingarna. Entreprenören avviker från dem eller begär betalt för kontraktsarbete. | A ("Ingick arbetet?") blir bärande. Klassificering i Steg 1 görs bara för de delar som inte ryms. |
| **Utförandet har rätt** | Handlingarna stämmer inte med verkligheten eller behovet, och det utförda eller begärda är det som måste gälla. | Handlingarna behöver ändras. Gå vidare till Steg 1 för klassificering (förskrivet, föranlett, rubbning m.m.). |
| **Ingen har rätt** | Handlingarna är oklara eller motstridiga, och utförandet följer inte heller någon rimlig tolkning. | Rangordning och tolkning (Steg 4–5) blir bärande. Behövs uppgifter för att avgöra: KOMPLETTERING KRÄVS. |

Utfallet är en strukturering, inte en rättslig slutsats. Att handlingarna har rätt betyder inte i sig att anspråket ska avslås; det avgörs i formalia och A–J.

Om utfallet inte går att avgöra ur underlaget redovisas det i 9B (se nedan) och får `behover_verifiering` i fynd.json med exakt saknat faktum.

## Tillägg i Steg 9B (FÖRSLAG – ej infört)

Ny rad direkt efter KLASSIFICERING i standardformatet:

```
MÅTTSTOCK:        [Handlingarna har rätt / Utförandet har rätt / Ingen har rätt / Ej avgjord]
```

När MÅTTSTOCK är "Ej avgjord" fylls ett beslutsblock i före REKOMMENDATION:

```
VEM HAR RÄTT – BESLUT KRÄVS
- Handlingarna säger:   [citat med dokument och avsnitt]
- Utfört / krävs:       [vad som gjorts eller begärs, med källa]
- Granskade handlingar: [exakt förteckning]
- Minsta val:           [2–3 alternativ, inget mer]
- Rekommendation:       [ett alternativ och varför]
- Löser också:          [vilka andra delar av anspråket beslutet avgör]
```

Gruppera frågor efter grundbeslut. Ställ inte en fråga per symptom.

## Varför
- I dag börjar Del A direkt med att klassificera rättsfigur. Frågan om arbetet alls ligger utanför kontraktet prövas först i A ("Ingick arbetet?"), efter formaliakontrollen. Att avgöra måttstocken först gör att formalia och A–J prövas mot rätt sida från början.
- Beslutsblocket ger dig samma sex uppgifter varje gång det är oklart vem som har rätt, i stället för fri text.
- Idén kommer från pdd-kits verifieringsrubrik, där en avvikelse mellan beskrivning och kod klassas som "model-right", "code-right" eller "neither-right" innan något åtgärdas.

## Begränsning
Detta är en ren textändring utan kommando eller sökväg. Enligt underlaget i governance/README.md (arXiv:2610.04832 §5) har ändringar som bara rör prosa liten mätbar effekt (+0,017). MÅTTSTOCK-raden är gjord som ett obligatoriskt fält i 9B för att vara kontrollerbar i granskning; någon maskinell kontroll finns inte.

## Återställning
Vid avslag ändras ingenting. Om förslaget införts och ska ångras stryks Steg 0.9, MÅTTSTOCK-raden och beslutsblocket i 9B.
