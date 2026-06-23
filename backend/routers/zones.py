from fastapi import APIRouter

import state
from schemas import Zone

router = APIRouter(tags=["zones"])


@router.get("/zones", response_model=list[Zone])
def get_zones():
    return [
        Zone(
            codigo_subcircuito=row["codigo_subcircuito"],
            nombre=row["nombre_subcircuito"],
            codigo_circuito=row["codigo_circuito"],
            codigo_distrito=row["codigo_distrito"],
            lat=float(row["lat"]),
            lng=float(row["lng"]),
            freq_subcircuito=int(row["freq_subcircuito"]),
            parroquia=str(row.get("parroquia", "") or ""),
            es_rural=bool(row.get("es_rural", 0)),
        )
        for _, row in state.zones_df.iterrows()
    ]
