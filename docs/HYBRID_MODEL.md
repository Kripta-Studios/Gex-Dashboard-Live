# Hybrid Attention-MLP Trading Model

Documentación técnica detallada sobre la arquitectura del modelo de machine learning utilizado para generar señales de trading de alta precisión, combinando exposiciones de griegas (0DTE y Semanales) con análisis de contexto de mercado.

---

## Índice

1. [Introducción](#1-introducción)
2. [Arquitectura del Modelo](#2-arquitectura-del-modelo)
3. [Features de Entrada (66 Features)](#3-features-de-entrada-66-features)
4. [Flujo de Datos](#4-flujo-de-datos)
5. [Técnicas Anti-Overfitting](#5-técnicas-anti-overfitting)
6. [Interpretabilidad](#6-interpretabilidad)
7. [Entrenamiento Walk-Forward](#7-entrenamiento-walk-forward)
8. [Configuración y Uso](#8-configuración-y-uso)

---

## 1. Introducción

El **Hybrid Attention-MLP** es una red neuronal diseñada para superar los desafíos del trading algorítmico con datasets limitados (market data es caro y finito). A diferencia de modelos "caja negra", este sistema está diseñado para ser **interpretable** y **robusto**.

### Innovaciones Clave
*   **Feature Attention Layer**: Mecanismo de atención que aprende dinámicamente qué variables (griegas, niveles, momentum) son relevantes para cada predicción.
*   **Dual-Head Output**:
    *   **Clasificación**: Predice la dirección (LONG/SHORT/HOLD).
    *   **Regresión Bayesiana (Tiempo)**: Estima *cuándo* se alcanzará el objetivo y la *incertidumbre* (sigma) de esa predicción.
*   **Multi-Timeframe Analysis**: Integra griegas de 0DTE (corto plazo) con griegas Semanales (estructural) para detectar divergencias.

---

## 2. Arquitectura del Modelo

El modelo combina la capacidad de selección de features de los Transformers con la eficiencia de los MLPs regularizados.

```mermaid
graph TD
    Input[Input Features (66)] --> Norm[Z-Score Normalization]
    Norm --> AttnLayer[Feature Attention Layer]
    
    subgraph "Feature Attention Block"
    AttnLayer --> Embed[Feature Embedding (64 dims)]
    Embed --> TypeEmbed[Feature Type Embedding]
    TypeEmbed --> MultiHead[Multi-Head Self-Attention]
    MultiHead --> Weighted[Weighted Feature Combination]
    end
    
    Weighted --> Concat[Concatenation (Attended + Original)]
    Concat --> MLP[Regularized MLP Blocks]
    
    subgraph "Deep Processing"
    MLP --> Block1[Dense 256 + BN + GELU + Dropout]
    Block1 --> Block2[Dense 128 + BN + GELU + Dropout]
    Block2 --> Block3[Dense 64 + BN + GELU + Dropout]
    end
    
    Block3 --> Head1[Classification Head]
    Block3 --> Head2[Bayesian Time Head]
    
    Head1 --> ClassOut[Probabilities (LONG, HOLD, SHORT)]
    Head2 --> TimeOut[Time Prediction (Mu, Sigma)]
```

### Componentes Principales

1.  **Feature Attention Layer**:
    *   Proyecta cada feature a un espacio latente de 64 dimensiones.
    *   Usa *Self-Attention* para entender las relaciones entre features (ej. "¿Importa el Gamma Negativo si el Vanna es positivo?").
    *   Genera un vector de "importancia" que pondera las features antes de pasarlas al MLP.

2.  **Regularized MLP Blocks**:
    *   Red neuronal densa profunda con **Residual Connections** (ResNet-style).
    *   Uso agresivo de **Dropout (0.3 - 0.5)** y **Batch Normalization** para prevenir overfitting en datasets pequeños.

3.  **Bayesian Time Head**:
    *   No solo predice la dirección, sino el **tiempo estimado para el target**.
    *   Salida probabilística: Media ($\mu$) e Incertidumbre ($\sigma$).
    *   *Uso en Trading*: Si la incertidumbre ($\sigma$) es muy alta (>45 min), el bot puede decidir no operar aunque la señal direccional sea fuerte.

---

## 3. Features de Entrada (93 Features)

El modelo utiliza un set expandido de **93 variables** derivadas de la cadena de opciones, contexto de mercado y análisis técnico avanzado.

### 3.1 0DTE Greeks (21 Features)
Energía intradiaria del mercado.
*   **Net Exposures**: `net_gamma`, `net_vanna`, `net_charm`, `net_dgex`, `net_zomma`, `net_delta`.
*   **Vol/Risk Exposures**: `net_vega` (Sensibilidad a Vol), `net_vomma` (Aceleración de Vol).
*   **Regime Signals**: Flags binarios/continuos como `gamma_regime`, `vanna_bullish`, `dgex_sticky`, `zomma_stabilizing`.
*   **Level Distances**: Distancia porcentual al precio actual de niveles clave (`max_gamma`, `min_vanna`, `zero_gamma`).

### 3.2 Weekly Greeks (16 Features)
Estructura de mercado a mediano plazo.
*   **Net Exposures**: `wk_net_gamma`, `wk_net_vanna`, `wk_net_vega`, `wk_net_vomma`.
*   **Level Distances**: Distancias a muros semanales (`wk_max_gamma`, `wk_max_dgex`, etc.).
*   **Regime**: Contexto semanal (`wk_gamma_regime`) para filtrar ruido intradiario.

### 3.3 Cross-Expiry Divergence (6 Features)
Conflictos entre plazos temporales.
*   `gamma_0dte_vs_wk`: Divergencia de signo en Gamma.
*   `vanna_0dte_vs_wk`: flujo 0DTE vs flujo semanal.
*   `dgex_0dte_vs_wk`, `vega_0dte_vs_wk`.

### 3.4 IB + Fibonacci + Confluences (25 Features)
Contexto de precio avanzado y zonas de confluencia.
*   **Initial Balance (IB)**: Niveles `price_vs_ib_high`, `ib_range_pct`.
*   **Fibonacci Extensions**: Distancias a extensiones 127.2%, 161.8% y 200% (Bullish y Bearish).
*   **RBF Confluences**: Features sintéticos generados por Kernels RBF que miden la superposición entre niveles técnicos (IB/Fib) y niveles de Griegas (Muros de Gamma/Vega).
    *   *Ejemplo*: `confluence_ib_high_max_gamma` (1.0 si IB High coincide con Max Gamma).

### 3.5 Engineered Features (25 Features)
Variables de alto orden y dinámicas.
*   **Ratios**: Relaciones de fuerza relativa.
    *   `gamma_vanna_ratio`, `dgex_gamma_ratio`, `vomma_vega_ratio`.
*   **Temporal Deltas**: Derivada temporal (cambio por minuto).
    *   `gamma_change`, `vanna_change`, `vega_change`, `vomma_change`.
*   **Momentum & Magnetism**: `gamma_momentum`, `price_vs_dgex_magnet`.

---

## 4. Dimensionality Reduction Pipeline

Dada la alta dimensionalidad (93 features), el sistema implementa un pipeline de reducción de características antes del entrenamiento para evitar la "maldición de la dimensionalidad":

1.  **Variance Filtering**: Elimina features estáticas o con varianza casi nula.
2.  **Correlation Grouping (Union-Find)**: Agrupa features colineales (corr > 0.95) y selecciona la más representativa del grupo.
3.  **Grouped PCA**: Aplica PCA independientemente a cada grupo lógico de features (ej. Grupo Volatilidad, Grupo Gamma) para extraer componentes principales densos manteniendo la interpretabilidad semántica.

---

## 5. Flujo de Datos

1.  **Colección de Datos (Market Hours)**:
    *   `gex_daemon.py` genera snapshots de griegas (Madrid Time).
    *   `ib_service.py` calcula niveles de Initial Balance.
2.  **Pre-procesamiento (`collect_training_data.py`)**:
    *   Alineación de Timezones (Madrid (-6h) -> EST).
    *   Cálculo de Targets (Lookahead 120min, Threshold 0.4%).
    *   Generación de `training_data.csv`.
3.  **Entrenamiento (`train_hybrid.py`)**:
    *   Feature Selection automática.
    *   Optimización de pesos con **Label Smoothing Loss** (para clasificación) y **Gaussian NLL** (para tiempo).

---

## 5. Técnicas Anti-Overfitting

Dado el ruido inherente a los mercados financieros, el modelo prioriza la **generalización** sobre la precisión en training.

| Técnica | Implementación | Propósito |
| :--- | :--- | :--- |
| **Label Smoothing** | `target = 0.9` en lugar de `1.0` | Evita que el modelo tenga "exceso de confianza" en señales ruidosas. |
| **Heavy Dropout** | `p=0.3` a `0.4` | Apaga neuronas aleatoriamente para forzar redundancia en el aprendizaje. |
| **Feature Augmentation** | Ruido Gaussiano durante training | Simula variaciones de mercado y errores de datos. |
| **Weight Decay** | L2 Regularization | Mantiene los pesos pequeños para evitar curvas de decisión complejas. |

---

## 6. Interpretabilidad

A diferencia de muchos modelos de "caja negra", el Hybrid Model puede explicar sus decisiones.

Mediante el método `get_feature_importance(x)`, podemos extraer qué features contribuyeron más a una señal específica.
*   *Ejemplo*: "El modelo entró en LONG porque detectó `gamma_regime` positivo alineado con un `vanna_bullish` fuerte, ignorando el RSI."

Esto es crucial para que el trader humano confíe en (o descarte) la señal.

---

## 7. Entrenamiento Walk-Forward

El modelo se valida utilizando una metodología estricta de **Walk-Forward** para evitar el *Lookahead Bias* (ver el futuro).

*   **Ventana Deslizante**: Entrena en [Enero-Marzo], Testea en [Abril]. Luego Entrena en [Febrero-Abril], Testea en [Mayo].
*   **Beneficio**: Simula exactamente cómo se comportaría el modelo en producción, re-entrenándose periódicamente con nuevos datos.

---

## 8. Configuración y Uso

### Entrenamiento
```bash
python bots/train_hybrid.py --model-size medium --epochs 200 --batch-size 128
```

### Inferencia (Trading)
El modelo es cargado por `tradingbot_wrapper.py`:
```python
model = load_hybrid_model("models/trading_hybrid.pt", "models/hybrid_normalizer.npz")
probs, time_pred = model.predict(features)
feature_imp = model.get_feature_importance(features)
```
