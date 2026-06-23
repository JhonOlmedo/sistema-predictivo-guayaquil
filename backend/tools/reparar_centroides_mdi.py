"""Reparación de centroides URBANOS CORRIDOS en subcircuitos.csv.

Validación previa (ver validar_coordenadas_mdi.py) contra el ground truth del
Ministerio del Interior (CMI 2019-2022): 9 subcircuitos tienen un cluster de
incidentes COMPACTO pero su centroide guardado está a >700 m de donde realmente
ocurren los hechos. `lugar_referencia` confirma el barrio real en cada caso.

Estos 9 centroides se reemplazan por la MEDIANA de las coordenadas reales de su
subcircuito (robusta a outliers). Los valores nuevos van fijos en este archivo
—calculados una sola vez desde el MDI 2019-2022— para que la reparación sea
reproducible y revisable sin depender del Excel original.

IMPORTANTE: lat/lng solo se usan para DIBUJAR en el mapa. El modelo predice con
los códigos + freq_subcircuito, así que esta corrección NO altera ninguna
predicción ni las métricas del modelo; solo hace que los puntos del mapa caigan
en el barrio correcto.

No se tocan las zonas RURALES/DISPERSAS (Puná, Progreso, Morro…): ahí los hechos
están repartidos en muchos km y un centroide-mediana tampoco sería representativo.

Uso:
    python reparar_centroides_mdi.py          # --check: solo reporta, no escribe
    python reparar_centroides_mdi.py --fix    # corrige y guarda (crea backup .bak)
"""
from __future__ import annotations

import math
import shutil
import sys
from datetime import datetime
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

CSV_PATH = Path(__file__).resolve().parent.parent / "data" / "subcircuitos.csv"

# (codigo_subcircuito, nombre, nueva_lat, nueva_lng) — medianas reales MDI 2019-2022.
CORRECCIONES = [
    ("09D07C07S04", "SAN FRANCISCO 4",   -2.013305484, -79.9609403133),
    ("09D05C01S01", "ATARAZANA 1",       -2.176042,    -79.878299),
    ("09D07C08S01", "PUENTE LUCÍA 1",    -2.001248282, -79.9674353248),
    ("09D08C04S02", "FLOR DE BASTIÓN 2", -2.084057183, -79.96632814),
    ("09D07C07S03", "SAN FRANCISCO 3",   -2.026590478, -79.94791551),
    ("09D07C07S02", "SAN FRANCISCO 2",   -2.061692905, -79.9459723539),
    ("09D05C07S01", "TENGUEL 1",         -2.998347059, -79.78559036415),
    ("09D10C02S01", "POSORJA 1",         -2.711086937, -80.250440175),
    ("09D08C05S08", "MONTE SINAÍ 8",     -2.13007337,  -80.00997548),
]
NUEVO = {c: (lat, lng) for c, _, lat, lng in CORRECCIONES}
NOMBRE = {c: n for c, n, _, _ in CORRECCIONES}


def haversine_m(lat1, lon1, lat2, lon2):
    R = 6371000.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = math.radians(lat2 - lat1), math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * R * math.asin(math.sqrt(a))


def main(fix: bool) -> int:
    # UTF-8 sin BOM, CRLF — se preserva todo salvo las celdas lat/lng corregidas.
    text = CSV_PATH.read_bytes().decode("utf-8")
    lines = text.split("\r\n")
    header = lines[0].split(",")
    LAT, LNG, SUB = header.index("lat"), header.index("lng"), header.index("codigo_subcircuito")

    print(f"Archivo: {CSV_PATH.name}")
    print(f"{'subcircuito':<13} {'nombre':<19} {'actual (lat,lng)':<28} "
          f"{'nuevo (lat,lng)':<26} desplaza")
    print("-" * 100)

    pendientes = set(NUEVO)
    for idx, line in enumerate(lines):
        if idx == 0 or line == "":
            continue
        f = line.split(",")
        code = f[SUB]
        if code not in NUEVO:
            continue
        pendientes.discard(code)
        cur_lat, cur_lng = float(f[LAT]), float(f[LNG])
        new_lat, new_lng = NUEVO[code]
        move = haversine_m(cur_lat, cur_lng, new_lat, new_lng)
        print(f"{code:<13} {NOMBRE[code]:<19} "
              f"{cur_lat:.5f},{cur_lng:.5f}      "
              f"{new_lat:.5f},{new_lng:.5f}    {move:6.0f} m")
        if fix:
            f[LAT], f[LNG] = repr(new_lat), repr(new_lng)
            lines[idx] = ",".join(f)

    if pendientes:
        print(f"\n[AVISO] No se encontraron en el CSV: {sorted(pendientes)}")

    if not fix:
        print("\n[CHECK] No se escribió nada. Ejecuta con --fix para aplicar.")
        return 0

    backup = CSV_PATH.with_suffix(CSV_PATH.suffix + f".{datetime.now():%Y%m%d_%H%M%S}.bak")
    shutil.copy2(CSV_PATH, backup)
    CSV_PATH.write_bytes("\r\n".join(lines).encode("utf-8"))
    print(f"\n[FIX] {len(NUEVO) - len(pendientes)} centroides corregidos.")
    print(f"[FIX] Backup del original: {backup.name}")
    print(f"[FIX] Guardado: {CSV_PATH.name}")
    return 0


if __name__ == "__main__":
    sys.exit(main(fix="--fix" in sys.argv[1:]))
