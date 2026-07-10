---
title: Sistema Predictivo de Incidentes - Guayaquil
emoji: 🗺️
colorFrom: blue
colorTo: red
sdk: docker
app_port: 7860
pinned: false
---

# Sistema Web Geoespacial para la Predicción de Incidentes Delictivos en Guayaquil

![Python](https://img.shields.io/badge/Python-3.12-3776AB?logo=python&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-0.111-009688?logo=fastapi&logoColor=white)
![Angular](https://img.shields.io/badge/Angular-19-DD0031?logo=angular&logoColor=white)
![LightGBM](https://img.shields.io/badge/LightGBM-4.5-9ACD32)
![Leaflet](https://img.shields.io/badge/Leaflet-1.9-199900?logo=leaflet&logoColor=white)
![Docker](https://img.shields.io/badge/Docker-monolito-2496ED?logo=docker&logoColor=white)
![Licencia](https://img.shields.io/badge/Licencia-Uso%20acad%C3%A9mico-lightgrey)

Aplicación web que estima y visualiza la gravedad delictiva esperada por zona
geográfica en Guayaquil (Ecuador). La estimación está condicionada a los registros
institucionales de detenciones y aprehensiones del Ministerio del Interior del
período 2019-2025, y se apoya en un modelo de aprendizaje automático (LightGBM). El
resultado se presenta como un mapa de calor por subcircuito y como un índice de
peligrosidad de 0 a 100 % para la consulta que arme el usuario (hora, fecha, zona,
tipo de delito y tipo de lugar).

El sistema no predice hechos individuales ni señala personas. Dada una consulta,
devuelve la probabilidad de cada uno de cuatro niveles de gravedad (baja, media,
alta y crítica) para una zona y unas condiciones dadas, y traduce esa distribución
en un valor de riesgo relativo comprensible para un usuario no técnico.

## Despliegue en vivo

El sistema está desplegado como un Space público en Hugging Face:

**https://huggingface.co/spaces/JhonOlmedo/sistema-predictivo-guayaquil**

Este repositorio es el espejo de ese despliegue: contiene el mismo código,
modelo y datos que reproducen el contenedor publicado.

## Arquitectura

Es un monolito servido por un único contenedor Docker. Un solo proceso de FastAPI
atiende la API REST y, a la vez, sirve el frontend de Angular ya compilado como
archivos estáticos. Por eso la API y la interfaz viven en el mismo origen y no
requieren CORS en producción.

- **Backend:** FastAPI carga el modelo LightGBM y los codificadores en memoria al
  arrancar. La API se expone bajo el prefijo `/api` (estado en `/api/health`,
  documentación interactiva en `/docs`).
- **Frontend:** Angular con Leaflet para el mapa de calor y Chart.js para las
  gráficas. En producción consume la API por ruta relativa (`/api`).
- **Empaquetado:** imagen Docker multi etapa. La primera etapa (Node 20) compila
  Angular a estáticos; la segunda (Python 3.12) instala las dependencias, hornea el
  modelo y el dataset en la imagen, copia el build de Angular a `./static` y levanta
  Uvicorn. El contenedor escucha en el puerto **7860** (el que espera Hugging Face
  Spaces).

Endpoints principales de la API: `GET /api/health`, `GET /api/zones`,
`POST /api/predict`, `POST /api/predict/batch` (para el mapa de calor completo),
`GET /api/incidents`, `GET /api/options`, `GET /api/metadata` y el ranking de
delitos por zona.

## Stack tecnológico

| Capa | Tecnología |
|---|---|
| API / Backend | FastAPI 0.111, Uvicorn |
| Modelo ML | LightGBM 4.5, scikit-learn 1.7 (codificadores), joblib |
| Datos | pandas 2.2, NumPy 2.2 |
| Frontend | Angular 19 (componentes standalone), TypeScript 5.7 |
| Mapa y gráficas | Leaflet 1.9, Chart.js |
| Empaquetado | Docker multi etapa (Node 20 + Python 3.12) |

## Estructura del repositorio

```
SISTEMA_PREDICTIVO/
├── Dockerfile                 # Imagen multi etapa (Node compila Angular, Python sirve)
├── backend/
│   ├── main.py                # App FastAPI: carga modelo, sirve API y estáticos
│   ├── schemas.py             # Modelos Pydantic de entrada y salida
│   ├── state.py               # Estado en memoria (modelo, encoders, dataframes)
│   ├── requirements.txt
│   ├── routers/               # zones, predict, incidents, top_delitos
│   ├── model/
│   │   ├── modelo_final.pkl    # Modelo LightGBM entrenado (Git LFS)
│   │   └── encoders.pkl        # LabelEncoders de scikit-learn (Git LFS)
│   ├── data/
│   │   ├── subcircuitos.csv    # 240 subcircuitos con centroide y frecuencia
│   │   ├── mdi_...2019_2025... # Dataset histórico del MDI (Git LFS)
│   │   └── *_labels.json       # Etiquetas legibles de ICCS, distritos y circuitos
│   └── tools/                 # Scripts de validación y reparación de coordenadas
├── frontend/
│   └── src/app/               # Componentes: map, filters, charts, prediction-panel,
│                              # sidebar, summary-cards, top-delitos; services/api.service.ts
├── notebooks/                 # Pipeline CRISP-DM (01 a 07) y generación de encoders
├── ablacion/                  # Estudio de ablación del modelo
├── prueba_objetivo/           # Pruebas de señal real del objetivo
└── LICENSE                    # Licencia de uso académico
```

## Cómo ejecutar en local

### Opción A: contenedor (reproduce el despliegue)

Con Docker instalado, desde la raíz del repositorio:

```bash
docker build -t sistema-predictivo .
docker run -p 7860:7860 sistema-predictivo
```

La aplicación completa queda en `http://localhost:7860`.

### Opción B: backend y frontend por separado (desarrollo)

Requiere Git LFS instalado antes de clonar, para bajar el modelo y el dataset:

```bash
git lfs install
git clone <url-del-repositorio>
```

Backend (Python 3.12):

```bash
cd backend
pip install -r requirements.txt
uvicorn main:app --reload --port 8000
```

La API queda en `http://localhost:8000/api` y la documentación en
`http://localhost:8000/docs`. Sin la carpeta `static`, el backend funciona como API
pura, que es lo que espera el frontend en modo desarrollo.

Frontend (Node 20, Angular):

```bash
cd frontend
npm install
npm start        # ng serve en http://localhost:4200 (consume la API en :8000)
```

Para generar el build de producción que sirve el monolito:

```bash
npm run build    # genera dist/frontend/browser
```

## Datos y procedencia

El conjunto de datos proviene del portal de datos abiertos del Ministerio del
Interior del Ecuador. Corresponde a registros de personas detenidas y aprehendidas
en el cantón Guayaquil durante el período 2019-2025, con aproximadamente **76.860
registros**. Cada registro incluye el código ICCS del delito, el tipo y la
descripción del arma, la fecha y la hora del hecho, el tipo de lugar, la jerarquía
geográfica policial (distrito, circuito y subcircuito) y las coordenadas cuando
están disponibles.

El territorio se organiza en tres niveles: **240 subcircuitos** (nivel principal del
modelo y del mapa), agrupados en **57 circuitos** y **10 distritos** policiales. El
archivo `subcircuitos.csv` guarda un centroide (latitud y longitud) por subcircuito,
usado únicamente para dibujar cada zona en el mapa.

## Alcance y limitaciones

Estas limitaciones acotan lo que el sistema puede y no puede afirmar. Se declaran de
forma explícita para evitar interpretaciones que el modelo no sostiene.

1. **La fuente son detenciones, no delitos.** El dataset registra personas detenidas
   o aprehendidas, no eventos delictivos discretos. Por lo tanto es un proxy de la
   actividad de aplicación de la ley, no de la victimización real de la población.
   Una zona con muchos registros puede reflejar tanto mayor delincuencia como mayor
   presencia y actividad policial.

2. **Las coordenadas son centroides, no ubicaciones de hechos.** Los puntos que se
   muestran en el mapa son el centroide de cada subcircuito y sirven solo para
   visualización. No corresponden al lugar exacto de ningún hecho. El modelo predice
   con los códigos de zona y la frecuencia histórica, no con la latitud y longitud.

3. **Solapamiento parcial entre el objetivo y sus predictores.** La variable de
   gravedad se construye a partir de la clasificación ICCS del delito, el arma, la
   frecuencia histórica por subcircuito y la hora. Existe solapamiento parcial entre
   ese objetivo y algunos de sus predictores, lo que documentamos con un estudio de
   ablación (carpeta `ablacion/`). Al retirar del modelo las tres variables más
   ligadas a la construcción del objetivo, el F1 macro cae de 0.878 a 0.470 y el
   AUC de 0.982 a 0.774. Es decir, parte del desempeño proviene de esa relación y no
   solo de una señal predictiva independiente. Esto no invalida el sistema, pero
   define su lectura correcta: estima gravedad esperada bajo las condiciones
   consultadas, no descubre patrones ocultos ajenos a su propia definición.

4. **Uso recomendado.** El sistema está pensado para fines académicos y como apoyo a
   la consulta preventiva de zonas y horarios de riesgo. No está pensado ni validado
   para uso operativo policial ni para decisiones sobre personas individuales.

Las métricas de referencia del modelo completo, sobre el conjunto de evaluación, son
F1 macro de 0.878, AUC ROC de 0.982 y exactitud de 0.915 (ver `ablacion/`).

## Metodología

El desarrollo siguió CRISP-DM. Los notebooks de la carpeta `notebooks/` documentan
el pipeline: limpieza (01), análisis exploratorio (02), preparación de datos (03),
modelado y comparación de algoritmos (04), validación externa (05), consistencia con
una fuente independiente (06) y figuras finales (07), además del cuaderno que genera
los codificadores. El modelo ganador fue LightGBM, interpretado con SHAP.

## Autores y afiliación

- **Autores:** Jhon Israel Olmedo Olvera y Kenneth Daniel Vera Valenzuela.
- **Tutor:** Ing. Joe Llerena Izquierdo.
- **Afiliación:** Universidad Politécnica Salesiana, sede Guayaquil, Carrera de
  Computación.

Trabajo de titulación. Metodología CRISP-DM, modelo LightGBM con análisis SHAP.

## Nota de uso académico y citación

Este repositorio se publica con fines académicos y educativos, bajo la licencia
descrita en el archivo [LICENSE](LICENSE). Si utilizas este trabajo, por favor cita
a los autores:

> Olmedo Olvera, J. I. y Vera Valenzuela, K. D. (2026). *Sistema Web Geoespacial
> para la Predicción de Incidentes Delictivos en Guayaquil* [software]. Universidad
> Politécnica Salesiana, sede Guayaquil.
