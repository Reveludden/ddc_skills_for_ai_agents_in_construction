"""Nominella rördimensioner.

Ytterdiametrar för gängade/svetsade stålrör enligt den vanliga ISO-serien
(SS-EN 10255 / EN 10220). Värdena är [S] sannolika och ska verifieras mot
standarden innan de används i en leverans. Isolerade rör mäts på isoleringens
utsida och kan därför inte klassas med denna tabell.
"""

STEEL_OD_MM = {
    "DN15": 21.3, "DN20": 26.9, "DN25": 33.7, "DN32": 42.4, "DN40": 48.3,
    "DN50": 60.3, "DN65": 76.1, "DN80": 88.9, "DN100": 114.3, "DN125": 139.7,
    "DN150": 168.3, "DN200": 219.1, "DN250": 273.0, "DN300": 323.9,
}


def nearest_dn(outer_diameter_mm: float, table=STEEL_OD_MM, max_rel_error=0.12):
    """Närmaste DN och relativt fel. None om inget ligger inom max_rel_error."""
    name, od = min(table.items(), key=lambda kv: abs(kv[1] - outer_diameter_mm))
    rel = abs(od - outer_diameter_mm) / od
    return (name, round(rel, 3)) if rel <= max_rel_error else (None, round(rel, 3))
