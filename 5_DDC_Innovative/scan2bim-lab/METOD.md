# Metodbeskrivning: scan2bim-lab

Den här filen beskriver metoderna med egna ord. Koden är skriven utifrån
beskrivningen, inte utifrån någon annans källkod. Underlaget är:

- allmänt kända metoder inom punktmolnsbehandling (RANSAC, PCA, cirkelanpassning)
- det som syns utifrån i kommersiella verktyg: dokumentation, recensioner och demonstrationer
- egna tester mot syntetiskt facit

Ingen kod är kopierad, och inga stängda program har plockats isär.

## Vad de kommersiella verktygen gör

| Verktyg | Vad som syns utifrån | Vad vi tar efter |
|---|---|---|
| ClearEdge3D Edgewise | Tar automatiskt fram rör ur punktmolnet, som sedan kopplas ihop till rörsträckor och förs in i Revit som rörobjekt där diametern följer med. Användaren kopplar själv ihop rör som missats. | Plocka ut parametrar (axel, diameter, längd) i stället för mesh. Kopplingar föreslås men godkänns av en människa. |
| BIMIT | Molntjänst. Tar emot ett registrerat punktmoln (E57/XYZ) och levererar en Revit-modell på LOD200+. Uppger ±15 mm och att bara tydligt synliga element modelleras. | Toleranser redovisas per element, och element som inte syns tydligt redovisas som osäkra. |
| Pointfuse / ReCap | Gör om punktmolnet till en segmenterad mesh. | Används inte. Mesh blir tung och svår att städa (jfr Reddit-tråden). |

## Kedjan

1. **Inläsning** (`pc_io.py`). Läser E57 med skanningarnas registrering, LAS/LAZ i delar, eller XYZ/PTS. Molnet kan beskäras med `--bbox` och glesas ut per skanning så att minnet räcker.
2. **Voxel-utglesning** (`geometry.py`). En medelpunkt per kub med sidan `voxel`. Det ger jämn täthet och styr beräkningstiden.
3. **Normaler** (`geometry.py`). PCA på de 16 närmaste grannarna. Normalen är riktningen med minst spridning.
4. **Plan** (`planes.py`).
   - RANSAC: tre slumpade punkter ger ett plan. En punkt räknas till planet om den ligger inom 15 mm från det och har en normal inom 20° från planets.
   - Bästa planet förfinas med minsta kvadrat. Det delas sedan i sammanhängande ytor, och bara ytor som är minst 0,4 m i båda riktningar behålls. Det hindrar att en remsa på ovansidan av ett rör tolkas som plan.
   - Planet klassas utifrån normalen: golv eller tak om det är vågrätt, annars vägg eller lutande.
5. **Rör** (`pipes.py`). Körs på punkterna som inte hör till något plan.
   - Grundidé: på en cylinder är ytnormalen alltid vinkelrät mot axeln. Två punkter med olika normaler ger därför axelns riktning direkt, som kryssprodukten av normalerna.
   - I ett snitt vinkelrätt mot axeln skär normallinjerna från de två punkterna varandra i rörets centrum. Avståndet till centrum är radien.
   - RANSAC över punktpar inom 25 cm från varandra. Modellen med flest punkter på mantelytan, och med normaler vinkelräta mot axeln, vinner.
   - Förfining: axeln sätts till den riktning där inlier-normalerna har minst spridning. Centrum och radie tas fram med geometrisk cirkelanpassning (Gauss-Newton), med en algebraisk anpassning som startvärde.
   - Inliers delas längs axeln där det finns glapp på mer än 15 cm, så att två rör på samma linje blir två rör.
   - Filter mot skräp:
     - minst 100° av omkretsen ska synas
     - punkttätheten på den synliga mantelytan ska vara minst 30 % av den täthet utglesningen ger
     - Båda filtren infördes efter benchmark. Utan dem gav hörnen mellan vägg och golv, och skåpets kant, falska rör.
   - DN tas från närmaste ytterdiameter i stålrörsserien (`dimensions.py`). Om avvikelsen är över 12 % lämnas DN tom.
6. **Kopplingskandidater** (`pipes.py`). Rörändar som ligger nära varandra och har liknande dimension. Paret märks som böj, rak skarv eller vinklad skarv. **Inget kopplas ihop automatiskt.** Det är en lista att granska.

## Mätriggen

`python -m scan2bim.cli bench` gör följande:

- bygger ett syntetiskt teknikrum på 6 × 4 × 3 m med 9 rör (DN25–DN150, en böj, två rör på samma linje), ett skåp som störobjekt och slumpmässigt skräp
- kör hela kedjan och jämför resultatet med facit

Kraven står i `cli.py` (`KRAV`) och får bara ändras av en människa.

## Begränsningar (kända)

- **Skuggning modelleras inte** i det syntetiska rummet. Ett rör kan alltså inte skymma ett annat, vilket gör testet lättare än verkligheten.
- **Isolerade rör** mäts på isoleringens utsida, och DN kan då inte bestämmas.
- **Kopparrör och plaströr** har andra ytterdiametrar än stålrörsserien. Tabellen behöver kompletteras.
- **Kanaler** (rektangulära) och kabelstegar hanteras inte ännu.
- **Böjar och T-rör** modelleras inte som geometri. De föreslås bara som kopplingskandidater.
- **Täthetsfiltret** utgår från att punkttätheten efter utglesning är ungefär jämn. Rör långt från skannern kan ha lägre täthet och då filtreras bort. Det måste prövas på riktiga skanningar.
