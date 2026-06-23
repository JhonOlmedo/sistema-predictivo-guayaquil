# ──────────────────────────────────────────────────────────────────────────────
# Stage 1 — Compila el frontend Angular a archivos estáticos
# ──────────────────────────────────────────────────────────────────────────────
FROM node:20-alpine AS frontend
WORKDIR /app/frontend

# Dependencias primero (capa cacheable mientras no cambie package-lock.json)
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci

# Código y build en modo producción (usa environment.prod.ts -> apiUrl '/api')
COPY frontend/ ./
RUN npm run build

# ──────────────────────────────────────────────────────────────────────────────
# Stage 2 — Backend FastAPI que ademas sirve el frontend compilado
# ──────────────────────────────────────────────────────────────────────────────
FROM python:3.12-slim AS backend
WORKDIR /app

# libgomp1: biblioteca OpenMP que LightGBM necesita en Debian slim
RUN apt-get update \
    && apt-get install -y --no-install-recommends libgomp1 \
    && rm -rf /var/lib/apt/lists/*

# Dependencias Python primero (capa cacheable)
COPY backend/requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# Código del backend (incluye model/*.pkl y data/*.csv, horneados en la imagen)
COPY backend/ ./

# Frontend ya compilado -> carpeta ./static que main.py detecta y sirve
COPY --from=frontend /app/frontend/dist/frontend/browser ./static

# Hugging Face Spaces espera el servicio en el puerto 7860
ENV PORT=7860
EXPOSE 7860

CMD ["sh", "-c", "uvicorn main:app --host 0.0.0.0 --port ${PORT:-7860}"]
