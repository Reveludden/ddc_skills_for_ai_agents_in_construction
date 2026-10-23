---
status: proposed
skill: fu-entreprenad
kalla: claude (session), idé från itai-gendler/pdd-kit (MIT), pdd-verify/references/verification-rubric.md ("The border")
typ: lägg till (textändring, ingen Kontrollregel)
tak: ej satt (--tak är en flagga; overhead är bromsen)
grund_skill_version: 1.3.0
grund_skill_sha256: 23d758fb905025abf9c9b5c3273210a60c5e2a3e0d8c24c45cc349ec7069c2dc
---
## Tillägg i Steg 2b — Omgörningstestet (FÖRSLAG – ej infört)

Efter stycket om Verifieringskolumnen:

> **Omgörningstestet.** Ett funktionskrav i KUV-registret ska klara frågan: om lösningen gjordes om från grunden med andra produkter, annan utformning och annat utförande, skulle kravet fortfarande behöva vara uppfyllt? Bara det som klarar testet hör hemma i Krav-kolumnen. Det som en ny lösning fritt kan ändra är utförande, och hör hemma i en beskrivning eller som exempel, inte som krav.
>
> Exempel (formen, inte värdet, är poängen; klassen är inte verifierad mot BBR): "Dörr i utrymningsväg ska ha brandteknisk klass EI 30" klarar testet. "Dörr av fabrikat X" gör det inte, om inte ett objektskrav (KML, varsamhet) motiverar det; då anges grunden i Grundning-kolumnen.

## Tillägg i Steg 5, punkt 3 (FÖRSLAG – ej infört)

Efter "Är arbetet verkligen en ändring, ett tillägg eller ett avgående arbete mot kontraktshandlingarna?":

> Vid funktionskrav: pröva med omgörningstestet. En avvikelse från ett krav som klarar testet är en kravavvikelse. En skillnad i det som entreprenören fritt får välja är inte en ändring och grundar ingen ÄTA. Testet gäller bara funktionskrav. Där handlingarna föreskriver utförandet (utförandeentreprenad) gäller handlingarna som de är skrivna.

## Varför
- KUV-registret skiljer redan Krav från Uppfyllnad, men anger inte hur man avgör vad som är krav och vad som är entreprenörens val. Testet ger en fråga att ställa per rad.
- Samma fråga avgör ÄTA-anspråk vid funktionskrav: en ändring av ett fritt val är inte en ändring av kontraktet.
- Idén kommer från pdd-kits "redesign test": en skillnad räknas bara som avvikelse om den måste stå kvar när ytan byggs om från grunden.

## Osäkerhet
Hur gränsen mellan funktionskrav och fritt utförande dras rättsligt beror på entreprenadform och handlingarnas formulering [O]. Testet är ett arbetsverktyg för att formulera och läsa krav, inte en tolkningsregel. Rättslig bedömning sker i `ata-hindersanalys`.

## Begränsning
Ren textändring utan kommando eller sökväg; jfr governance/README.md om prosaändringars låga mätbara effekt.

## Återställning
Vid avslag ändras ingenting. Om förslaget införts och ska ångras stryks de två tilläggen.
