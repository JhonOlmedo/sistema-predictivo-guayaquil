# -*- coding: utf-8 -*-
"""
Análisis de ablación — ¿cuánto del desempeño depende del solapamiento DIRECTO
entre la etiqueta 'gravedad' y sus predictoras?

La etiqueta 'gravedad' es un índice compuesto de 4 pesos; tres de esos pesos
derivan de variables que TAMBIÉN son entradas del modelo:
    - freq_subcircuito  (peso_zona)
    - codigo_iccs       (peso_delito)
    - hora              (peso_franja, vía franja_horaria)

Se entrenan DOS LightGBM idénticos en todo salvo la lista de columnas:
    - Completo     : las 12 variables del modelo final.
    - Ablacionado  : las mismas MENOS {freq_subcircuito, codigo_iccs, hora} (9).

Ambos se entrenan con el MISMO train balanceado por SMOTE y se evalúan sobre
EXACTAMENTE el mismo test SIN balancear (intacto). Los hiperparámetros se toman
del modelo final EXISTENTE con get_params() — no se inventan valores.

NO modifica el pipeline, no reentrena ni sobreescribe modelo_final.pkl.
Solo crea/usa la carpeta ablacion/.
"""

import warnings
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from lightgbm import LGBMClassifier
from sklearn.metrics import accuracy_score, f1_score, roc_auc_score

# El .pkl del modelo final se serializó con sklearn 1.7.1; aquí corre 1.6.1.
# Solo leemos get_params() (no predecimos con él), así que el warning de versión
# de su LabelEncoder interno es inocuo. Lo silenciamos para dejar salida limpia.
warnings.filterwarnings("ignore", category=UserWarning)

# ── Rutas (portátiles: relativas a la ubicación de este script) ───────────────
AQUI      = Path(__file__).resolve()
REPO      = AQUI.parents[1]                 # ...\SISTEMA_PREDICTIVO
CSV_DIR   = REPO.parent / "CSV"             # carpeta hermana con las particiones
MODEL_PKL = REPO / "backend" / "model" / "modelo_final.pkl"
OUT_CSV   = AQUI.parent / "resultados_ablacion.csv"

TRAIN_BAL = CSV_DIR / "mdi_train_balanceado.csv"   # train balanceado por SMOTE
TEST      = CSV_DIR / "mdi_test.csv"               # test intacto (sin balancear)

TARGET = "gravedad"

# 12 variables del modelo final, en el mismo orden que FEATURES del pipeline.
FEATURES_COMPLETO = [
    "anio", "mes", "dia_semana", "es_fin_de_semana", "hora",
    "codigo_distrito", "codigo_circuito", "codigo_subcircuito",
    "freq_subcircuito", "codigo_iccs", "macro_lugar", "flag_coord",
]

# Variables que participan en la construcción de la etiqueta (solapamiento directo).
EXCLUIDAS = ["freq_subcircuito", "codigo_iccs", "hora"]
FEATURES_ABLACION = [f for f in FEATURES_COMPLETO if f not in EXCLUIDAS]

MAPA_CLASES = {0: "BAJA", 1: "MEDIA", 2: "ALTA", 3: "CRITICA"}


def cargar_datos():
    train_bal = pd.read_csv(TRAIN_BAL, sep=";", encoding="utf-8-sig")
    test_df   = pd.read_csv(TEST,      sep=";", encoding="utf-8-sig")
    return train_bal, test_df


def hiperparametros_del_modelo_final():
    """Toma los hiperparámetros del modelo final EXISTENTE (no se inventan)."""
    modelo = joblib.load(MODEL_PKL)
    if type(modelo).__name__ != "LGBMClassifier":
        raise SystemExit(f"El modelo final no es LGBMClassifier sino {type(modelo).__name__}")
    return modelo.get_params()


def evaluar(nombre, cols, params, train_bal, test_df):
    """Entrena un LGBMClassifier sobre `cols` y lo evalúa en el test intacto."""
    X_tr, y_tr = train_bal[cols], train_bal[TARGET]
    X_te, y_te = test_df[cols],   test_df[TARGET]

    modelo = LGBMClassifier(**params)     # mismos hiperparámetros para ambos
    modelo.fit(X_tr, y_tr)

    y_pred = modelo.predict(X_te)
    y_prob = modelo.predict_proba(X_te)

    acc = accuracy_score(y_te, y_pred)
    f1  = f1_score(y_te, y_pred, average="macro")
    # AUC-ROC multiclase, tal como lo pide el trabajo: OVR + promedio ponderado.
    auc = roc_auc_score(y_te, y_prob, multi_class="ovr", average="weighted")

    return {
        "Modelo":               nombre,
        "N_variables":          len(cols),
        "Accuracy":             round(acc, 4),
        "F1_macro":             round(f1, 4),
        "AUC_ROC_ovr_weighted": round(auc, 4),
    }


def main():
    print("=" * 70)
    print("ANÁLISIS DE ABLACIÓN — solapamiento DIRECTO etiqueta ↔ predictoras")
    print("=" * 70)

    train_bal, test_df = cargar_datos()
    params = hiperparametros_del_modelo_final()

    # ── Constancia de configuración ──────────────────────────────────────────
    print("\nHiperparámetros REUTILIZADOS del modelo final (get_params()):")
    relevantes = ["boosting_type", "n_estimators", "num_leaves", "max_depth",
                  "learning_rate", "subsample", "colsample_bytree",
                  "class_weight", "random_state", "n_jobs"]
    for k in relevantes:
        print(f"    {k:<18}= {params[k]!r}")

    print(f"\nCompleto     ({len(FEATURES_COMPLETO)} vars): {FEATURES_COMPLETO}")
    print(f"Ablacionado  ({len(FEATURES_ABLACION)} vars): {FEATURES_ABLACION}")
    print(f"Excluidas del ablacionado: {EXCLUIDAS}")

    # ── Constancia de que el TEST no se toca (idéntico en ambos casos) ────────
    y_test = test_df[TARGET]
    print("\n" + "-" * 70)
    print("VERIFICACIÓN DEL CONJUNTO DE PRUEBA (intacto, sin balancear)")
    print("-" * 70)
    print(f"Tamaño del test (y_test): {len(y_test):,} registros")
    dist = y_test.value_counts().sort_index()
    print("Distribución de clases en y_test:")
    for cod, n in dist.items():
        print(f"    {cod} = {MAPA_CLASES[cod]:<8}: {n:>6,}  ({n/len(y_test)*100:5.2f}%)")
    print("Train (balanceado por SMOTE):", f"{len(train_bal):,} registros")
    print("Nota: ambos modelos usan ESTE mismo y_test; la única diferencia entre "
          "variantes es la lista de columnas.")

    # ── Entrenamiento y evaluación de ambas variantes ─────────────────────────
    filas = [
        evaluar("Completo",    FEATURES_COMPLETO, params, train_bal, test_df),
        evaluar("Ablacionado", FEATURES_ABLACION, params, train_bal, test_df),
    ]
    tabla = pd.DataFrame(filas)

    OUT_CSV.parent.mkdir(parents=True, exist_ok=True)
    tabla.to_csv(OUT_CSV, index=False, encoding="utf-8-sig")

    print("\n" + "=" * 70)
    print("TABLA COMPARATIVA (evaluación sobre el mismo test intacto)")
    print("=" * 70)
    print(tabla.to_string(index=False))
    print(f"\nGuardada en: {OUT_CSV}")

    # ── Resumen de 3 líneas ───────────────────────────────────────────────────
    f1_comp = tabla.loc[tabla.Modelo == "Completo",    "F1_macro"].iloc[0]
    f1_abla = tabla.loc[tabla.Modelo == "Ablacionado", "F1_macro"].iloc[0]
    caida_abs = f1_comp - f1_abla
    caida_rel = caida_abs / f1_comp * 100

    print("\n" + "=" * 70)
    print("RESUMEN")
    print("=" * 70)
    print(f"1) F1 macro — Completo: {f1_comp:.4f} | Ablacionado: {f1_abla:.4f}")
    print(f"2) Caída al quitar {{{', '.join(EXCLUIDAS)}}}: "
          f"{caida_abs:.4f} absoluta ({caida_rel:.1f}% relativa).")
    print("3) Referencia: 0,25 es el F1 macro esperado por azar con 4 clases "
          "balanceadas.")

    # ── Interpretación (no llamar 'limpio' al ablacionado) ────────────────────
    print("\nInterpretación: el modelo ablacionado NO es un 'modelo limpio'. Al "
          "quitar esas 3 variables aún queda solapamiento INDIRECTO "
          "(codigo_distrito/circuito/subcircuito correlacionan con "
          "freq_subcircuito, y es_fin_de_semana con la franja horaria). Por eso "
          "su caída mide cuánto pesa el SOLAPAMIENTO DIRECTO, no el desempeño "
          "libre de fuga.")


if __name__ == "__main__":
    main()
