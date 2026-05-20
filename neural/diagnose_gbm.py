"""
diagnose_gbm.py — Diagnóstico del modelo GBM (LightGBM ensemble)

Investiga por qué el modelo produce HOLD 100% en ciertos regímenes de mercado:
  1. Distribución de labels en training data por régimen (VIX, gamma, hora)
  2. Feature importance del ensemble
  3. Calibración de probabilidades (¿produce extremos 0%/100% con frecuencia?)
  4. Análisis de régimen crítico: VIX>25 + net_gamma muy negativo
  5. Simulación del vector de features del fallo (13:03 ET de ayer)
  6. Árbol de decisión simplificado para entender el camino a HOLD 100%

Uso:
    python diagnose_gbm.py --model neural/models/trading_hybrid_wf.joblib
                           --norm  neural/models/hybrid_normalizer_wf.npz
                           --data  training_data/training_data.csv

    # Solo investigar el modelo sin training data:
    python diagnose_gbm.py --model neural/models/trading_hybrid_wf.joblib
                           --norm  neural/models/hybrid_normalizer_wf.npz
"""

import argparse
import os
import sys
import math
import warnings
warnings.filterwarnings("ignore")

import numpy as np
import pandas as pd
import joblib

# ── Colores ANSI ──────────────────────────────────────────────────────────────
GREEN  = "\033[92m"
YELLOW = "\033[93m"
RED    = "\033[91m"
CYAN   = "\033[96m"
BOLD   = "\033[1m"
RESET  = "\033[0m"

def bold(s):  return f"{BOLD}{s}{RESET}"
def green(s): return f"{GREEN}{s}{RESET}"
def yellow(s):return f"{YELLOW}{s}{RESET}"
def red(s):   return f"{RED}{s}{RESET}"
def cyan(s):  return f"{CYAN}{s}{RESET}"

# ── safe_log (debe coincidir exactamente con training) ────────────────────────
def safe_log(x):
    return math.copysign(math.log1p(abs(x)), x)

# ══════════════════════════════════════════════════════════════════════════════
# CARGA DE MODELO
# ══════════════════════════════════════════════════════════════════════════════
def load_model(model_path: str, norm_path: str):
    print(bold(f"\n[CARGA] {model_path}"))

    raw = joblib.load(model_path)
    if not isinstance(raw, list):
        raw = [raw]
    raw = [o['model'] if (isinstance(o, dict) and 'model' in o) else o for o in raw]
    print(f"  {len(raw)} modelo(s) en el ensemble")

    # Normalizer — RobustScaler (mediana + IQR)
    norm_data = np.load(norm_path, allow_pickle=True)
    medians   = norm_data["medians"]
    iqrs      = norm_data["iqrs"]
    p_low     = norm_data["p_low"]
    p_high    = norm_data["p_high"]
    log_mask  = norm_data["log_mask"].astype(bool)
    try:
        feat_names_norm = list(norm_data["feature_names"])
    except Exception:
        feat_names_norm = [f"f{i}" for i in range(len(medians))]

    norm = {
        "medians":   medians,
        "iqrs":      iqrs,
        "p_low":     p_low,
        "p_high":    p_high,
        "log_mask":  log_mask,
        "feat_names": feat_names_norm,
    }
    print(f"  Normalizer: {len(medians)} features (RobustScaler)")

    # Feature names — el modelo puede tener nombres genéricos (Column_N).
    # Usamos los del normalizer como fuente canónica, que sí tienen nombres reales.
    try:
        model_feat_names = list(raw[0].feature_name_)
        # Si el modelo devuelve Column_N genéricos, usar los del normalizer
        if model_feat_names and model_feat_names[0].startswith("Column_"):
            feat_names = feat_names_norm
            print(f"  Nombres de features: del normalizer ({len(feat_names_norm)} features)")
        else:
            feat_names = model_feat_names
            print(f"  Nombres de features: del modelo LGBM ({len(feat_names)} features)")
    except AttributeError:
        feat_names = feat_names_norm
        model_feat_names = feat_names_norm
        print(f"  Nombres de features: del normalizer (fallback)")

    norm["model_feat_names"] = model_feat_names  # guardamos los Column_N para predict

    return raw, norm, feat_names


def normalize_robust(X: np.ndarray, norm: dict) -> np.ndarray:
    """
    Replica exacta del FeatureNormalizer.transform() con RobustScaler.
    Aplica log1p a features marcadas en log_mask, luego clip a p_low/p_high,
    luego (x - mediana) / IQR, luego clip final a [-5, 5].
    """
    X = X.astype(np.float64).copy()
    X = np.nan_to_num(X, nan=0.0, posinf=5.0, neginf=-5.0)

    log_mask = norm["log_mask"]
    if log_mask.any():
        X[:, log_mask] = np.sign(X[:, log_mask]) * np.log1p(np.abs(X[:, log_mask]))

    # Clip percentil
    p_low  = norm["p_low"]
    p_high = norm["p_high"]
    for i in range(X.shape[1]):
        X[:, i] = np.clip(X[:, i], p_low[i], p_high[i])

    # RobustScaler
    iqrs = norm["iqrs"].copy()
    iqrs[iqrs == 0] = 1.0
    X = (X - norm["medians"]) / iqrs

    return np.clip(X, -5, 5).astype(np.float32)


def predict_ensemble(models, X_norm: np.ndarray) -> np.ndarray:
    """Promedia predict_proba de todos los modelos. Devuelve [N, 3]."""
    probs_list = []
    for m in models:
        try:
            # Usar los nombres internos del modelo (pueden ser Column_N)
            internal_names = m.feature_name_
            df = pd.DataFrame(X_norm, columns=internal_names)
            probs_list.append(m.predict_proba(df))
        except Exception:
            probs_list.append(m.predict_proba(X_norm))
    return np.stack(probs_list, axis=0).mean(axis=0)


# ══════════════════════════════════════════════════════════════════════════════
# 1. FEATURE IMPORTANCE
# ══════════════════════════════════════════════════════════════════════════════
def section_feature_importance(models, feat_names, top_n=30):
    print(bold(f"\n{'═'*65}"))
    print(bold(f"  [ 1 ] FEATURE IMPORTANCE (top {top_n})"))
    print(bold(f"{'═'*65}"))

    importances = []
    for m in models:
        try:
            imp = m.feature_importances_
            importances.append(imp)
        except AttributeError:
            pass

    if not importances:
        print(yellow("  Sin datos de importancia disponibles"))
        return

    avg_imp = np.stack(importances, axis=0).mean(axis=0)
    order = np.argsort(avg_imp)[::-1]

    print(f"  {'Feature':<45} {'Importancia':>12}  {'Bar'}")
    print(f"  {'-'*45} {'-'*12}  {'-'*30}")

    max_imp = avg_imp[order[0]]
    for rank, idx in enumerate(order[:top_n]):
        name = feat_names[idx] if idx < len(feat_names) else f"f{idx}"
        val  = avg_imp[idx]
        bar_len = int(val / max_imp * 30)
        bar = "█" * bar_len

        # Destacar features clave del problema
        highlight = ""
        if any(k in name for k in ("vix", "gamma", "spot_change", "ret_", "time_")):
            highlight = CYAN
        print(f"  {highlight}{name:<45} {val:>12.1f}  {bar}{RESET}")

    # Resumen de grupos
    print(bold(f"\n  Grupos de features más importantes:"))
    groups = {
        "Tiempo (time_*, minutes_to_close)":     [n for n in feat_names if "time" in n or "minutes_to_close" in n],
        "Spot/retornos (ret_*, spot_change)":     [n for n in feat_names if "ret_" in n or "spot_change" in n],
        "VIX/IV (vix_*, atm_iv, iv_*)":          [n for n in feat_names if "vix" in n or "atm_iv" in n or "iv_" in n],
        "Gamma/greeks (net_gamma, *change*)":     [n for n in feat_names if "gamma" in n or "vanna" in n or "delta" in n],
        "IB/Fibonacci (ib_*, fib_*, dist_*)":     [n for n in feat_names if "ib_" in n or "fib_" in n or "dist_" in n],
        "Confluencias (confluence_*)":            [n for n in feat_names if "confluence" in n],
    }
    for group_name, group_feats in groups.items():
        idxs = [i for i, n in enumerate(feat_names) if n in group_feats]
        if idxs:
            total = avg_imp[idxs].sum()
            pct   = total / avg_imp.sum() * 100
            print(f"    {group_name:<45} {pct:>5.1f}%")


# ══════════════════════════════════════════════════════════════════════════════
# 2. DISTRIBUCIÓN DE LABELS POR RÉGIMEN (requiere training data)
# ══════════════════════════════════════════════════════════════════════════════
def section_label_distribution(df: pd.DataFrame):
    print(bold(f"\n{'═'*65}"))
    print(bold(f"  [ 2 ] DISTRIBUCIÓN DE LABELS POR RÉGIMEN"))
    print(bold(f"{'═'*65}"))

    # Normalizar target a {0=SHORT, 1=HOLD, 2=LONG}
    y = df["target"].values.copy()
    if y.min() < 0:
        y = (y + 1).astype(int)
    df = df.copy()
    df["_y"] = y

    n_total = len(df)
    dist = np.bincount(y, minlength=3)
    print(f"\n  GLOBAL ({n_total:,} muestras):")
    print(f"    SHORT={dist[0]:>6,} ({dist[0]/n_total:.1%})  "
          f"HOLD={dist[1]:>6,} ({dist[1]/n_total:.1%})  "
          f"LONG={dist[2]:>6,} ({dist[2]/n_total:.1%})")

    def show_regime(mask, label):
        sub = df[mask]
        n = len(sub)
        if n == 0:
            print(f"    {label:<45}  sin datos")
            return
        yd = np.bincount(sub["_y"].values, minlength=3)
        hold_pct = yd[1] / n
        color = RED if hold_pct > 0.80 else (YELLOW if hold_pct > 0.65 else GREEN)
        print(f"    {label:<45}  n={n:>6,}  "
              f"S={yd[0]/n:.0%} H={color}{yd[1]/n:.0%}{RESET} L={yd[2]/n:.0%}")

    # ── Por régimen VIX ───────────────────────────────────────────────────────
    if "vix_spot" in df.columns:
        print(f"\n  Por VIX (feature vix_spot normalizado):")
        # vix_spot en training está dividido por 50
        vix_raw = df["vix_spot"] * 50
        show_regime(vix_raw < 15,  "VIX < 15 (low vol)")
        show_regime((vix_raw >= 15) & (vix_raw < 20), "VIX 15-20")
        show_regime((vix_raw >= 20) & (vix_raw < 25), "VIX 20-25")
        show_regime(vix_raw >= 25,  "VIX >= 25 (high vol)  ← RÉGIMEN AYER")
        show_regime(vix_raw >= 30,  "VIX >= 30 (extreme)")

    # ── Por régimen gamma ─────────────────────────────────────────────────────
    # net_gamma en features está como safe_log — buscamos columna raw o safe_log
    gamma_col = None
    for c in ("net_gamma", "gamma_regime"):
        if c in df.columns:
            gamma_col = c
            break

    if gamma_col == "gamma_regime":
        print(f"\n  Por gamma_regime (0=neg, 0.5=neutral, 1.0=pos):")
        show_regime(df[gamma_col] == 0.0, "Gamma negativo (dealers short gamma)  ← AYER")
        show_regime(df[gamma_col] == 0.5, "Gamma neutral")
        show_regime(df[gamma_col] == 1.0, "Gamma positivo")
    elif gamma_col == "net_gamma":
        print(f"\n  Por net_gamma (raw):")
        show_regime(df[gamma_col] < -1e10, "net_gamma < -1e10 (muy negativo)  ← AYER")
        show_regime((df[gamma_col] >= -1e10) & (df[gamma_col] < 0), "net_gamma -1e10 a 0")
        show_regime(df[gamma_col] >= 0,   "net_gamma positivo")

    # ── Por hora del día ──────────────────────────────────────────────────────
    if "time_sin" in df.columns and "time_cos" in df.columns:
        # Reconstruir minutos desde apertura
        ts = df["time_sin"].values
        tc = df["time_cos"].values
        angle = np.arctan2(ts, tc)
        mins = (angle / (2 * np.pi) * 390) % 390
        df["_mins"] = mins
        print(f"\n  Por hora del día (minutos desde 9:30):")
        show_regime(df["_mins"] < 60,                       "09:30-10:30 (primera hora)")
        show_regime((df["_mins"] >= 60)  & (df["_mins"] < 120), "10:30-11:30")
        show_regime((df["_mins"] >= 120) & (df["_mins"] < 210), "11:30-13:00 (midday)  ← AYER ~13h")
        show_regime((df["_mins"] >= 210) & (df["_mins"] < 300), "13:00-14:30 (post-lunch)")
        show_regime(df["_mins"] >= 300,                     "14:30-16:00 (power hour)")

    # ── Régimen crítico combinado ─────────────────────────────────────────────
    print(bold(f"\n  RÉGIMEN CRÍTICO (condiciones del fallo de ayer):"))

    has_vix    = "vix_spot" in df.columns
    has_gamma  = "gamma_regime" in df.columns
    has_time   = "_mins" in df.columns

    if has_vix and has_gamma and has_time:
        vix_crit   = df["vix_spot"] * 50 >= 25
        gamma_crit = df["gamma_regime"] == 0.0
        time_crit  = (df["_mins"] >= 120) & (df["_mins"] < 240)

        show_regime(vix_crit,                             "VIX >= 25")
        show_regime(gamma_crit,                           "Gamma negativo")
        show_regime(vix_crit & gamma_crit,                "VIX>=25 AND Gamma negativo")
        show_regime(vix_crit & gamma_crit & time_crit,    "VIX>=25 AND Gamma neg AND midday  ← EXACTO")
    elif has_vix and has_gamma:
        vix_crit   = df["vix_spot"] * 50 >= 25
        gamma_crit = df["gamma_regime"] == 0.0
        show_regime(vix_crit & gamma_crit, "VIX>=25 AND Gamma negativo  ← AYER")

    # ── Detección de colapso ──────────────────────────────────────────────────
    print(bold(f"\n  Detección de colapso (HOLD > 80% en algún subgrupo):"))
    warned = False
    subgroups = {}

    if "vix_spot" in df.columns:
        vix_raw = df["vix_spot"] * 50
        for low, high, lbl in [(0, 15, "VIX<15"), (15, 20, "VIX 15-20"),
                               (20, 25, "VIX 20-25"), (25, 100, "VIX>=25")]:
            m = (vix_raw >= low) & (vix_raw < high)
            subgroups[lbl] = m

    if "gamma_regime" in df.columns:
        subgroups["Gamma neg"] = df["gamma_regime"] == 0.0
        subgroups["Gamma pos"] = df["gamma_regime"] == 1.0

    for lbl, mask in subgroups.items():
        sub = df[mask]
        if len(sub) < 50:
            continue
        yd = np.bincount(sub["_y"].values, minlength=3)
        hold_pct = yd[1] / len(sub)
        if hold_pct > 0.80:
            print(red(f"    COLAPSO DETECTADO: {lbl} — HOLD={hold_pct:.0%} ({len(sub):,} muestras)"))
            warned = True

    if not warned:
        print(green("    Sin colapsos obvios detectados"))


# ══════════════════════════════════════════════════════════════════════════════
# 3. CALIBRACIÓN DE PROBABILIDADES
# ══════════════════════════════════════════════════════════════════════════════
def section_calibration(models, norm, feat_names, df: pd.DataFrame):
    print(bold(f"\n{'═'*65}"))
    print(bold(f"  [ 3 ] CALIBRACIÓN DE PROBABILIDADES"))
    print(bold(f"{'═'*65}"))

    # Preparar features normalizadas
    cols = [c for c in feat_names if c in df.columns]
    if not cols:
        # Intentar por posición: el CSV puede tener nombres distintos
        # Verificar si el número de columnas numéricas coincide
        num_cols = df.select_dtypes(include=[np.number]).columns.tolist()
        non_meta = [c for c in num_cols if c not in ("target", "date", "_date", "weight")]
        if len(non_meta) >= len(feat_names):
            cols = feat_names
            df = df.copy()
            for i, name in enumerate(feat_names):
                if name not in df.columns and i < len(non_meta):
                    df[name] = df[non_meta[i]].values
            print(yellow(f"  Columnas mapeadas por posición ({len(cols)} features)"))
        else:
            print(yellow("  No hay features comunes entre modelo y training data"))
            print(yellow(f"  Columnas del CSV: {list(df.columns[:10])}..."))
            return

    X_raw = df[cols].values.astype(np.float32)
    X_raw = np.nan_to_num(X_raw, nan=0.0, posinf=5.0, neginf=-5.0)

    # Normalizar con RobustScaler (replica FeatureNormalizer.transform)
    # Subset de features que existen en el df — alinear norm con cols
    feat_idx = [list(feat_names).index(c) for c in cols if c in feat_names]
    norm_sub = {
        "medians":  norm["medians"][feat_idx],
        "iqrs":     norm["iqrs"][feat_idx],
        "p_low":    norm["p_low"][feat_idx],
        "p_high":   norm["p_high"][feat_idx],
        "log_mask": norm["log_mask"][feat_idx],
    }
    X_norm = normalize_robust(X_raw, norm_sub)

    print(f"\n  Calculando probabilidades en {len(X_norm):,} muestras... ", end="", flush=True)
    probs = predict_ensemble(models, X_norm)
    print("listo")

    p_short = probs[:, 0]
    p_hold  = probs[:, 1]
    p_long  = probs[:, 2]

    print(f"\n  Distribución de p(HOLD):")
    thresholds = [0.50, 0.70, 0.80, 0.90, 0.95, 0.99, 1.00]
    for t in thresholds:
        pct = (p_hold >= t).mean()
        bar = "█" * int(pct * 40)
        color = RED if t >= 0.90 else (YELLOW if t >= 0.70 else "")
        print(f"    p(HOLD) >= {t:.0%}:  {color}{pct:.1%}  {bar}{RESET}")

    # Casos de 100% HOLD exacto
    exact_100 = (p_hold == 1.0).sum()
    near_100  = (p_hold >= 0.999).sum()
    print(f"\n  p(HOLD) = 100% exacto: {exact_100:,} casos ({exact_100/len(probs):.1%})")
    print(f"  p(HOLD) >= 99.9%:      {near_100:,} casos ({near_100/len(probs):.1%})")

    if exact_100 > 0 and "gamma_regime" in df.columns:
        mask_100 = (p_hold >= 0.999)
        print(f"\n  Composición de los casos HOLD ~100%:")
        sub = df[mask_100]
        if "vix_spot" in sub.columns:
            vix_dist = sub["vix_spot"] * 50
            print(f"    VIX medio:     {vix_dist.mean():.1f}  (rango {vix_dist.min():.1f}–{vix_dist.max():.1f})")
        if "gamma_regime" in sub.columns:
            gr = sub["gamma_regime"].value_counts(normalize=True)
            print(f"    Gamma neg:     {gr.get(0.0, 0):.0%}")
            print(f"    Gamma neutral: {gr.get(0.5, 0):.0%}")
            print(f"    Gamma pos:     {gr.get(1.0, 0):.0%}")

    # Entropía media de las predicciones
    eps = 1e-10
    entropy = -(probs * np.log(probs + eps)).sum(axis=1)
    max_entropy = math.log(3)
    norm_entropy = entropy / max_entropy
    print(f"\n  Entropía media (0=certeza total, 1=máxima incertidumbre):")
    print(f"    Global:          {norm_entropy.mean():.3f}")
    y = df["target"].values.copy()
    if y.min() < 0:
        y = (y + 1).astype(int)
    for cls, name in [(0, "SHORT"), (1, "HOLD"), (2, "LONG")]:
        sub_ent = norm_entropy[y == cls]
        if len(sub_ent) > 0:
            color = RED if sub_ent.mean() < 0.2 else ""
            print(f"    Clase {name}: {color}{sub_ent.mean():.3f}{RESET}  "
                  f"({'modelo muy seguro — posible sobreajuste' if sub_ent.mean() < 0.2 else 'OK'})")


# ══════════════════════════════════════════════════════════════════════════════
# 4. SIMULACIÓN DEL VECTOR DE FALLO (13:03 ET, SPX 6724.13)
# ══════════════════════════════════════════════════════════════════════════════
def section_failure_simulation(models, norm, feat_names):
    print(bold(f"\n{'═'*65}"))
    print(bold(f"  [ 4 ] SIMULACIÓN DEL VECTOR DE FALLO"))
    print(bold(f"  (Condiciones observadas 13:03 ET — SPX 6724.13, VIX 26.87)"))
    print(bold(f"{'═'*65}"))

    # Valores del log del bot:
    # spot=6724.13, atm_iv=0.253, vix=26.87, tlt=88.88
    # net_gamma=-1.56e+10, net_delta=-2.35e+08, net_vanna=-4.84e+07
    # TODOS los deltas a 0 (spot congelado 2+ ciclos)

    spot        = 6724.13
    atm_iv_raw  = 0.253
    vix_spot    = 26.87
    net_gamma   = -1.56e10
    net_delta   = -2.35e8
    net_vanna   = -4.84e7

    # Minutos desde apertura a las 13:03 ET = 9:30 + 213 min
    mins_since_open = 213
    minutes_to_close = 390 - mins_since_open  # 177

    base = {n: 0.0 for n in feat_names}

    # Greeks (safe_log aplicado como en training)
    base["net_gamma"]      = safe_log(net_gamma)
    base["net_delta"]      = safe_log(net_delta)
    base["net_vanna"]      = safe_log(net_vanna)
    base["net_charm"]      = safe_log(-1e6)     # estimado
    base["net_dgex"]       = safe_log(-5e8)     # estimado
    base["net_vega"]       = safe_log(-2e6)     # estimado
    base["net_vomma"]      = safe_log(-1e5)     # estimado

    # Ratios (todos congelados = delta ≈ 0)
    eps = 1e-6
    base["gamma_vanna_ratio"] = safe_log(net_gamma / (abs(net_vanna) + eps))
    base["delta_gamma_ratio"] = safe_log(net_delta / (abs(net_gamma) + eps))

    # Deltas temporales — TODOS 0 por spot congelado
    for f in ["gamma_change", "vanna_change", "dgex_change", "delta_change",
              "spot_change", "gamma_momentum", "price_vs_dgex_magnet",
              "vega_change", "vomma_change"]:
        base[f] = 0.0

    # IV / VIX
    base["atm_iv"]          = atm_iv_raw
    base["iv_zscore"]       = 0.0      # iv plana varios ciclos
    base["iv_percentile"]   = 0.5
    base["vix_spot"]        = vix_spot / 50.0
    base["vix_regime"]      = 1.0      # VIX>25: valor 2/2 = 1.0
    base["gamma_regime"]    = 0.0      # gamma negativo: 0/2 = 0.0

    # Tiempo
    base["time_sin"]             = math.sin(2 * math.pi * mins_since_open / 390)
    base["time_cos"]             = math.cos(2 * math.pi * mins_since_open / 390)
    base["minutes_to_close_norm"]= minutes_to_close / 390.0
    base["dow_sin"]              = math.sin(2 * math.pi * 0 / 5)   # lunes
    base["dow_cos"]              = math.cos(2 * math.pi * 0 / 5)

    # RSI neutro (sin movimiento)
    base["rsi"]              = 0.50
    base["vol_relative"]     = 0.20

    # Retornos vol-adj — 0 por spot congelado
    for lbl in ["1m", "5m", "15m", "30m"]:
        base[f"ret_{lbl}_vol_adj"] = 0.0

    # Wonham trend — sin tendencia
    base["wonham_trend_prob"] = 0.50

    # Gamma phase — sin señal (ventana < 30 ciclos al inicio)
    for f in ["gamma_phase_sin", "gamma_phase_cos", "gamma_amplitude_ratio", "gamma_phase_delta"]:
        base[f] = 0.0

    # Gamma speed y charm accel
    base["gamma_speed"]          = 0.0
    base["charm_accel_weighted"] = 0.0
    base["signal_persistence_5m"]= 0.0

    # ── Construir vector ──────────────────────────────────────────────────────
    X = np.array([base.get(n, 0.0) for n in feat_names], dtype=np.float32).reshape(1, -1)

    # Normalizar con RobustScaler
    X_norm = normalize_robust(X, norm)

    probs = predict_ensemble(models, X_norm)[0]

    p_short, p_hold, p_long = probs[0], probs[1], probs[2]
    pred = ["SHORT", "HOLD", "LONG"][np.argmax(probs)]
    conf = float(np.max(probs))

    print(f"\n  Predicción con vector de fallo:")
    print(f"    SHORT = {p_short:.1%}   HOLD = {p_hold:.1%}   LONG = {p_long:.1%}")
    print(f"    → {bold(pred)}  conf={conf:.0%}")

    if p_hold > 0.95:
        print(red(f"\n  CONFIRMADO: el modelo reproduce el HOLD {p_hold:.0%} con estas condiciones"))
    else:
        print(green(f"\n  El modelo NO reproduce el fallo con estas condiciones"))
        print(yellow("  Puede que falten features IB/Fibonacci que también contribuían"))

    # ── Análisis de sensibilidad: ¿qué feature rompe el HOLD? ────────────────
    print(bold(f"\n  Sensibilidad — ¿qué cambia la predicción?"))
    print(f"  {'Feature perturb.':<40} {'SHORT':>7} {'HOLD':>7} {'LONG':>7}  {'Predicción'}")
    print(f"  {'-'*40} {'-'*7} {'-'*7} {'-'*7}  {'-'*12}")

    perturbations = {
        "spot_change = +50bps  (spot sube)":      ("spot_change", 50.0),
        "spot_change = -50bps  (spot baja)":       ("spot_change", -50.0),
        "spot_change = +150bps (movimiento real)": ("spot_change", 150.0),
        "gamma_change = safe_log(-1e9)":           ("gamma_change", safe_log(-1e9)),
        "vix_spot = 20 (VIX baja)":               ("vix_spot", 20.0 / 50.0),
        "vix_regime = 0.5 (VIX 18-25)":           ("vix_regime", 0.5),
        "ret_5m_vol_adj = +2.0":                   ("ret_5m_vol_adj", 2.0),
        "ret_5m_vol_adj = -2.0":                   ("ret_5m_vol_adj", -2.0),
        "gamma_regime = 0.5 (neutral)":            ("gamma_regime", 0.5),
        "gamma_regime = 1.0 (positivo)":           ("gamma_regime", 1.0),
        "iv_zscore = +1.5 (IV sube)":              ("iv_zscore", 1.5 / 3.0),
        "minutes_to_close_norm = 0.1 (final día)": ("minutes_to_close_norm", 0.1),
        "rsi = 0.30 (oversold)":                   ("rsi", 0.30),
        "rsi = 0.70 (overbought)":                 ("rsi", 0.70),
    }

    found = [feat for _, (feat, _) in perturbations.items() if feat in feat_names]
    if not found:
        print(yellow(f"  Ninguna feature de sensibilidad encontrada en feat_names."))
        print(yellow(f"  Primeras 10 feat_names: {list(feat_names)[:10]}"))
    for label, (feat, val) in perturbations.items():
        if feat not in feat_names:
            continue
        X_p = X.copy()
        idx = list(feat_names).index(feat)
        X_p[0, idx] = val
        X_p_norm = normalize_robust(X_p, norm)
        p_p = predict_ensemble(models, X_p_norm)[0]
        pred_p = ["SHORT", "HOLD", "LONG"][np.argmax(p_p)]
        changed = " ← CAMBIA" if pred_p != pred else ""
        color = GREEN if pred_p != "HOLD" else ""
        print(f"  {label:<40} {p_p[0]:>7.1%} {p_p[1]:>7.1%} {p_p[2]:>7.1%}  "
              f"{color}{pred_p}{changed}{RESET}")


# ══════════════════════════════════════════════════════════════════════════════
# 5. DISTRIBUCIÓN DE LABELS EN RÉGIMEN CRÍTICO DETALLADO
# ══════════════════════════════════════════════════════════════════════════════
def section_critical_regime_deep(df: pd.DataFrame):
    print(bold(f"\n{'═'*65}"))
    print(bold(f"  [ 5 ] RÉGIMEN CRÍTICO — ANÁLISIS PROFUNDO"))
    print(bold(f"{'═'*65}"))

    y = df["target"].values.copy()
    if y.min() < 0:
        y = (y + 1).astype(int)
    df = df.copy()
    df["_y"] = y

    # Construir máscara del régimen crítico
    masks = {}

    if "vix_spot" in df.columns:
        masks["VIX>=25"] = df["vix_spot"] * 50 >= 25

    if "gamma_regime" in df.columns:
        masks["Gamma_neg"] = df["gamma_regime"] == 0.0
        masks["Gamma_neg_AND_vix25"] = (
            masks.get("VIX>=25", pd.Series(True, index=df.index)) & masks["Gamma_neg"]
        )

    if not masks:
        print(yellow("  Faltan columnas vix_spot o gamma_regime en training data"))
        return

    for name, mask in masks.items():
        sub = df[mask]
        n = len(sub)
        if n == 0:
            continue
        yd = np.bincount(sub["_y"].values, minlength=3)
        hold_pct = yd[1] / n
        print(f"\n  {bold(name)} — {n:,} muestras")
        print(f"    SHORT={yd[0]:,} ({yd[0]/n:.1%})  "
              f"HOLD={yd[1]:,} ({hold_pct:.1%})  "
              f"LONG={yd[2]:,} ({yd[2]/n:.1%})")

        # Ratio HOLD vs global
        global_hold = (y == 1).mean()
        ratio = hold_pct / global_hold if global_hold > 0 else 0
        color = RED if ratio > 1.5 else (YELLOW if ratio > 1.2 else GREEN)
        print(f"    Ratio HOLD vs global: {color}{ratio:.2f}x{RESET}  "
              f"({'sesgo detectado' if ratio > 1.5 else 'normal'})")

        # Señales disponibles en este régimen
        if n >= 10:
            shorts = yd[0]
            longs  = yd[2]
            signals = shorts + longs
            print(f"    Señales disponibles (SHORT+LONG): {signals:,} de {n:,} ({signals/n:.1%})")
            if signals < 50:
                print(red(f"    ADVERTENCIA: solo {signals} ejemplos direccionales — "
                          f"modelo nunca aprendió a señalizar aquí"))



# ══════════════════════════════════════════════════════════════════════════════
# ANÁLISIS DE PARQUETS INPUT (sin target — solo features)
# ══════════════════════════════════════════════════════════════════════════════
def _analyze_input_parquets(parquet_files: list, feat_names: list, sample: int = 50000):
    """
    Analiza la distribución de regímenes en los parquets INPUT_SPY_*.parquet.
    Estos no tienen 'target' pero sí las features del modelo.
    Muestra cuántas filas hay en cada régimen de VIX/gamma para evaluar
    si el training data cubre el régimen de alta volatilidad.
    """
    print(bold(f"\n{'═'*65}"))
    print(bold(f"  [ 2b ] COBERTURA DE RÉGIMEN EN TRAINING DATA"))
    print(bold(f"  (Parquets INPUT sin target — análisis de features de régimen)"))
    print(bold(f"{'═'*65}"))

    chunks = []
    max_per_file = max(1, sample // len(parquet_files)) if sample > 0 else None

    for fpath in parquet_files:
        try:
            df_d = pd.read_parquet(fpath)
            if max_per_file and len(df_d) > max_per_file:
                df_d = df_d.sample(n=max_per_file, random_state=42)
            # Extraer fecha del nombre de archivo
            bname = os.path.basename(fpath)
            date_part = bname.replace("INPUT_SPY_", "").replace(".parquet", "")
            df_d["_date"] = date_part
            chunks.append(df_d)
        except Exception as e:
            print(yellow(f"  Saltando {os.path.basename(fpath)}: {e}"))

    if not chunks:
        print(red("  No se pudieron cargar parquets"))
        return

    df = pd.concat(chunks, ignore_index=True)
    print(f"\n  Total: {len(df):,} filas | {len(parquet_files)} días de trading")

    # ── Detectar columna VIX ──────────────────────────────────────────────────
    vix_col = None
    for c in ("vix_spot", "vix", "VIX"):
        if c in df.columns:
            vix_col = c
            break

    if vix_col:
        vix_raw = df[vix_col]
        # Si está normalizado (dividido /50), reconstruir
        if vix_raw.max() < 2.0:
            vix_raw = vix_raw * 50.0

        print(f"\n  Distribución VIX en training data:")
        print(f"  {'Régimen':<35} {'Filas':>8}  {'%':>6}  {'Días aprox':>10}")
        print(f"  {'-'*35} {'-'*8}  {'-'*6}  {'-'*10}")

        bands = [
            ("VIX < 15  (low vol, post-election)",  vix_raw < 15),
            ("VIX 15-18",                            (vix_raw >= 15) & (vix_raw < 18)),
            ("VIX 18-20",                            (vix_raw >= 18) & (vix_raw < 20)),
            ("VIX 20-25",                            (vix_raw >= 20) & (vix_raw < 25)),
            ("VIX 25-30  ← RÉGIMEN 9-MAR",          (vix_raw >= 25) & (vix_raw < 30)),
            ("VIX >= 30  (crisis)",                  vix_raw >= 30),
        ]
        for label, mask in bands:
            n = mask.sum()
            pct = n / len(df)
            days_est = df[mask]["_date"].nunique() if "_date" in df.columns else "?"
            color = RED if (n == 0 and "25-30" in label) else (YELLOW if pct < 0.05 and "25" in label else "")
            print(f"  {color}{label:<35} {n:>8,}  {pct:>6.1%}  {days_est:>10}{RESET}")

        vix_mean = vix_raw.mean()
        vix_max  = vix_raw.max()
        print(f"\n  VIX medio en training: {vix_mean:.1f}  |  VIX máximo: {vix_max:.1f}")

        if vix_max < 25:
            print(red(f"\n  PROBLEMA CRÍTICO: el training data NO contiene ningún día con VIX>=25"))
            print(red(f"  El modelo nunca vio el régimen del 9-Mar-2026 (VIX=26.87)"))
            print(yellow(f"  Solución: añadir datos de Feb-Mar 2025 (VIX llegó a 28+) al training"))
        elif (vix_raw >= 25).sum() / len(df) < 0.05:
            pct_25 = (vix_raw >= 25).sum() / len(df)
            print(yellow(f"\n  ADVERTENCIA: solo {pct_25:.1%} del training data tiene VIX>=25"))
            print(yellow(f"  El modelo tiene muy pocos ejemplos de este régimen"))

    # ── Detectar columna gamma_regime ─────────────────────────────────────────
    gamma_col = None
    for c in ("gamma_regime", "net_gamma"):
        if c in df.columns:
            gamma_col = c
            break

    if gamma_col == "gamma_regime":
        print(f"\n  Distribución gamma_regime en training data:")
        gr = df[gamma_col].value_counts().sort_index()
        names = {0.0: "Negativo (dealers short gamma)", 0.5: "Neutral", 1.0: "Positivo"}
        for val, count in gr.items():
            lbl = names.get(val, str(val))
            color = YELLOW if val == 0.0 and count / len(df) < 0.15 else ""
            print(f"  {color}  gamma={val:.1f} ({lbl:<35}) {count:>8,}  ({count/len(df):.1%}){RESET}")

    # ── Régimen crítico combinado ─────────────────────────────────────────────
    if vix_col and gamma_col == "gamma_regime":
        vix_crit   = vix_raw >= 25
        gamma_crit = df[gamma_col] == 0.0
        combined   = vix_crit & gamma_crit
        n_comb = combined.sum()
        print(f"\n  {bold('Régimen crítico combinado (VIX>=25 AND gamma negativo):')} "
              f"{n_comb:,} filas ({n_comb/len(df):.2%})")
        if n_comb == 0:
            print(red("  NINGÚN ejemplo de este régimen en training — el modelo opera a ciegas aquí"))
        elif n_comb < 500:
            print(red(f"  Solo {n_comb} ejemplos — insuficiente para aprender señales direccionales"))

    # ── Timeline de VIX por fecha ─────────────────────────────────────────────
    if vix_col and "_date" in df.columns:
        print(bold(f"\n  VIX medio por fecha de trading:"))
        daily_vix = df.groupby("_date")[vix_col].mean()
        if daily_vix.max() < 2.0:
            daily_vix = daily_vix * 50.0
        # Mostrar solo días con VIX>18 o primero/último
        dates = sorted(daily_vix.index)
        print(f"  {'Fecha':<12} {'VIX medio':>10}  {'Régimen'}")
        print(f"  {'-'*12} {'-'*10}  {'-'*20}")
        for d in dates:
            v = daily_vix[d]
            if v >= 25:
                regime = red("ALTO  ← en training")
            elif v >= 20:
                regime = yellow("ELEVADO")
            elif v >= 18:
                regime = yellow("moderado")
            else:
                regime = "bajo"
            # Mostrar todos los días con VIX>18 y el primero/último
            if v >= 18 or d == dates[0] or d == dates[-1]:
                print(f"  {d:<12} {v:>10.1f}  {regime}")


# ══════════════════════════════════════════════════════════════════════════════
# MAIN
# ══════════════════════════════════════════════════════════════════════════════
def main():
    parser = argparse.ArgumentParser(description="Diagnóstico del modelo GBM")
    parser.add_argument("--model", required=True,   help="Ruta al .joblib del modelo")
    parser.add_argument("--norm",  required=True,   help="Ruta al .npz del normalizer")
    parser.add_argument("--data",  default=None,    help="CSV/parquet de training data (opcional)")
    parser.add_argument("--top-features", type=int, default=30)
    parser.add_argument("--sample", type=int, default=50000,
                        help="Max muestras a usar del training data (0=todas)")
    args = parser.parse_args()

    # ── Cargar modelo ─────────────────────────────────────────────────────────
    models, norm, feat_names = load_model(args.model, args.norm)

    # ── Feature importance (no requiere data) ─────────────────────────────────
    section_feature_importance(models, feat_names, top_n=args.top_features)

    # ── Simulación del fallo (no requiere data) ───────────────────────────────
    section_failure_simulation(models, norm, feat_names)

    # ── Análisis de training data (si se proporciona) ─────────────────────────
    if args.data:
        import glob as _glob
        data_path = args.data

        # ── Detectar si es directorio con parquets diarios ─────────────────
        parquet_files = []
        if os.path.isdir(data_path):
            parquet_files = sorted(_glob.glob(os.path.join(data_path, "**", "*.parquet"), recursive=True))
            parquet_files += sorted(_glob.glob(os.path.join(data_path, "*.parquet")))
            parquet_files = sorted(set(parquet_files))
        elif data_path.endswith(".parquet"):
            parquet_files = [data_path]

        if parquet_files:
            print(bold(f"\n[DATOS] {len(parquet_files)} archivos parquet encontrados"))
            print(f"  Rango: {os.path.basename(parquet_files[0])} → {os.path.basename(parquet_files[-1])}")

            # Inspeccionar columnas del primero
            df_peek = pd.read_parquet(parquet_files[0])
            print(f"  Columnas ({len(df_peek.columns)}): {list(df_peek.columns[:8])}...")
            has_target = "target" in df_peek.columns
            if not has_target:
                print(red("  Columna 'target' no encontrada en los parquets INPUT"))
                print(yellow("  Estos son parquets de INPUT (features sin label)."))
                print(yellow("  Analizando distribución de features de régimen..."))
                _analyze_input_parquets(parquet_files, feat_names, args.sample)
            else:
                # Cargar todos con sampling
                chunks = []
                total_rows = 0
                max_per_file = max(1, args.sample // len(parquet_files)) if args.sample > 0 else None
                for fpath in parquet_files:
                    try:
                        df_day = pd.read_parquet(fpath)
                        if max_per_file and len(df_day) > max_per_file:
                            df_day = df_day.sample(n=max_per_file, random_state=42)
                        chunks.append(df_day)
                        total_rows += len(df_day)
                    except Exception as e:
                        print(yellow(f"  Saltando {os.path.basename(fpath)}: {e}"))
                df = pd.concat(chunks, ignore_index=True)
                print(f"  Total cargado: {len(df):,} filas de {len(parquet_files)} archivos")
                section_label_distribution(df)
                section_critical_regime_deep(df)
                section_calibration(models, norm, feat_names, df)

        elif data_path.endswith(".csv"):
            print(bold(f"\n[DATOS] Cargando {data_path}..."))
            try:
                df = pd.read_csv(data_path)
                print(f"  {len(df):,} filas, {len(df.columns)} columnas")
                if args.sample > 0 and len(df) > args.sample:
                    df = df.sample(n=args.sample, random_state=42)
                if "target" not in df.columns:
                    print(red("  Columna 'target' no encontrada"))
                else:
                    section_label_distribution(df)
                    section_critical_regime_deep(df)
                    section_calibration(models, norm, feat_names, df)
            except Exception as e:
                print(red(f"  Error cargando datos: {e}"))
        else:
            print(red(f"  No se encontraron datos en: {data_path}"))
    else:
        print(yellow("\n  Tip: añade --data training_data/data_training_input para análisis de régimen"))

    print(bold(f"\n{'═'*65}"))
    print(bold(f"  Diagnóstico completado"))
    print(bold(f"{'═'*65}\n"))


if __name__ == "__main__":
    main()
