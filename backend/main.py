import json
import os
from contextlib import asynccontextmanager
from pathlib import Path

import joblib
import pandas as pd
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse

import state
from schemas import HealthResponse
from routers import predict, zones, incidents, top_delitos

BASE_DIR       = Path(__file__).parent
MODEL_PATH     = BASE_DIR / "model" / "modelo_final.pkl"
ENCODERS_PATH  = BASE_DIR / "model" / "encoders.pkl"
DATA_PATH      = BASE_DIR / "data" / "subcircuitos.csv"
DATA_DIR       = BASE_DIR / "data"
INCIDENTS_PATH = BASE_DIR / "data" / "mdi_detenidosaprehendidos_guayaquil_2019_2025_con_delitos_y_tipo_dato.csv"


def _load_json(path: Path) -> dict | list:
    """Lee JSON tolerando archivos guardados en UTF-8 o en Latin-1/CP1252
    (varios labels traen acentos en codificación Windows)."""
    raw = path.read_bytes()
    for enc in ("utf-8-sig", "utf-8", "latin-1"):
        try:
            return json.loads(raw.decode(enc))
        except (UnicodeDecodeError, json.JSONDecodeError):
            continue
    return json.loads(raw.decode("latin-1", errors="replace"))

# macro_lugar and flag_coord values from the actual training dataset
_MACRO_VALUES = sorted([
    'COMERCIO_SERVICIOS', 'CPL', 'ESPACIO_PUBLICO',
    'INSTITUCION', 'OTRO', 'TRANSPORTE', 'VIVIENDA_PRIVADA',
])
_FLAG_VALUES = sorted(['IMPUTADO', 'REAL'])


def _load_incidents() -> pd.DataFrame:
    """Carga el histórico MDI y lo deja listo para agregaciones rápidas.
    Solo conserva columnas-código + delito legible + hora entera. Las etiquetas
    se derivan de los label maps (limpios), no del texto del CSV (mojibake)."""
    usecols = [
        "codigo_iccs", "codigo_distrito", "codigo_circuito",
        "codigo_subcircuito", "hora_detencion_aprehension",
    ]
    df = pd.read_csv(INCIDENTS_PATH, sep=";", encoding="latin-1", usecols=usecols)

    # codigo_iccs llega como float → join por valor float contra los labels
    icc_by_float = {float(k): v for k, v in state.iccs_labels.items()}
    df["delito"] = df["codigo_iccs"].map(
        lambda x: icc_by_float.get(float(x), "Otros delitos")
        if pd.notna(x) else "Otros delitos"
    )

    df["hora"] = pd.to_datetime(
        df["hora_detencion_aprehension"], format="%H:%M:%S", errors="coerce"
    ).dt.hour
    df = df.dropna(subset=["hora"])
    df["hora"] = df["hora"].astype(int)

    return df[["delito", "codigo_distrito", "codigo_circuito", "codigo_subcircuito", "hora"]]


@asynccontextmanager
async def lifespan(app: FastAPI):
    # ── Model & encoders ──────────────────────────────────────────────────────
    state.model    = joblib.load(MODEL_PATH)
    state.encoders = joblib.load(ENCODERS_PATH)
    state.zones_df = pd.read_csv(DATA_PATH)

    # ── Geographic pre-encoding maps (alphabetical sort = same as LabelEncoder at training) ──
    sorted_subs      = sorted(state.zones_df['codigo_subcircuito'].unique())
    sorted_circuits  = sorted(state.zones_df['codigo_circuito'].unique())
    sorted_districts = sorted(state.zones_df['codigo_distrito'].unique())

    state.idx_subcircuito = {c: str(i) for i, c in enumerate(sorted_subs)}
    state.idx_circuito    = {c: str(i) for i, c in enumerate(sorted_circuits)}
    state.idx_distrito    = {c: str(i) for i, c in enumerate(sorted_districts)}
    state.idx_macro_lugar = {v: str(i) for i, v in enumerate(_MACRO_VALUES)}
    state.idx_flag_coord  = {v: str(i) for i, v in enumerate(_FLAG_VALUES)}

    # ── Label maps (acentos en Latin-1/CP1252; se decodifican correctamente) ──
    state.iccs_labels     = _load_json(DATA_DIR / "iccs_labels.json")
    state.district_labels = _load_json(DATA_DIR / "district_labels.json")
    state.circuit_labels  = _load_json(DATA_DIR / "circuit_labels.json")
    state.delito_options  = _load_json(DATA_DIR / "options_delitos.json")

    # ── ICCS pre-encoding map (string repr of float → alphabetical index str) ─
    sorted_iccs = sorted(state.iccs_labels.keys())
    state.idx_iccs = {c: str(i) for i, c in enumerate(sorted_iccs)}

    # ── Historical incidents → in-memory aggregate for the summary tables ─────
    state.incidents_df = _load_incidents()

    yield

    state.model        = None
    state.encoders     = {}
    state.zones_df     = None
    state.incidents_df = None


app = FastAPI(
    title="Sistema Predictivo de Incidentes Delictivos — Guayaquil",
    version="1.0.0",
    lifespan=lifespan,
)

# Con un solo servicio (frontend y API en el mismo origen) CORS no es necesario.
# Se deja configurable por si se usa `ng serve` local (:4200) o un frontend aparte:
# la variable de entorno ALLOWED_ORIGINS admite orígenes separados por coma.
_env_origins = os.getenv("ALLOWED_ORIGINS", "")
ALLOWED_ORIGINS = (
    [o.strip() for o in _env_origins.split(",") if o.strip()]
    if _env_origins
    else ["http://localhost:4200"]
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(zones.router,       prefix="/api")
app.include_router(predict.router,     prefix="/api")
app.include_router(incidents.router,   prefix="/api")
app.include_router(top_delitos.router, prefix="/api")


@app.get("/api/health", response_model=HealthResponse, tags=["health"])
def health():
    return HealthResponse(status="ok", model_loaded=state.model is not None)


@app.get("/api/options", tags=["options"])
def options():
    """Returns human-readable filter options for the frontend."""
    rangos = [
        {"label": f"{h:02d}:00–{(h+1)%24:02d}:00", "value": h}
        for h in range(24)
    ]
    # Friendly hour labels
    def hl(h):
        s = "AM" if h < 12 else "PM"
        n = "AM" if (h+1) < 12 else "PM"
        return f"{h%12 or 12:02d}{s}–{(h+1)%12 or 12:02d}{n}"
    rangos_hr = [{"label": hl(h), "value": h} for h in range(24)]

    distritos = [
        {"label": state.district_labels.get(k, k), "value": k}
        for k in sorted(state.zones_df["codigo_distrito"].unique())
    ]
    circuitos = [
        {
            "label": state.circuit_labels.get(k, k),
            "value": k,
            "distrito": state.zones_df.loc[
                state.zones_df["codigo_circuito"] == k, "codigo_distrito"
            ].iloc[0],
        }
        for k in sorted(state.zones_df["codigo_circuito"].unique())
    ]
    subcircuitos = [
        {
            "label": row["nombre_subcircuito"],
            "value": row["codigo_subcircuito"],
            "circuito": row["codigo_circuito"],
        }
        for _, row in state.zones_df.sort_values("nombre_subcircuito").iterrows()
    ]

    return {
        "delitos": state.delito_options,
        "distritos": distritos,
        "circuitos": circuitos,
        "subcircuitos": subcircuitos,
        "rangos_horarios": rangos_hr,
    }


@app.get("/api/metadata", tags=["metadata"])
def metadata():
    return {
        "distritos": {k: state.district_labels.get(k, k)
                      for k in sorted(state.zones_df["codigo_distrito"].unique())},
        "circuitos": state.circuit_labels,
        "iccs_labels": state.iccs_labels,
    }


# ──────────────────────────────────────────────────────────────────────────────
# Frontend Angular compilado (en Docker / Hugging Face Spaces)
# El Dockerfile copia el build de Angular a ./static. Si esa carpeta existe,
# servimos sus archivos y hacemos fallback a index.html para el routing del SPA.
# Las rutas /api/*, /docs y /openapi.json se registran ANTES, así que mantienen
# prioridad sobre este catch-all. En local (sin ./static) el bloque se omite y
# el backend funciona como API pura (el frontend corre con `ng serve`).
# ──────────────────────────────────────────────────────────────────────────────
FRONTEND_DIR = BASE_DIR / "static"

if FRONTEND_DIR.is_dir():

    @app.get("/{full_path:path}", include_in_schema=False)
    async def serve_spa(full_path: str):
        candidate = (FRONTEND_DIR / full_path).resolve()
        # Servir el archivo solicitado si existe y está dentro de ./static
        if (
            full_path
            and FRONTEND_DIR.resolve() in candidate.parents
            and candidate.is_file()
        ):
            return FileResponse(candidate)
        # Cualquier otra ruta -> index.html (la maneja el router de Angular)
        return FileResponse(FRONTEND_DIR / "index.html")
