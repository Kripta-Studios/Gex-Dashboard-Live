# Hybrid Attention-MLP Trading Model

Documentación técnica y divulgativa sobre la arquitectura del modelo de machine learning utilizado para generar señales de trading basándose en exposiciones de griegas de opciones.

---

## Índice

1. [Introducción](#1-introducción)
2. [¿Por Qué un Modelo Híbrido?](#2-por-qué-un-modelo-híbrido)
3. [Arquitectura del Modelo](#3-arquitectura-del-modelo)
4. [Features de Entrada](#4-features-de-entrada)
5. [Flujo de Datos](#5-flujo-de-datos)
6. [Técnicas Anti-Overfitting](#6-técnicas-anti-overfitting)
7. [Interpretabilidad](#7-interpretabilidad)
8. [Configuraciones del Modelo](#8-configuraciones-del-modelo)
9. [Entrenamiento Walk-Forward](#9-entrenamiento-walk-forward)
10. [Métricas de Evaluación](#10-métricas-de-evaluación)

---

## 1. Introducción

El **Hybrid Attention-MLP** es una red neuronal diseñada específicamente para trading algorítmico con datasets pequeños (10K-100K muestras). Combina dos técnicas poderosas:

```
Features (Greeks + IB + IV) → Attention Layer → MLP Classifier → Señal (LONG/HOLD/SHORT)
```

### Problema que Resuelve

Los modelos de trading tradicionales tienen un problema: **overfitting**. Con solo ~50K muestras de mercado, es fácil que un modelo "memorice" los datos en lugar de aprender patrones generalizables.

Nuestro modelo híbrido ataca esto con:
- **Feature Attention**: El modelo aprende qué features son importantes dinámicamente
- **Regularización pesada**: Dropout, BatchNorm, weight decay
- **Walk-forward training**: Evita lookahead bias completamente

---

## 2. ¿Por Qué un Modelo Híbrido?

### Alternativas Consideradas

| Modelo | Pros | Contras |
|--------|------|---------|
| **MLP Simple** | Rápido, fácil | No sabe qué features importan |
| **Transformer** | Mucha capacidad | Overfitting con datos pequeños |
| **Random Forest** | Robusto | No captura relaciones complejas |
| **LSTM** | Bueno para secuencias | Necesita mucha data temporal |

### Nuestra Solución: Lo Mejor de Ambos Mundos

```
┌─────────────────────────────────────────────────────────────────┐
│                  HYBRID ATTENTION-MLP MODEL                     │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  ┌─────────────────┐     ┌─────────────────┐                   │
│  │ Feature Attention│ +   │ MLP Classifier  │                   │
│  │ (Del Transformer) │     │ (Regularizado)  │                   │
│  └─────────────────┘     └─────────────────┘                   │
│         │                       │                               │
│         │   Interpretabilidad   │   Eficiencia                  │
│         │   Qué features        │   Predicción                  │
│         │   importan            │   robusta                     │
│         │                       │                               │
└─────────────────────────────────────────────────────────────────┘
```

---

## 3. Arquitectura del Modelo

### Diagrama Completo

```
Input: 38 features
         │
         ▼
┌─────────────────────────────────────────────────────────────────┐
│                    FEATURE ATTENTION LAYER                      │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  1. Feature Embedding                                           │
│     Cada feature → vector de 64 dimensiones                     │
│     [net_gamma] → [0.23, -0.54, 0.81, ...]                     │
│                                                                 │
│  2. Type Embedding (como "positional encoding")                 │
│     Cada posición de feature tiene embedding único              │
│     Posición 0 (net_gamma) ≠ Posición 5 (gamma_regime)         │
│                                                                 │
│  3. Multi-Head Self-Attention                                   │
│     Cada feature "mira" a las otras features                    │
│     "¿El net_gamma es relevante dado el vanna_bullish?"        │
│                                                                 │
│  4. Importance Query                                            │
│     Vector aprendido que determina pesos finales                │
│     Output: attention_weights (38 valores, suman 1.0)           │
│                                                                 │
│  Output: attended_features (64 dims) + attention_weights        │
└─────────────────────────────────────────────────────────────────┘
         │
         │ Concatenar con features originales
         │ [attended_features (64) + original_features (38)]
         ▼
┌─────────────────────────────────────────────────────────────────┐
│                    REGULARIZED MLP BLOCKS                       │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  Block 1: Linear(102 → 128) + BatchNorm + GELU + Dropout(0.35) │
│  Block 2: Linear(128 → 64)  + BatchNorm + GELU + Dropout(0.35) │
│  Block 3: Linear(64 → 32)   + BatchNorm + GELU + Dropout(0.35) │
│                                                                 │
│  * Cada block tiene conexión residual si dims coinciden        │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
         │
         ▼
┌─────────────────────────────────────────────────────────────────┐
│                    CLASSIFICATION HEAD                          │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  Linear(32 → 16) + BatchNorm + GELU + Dropout                  │
│  Linear(16 → 3)  → Softmax                                     │
│                                                                 │
│  Output: [P(SHORT), P(HOLD), P(LONG)]                          │
│          [0.15,     0.25,    0.60]                              │
│                                                                 │
│  Predicción: LONG (60% confianza)                              │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

---

## 4. Features de Entrada

El modelo recibe **38 features** organizadas en 6 categorías:

### 4.1 Greek Exposures (5 features)

| Feature | Descripción | Rango Típico |
|---------|-------------|--------------|
| `net_gamma` | Exposición neta de gamma | -1e9 a +1e9 |
| `net_vanna` | Exposición neta de vanna | -1e9 a +1e9 |
| `net_charm` | Exposición neta de charm | -1e9 a +1e9 |
| `net_dgex` | Delta-adjusted gamma | -1e9 a +1e9 |
| `net_zomma` | Sensibilidad de gamma a vol | -1e9 a +1e9 |

**Intuición**: Estas métricas miden el "combustible" que los dealers tienen. Gamma positivo = dealers compran dips. Gamma negativo = dealers amplifican movimientos.

### 4.2 Greek Signals (5 features)

| Feature | Descripción | Valores |
|---------|-------------|---------|
| `gamma_regime` | Régimen de gamma | 0 (negativo) / 1 (positivo) |
| `vanna_bullish` | Señal de vanna | 0 / 1 |
| `charm_bullish` | Señal de charm | 0 / 1 |
| `dgex_sticky` | Mercado "pegajoso" | 0 / 1 |
| `zomma_stabilizing` | Estabilización | 0 / 1 |

### 4.3 Level Distances (4 features)

| Feature | Descripción |
|---------|-------------|
| `dist_to_max_gamma` | Distancia al strike con máximo gamma |
| `dist_to_min_gamma` | Distancia al strike con mínimo gamma |
| `dist_to_min_vanna` | Distancia al "imán" de Min Vanna |
| `dist_to_zero_gamma` | Distancia al nivel de gamma = 0 |

### 4.4 IB Features (8 features)

| Feature | Descripción |
|---------|-------------|
| `price_vs_ib_high` | Precio relativo al IB high |
| `price_vs_ib_low` | Precio relativo al IB low |
| `ib_range_pct` | Tamaño del rango IB (%) |
| `near_ib_high` | ¿Cerca del IB high? |
| `near_ib_low` | ¿Cerca del IB low? |
| `above_ib` | ¿Por encima del rango IB? |
| `below_ib` | ¿Por debajo del rango IB? |
| `in_ib_range` | ¿Dentro del rango IB? |

### 4.5 IV/VIX Features (6 features)

| Feature | Descripción |
|---------|-------------|
| `atm_iv` | Volatilidad implícita ATM |
| `iv_zscore` | Z-score de IV (normalizado) |
| `iv_percentile` | Percentil de IV histórica |
| `vix_spot` | VIX spot normalizado |
| `vix_gamma` | Gamma del VIX |
| `vix_regime` | Régimen de volatilidad |

### 4.6 Market Context (10 features)

| Feature | Descripción |
|---------|-------------|
| `hour` | Hora del día (normalizada) |
| `minute` | Minuto (normalizado) |
| `rsi` | RSI (0-1) |
| `vol_relative` | Volumen relativo al promedio |
| `near_max_gamma` | Flag: cerca del max gamma |
| `near_min_gamma` | Flag: cerca del min gamma |
| `near_min_vanna` | Flag: cerca del min vanna |
| `near_zero_gamma` | Flag: cerca del zero gamma |
| `dist_fib_127_up` | Distancia a Fib 127% up |
| `dist_fib_161_up` | Distancia a Fib 161% up |

---

## 5. Flujo de Datos

### Paso a Paso

```
1. DATOS CRUDOS
   ├── Greeks JSON (gex_daemon.py)
   ├── IB JSON (ib_service.py)
   └── Fourier JSON (fourier_service_fast.py)
              │
              ▼
2. FEATURE EXTRACTION (collect_training_data.py)
   ├── Calcular net exposures
   ├── Detectar niveles clave
   ├── Normalizar a [0,1] o z-score
   └── Generar labels (LONG/HOLD/SHORT basado en movimiento futuro)
              │
              ▼
3. NORMALIZACIÓN (FeatureNormalizer)
   ├── Z-score: (x - mean) / std
   └── Guardar mean/std para inference
              │
              ▼
4. FORWARD PASS
   ├── Feature Attention: importancia de cada feature
   ├── Concatenar: attended + original
   ├── MLP Blocks: transformaciones no-lineales
   └── Classification: probabilidades por clase
              │
              ▼
5. OUTPUT
   ├── Predicción: LONG/HOLD/SHORT
   ├── Confianza: 0-100%
   └── Feature Importance: cuáles features influyeron
```

---

## 6. Técnicas Anti-Overfitting

### 6.1 Dropout (0.25-0.40)

```python
# Durante training, 35% de neuronas se "apagan" aleatoriamente
self.dropout = nn.Dropout(0.35)
```

**Efecto**: El modelo no puede depender de un solo camino → aprende representaciones robustas.

### 6.2 Batch Normalization

```python
self.bn = nn.BatchNorm1d(hidden_dim)
```

**Efecto**: Normaliza activaciones entre capas → training más estable, generalización mejor.

### 6.3 Weight Decay (L2 Regularization)

```python
optimizer = optim.AdamW(model.parameters(), weight_decay=0.05)
```

**Efecto**: Penaliza pesos grandes → modelo más simple.

### 6.4 Label Smoothing

```python
# En vez de target = [0, 0, 1], usamos:
target = [0.05, 0.05, 0.90]
```

**Efecto**: El modelo no tiene overconfidence → calibración mejor.

### 6.5 Early Stopping

```python
if val_loss > best_val_loss for 25 epochs:
    stop_training()
```

**Efecto**: Paramos antes de que memorice el training set.

### 6.6 Data Augmentation

```python
# Añadir ruido gaussiano a features
x_augmented = x + torch.randn_like(x) * 0.05
```

**Efecto**: Más variedad en datos → mejor generalización.

---

## 7. Interpretabilidad

### Feature Attention Weights

Una ventaja clave del modelo híbrido es que sabemos **qué features le importan** para cada predicción:

```python
model.eval()
logits, attention = model(features, return_attention=True)

# attention.shape = (batch_size, 38)
# attention[0] = [0.12, 0.08, 0.03, ..., 0.05]  # suman 1.0
```

### Ejemplo de Interpretación

```
Predicción: LONG (72% confianza)

Feature Importance:
  gamma_regime:    0.18  ← El modelo ve gamma positivo
  near_support:    0.15  ← Cerca de soporte
  vanna_bullish:   0.12  ← Vanna apunta arriba
  dist_min_vanna:  0.10  ← Min vanna está arriba (imán)
  net_dgex:        0.08  ← DGEX sticky
  ...otros:        0.37

Interpretación humana:
"Gamma positivo + cerca de soporte + vanna bullish = dealers comprarán dips"
```

### Visualización de Attention

```python
from visualize_hybrid import plot_feature_importance

plot_feature_importance(model, sample_features, FEATURE_COLUMNS)
# Genera heatmap de importancia por feature
```

---

## 8. Configuraciones del Modelo

### Tamaños Disponibles

| Size | Params | embed_dim | hidden_dims | dropout | Uso Recomendado |
|------|--------|-----------|-------------|---------|-----------------|
| **micro** | ~50K | 32 | [64, 32] | 0.40 | Datasets < 10K |
| **small** | ~150K | 64 | [128, 64, 32] | 0.35 | **Recomendado** |
| **medium** | ~500K | 128 | [256, 128, 64] | 0.30 | Datasets > 50K |
| **large** | ~1M | 256 | [512, 256, 128, 64] | 0.25 | Datasets > 100K |

### Recomendación

Para trading con datos de ~30 días ≈ 50K samples:
- **Usa `small`** - Buen balance entre capacidad y generalización
- **Si overfitting**: Cambia a `micro` o aumenta dropout
- **Si underfitting**: Prueba `medium` con más epochs

```python
from hybrid_model import get_hybrid_model

model = get_hybrid_model("small", input_size=38)
```

---

## 9. Entrenamiento Walk-Forward

### ¿Por Qué Walk-Forward?

El problema del training/validation tradicional en trading:

```
❌ Random Split (MALO)
   Training: [Jan, Mar, Abr, Jun, Sep, Nov]
   Validation: [Feb, May, Jul, Aug, Oct, Dec]
   
   Problema: El modelo "ve el futuro" durante training
```

Walk-forward simula trading real:

```
✅ Walk-Forward (BUENO)
   Window 1: Train [Jan-Mar] → Test [Apr]
   Window 2: Train [Feb-Apr] → Test [May]
   Window 3: Train [Mar-May] → Test [Jun]
   ...
   
   El modelo NUNCA ve datos futuros durante training
```

### Implementación

```bash
python bots/train_walkforward.py \
  --data training_data/training_data.csv \
  --train-months 3 \
  --test-months 1 \
  --step-months 1
```

### Output

```
Window 1/8: Train 2025-10 to 2025-12, Test 2026-01
  Accuracy: 58.2%, Win Rate: 54.3%, Profit Factor: 1.18

Window 2/8: Train 2025-11 to 2026-01, Test 2026-02
  Accuracy: 56.8%, Win Rate: 52.1%, Profit Factor: 1.05

...

AGGREGATE RESULTS:
  Mean Win Rate: 53.2%
  Mean Profit Factor: 1.12
  Sharpe Ratio: 0.85
```

---

## 10. Métricas de Evaluación

### Métricas de Clasificación

| Métrica | Descripción | Objetivo |
|---------|-------------|----------|
| **Accuracy** | Predicciones correctas / total | > 50% |
| **Precision (LONG)** | TP / (TP + FP) para LONG | > 52% |
| **Precision (SHORT)** | TP / (TP + FP) para SHORT | > 52% |

### Métricas de Trading (Más Importantes)

| Métrica | Descripción | Objetivo |
|---------|-------------|----------|
| **Win Rate** | Trades ganadores / total trades | > 52% |
| **Profit Factor** | Ganancias / Pérdidas | > 1.0 |
| **Sharpe Ratio** | Retorno adj. por riesgo | > 0.5 |
| **Max Drawdown** | Pérdida máxima desde pico | < 10% |

### Benchmark

Un modelo aleatorio tendría:
- Accuracy: 33% (3 clases)
- Win Rate: 50%
- Profit Factor: 1.0

**Si tu modelo tiene Win Rate > 52% y PF > 1.0, tiene edge real.**

---

## Resumen

El Hybrid Attention-MLP es un modelo diseñado específicamente para trading con datasets pequeños:

1. **Feature Attention** → Aprende qué features importan
2. **MLP Regularizado** → Predicción robusta sin overfitting
3. **Walk-Forward** → Evaluación sin lookahead bias
4. **Interpretabilidad** → Sabemos POR QUÉ predice

```
Datos de Greeks + IB + IV
         │
    Feature Attention (¿Qué importa?)
         │
    MLP Classifier (Predicción)
         │
    Output: LONG/HOLD/SHORT + Confianza + Explicación
```

---

## Referencias

- **Attention Is All You Need** (Vaswani et al., 2017) - Base teórica de attention
- **Batch Normalization** (Ioffe & Szegedy, 2015) - Normalización entre capas
- **Walk-Forward Analysis** (Pardo, 2008) - Metodología de validación para trading
- **Greek Exposures** (Sinclair, 2010) - Fundamentos de market making con opciones
