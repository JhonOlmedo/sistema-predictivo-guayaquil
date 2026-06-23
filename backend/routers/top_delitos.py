"""Tabla resumen — 10 delitos más frecuentes (datos históricos MDI 2019–2025).

La fuente es `state.incidents_df`, agregada en memoria. Respeta los filtros
geográficos (distrito / circuito / subcircuito) y la hora. El nombre del delito
se agrupa por etiqueta legible (varios códigos ICCS comparten nombre)."""
from fastapi import APIRouter

import state
from schemas import TopDelitoItem, TopDelitosRequest, TopDelitosResponse

router = APIRouter(tags=["top-delitos"])

TOP_N = 10


def _filter(df, req: TopDelitosRequest):
    if req.codigo_subcircuito_filtro:
        df = df[df["codigo_subcircuito"] == req.codigo_subcircuito_filtro]
    elif req.codigo_circuito:
        df = df[df["codigo_circuito"] == req.codigo_circuito]
    elif req.codigo_distrito:
        df = df[df["codigo_distrito"] == req.codigo_distrito]
    if req.hora is not None:
        df = df[df["hora"] == req.hora]
    return df


@router.post("/top-delitos", response_model=TopDelitosResponse)
def top_delitos(req: TopDelitosRequest):
    df = state.incidents_df
    if df is None or df.empty:
        return TopDelitosResponse(items=[], total=0)

    df = _filter(df, req)
    total = int(len(df))
    if total == 0:
        return TopDelitosResponse(items=[], total=0)

    counts = df["delito"].value_counts().head(TOP_N)

    items: list[TopDelitoItem] = []
    for delito, freq in counts.items():
        sub = df[df["delito"] == delito]
        dom_code = sub["codigo_distrito"].value_counts().idxmax()
        dom_name = state.district_labels.get(dom_code, dom_code)
        items.append(TopDelitoItem(
            delito=str(delito),
            frecuencia=int(freq),
            distrito_predominante=dom_name,
            distrito_codigo=str(dom_code),
            porcentaje=round(int(freq) / total * 100, 1),
        ))

    return TopDelitosResponse(items=items, total=total)
