import numpy as np
from fastapi import APIRouter, HTTPException

import state
from schemas import (
    BatchPredictRequest, PredictRequest, PredictResponse,
    StatsRequest, StatsResponse, HourlyStat, ZonePrediction,
)

router = APIRouter(tags=["predict"])

MAPA_CLASES = {0: "BAJA", 1: "MEDIA", 2: "ALTA", 3: "CRITICA"}

FEATURES = [
    "anio", "mes", "dia_semana", "es_fin_de_semana", "hora",
    "codigo_distrito", "codigo_circuito", "codigo_subcircuito",
    "freq_subcircuito", "codigo_iccs", "macro_lugar", "flag_coord",
]
CAT_COLS = {
    "codigo_distrito", "codigo_circuito", "codigo_subcircuito",
    "codigo_iccs", "macro_lugar", "flag_coord",
}

# ── Encoding helpers ──────────────────────────────────────────────────────────

def _pre(col: str, original: str) -> str:
    """Convert original string → pre-encoded integer string (alphabetical index)."""
    maps = {
        "codigo_subcircuito": state.idx_subcircuito,
        "codigo_circuito":    state.idx_circuito,
        "codigo_distrito":    state.idx_distrito,
        "macro_lugar":        state.idx_macro_lugar,
        "flag_coord":         state.idx_flag_coord,
        "codigo_iccs":        state.idx_iccs,
    }
    return maps[col].get(original, "0")


def _encode(col: str, val: str) -> int:
    pre = _pre(col, val)
    return int(state.encoders[col].transform([pre])[0])


def _build_vector(raw: dict) -> list:
    row = []
    for col in FEATURES:
        val = raw[col]
        if col in CAT_COLS:
            val = _encode(col, str(val))
        row.append(val)
    return row


def _peligrosidad(proba: np.ndarray) -> float:
    return round(
        (0 * proba[0] + 1 * proba[1] + 2 * proba[2] + 3 * proba[3]) / 3 * 100, 2
    )


def _filter_df(codigo_distrito, codigo_circuito, codigo_subcircuito_filtro):
    df = state.zones_df
    if codigo_distrito:
        df = df[df["codigo_distrito"] == codigo_distrito]
    if codigo_circuito:
        df = df[df["codigo_circuito"] == codigo_circuito]
    if codigo_subcircuito_filtro:
        df = df[df["codigo_subcircuito"] == codigo_subcircuito_filtro]
    # Sin fallback: si la combinación de filtros no coincide con nada, devolvemos
    # el resultado vacío tal cual. El antiguo `else state.zones_df` enmascaraba
    # filtros inválidos devolviendo TODAS las zonas (mezclando distritos); el
    # frontend ya maneja el caso vacío mostrando "sin datos".
    return df


def _base_raw(zone, hora, mes, anio, dia_semana, es_fin_de_semana, codigo_iccs, macro_lugar):
    return {
        "anio": anio, "mes": mes, "dia_semana": dia_semana,
        "es_fin_de_semana": es_fin_de_semana, "hora": hora,
        "codigo_distrito":    zone["codigo_distrito"],
        "codigo_circuito":    zone["codigo_circuito"],
        "codigo_subcircuito": zone["codigo_subcircuito"],
        "freq_subcircuito":   int(zone["freq_subcircuito"]),
        "codigo_iccs":  codigo_iccs,
        "macro_lugar":  macro_lugar,
        "flag_coord":   "IMPUTADO",
    }


# ── POST /predict ─────────────────────────────────────────────────────────────

@router.post("/predict", response_model=PredictResponse)
def predict(req: PredictRequest):
    match = state.zones_df[state.zones_df["codigo_subcircuito"] == req.codigo_subcircuito]
    if match.empty:
        raise HTTPException(404, detail=f"Subcircuito '{req.codigo_subcircuito}' no encontrado")

    zone = match.iloc[0]
    raw  = _base_raw(zone, req.hora, req.mes, req.anio, req.dia_semana,
                     req.es_fin_de_semana, req.codigo_iccs, req.macro_lugar)
    try:
        vector = _build_vector(raw)
    except ValueError as e:
        raise HTTPException(422, detail=str(e))

    proba         = state.model.predict_proba(np.array([vector]))[0]
    gravedad_code = int(np.argmax(proba))
    return PredictResponse(
        gravedad=MAPA_CLASES[gravedad_code],
        gravedad_codigo=gravedad_code,
        probabilidades={MAPA_CLASES[i]: round(float(p), 4) for i, p in enumerate(proba)},
        peligrosidad=_peligrosidad(proba),
        subcircuito=req.codigo_subcircuito,
    )


# ── POST /predict/batch ───────────────────────────────────────────────────────

@router.post("/predict/batch", response_model=list[ZonePrediction])
def predict_batch(req: BatchPredictRequest):
    df = _filter_df(req.codigo_distrito, req.codigo_circuito, req.codigo_subcircuito_filtro)

    vectors, valid_zones = [], []
    for _, zone in df.iterrows():
        raw = _base_raw(zone, req.hora, req.mes, req.anio, req.dia_semana,
                        req.es_fin_de_semana, req.codigo_iccs, req.macro_lugar)
        try:
            vectors.append(_build_vector(raw))
            valid_zones.append(zone)
        except ValueError:
            continue

    if not vectors:
        return []

    probas  = state.model.predict_proba(np.array(vectors))
    results = []
    for zone, proba in zip(valid_zones, probas):
        gc = int(np.argmax(proba))
        results.append(ZonePrediction(
            codigo_subcircuito=zone["codigo_subcircuito"],
            nombre=zone["nombre_subcircuito"],
            lat=float(zone["lat"]),
            lng=float(zone["lng"]),
            peligrosidad=_peligrosidad(proba),
            gravedad=MAPA_CLASES[gc],
            parroquia=str(zone.get("parroquia", "") or ""),
            es_rural=bool(zone.get("es_rural", 0)),
        ))
    return results


# ── POST /predict/stats ───────────────────────────────────────────────────────

@router.post("/predict/stats", response_model=StatsResponse)
def predict_stats(req: StatsRequest):
    df = _filter_df(req.codigo_distrito, req.codigo_circuito, req.codigo_subcircuito_filtro)

    all_vectors, hour_map = [], []
    for hora in range(24):
        for _, zone in df.iterrows():
            raw = _base_raw(zone, hora, req.mes, req.anio, req.dia_semana,
                            req.es_fin_de_semana, req.codigo_iccs, req.macro_lugar)
            try:
                all_vectors.append(_build_vector(raw))
                hour_map.append(hora)
            except ValueError:
                pass

    if not all_vectors:
        return StatsResponse(hourly=[], by_gravedad={}, total_zonas=0, peligrosidad_media=0)

    probas        = state.model.predict_proba(np.array(all_vectors))
    peligrosidades = [_peligrosidad(p) for p in probas]
    gravedades     = [MAPA_CLASES[int(np.argmax(p))] for p in probas]

    hora_sums: dict[int, list[float]] = {h: [] for h in range(24)}
    for h, pel in zip(hour_map, peligrosidades):
        hora_sums[h].append(pel)

    hourly = [
        HourlyStat(hora=h, peligrosidad=round(sum(v) / len(v), 2) if v else 0.0)
        for h, v in sorted(hora_sums.items())
    ]

    # Distribution at the selected hour across all filtered zones
    by_gravedad: dict[str, int] = {"BAJA": 0, "MEDIA": 0, "ALTA": 0, "CRITICA": 0}
    for h, g in zip(hour_map, gravedades):
        if h == req.hora:
            by_gravedad[g] = by_gravedad.get(g, 0) + 1

    avg_pel = round(sum(peligrosidades) / len(peligrosidades), 2) if peligrosidades else 0.0

    return StatsResponse(
        hourly=hourly,
        by_gravedad=by_gravedad,
        total_zonas=len(df),
        peligrosidad_media=avg_pel,
    )
