from fastapi import APIRouter

import state
from schemas import Incident

router = APIRouter(tags=["incidents"])


@router.get("/incidents", response_model=list[Incident])
def get_incidents():
    df = state.zones_df
    max_freq = float(df["freq_subcircuito"].max())

    return [
        Incident(
            codigo_subcircuito=row["codigo_subcircuito"],
            lat=float(row["lat"]),
            lng=float(row["lng"]),
            total_incidentes=int(row["freq_subcircuito"]),
            peligrosidad_media=round(row["freq_subcircuito"] / max_freq * 100, 2),
        )
        for _, row in df.iterrows()
    ]
