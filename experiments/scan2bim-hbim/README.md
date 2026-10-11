# Scan2BIM för HBIM – lokal prototyp på syntetiska punktmoln

**Status:** utforskning. Ingen produktionskod. Inget riktigt punktmoln har använts.

**Beslut:** Bengt Skoglund hävde 2026-10-11 förbudet mot E57 och IFC-skrivning för valv, fönster och innervägg (FORBUD 8.1). Beslutet gäller bygge, test och utforskning, och resultatet ska visas för honom.

## Vad prototypen gör

Kedjan går från punktmoln till IFC4. All beräkning sker lokalt med numpy, scipy och IfcOpenShell. Inget skickas över nätet.

1. **Segmentering**: RANSAC delar upp molnet i plan. Planen klassas sedan som golv, tak, vägg eller övrig yta, till exempel smyg eller korridor.
2. **Robust anpassning per vägg**: anpassningen sker i två varv. Varv 1 hittar öppningar och insänkta fält. I varv 2 tas de bort från anpassningen. Viktningen är Huber följd av Tukey. Ovanpå planet läggs en ytmodell (andragradsyta) som fångar buktning.
3. **Hörn**: väggens längd räknas fram som skärningen med grannväggarna.
4. **Öppningar**: ett rutnät på 5 cm i väggens plan delar in ytan i tomma och insänkta rutor. Kanterna förfinas med punkterna. Varje öppning klassas som dörröppning, fönsteröppning, stängd dörr (kandidat) eller osäker.
5. **IFC4**: IfcWall, IfcOpeningElement och IfcDoor/IfcWindow kopplas via `IfcRelVoidsElement` och `IfcRelFillsElement`. En skev vägg skrivs som en triangulerad yta i stället för ett tvingat plan. GUID:erna härleds ur geometrin så att de blir desamma vid omkörning.
6. **Källa per objekt**: Psetet `SFV_Scan2BIM` anger `Kalla` = observerad, härledd eller antagen, samt metod, residualer, lutning, täckning och hur tjockleken bestämts.

## Testmiljön

Testmiljön är ett syntetiskt rum med exakt känt facit (`syntetisk.py`):

| Vägg | Innehåll |
|---|---|
| S | Dörröppning 0,90 × 2,10 m. Väggen är 0,45 m tjock och smygen är skannad |
| O | Fönster 1,20 × 1,30 m med bröstning 0,90 m och karm 0,25 m in |
| N | Historisk vägg: buktning 20 mm och lutning 15 mm på 3 m |
| V | Stängd dörr med dörrbladet insänkt 30 mm |

## Körning

```
pip install -r requirements.txt
python prov.py utdata      # 27 prov, ca 40 s
```

Körningen skriver `utdata/modell.ifc`, `utdata/rapport.json` och `utdata/provlogg.txt`.

## Resultat (27/27 godkända i slutversionen)

| Prov | Vad | Uppmätt |
|---|---|---|
| A2–A4 | Dörr, fönster och stängd dörr hittade med rätt typ | Kantfel ≤ 3,8 mm |
| A5–A6 | Skev vägg flaggas, lutning mäts | N flaggad, 5,0 mm/m (facit 5,0) |
| A7–A8 | Tjocklek observerad i dörrsmyg, annars markerad som antagen | 451 mm (facit 450) |
| A10–A12 | IFC: schema, relationer, källa, öppningarnas läge och väggytan mot punktmolnet | 0 fel, 0,0 mm, ≤ 1,8 mm |
| B1–B2 | **Förstörelseprov**: en känd utbuktning på 14 mm mäts upp | 13,9 mm |
| C1–C2 | **Förstörelseprov av IFC-kontrollen**: borttagna relationer och ett brutet attribut | Upptäckta |
| D1–D2 | Negativ kontroll: rum utan öppningar och utan skevhet | 0 falska |
| E1 | En stängd dörr i liv med väggen (5 mm) ska inte påstås vara en dörr | 0 påståenden |
| F1–F4 | Brus 5 mm och halv täthet | Kantfel ≤ 4,8 mm, N flaggas fortfarande |
| G1 | Samma GUID efter omkörning med nytt brus | 7/7 |
| H1–H3 | 10 rum, 30 öppningar | Precision 1,00, recall 1,00, MAE ≤ 1,6 mm |

## Fel som proven hittade under bygget

Proven hittade fem fel. Alla satt i mätningen själv och inte i det som mättes:

| # | Fel | Hittat av | Följd före rättning | Rättning |
|---|---|---|---|---|
| 1 | Smygdjupet mättes som 97-percentil | Facit 450 mm | 437 mm (−3 %) | k:te största värdet |
| 2 | Den stängda dörren drog väggplanet bakåt | Facit lutning 0 | Falsk lutning 1,05 mm/m och P95 28 mm | Två varv, där kandidaterna tas bort |
| 3 | Huber-viktning lät den lokala utbuktningen dra referensytan till sig | **Förstörelseprov B2** | 14 mm mättes som 10,9 mm (−22 %) | Tukey efter Huber |
| 4 | Skevhetskriteriet jämförde residualer med varandra | Prov F4 (brus 5 mm) | Bruset dolde buktningen på 20 mm | Ytmodellens avvikelse mot planet |
| 5 | Väggens riktning togs från RANSAC i stället för den robusta anpassningen | **Prov A12** (IFC-ytan mot punktmolnet) | Väggytan i IFC låg 14,6 mm fel vid hörnet | Ny ram efter anpassningen |

Dessutom hade nyckeln för väggen ett teckenfel på noll: `-0.0` och `0.0` gav olika GUID för samma vägg (prov G1).

Fel 3 är samma typ som "mätinstrumentet halverar" i B1j. Referensytan anpassas till samma data som avvikelsen finns i, och avvikelsen blir då för liten. Fel 5 passerade alla prov tills ett prov jämförde IFC-modellen mot punktmolnet i stället för mot kedjans egna tal.

## Kända begränsningar

- **Syntetiskt facit.** Riktiga moln har skuggor, möbler, flera skanningar och registreringsfel. Siffrorna ovan gäller bara det syntetiska rummet.
- **Hörn mot skev vägg.** O och V blir 3 983 mm i stället för 3 992,5 mm vid halva höjden. Felet är 9 mm och beror på att hörnet räknas mot N:s *plan*, inte mot dess ytmodell.
- **Stängd dörr i liv med väggen** går inte att upptäcka med den här metoden (E1). Metoden påstår då ingenting, vilket är rätt beteende.
- **Ytmodellen är en andragradsyta.** Lokala skador eller profiler mindre än väggen kräver en finare modell.
- **GUID via avrundning.** En vägg vars läge ligger nära en avrundningsgräns (x,x5 m) kan byta GUID. En hållbar lösning är att matcha mot föregående modell.
- **Smygdjup** söks bara ned till 1,2 m. Tjockare historiska murar kräver en högre gräns.
- **Toleranser.** Gränsen 20 mm och precision/recall är startmål från analysunderlaget och har inte kalibrerats.
- Golv, tak och IfcSpace skrivs inte till IFC än.

## Nästa steg (kräver beslut)

1. Kör kedjan på ett riktigt utsnitt på Bengts dator. Inget moln lämnar maskinen, och bara `rapport.json` och provloggen visas.
2. Inför ett förstörelseprov på riktiga data: lägg in en känd förskjutning i ett riktigt moln och mät den igen, på samma sätt som i prov B.
3. Jämför med registreringsfelet i B1j, eftersom felbudgeten saknas.
