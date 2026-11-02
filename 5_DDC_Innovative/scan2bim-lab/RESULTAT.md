# Mätresultat: scan2bim-lab 0.1.0

Körda 2026-11-02 mot syntetiskt facit (`python -m scan2bim.cli bench`). Rådata finns i `resultat/*.json`.

**Viktigt:** detta är syntetiska data utan skuggning mellan föremål. Resultaten visar att metoden fungerar under kontrollerade förhållanden. De visar inte hur bra den fungerar på riktiga skanningar. Det kräver mätning mot ett verkligt facit.

## Krav (kontrollregel SCAN2BIM-01)

| Mått | Krav |
|---|---|
| Andel rumsytor hittade | 100 % |
| Andel rör hittade | ≥ 85 % |
| Max radiefel | ≤ 3 mm |
| Max axelfel | ≤ 10 mm |
| Andel rätt DN | ≥ 85 % |

## Resultat

| Scenario | Seed | Plan (facit 6) | Rör (facit 9) | Falska rör | DN rätt | Max radiefel mm | Max axelfel mm | Böj hittad | Krav |
|---|---|---|---|---|---|---|---|---|---|
| Standard: brus 2 mm, 6 mm punktavstånd, 2 skannerpositioner | 0 | 6 | 9 | 0 | 9/9 | 0.25 | 2.2 | 1/1 | godkänd |
| Standard: brus 2 mm, 6 mm punktavstånd, 2 skannerpositioner | 1 | 6 | 9 | 0 | 9/9 | 0.25 | 2.0 | 1/1 | godkänd |
| Standard: brus 2 mm, 6 mm punktavstånd, 2 skannerpositioner | 2 | 6 | 9 | 0 | 9/9 | 0.6 | 1.8 | 1/1 | godkänd |
| En skannerposition | 0 | 6 | 9 | 0 | 9/9 | 0.25 | 1.0 | 1/1 | godkänd |
| En skannerposition | 1 | 6 | 9 | 0 | 8/9 | 2.6 | 2.8 | 1/1 | godkänd |
| Brus 5 mm | 0 | 6 | 9 | 0 | 7/9 | 3.95 | 2.6 | 1/1 | ej godkänd |
| Brus 5 mm | 1 | 6 | 9 | 1 | 8/9 | 5.5 | 8.2 | 1/1 | ej godkänd |
| Glest: 12 mm punktavstånd, voxel 12 mm | 0 | 6 | 8 | 0 | 6/8 | 31.7 | 35.6 | 1/1 | ej godkänd |
| Glest: 12 mm punktavstånd, voxel 12 mm | 1 | 6 | 7 | 0 | 7/7 | 2.75 | 4.0 | 1/1 | ej godkänd |

"Falska rör" räknar rör som inte finns i facit. Extra plan (2 per körning) är skåpets sidor. Det är verkliga ytor som inte ingår i facit, inte fel.

## Slutsatser

1. **Under goda förhållanden** (brus ≤ 2 mm, punktavstånd ≤ 6 mm) hittas alla rör från DN25 till DN150, med radiefel under 1 mm och rätt DN. Det gäller både med en och två skannerpositioner.
2. **Brus 5 mm** ger radiefel på 4–6 mm. Det räcker för att DN25/DN32 och DN32/DN40 ska förväxlas, eftersom deras ytterdiametrar skiljer bara 6–9 mm. Detta är en fysisk gräns, inte ett programfel. Små dimensioner kräver en skanner med lågt brus.
3. **Glest moln (12 mm)** gör att DN25, och ibland DN32, försvinner eller mäts fel. Tumregel från testet: punktavståndet bör vara högst ungefär en tredjedel av rörets diameter [S, bara syntetiskt prövat].
4. **Böjen** mellan P5 och P6 föreslogs korrekt som kopplingskandidat i samtliga körningar.

## Ändringar som mätningen ledde till

| Problem som mätningen visade | Åtgärd | Effekt |
|---|---|---|
| Falska rör i hörn mellan vägg och golv/tak (60–80° synlig omkrets) | Krav på minst 100° synlig omkrets | Seed 0: 3 → 0 falska rör. Seed 1 hade fortfarande 3 kvar. |
| Falska rör längs skåpkant och i hörn (gles punkttäthet) | Krav på täthet ≥ 30 % av 1/voxel² | 0 falska rör i alla tre standardkörningarna |

## Nästa mätning

Mätning mot verkliga skanningar med manuellt kontrollerat facit: diametrar uppmätta på plats, eller en befintlig, granskad modell.
