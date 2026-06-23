from typing import Literal, Optional
from pydantic import BaseModel, Field


# ── Predict ──────────────────────────────────────────────────────────────────

class PredictRequest(BaseModel):
    anio: int = Field(..., ge=2019, le=2030)
    mes: int = Field(..., ge=1, le=12)
    dia_semana: int = Field(..., ge=0, le=6)
    es_fin_de_semana: Literal[0, 1]
    hora: int = Field(..., ge=0, le=23)
    codigo_subcircuito: str
    codigo_iccs: str
    macro_lugar: Literal[
        "ESPACIO_PUBLICO","VIVIENDA_PRIVADA","COMERCIO_SERVICIOS",
        "TRANSPORTE","INSTITUCIONAL","OTRO",
    ]


class PredictResponse(BaseModel):
    gravedad: str
    gravedad_codigo: int
    probabilidades: dict[str, float]
    peligrosidad: float
    subcircuito: str


# ── Batch predict ─────────────────────────────────────────────────────────────

class BatchPredictRequest(BaseModel):
    hora: int = Field(..., ge=0, le=23)
    mes: int = Field(..., ge=1, le=12)
    anio: int = Field(..., ge=2019, le=2030)
    dia_semana: int = Field(..., ge=0, le=6)
    es_fin_de_semana: Literal[0, 1]
    macro_lugar: str = "ESPACIO_PUBLICO"
    codigo_iccs: str
    # Filtros geográficos opcionales
    codigo_distrito: Optional[str] = None
    codigo_circuito: Optional[str] = None
    codigo_subcircuito_filtro: Optional[str] = None


class ZonePrediction(BaseModel):
    codigo_subcircuito: str
    nombre: str
    lat: float
    lng: float
    peligrosidad: float
    gravedad: str
    parroquia: str = ""
    es_rural: bool = False


# ── Stats ─────────────────────────────────────────────────────────────────────

class StatsRequest(BaseModel):
    hora: int = Field(..., ge=0, le=23)
    mes: int = Field(..., ge=1, le=12)
    anio: int = Field(..., ge=2019, le=2030)
    dia_semana: int = Field(..., ge=0, le=6)
    es_fin_de_semana: Literal[0, 1]
    macro_lugar: str = "ESPACIO_PUBLICO"
    codigo_iccs: str
    codigo_distrito: Optional[str] = None
    codigo_circuito: Optional[str] = None
    codigo_subcircuito_filtro: Optional[str] = None


class HourlyStat(BaseModel):
    hora: int
    peligrosidad: float


class StatsResponse(BaseModel):
    hourly: list[HourlyStat]
    by_gravedad: dict[str, int]
    total_zonas: int
    peligrosidad_media: float


# ── Top delitos (tabla resumen, datos históricos) ──────────────────────────────

class TopDelitosRequest(BaseModel):
    """Filtros geográficos / horarios. El filtro de delito NO aplica aquí
    (la tabla justamente lista los delitos)."""
    codigo_distrito: Optional[str] = None
    codigo_circuito: Optional[str] = None
    codigo_subcircuito_filtro: Optional[str] = None
    hora: Optional[int] = Field(None, ge=0, le=23)


class TopDelitoItem(BaseModel):
    delito: str
    frecuencia: int
    distrito_predominante: str
    distrito_codigo: str
    porcentaje: float


class TopDelitosResponse(BaseModel):
    items: list[TopDelitoItem]
    total: int


# ── Zones ─────────────────────────────────────────────────────────────────────

class Zone(BaseModel):
    codigo_subcircuito: str
    nombre: str
    codigo_circuito: str
    codigo_distrito: str
    lat: float
    lng: float
    freq_subcircuito: int
    parroquia: str = ""
    es_rural: bool = False


# ── Incidents ─────────────────────────────────────────────────────────────────

class Incident(BaseModel):
    codigo_subcircuito: str
    lat: float
    lng: float
    total_incidentes: int
    peligrosidad_media: float


# ── Health ────────────────────────────────────────────────────────────────────

class HealthResponse(BaseModel):
    status: str
    model_loaded: bool
