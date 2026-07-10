# -*- coding: utf-8 -*-
"""
PRUEBA EXPLORATORIA DE OBJETIVO — ¿existe señal predictiva REAL sobre una
etiqueta que NO construimos nosotros y que NO se pueda reconstruir desde las
entradas del modelo?

Motivación
----------
La etiqueta actual del proyecto ('gravedad') es un índice compuesto que se
solapa con varias de sus propias predictoras (freq_subcircuito, codigo_iccs,
hora). El análisis de ablación (carpeta ablacion/) ya cuantificó ese
solapamiento DIRECTO. Aquí damos un paso distinto: probamos DOS objetivos
alternativos que NO derivan de un índice diseñado por nosotros, usando SOLO
variables de contexto como predictoras.

    Objetivo A — Tipo de delito (codigo_iccs como ETIQUETA, nunca como entrada).
                 Agrupado a las TOP-K categorías + 'OTROS'. Es un objetivo
                 genuinamente externo: el modelo NO puede reconstruirlo desde
                 las entradas de contexto.

    Objetivo B — Zona-hora de alta concentración (binario). Se marca 1 el par
                 (subcircuito, franja horaria) cuyo conteo de registros en el
                 TRAIN cae en el cuartil superior; 0 el resto. Los umbrales se
                 aprenden SOLO en train y se aplican al test (sin fuga temporal).

Reglas que respeta este script
------------------------------
- NO toca el pipeline, ni el modelo desplegado, ni los CSV originales.
- NO reentrena ni sobreescribe modelo_final.pkl (solo lee sus hiperparámetros
  con get_params(), igual que el análisis de ablación).
- SOLO escribe dentro de la carpeta prueba_objetivo/.
- Reutiliza las particiones ya persistidas (mdi_train_balanceado.csv y
  mdi_test.csv), separador ';', encoding utf-8-sig, ya codificadas a enteros.

Nota metodológica: el train reutilizado está balanceado por SMOTE respecto a
'gravedad' (no respecto a codigo_iccs ni a la concentración zona-hora). Se usa
tal cual porque es la partición persistida que pide la prueba; se deja
constancia del caveat en la salida.
"""

import warnings
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from lightgbm import LGBMClassifier
from sklearn.metrics import accuracy_score, f1_score, roc_auc_score

# El modelo_final.pkl se serializó con otra versión de sklearn; aquí solo
# leemos sus hiperparámetros (no predecimos con él), así que el warning de
# versión del LabelEncoder interno es inocuo. Salida limpia.
warnings.filterwarnings("ignore", category=UserWarning)

# ── Rutas (portátiles: relativas a la ubicación de este script) ───────────────
AQUI      = Path(__file__).resolve()
REPO      = AQUI.parents[1]                 # ...\SISTEMA_PREDICTIVO
CSV_DIR   = REPO.parent / "CSV"             # carpeta hermana con las particiones
MODEL_PKL = REPO / "backend" / "model" / "modelo_final.pkl"
OUT_CSV   = AQUI.parent / "resultados_prueba_objetivo.csv"

TRAIN_BAL = CSV_DIR / "mdi_train_balanceado.csv"
TEST      = CSV_DIR / "mdi_test.csv"

# Predictoras: SOLO variables de contexto. Se excluye explícitamente
# freq_subcircuito (derivada del subcircuito y usada para construir 'gravedad'),
# codigo_iccs (es la etiqueta del Objetivo A) y la propia 'gravedad'.
PREDICTORAS = [
    "anio", "mes", "dia_semana", "es_fin_de_semana", "hora",
    "codigo_distrito", "codigo_circuito", "codigo_subcircuito",
    "macro_lugar", "flag_coord",
]

# TOP-K categorías de delito antes de colapsar el resto en 'OTROS'.
K_ICCS = 8

# Franja horaria canónica del proyecto (03_preparacion_finalV2.ipynb).
# Nota: refleja horario de DETENCIÓN (actividad policial), no ocurrencia real.
def asignar_franja(hora: int) -> str:
    h = int(hora)
    if 9 <= h <= 13:
        return "PICO_MANANA"     # pico principal
    elif 14 <= h <= 19:
        return "PICO_TARDE"      # segundo pico
    elif 20 <= h <= 23:
        return "NOCHE"
    else:                        # 0-8h
        return "MADRUGADA"


# ──────────────────────────────────────────────────────────────────────────────
# Utilidades
# ──────────────────────────────────────────────────────────────────────────────
def cargar_datos():
    if not TRAIN_BAL.exists() or not TEST.exists():
        raise SystemExit(
            f"No encuentro las particiones en {CSV_DIR}\n"
            f"  train: {TRAIN_BAL} (existe={TRAIN_BAL.exists()})\n"
            f"  test : {TEST} (existe={TEST.exists()})"
        )
    train = pd.read_csv(TRAIN_BAL, sep=";", encoding="utf-8-sig")
    test  = pd.read_csv(TEST,      sep=";", encoding="utf-8-sig")
    return train, test


def verificar_columnas(train, test):
    """Si algún nombre esperado no está, detenerse y mostrar los reales."""
    requeridas = set(PREDICTORAS) | {"codigo_iccs", "codigo_subcircuito", "hora"}
    for nombre, df in [("train", train), ("test", test)]:
        faltan = requeridas - set(df.columns)
        if faltan:
            raise SystemExit(
                f"[DETENIDO] En {nombre} faltan columnas esperadas: {sorted(faltan)}\n"
                f"Columnas reales de {nombre}: {list(df.columns)}"
            )


def hiperparametros_del_modelo_final():
    """Reutiliza los hiperparámetros del modelo final EXISTENTE (no se inventan)."""
    modelo = joblib.load(MODEL_PKL)
    if type(modelo).__name__ != "LGBMClassifier":
        raise SystemExit(f"El modelo final no es LGBMClassifier sino {type(modelo).__name__}")
    return modelo.get_params()


def distribucion(nombre, y):
    vc = pd.Series(y).value_counts().sort_index()
    print(f"  Distribución de clases en {nombre} ({len(y):,} registros):")
    for cls, n in vc.items():
        print(f"    clase {cls!r:<14}: {n:>7,}  ({n/len(y)*100:5.2f}%)")


def veredicto_senal(mejora_abs_f1):
    """Traduce la mejora absoluta en F1 sobre el baseline a sí/marginal/no."""
    if mejora_abs_f1 >= 0.15:
        return "sí"
    if mejora_abs_f1 >= 0.05:
        return "marginal"
    return "no"


# ──────────────────────────────────────────────────────────────────────────────
# Objetivo A — Tipo de delito (codigo_iccs) agrupado a TOP-K + OTROS
# ──────────────────────────────────────────────────────────────────────────────
def objetivo_A(train, test, params):
    print("\n" + "=" * 74)
    print("OBJETIVO A — TIPO DE DELITO (codigo_iccs como ETIQUETA, no como entrada)")
    print("=" * 74)

    # TOP-K categorías por frecuencia en TRAIN; el resto -> 'OTROS'.
    top = train["codigo_iccs"].value_counts().nlargest(K_ICCS).index.tolist()

    def a_clase(v):
        return str(v) if v in top else "OTROS"

    y_tr = train["codigo_iccs"].map(a_clase).astype(str)
    y_te = test["codigo_iccs"].map(a_clase).astype(str)

    X_tr = train[PREDICTORAS]
    X_te = test[PREDICTORAS]

    print(f"\n  Etiqueta      : codigo_iccs -> TOP-{K_ICCS} + 'OTROS'")
    print(f"  TOP-{K_ICCS} (códigos): {top}")
    print(f"  Nº de clases  : {y_tr.nunique()}")
    print(f"  Predictoras ({len(PREDICTORAS)}): {PREDICTORAS}")
    print()
    distribucion("y_test", y_te)

    # Baseline: clase mayoritaria aprendida en TRAIN, aplicada al TEST.
    clase_may = y_tr.value_counts().idxmax()
    y_base = np.full(len(y_te), clase_may, dtype=object)
    f1_base  = f1_score(y_te, y_base, average="macro")
    acc_base = accuracy_score(y_te, y_base)
    azar = 1.0 / y_tr.nunique()
    print(f"\n  Baseline (mayoritaria = {clase_may!r}): "
          f"F1_macro={f1_base:.4f} | Accuracy={acc_base:.4f}")
    print(f"  (F1_macro esperado por azar uniforme con {y_tr.nunique()} clases ≈ {azar:.4f})")

    # Modelo
    modelo = LGBMClassifier(**params)
    modelo.fit(X_tr, y_tr)
    y_pred = modelo.predict(X_te)

    f1_mod  = f1_score(y_te, y_pred, average="macro")
    acc_mod = accuracy_score(y_te, y_pred)

    # AUC multiclase (OVR ponderado); guardado como referencia extra.
    try:
        y_prob = modelo.predict_proba(X_te)
        auc_mod = roc_auc_score(y_te, y_prob, multi_class="ovr", average="weighted",
                                labels=modelo.classes_)
    except Exception as e:
        auc_mod = float("nan")
        print(f"  (AUC no calculable: {e})")

    print(f"\n  Modelo LightGBM (contexto): "
          f"F1_macro={f1_mod:.4f} | Accuracy={acc_mod:.4f} | AUC_ovr_w={auc_mod:.4f}")

    mejora_f1 = f1_mod - f1_base
    senal = veredicto_senal(mejora_f1)

    fila = {
        "objetivo": "A_tipo_delito",
        "etiqueta": f"codigo_iccs_TOP{K_ICCS}+OTROS",
        "n_clases": int(y_tr.nunique()),
        "n_predictoras": len(PREDICTORAS),
        "predictoras": "|".join(PREDICTORAS),
        "f1_tipo": "macro",
        "f1_modelo": round(f1_mod, 4),
        "f1_baseline": round(f1_base, 4),
        "mejora_f1_abs": round(mejora_f1, 4),
        "accuracy_modelo": round(acc_mod, 4),
        "accuracy_baseline": round(acc_base, 4),
        "auc_modelo": round(auc_mod, 4) if auc_mod == auc_mod else np.nan,
        "auc_baseline": np.nan,   # AUC de baseline mayoritario no está definido en multiclase
        "senal_real": senal,
    }
    return fila


# ──────────────────────────────────────────────────────────────────────────────
# Objetivo B — Zona-hora de alta concentración (binario, umbral aprendido en train)
# ──────────────────────────────────────────────────────────────────────────────
def objetivo_B(train, test, params):
    print("\n" + "=" * 74)
    print("OBJETIVO B — ZONA-HORA DE ALTA CONCENTRACIÓN (binario)")
    print("=" * 74)

    tr = train.copy()
    te = test.copy()
    tr["franja"] = tr["hora"].apply(asignar_franja)
    te["franja"] = te["hora"].apply(asignar_franja)

    # Conteo por par (subcircuito, franja) SOLO en train; umbral = cuartil superior.
    conteos = tr.groupby(["codigo_subcircuito", "franja"]).size()
    q3 = conteos.quantile(0.75)
    pares_altos = set(conteos[conteos >= q3].index)   # tuplas (subcircuito, franja)

    def etiquetar(df):
        pares = list(zip(df["codigo_subcircuito"], df["franja"]))
        return np.array([1 if p in pares_altos else 0 for p in pares], dtype=int)

    y_tr = etiquetar(tr)   # pares no vistos -> 0 (no aplica en train, pero es consistente)
    y_te = etiquetar(te)   # pares del test no vistos en train -> 0 (sin fuga)

    X_tr = tr[PREDICTORAS]
    X_te = te[PREDICTORAS]

    print(f"\n  Etiqueta      : 1 si (subcircuito, franja) está en el cuartil superior "
          f"de conteos del TRAIN")
    print(f"  Umbral Q3 (conteo por par en train): {q3:.1f} registros")
    print(f"  Pares (subcircuito, franja) totales en train: {len(conteos)}  |  "
          f"marcados como alta concentración (=1): {len(pares_altos)} "
          f"({len(pares_altos)/len(conteos)*100:.1f}% de los pares)")
    print(f"  Predictoras ({len(PREDICTORAS)}): {PREDICTORAS}")
    print()
    distribucion("y_test", y_te)

    # Baseline: clase mayoritaria aprendida en TRAIN, aplicada al TEST.
    clase_may = int(np.bincount(y_tr).argmax())
    y_base = np.full(len(y_te), clase_may, dtype=int)
    f1_base  = f1_score(y_te, y_base, average="binary", pos_label=1, zero_division=0)
    acc_base = accuracy_score(y_te, y_base)
    auc_base = 0.5  # un clasificador constante no ordena: AUC = 0.5 por definición
    print(f"\n  Baseline (mayoritaria = {clase_may}): "
          f"F1={f1_base:.4f} | Accuracy={acc_base:.4f} | AUC={auc_base:.4f}")

    # Modelo
    modelo = LGBMClassifier(**params)
    modelo.fit(X_tr, y_tr)
    y_pred = modelo.predict(X_te)
    y_prob = modelo.predict_proba(X_te)[:, 1]

    f1_mod  = f1_score(y_te, y_pred, average="binary", pos_label=1, zero_division=0)
    acc_mod = accuracy_score(y_te, y_pred)
    auc_mod = roc_auc_score(y_te, y_prob)

    print(f"\n  Modelo LightGBM (contexto): "
          f"F1={f1_mod:.4f} | Accuracy={acc_mod:.4f} | AUC={auc_mod:.4f}")

    mejora_f1 = f1_mod - f1_base
    senal = veredicto_senal(mejora_f1)

    fila = {
        "objetivo": "B_zona_hora_concentracion",
        "etiqueta": "alta_concentracion_(subcircuito,franja)_Q3_train",
        "n_clases": 2,
        "n_predictoras": len(PREDICTORAS),
        "predictoras": "|".join(PREDICTORAS),
        "f1_tipo": "binary(pos=1)",
        "f1_modelo": round(f1_mod, 4),
        "f1_baseline": round(f1_base, 4),
        "mejora_f1_abs": round(mejora_f1, 4),
        "accuracy_modelo": round(acc_mod, 4),
        "accuracy_baseline": round(acc_base, 4),
        "auc_modelo": round(auc_mod, 4),
        "auc_baseline": round(auc_base, 4),
        "senal_real": senal,
    }
    return fila, dict(f1_mod=f1_mod, acc_mod=acc_mod, auc_mod=auc_mod)


# ──────────────────────────────────────────────────────────────────────────────
def main():
    print("=" * 74)
    print("PRUEBA EXPLORATORIA DE OBJETIVO (no modifica el pipeline ni el modelo)")
    print("=" * 74)

    train, test = cargar_datos()
    verificar_columnas(train, test)
    params = hiperparametros_del_modelo_final()

    print("\nConstancia de configuración")
    print("-" * 74)
    print(f"  Train reutilizado : {TRAIN_BAL.name}  ({len(train):,} filas)  "
          f"[balanceado por SMOTE sobre 'gravedad']")
    print(f"  Test  intacto     : {TEST.name}  ({len(test):,} filas)")
    print(f"  Hiperparámetros REUTILIZADOS del modelo final (get_params()):")
    for k in ["boosting_type", "n_estimators", "num_leaves", "max_depth",
              "learning_rate", "subsample", "colsample_bytree",
              "class_weight", "random_state", "n_jobs"]:
        print(f"      {k:<18}= {params.get(k)!r}")
    print(f"  Predictoras (contexto, {len(PREDICTORAS)}): {PREDICTORAS}")
    print(f"  Excluidas como predictoras: freq_subcircuito (derivada), "
          f"codigo_iccs (etiqueta A), gravedad (etiqueta original).")

    fila_A = objetivo_A(train, test, params)
    fila_B, mB = objetivo_B(train, test, params)

    # ── Tabla resumen ─────────────────────────────────────────────────────────
    tabla = pd.DataFrame([fila_A, fila_B])
    OUT_CSV.parent.mkdir(parents=True, exist_ok=True)
    tabla.to_csv(OUT_CSV, index=False, encoding="utf-8-sig")

    resumen = tabla[["objetivo", "n_clases", "f1_tipo", "f1_modelo", "f1_baseline",
                     "mejora_f1_abs", "accuracy_modelo", "auc_modelo", "senal_real"]]
    print("\n" + "=" * 74)
    print("TABLA RESUMEN")
    print("=" * 74)
    print(resumen.to_string(index=False))
    print(f"\nGuardada en: {OUT_CSV}")

    # ── Veredicto de 3 líneas por objetivo ────────────────────────────────────
    print("\n" + "=" * 74)
    print("VEREDICTO")
    print("=" * 74)

    print("\n[Objetivo A — Tipo de delito]")
    print(f"  1) F1 macro={fila_A['f1_modelo']:.4f} | Accuracy={fila_A['accuracy_modelo']:.4f}.")
    print(f"  2) Supera al baseline mayoritario en F1 macro por "
          f"{fila_A['mejora_f1_abs']:+.4f} (baseline={fila_A['f1_baseline']:.4f}).")
    print(f"  3) Señal real: {fila_A['senal_real'].upper()}. Objetivo genuinamente externo "
          f"(no reconstruible desde las entradas de contexto): la mejora sobre el "
          f"baseline es la evidencia limpia de señal.")

    print("\n[Objetivo B — Zona-hora de alta concentración]")
    print(f"  1) F1={fila_B['f1_modelo']:.4f} | Accuracy={fila_B['accuracy_modelo']:.4f} | "
          f"AUC={fila_B['auc_modelo']:.4f}.")
    print(f"  2) Supera al baseline mayoritario en F1 por {fila_B['mejora_f1_abs']:+.4f} "
          f"y en AUC por {mB['auc_mod']-0.5:+.4f} sobre 0.5.")
    print(f"  3) Señal real: {fila_B['senal_real'].upper()} PERO con caveat: la etiqueta es "
          f"función de (subcircuito, franja(hora)) y ambos están entre las predictoras, "
          f"así que el objetivo ES reconstruible desde las entradas; mide memorización "
          f"del mapa de puntos calientes del train, no señal libre de fuga.")

    print()


if __name__ == "__main__":
    main()
