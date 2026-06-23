"""Validación y reparación de coordenadas del dataset MDI 2019–2025.

Detecta y corrige dos problemas de georreferenciación que comparten una sola
causa raíz:

  1. Registros REAL con el SIGNO invertido. Guayaquil está en el hemisferio sur
     y el meridiano occidental, de modo que toda coordenada válida cumple
     lat < 0 y lng < 0. Un valor positivo es un error de captura (se cargó la
     coordenada sin el signo negativo) que ubica el punto en el hemisferio
     opuesto, a miles de km.

  2. Centroides IMPUTADO contaminados. La imputación asigna a cada registro sin
     coordenada la MEDIA de las coordenadas REALES de su subcircuito. Como la
     media no es robusta, un único punto con el signo invertido desplaza el
     centroide cientos de km y ese centroide erróneo se hereda a TODOS los
     registros imputados del subcircuito. Tras corregir el signo, la media
     vuelve a ser válida: se recalcula el centroide y se reasignan los IMPUTADO.

El archivo se lee y se escribe en latin-1 (round-trip de bytes sin pérdida) y
solo se reescriben las celdas de coordenadas (ASCII puro); el resto del archivo
—incluidos los nombres con acentos— queda byte a byte idéntico.

Uso:
    python reparar_coordenadas.py            # --check: solo reporta, no escribe
    python reparar_coordenadas.py --fix      # corrige y guarda (crea backup .bak)
"""
from __future__ import annotations

import shutil
import sys
from datetime import datetime
from pathlib import Path

CSV_PATH = (
    Path(__file__).resolve().parent.parent
    / "data"
    / "mdi_detenidosaprehendidos_guayaquil_2019_2025_con_delitos_y_tipo_dato.csv"
)

# Bounding box generoso del cantón Guayaquil (incluye zonas rurales e insulares
# como Puná, Morro y Progreso). Cualquier coordenada fuera de aquí es un error
# grueso de georreferenciación, no dispersión legítima.
LAT_MIN, LAT_MAX = -3.30, -1.80
LNG_MIN, LNG_MAX = -80.60, -79.55

SEP = ";"


def _in_bbox(lat: float, lng: float) -> bool:
    return LAT_MIN <= lat <= LAT_MAX and LNG_MIN <= lng <= LNG_MAX


def main(fix: bool) -> int:
    raw = CSV_PATH.read_text(encoding="latin-1")
    lines = raw.split("\n")
    cols = [c.rstrip("\r") for c in lines[0].split(SEP)]
    LAT = cols.index("latitud")
    LNG = cols.index("longitud")
    SUB = cols.index("codigo_subcircuito")
    FLAG = cols.index("flag_coord")

    # Parsear filas de datos (conservando el índice en `lines` para reescribir).
    records: list[tuple[int, list[str]]] = []
    for i in range(1, len(lines)):
        if lines[i] == "":
            continue  # línea en blanco (p. ej. salto final) — se conserva intacta
        records.append((i, lines[i].split(SEP)))

    # ── PASO 1 — corregir el signo de los REAL invertidos ────────────────────
    inverted: list[str] = []
    real_coords: dict[str, list[tuple[float, float]]] = {}
    for _, f in records:
        if f[FLAG].rstrip("\r") != "REAL":
            continue
        lat, lng = float(f[LAT]), float(f[LNG])
        if lat > 0 or lng > 0:
            new_lat, new_lng = -abs(lat), -abs(lng)
            inverted.append(
                f"  {f[SUB]} {f[LAT]},{f[LNG]} -> {new_lat},{new_lng}"
            )
            lat, lng = new_lat, new_lng
            if fix:
                f[LAT] = repr(lat)
                f[LNG] = repr(lng)
        real_coords.setdefault(f[SUB], []).append((lat, lng))

    # ── PASO 2 — recalcular centroide (media) de los subcircuitos afectados ──
    affected = {s for line in inverted for s in [line.split()[0]]}
    centroids: dict[str, tuple[float, float]] = {}
    for sub in affected:
        pts = real_coords.get(sub, [])
        centroids[sub] = (
            sum(p[0] for p in pts) / len(pts),
            sum(p[1] for p in pts) / len(pts),
        )

    # ── PASO 3 — detectar / reasignar centroides IMPUTADO fuera del bbox ─────
    bad_imputed: dict[str, int] = {}
    reassigned = 0
    for _, f in records:
        if f[FLAG].rstrip("\r") != "IMPUTADO":
            continue
        lat, lng = float(f[LAT]), float(f[LNG])
        if not _in_bbox(lat, lng):
            bad_imputed[f[SUB]] = bad_imputed.get(f[SUB], 0) + 1
            if fix and f[SUB] in centroids:
                clat, clng = centroids[f[SUB]]
                f[LAT] = repr(clat)
                f[LNG] = repr(clng)
                reassigned += 1

    # ── Reporte ──────────────────────────────────────────────────────────────
    print(f"Archivo: {CSV_PATH.name}")
    print(f"Filas de datos: {len(records)}\n")
    print(f"REAL con signo invertido: {len(inverted)}")
    for line in inverted:
        print(line)
    print(f"\nCentroides IMPUTADO fuera del bbox: "
          f"{sum(bad_imputed.values())} filas en {len(bad_imputed)} subcircuito(s)")
    for sub, n in bad_imputed.items():
        c = centroids.get(sub)
        c_txt = f" -> nuevo centroide {c[0]:.10f},{c[1]:.10f}" if c else ""
        print(f"  {sub}: {n} filas{c_txt}")

    if not fix:
        if inverted or bad_imputed:
            print("\n[CHECK] Se detectaron problemas. Ejecuta con --fix para corregir.")
            return 1
        print("\n[CHECK] Sin problemas de georreferenciación.")
        return 0

    # ── Escritura (con backup) ────────────────────────────────────────────────
    for i, f in records:
        lines[i] = SEP.join(f)
    backup = CSV_PATH.with_suffix(
        CSV_PATH.suffix + f".{datetime.now():%Y%m%d_%H%M%S}.bak"
    )
    shutil.copy2(CSV_PATH, backup)
    CSV_PATH.write_text("\n".join(lines), encoding="latin-1")
    print(f"\n[FIX] Signos corregidos: {len(inverted)}  |  IMPUTADO reasignados: {reassigned}")
    print(f"[FIX] Backup del original: {backup.name}")
    print(f"[FIX] Archivo reparado guardado: {CSV_PATH.name}")
    return 0


if __name__ == "__main__":
    sys.exit(main(fix="--fix" in sys.argv[1:]))
