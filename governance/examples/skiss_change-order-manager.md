# Skiss: kontrollregler som förkontroll och Noul-frågor i `change-order-manager`

Det här är ett förslag. `4_DDC_Curated/Contract-Legal/change-order-manager/SKILL.md` är inte ändrad. Sektionen nedan förs in av en människa, som också fyller i `granskad_av`.

## 1. Sektion att föra in i SKILL.md

```markdown
## Kontrollregel
- id: SFV-ATA-01
- regel: Preskription kontrolleras innan anspråket bedöms i sak.
- kommando: `python governance/ordningskontroll.py check --logg korlogg.jsonl --regler governance/examples/regler_ata.json`
- granskad_av: <tomt tills en människa godkänt>
- granskad: <datum>
- källa: människa
```

Agenten loggar varje steg i `korlogg.jsonl` med namn och status, till exempel `preskription_kontroll`, `avtal_hamtat`, `citat_avtal` och `sakbedomning`. Utan logg finns inget att kontrollera, och körningen blir `OKÄNT`.

## 2. Tre lager i fast ordning

| Lager | Vad | Verktyg | Utfall |
|---|---|---|---|
| 1. Förkontroll | Ordning och närvaro: preskription före sakbedömning, avtalet hämtat innan det citeras | `ordningskontroll.py` | `BRUTEN` eller `OKÄNT`: underkänd direkt, utan AI-domare |
| 2. Belägg | Avtalets sha256, lydelse, preskriptionsdatum och K21-bas har inte ändrats | `evidence_guard.py check` | `OGILTIGT` eller `OKÄNT`: underkänd direkt |
| 3. Tolkning | Frågor som kräver läsning (se avsnitt 3) | AI-domare | Godkänd, granskning eller underkänd |

Lager 1 och 2 ger exakta svar och körs alltid först. Guiden till Jev-as-a-Judge visar varför: en körning där agenten hoppade över ett obligatoriskt steg fick cirka 86 % sannolikhet för "korrekt" och skulle ha passerat en 80 %-gräns.

## 3. Frågor till AI-domaren (lager 3)

Varje fråga är bunden till en kontrollregel eller ett belägg och ska gå att besvara från körningen.

| Typ | Fråga | Svarsalternativ med betydelse |
|---|---|---|
| Noul | Har varje påstående i slutsvaret om avtalets innehåll stöd i den avtalstext som hämtades i körningen? | ja: varje påstående kan knytas till hämtad text. nej: minst ett påstående saknar stöd eller motsägs |
| Noul | Stämmer slutsvarets slutsats om preskription med resultatet av steget `preskription_kontroll`? | ja: samma slutsats. nej: annan slutsats, eller slutsats trots att steget misslyckades |
| Choice | Vilket är huvudfelet? | inget fel · påstående utan stöd i hämtad text · slutsats som strider mot verktygsresultat · krävd handling påstås utförd men misslyckades · begäran lämnad obesvarad |
| Score | Hur allvarligt är felet för beslutet? | 0: påverkar inte · 1: kräver rättelse före utskick · 2: kan leda till felaktigt beslut om ersättning eller rätt |

Ingen fråga om kvaliteten på fri text, som "Är bedömningen välskriven?". I artikeln låg alla testade domare nära slumpnivå på fri text utan facit, men var ändå säkra på sina domar (arXiv:2609.26550, §7.4, avsnittet Limitations och bilaga H).

## 4. Från sannolikhet till beslut

| Sannolikhet för "ja" (Noul) | Beslut |
|---|---|
| minst `t_godkand` | Godkänd |
| mellan | Granskning av människa |
| högst `t_underkand` | Underkänd |

- Gränserna är **inte** satta. Ett felaktigt godkännande kostar mer än en granskning, så `t_godkand` bör ligga högre än 1 − `t_underkand`.
- Gränserna sätts på cirka 100 körningar som en människa har bedömt. Använd den undre konfidensgränsen för förlusten, inte punktskattningen (arXiv:2609.26550 §8), och kontrollera sedan på separata körningar.
- Upprepa samma körningar för att se att domarna är stabila. Håll frågor och gränser fasta när agentversioner jämförs.
- Score 2 går alltid till granskning, oavsett Noul.

## 5. Det som alltid förblir mänskligt

- Själva ställningstagandet i ÄTA-frågan: om arbetet ingår i kontraktet, vad det ska ersättas med och tolkningen av avtalet.
- Allt som går till motparten.
- Att föra in och stryka kontrollregler (`granskad_av`).

## 6. Innan AI-domaren används

- JEV är inte testad på agentkörningar och inte på långa underlag. Artikelns längsta underlag var cirka 3 600 tokens (arXiv:2609.26550, avsnittet Limitations och bilaga A).
- JEV är en molntjänst. Körningar med uppgifter från SFV-ärenden skickas inte dit utan avstämning med SFV:s informationssäkerhet. Ett alternativ är en öppen beslutsmodell som körs på SFV:s egen utrustning (bilaga A).
- Följsamheten per regel från `ordningskontroll.py` (k av n) kan användas som mätunderlag för `skill_curator.py overhead`.
