---
title: Sistema Predictivo de Incidentes - Guayaquil
emoji: 🗺️
colorFrom: blue
colorTo: red
sdk: docker
app_port: 7860
pinned: false
---

# Sistema Web Geoespacial para Predicción de Incidentes Delictivos en Guayaquil

Aplicación que predice y visualiza la **gravedad delictiva por zona geográfica** en
Guayaquil (Ecuador) usando un modelo **LightGBM** entrenado con registros del
Ministerio del Interior (2019–2025). Un único servicio **FastAPI** sirve la API y
el frontend **Angular** ya compilado, en la misma URL.

## Arquitectura

- **Backend:** FastAPI + LightGBM. La API vive bajo el prefijo `/api`
  (estado en `/api/health`).
- **Frontend:** Angular + Leaflet, servido como estáticos por el propio backend.
- **Despliegue:** imagen Docker multi-stage (Node compila Angular → Python lo sirve).

## Contexto académico

Trabajo de titulación — Universidad Politécnica Salesiana, Sede Guayaquil,
Carrera de Computación. Metodología CRISP-DM; modelo ganador LightGBM con SHAP.
