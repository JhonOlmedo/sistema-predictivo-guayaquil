"""Validación de los centroides de subcircuitos.csv contra el GROUND TRUTH del
Ministerio del Interior (CMI 2019-2022, coordenadas reales por incidente).

El CSV de zonas guarda UN punto (centroide) por subcircuito; ese punto solo se
usa para DIBUJAR en el mapa (el modelo predice con los códigos + freq, no con
lat/lng). Este script confirma que cada centroide cae donde realmente ocurren
los incidentes, comparándolo con la MEDIANA de las coordenadas reales del MDI
(la mediana es robusta a los pocos puntos con error de captura).

Para cada subcircuito calcula:
  • n            — incidentes reales con coordenada válida.
  • radio_med_m  — dispersión: distancia mediana de los incidentes a su mediana.
                   Chico = barrio compacto; enorme = zona repartida en km (islas).
  • dist_m       — error: distancia del centroide guardado a la mediana real.

Y clasifica:
  • RURAL/DISPERSO — radio grande o n<5: el centroide es difuso por naturaleza
                     (Puná, Progreso, Morro…). No es un bug; suelen ser es_rural.
  • URBANO CORRIDO — cluster compacto pero centroide lejos (>700 m): BUG real.
  • intermedio     — error 400-700 m.
  • ok             — error <=400 m.

Uso:
    python validar_coordenadas_mdi.py [ruta_al_xlsx]
    (por defecto busca CMI_2019_2022_unificado.xlsx en el directorio actual;
     ese archivo de ground truth no se distribuye con el repositorio)
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

DEFAULT_XLSX = Path("CMI_2019_2022_unificado.xlsx")
SHEET = "CMI_2019_2022"
CSV = Path(__file__).resolve().parent.parent / "data" / "subcircuitos.csv"

# Caja generosa de la costa de Guayas; fuera de aquí = error de geocodificación.
LAT_MIN, LAT_MAX = -3.5, -1.5
LNG_MIN, LNG_MAX = -81.0, -79.0


def haversine_m(lat1, lon1, lat2, lon2):
    R = 6371000.0
    p1, p2 = np.radians(lat1), np.radians(lat2)
    dp, dl = np.radians(lat2 - lat1), np.radians(lon2 - lon1)
    a = np.sin(dp / 2) ** 2 + np.cos(p1) * np.cos(p2) * np.sin(dl / 2) ** 2
    return 2 * R * np.arcsin(np.sqrt(a))


def _agg(g):
    mlat, mlng = g["lat"].median(), g["lng"].median()
    r = haversine_m(g["lat"].values, g["lng"].values, mlat, mlng)
    return pd.Series({"n": len(g), "real_lat": mlat, "real_lng": mlng,
                      "radio_med_m": float(np.median(r))})


def _tipo(r):
    if r["radio_med_m"] >= 1200 or r["n"] < 5:
        return "RURAL/DISPERSO"
    if r["dist_m"] > 700:
        return "URBANO CORRIDO"
    if r["dist_m"] > 400:
        return "intermedio"
    return "ok"


def main(xlsx: Path) -> int:
    if not xlsx.exists():
        print(f"[ERROR] No se encontró el ground truth: {xlsx}")
        print("Pásalo como argumento: python validar_coordenadas_mdi.py <ruta.xlsx>")
        return 2

    mdi = pd.read_excel(xlsx, sheet_name=SHEET, engine="openpyxl",
                        usecols=["cod_subcir", "latitud", "longitud"])
    mdi["cod_subcir"] = mdi["cod_subcir"].astype(str).str.strip()
    mdi["lat"] = pd.to_numeric(mdi["latitud"], errors="coerce")
    mdi["lng"] = pd.to_numeric(mdi["longitud"], errors="coerce")
    mdi = mdi[mdi["lat"].between(LAT_MIN, LAT_MAX) & mdi["lng"].between(LNG_MIN, LNG_MAX)]

    real = mdi.groupby("cod_subcir").apply(_agg, include_groups=False).reset_index()

    csv = pd.read_csv(CSV)
    csv["codigo_subcircuito"] = csv["codigo_subcircuito"].astype(str).str.strip()
    m = csv.merge(real, left_on="codigo_subcircuito", right_on="cod_subcir", how="inner")
    m["dist_m"] = haversine_m(m["lat"].values, m["lng"].values,
                              m["real_lat"].values, m["real_lng"].values)
    m["n"] = m["n"].astype(int)
    m["tipo"] = m.apply(_tipo, axis=1)

    print(f"Ground truth: {xlsx.name}  ({len(mdi)} incidentes válidos)")
    print(f"Centroides validados: {len(m)} / {len(csv)}\n")
    print("=== CLASIFICACIÓN ===")
    print(m["tipo"].value_counts().to_string())
    print(f"\nerror mediano: {m['dist_m'].median():.0f} m | "
          f"medio: {m['dist_m'].mean():.0f} m | p90: {m['dist_m'].quantile(.9):.0f} m")

    for t in ("URBANO CORRIDO", "intermedio", "RURAL/DISPERSO"):
        sub = m[m["tipo"] == t].sort_values("dist_m", ascending=False)
        print(f"\n=== {t} ({len(sub)}) ===")
        print(sub[["codigo_subcircuito", "nombre_subcircuito", "es_rural",
                   "n", "radio_med_m", "dist_m"]]
              .to_string(index=False,
                         formatters={"radio_med_m": "{:.0f}".format,
                                     "dist_m": "{:.0f}".format}))

    out = Path(__file__).resolve().parent / "reporte_validacion_coordenadas.csv"
    m.sort_values("dist_m", ascending=False)[
        ["codigo_subcircuito", "nombre_subcircuito", "es_rural", "lat", "lng",
         "real_lat", "real_lng", "n", "radio_med_m", "dist_m", "tipo"]
    ].to_csv(out, index=False)
    print(f"\n[reporte completo -> {out.name}]")
    return 0


if __name__ == "__main__":
    arg = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_XLSX
    sys.exit(main(arg))
