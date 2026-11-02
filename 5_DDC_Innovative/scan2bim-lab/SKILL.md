---
name: "scan2bim-lab"
description: "Extract walls, floors, ceilings and straight pipes (axis, diameter, DN, length) from laser-scan point clouds (E57/LAS/XYZ), propose pipe connections for human review, and measure accuracy against ground truth with a synthetic benchmark."
homepage: "https://datadrivenconstruction.io"
metadata: {"openclaw": {"emoji": "📡", "os": ["win32", "linux", "darwin"], "homepage": "https://datadrivenconstruction.io", "requires": {"bins": ["python3"]}}}
---
# scan2bim-lab

## Översikt

Egenutvecklad kedja från punktmoln till BIM-parametrar. Kedjan är ett labb: varje funktion mäts mot facit innan den används skarpt. Metoden beskrivs i `METOD.md`, och senaste mätresultat finns i `RESULTAT.md`.

**Förmågor:**
- läsa E57 (flera registrerade skanningar), LAS/LAZ och XYZ/PTS, med beskärning och utglesning
- detektera plan: golv, tak och väggar
- detektera raka rör: axel, diameter, närmaste DN, längd, synlig omkrets och avvikelse (rms)
- föreslå kopplingar (böj, skarv) som en människa granskar
- benchmark mot syntetiskt facit med krav som ger exitkod

**Gör inte (ännu):** kanaler, kabelstegar, böj- och T-rörsgeometri, IFC- eller Revit-export, isolerade rör.

## Installation

```bash
pip install -r requirements.txt
```

## Användning

```bash
# Översikt av en fil
python -m scan2bim.cli info teknikrum.e57

# Detektera inom ett utsnitt (meter i skanningens koordinatsystem)
python -m scan2bim.cli detect teknikrum.e57 --voxel 0.008 --bbox 0 0 0 6 4 3 --out resultat.json

# Mätrigg mot syntetiskt facit
python -m scan2bim.cli bench --seeds 0 1 2 --krav --out resultat/bench_standard.json
```

`resultat.json` innehåller `plan`, `ror` och `kopplingskandidater`. Varje rör har `diameter_mm`, `dn`, `dn_rel_error`, `rms_mm` och `coverage_deg`. En låg täckning eller hög rms betyder att röret ska granskas manuellt.

## Tolkning av resultat

- **Rör med `dn: null`** stämmer inte med stålrörsserien. Det kan vara ett isolerat rör, ett kopparrör, ett plaströr eller ett felaktigt fynd.
- **Kopplingskandidater är förslag.** De förs aldrig in i en modell utan granskning.
- **Benchmarken är syntetisk och utan skuggning.** Ett godkänt resultat där bevisar inte att kedjan fungerar på riktiga skanningar. Det kräver mätning mot ett verkligt facit, till exempel en manuellt kontrollerad modell.

## Kontrollregel
- id: SCAN2BIM-01
- regel: Ändringar i detekteringen godkänns bara om den syntetiska benchmarken uppfyller kraven i `scan2bim/cli.py` (KRAV).
- kommando: `python -m scan2bim.cli bench --seeds 0 1 2 --krav`
- sökväg: `RESULTAT.md`
- granskad_av:
- granskad:
- källa: agent
