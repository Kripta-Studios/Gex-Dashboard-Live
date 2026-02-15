# TinyGrad Trading Bot - Guía Completa

Bot de day trading basado en redes neuronales con TinyGrad. Utiliza exposiciones de griegas (Gamma, Vanna, Charm, DGEX, Zomma) y niveles de Initial Balance (IB) para generar señales de trading precisas.

---

## Cómo Funciona el Bot

### Visión General

```
┌─────────────────────┐    ┌─────────────────────┐    ┌─────────────────────┐
│   GEX Daemon        │    │   IB Service        │    │   TinyGrad Bot      │
│   (gex_daemon.py)   │───▶│   (ib_service.py)   │───▶│                     │
│                     │    │                     │    │  1. Lee JSONs       │
│  Genera griegas     │    │  Genera IB levels   │    │  2. Extrae features │
│  cada minuto        │    │  y candlesticks     │    │  3. Inferencia NN   │
│                     │    │                     │    │  4. Señal trading   │
└─────────────────────┘    └─────────────────────┘    └─────────────────────┘
```

### Flujo de Datos

1. **GEX Daemon** (`gex_daemon.py`) genera cada minuto:
   - Exposiciones de griegas: Gamma, Vanna, Charm, Delta, DGEX, Zomma
   - Niveles clave: Zero Gamma, Max/Min de cada griega
   - Guarda en: `/home/.../json_data/{ticker}_0dte_ExposureData_{fecha}_{hora}.json`

2. **IB Service** (`ib_service.py`) genera cada día:
   - Initial Balance (High/Low de primera hora RTH 9:30-10:30)
   - Volume Profile (VPOC, VAH, VAL)
   - Candlesticks minuto a minuto
   - Guarda en: `/home/.../ib_charts/ib_data_{ticker}_{fecha}.json`

3. **TinyGrad Bot** (`tradingbot_tinygrad.py`):
   - Lee los JSONs más recientes cada 30 segundos
   - Extrae ~30 features de cada archivo
   - Pasa los features por la red neuronal
   - Si confianza > 65% Y precio cerca de nivel clave (±0.04%) → Señal

---

## Fase de Entrenamiento

### 1. Recolección de Datos (`collect_training_data.py`)

**Qué datos recoge:**

| Fuente | Datos | Cómo los obtiene |
|--------|-------|------------------|
| Greek JSONs | Exposiciones netas (gamma, vanna, charm, dgex, zomma) | Suma todos los valores del array `totalgamma['all']` etc. |
| Greek JSONs | Niveles clave (max/min gamma, min vanna, zero gamma) | Busca máximo/mínimo en arrays y sus strikes correspondientes |
| IB JSONs | IB High/Low, Volume Profile | Lee `analysis.ib_high`, `analysis.ib_low` |
| IB JSONs | Serie de precios | Lee array `series` con OHLCV por minuto |
| Calculado | Fibonacci extensions | 1.272, 1.618, 2.0 del rango IB |
| Calculado | RSI, hora del día | Calculado de la serie de precios |

**Features extraídos (inputs del modelo):**

```python
FEATURES = [
    # Exposiciones netas de griegas (5)
    "net_gamma", "net_vanna", "net_charm", "net_dgex", "net_zomma",
    
    # Régimen y señales binarias (5)
    "gamma_regime",       # 0=short, 1=neutral, 2=long
    "vanna_bullish",      # 1 si vanna neto > 0
    "charm_bullish",      # 1 si charm neto > 0
    "dgex_sticky",        # 1 si DGEX alto (mercado pegajoso)
    "zomma_stabilizing",  # 1 si zomma estabiliza
    
    # Distancias a niveles (% del precio) (4)
    "dist_to_max_gamma", "dist_to_min_gamma", 
    "dist_to_min_vanna", "dist_to_zero_gamma",
    
    # Flags de proximidad ±0.04% (4)
    "near_max_gamma", "near_min_gamma", 
    "near_min_vanna", "near_zero_gamma",
    
    # Contexto IB (8)
    "price_vs_ib_high", "price_vs_ib_low", "ib_range_pct",
    "near_ib_high", "near_ib_low", 
    "above_ib", "below_ib", "in_ib_range",
    
    # Fibonacci (2)
    "dist_fib_127_up", "dist_fib_161_up",
    
    # Contexto mercado (4)
    "hour", "minute", "rsi", "vol_relative",
]
```

**Label (output objetivo):**

```python
# Para cada minuto, miramos 30 minutos hacia adelante:
# Si el precio subió ≥0.3% → LONG  (label = 1)
# Si el precio bajó ≥0.3% → SHORT (label = -1)
# Si no hubo movimiento significativo → HOLD (label = 0)
```

**Comando:**
```bash
python collect_training_data.py --days 10 --tickers SPX SPY QQQ NVDA
```

**Output:** `training_data/training_data.csv` con ~2000 muestras por día por ticker

---

### 2. Entrenamiento del Modelo (`train_model.py`)

**Tres tamaños de modelo disponibles:**

| Tamaño | Parámetros | GPU recomendada | Uso |
|--------|------------|-----------------|-----|
| `small` | ~5,000 | CPU / cualquier GPU | Testing rápido |
| `large` | ~155,000 | RTX 3060+ | Producción estándar |
| `xl` | ~602,000 | RTX 5070 Ti, 4080+ | Máxima precisión |

**Arquitectura XL (recomendada para RTX 5070 Ti):**

```
Input Layer (32 features)
        ↓
Dense(512) + ReLU + Dropout(0.3)
        ↓
Dense(512) + ReLU + Dropout(0.3)
        ↓                          ← Skip connection
Dense(256) + ReLU + Dropout(0.3) ──┘
        ↓
Dense(128) + ReLU + Dropout(0.3)
        ↓                          ← Skip connection
Dense(64) + ReLU + Dropout(0.3) ───┘
        ↓
Dense(32) + ReLU + Dropout(0.3)
        ↓
Dense(3) + Softmax
        ↓
Output: [P(SHORT), P(HOLD), P(LONG)]
```

**Entrenamiento en GPU (RTX 5070 Ti / Ryzen 9):**

```bash
# Activar CUDA para TinyGrad
set CUDA=1

# Entrenar modelo XL con batch grande (aprovecha la VRAM)
python train_model.py --model-size xl --epochs 300 --batch-size 256 --lr 0.0005

# O modelo Large si quieres más rápido
python train_model.py --model-size large --epochs 200 --batch-size 128
```

**Parámetros recomendados para RTX 5070 Ti:**

| Parámetro | Valor | Por qué |
|-----------|-------|---------|
| `--model-size` | `xl` | Máxima capacidad para tu GPU |
| `--batch-size` | 256 | Aprovecha la VRAM (~8-12GB) |
| `--epochs` | 300 | Más tiempo para converger |
| `--lr` | 0.0005 | Más bajo para modelos grandes |
| `--weight-decay` | 0.01 | Regularización L2 |
| `--patience` | 30 | Más paciencia para early stopping |

**Verificar que usa GPU:**
```bash
# Debe mostrar "[GPU] Using CUDA (NVIDIA GPU)"
set CUDA=1 && python -c "from tinygrad_model import setup_gpu; setup_gpu()"
```

**Proceso de entrenamiento:**

1. **Carga datos** desde CSV
2. **Normalización Z-score**: `(x - mean) / std` para cada feature
3. **Split** 80% train, 20% validation
4. **Training loop**:
   - Batch size: 32 muestras
   - Optimizer: AdamW (lr=0.001)
   - Loss: Cross-entropy
   - Early stopping: para si val_loss no mejora en 10 epochs

**Comando:**
```bash
python train_model.py --epochs 100 --batch-size 32 --lr 0.001
```

**Output:**
- `models/trading_model.safetensors` → Pesos de la red
- `models/normalizer.npz` → Medias y desviaciones para normalizar

---

### 3. Ejecución en Tiempo Real (`tradingbot_tinygrad.py`)

**Loop principal (cada 30 segundos):**

```python
while True:
    for ticker in TICKERS:
        # 1. Cargar datos frescos
        greek_data = load_latest_greek_json(ticker)
        ib_data = load_ib_json(ticker)
        
        # 2. Extraer features (mismo proceso que entrenamiento)
        features = extract_features(greek_data, ib_data)
        
        # 3. Normalizar features
        features_norm = (features - saved_means) / saved_stds
        
        # 4. Inferencia
        probs = model.forward(features_norm)  # [P_short, P_hold, P_long]
        prediction = argmax(probs)
        confidence = probs[prediction]
        
        # 5. Decisión de trading
        if confidence >= 0.65 and is_near_key_level(price):
            if prediction == LONG:
                open_long_trade()
            elif prediction == SHORT:
                open_short_trade()
```

**Lógica de señales de griegas:**

| Griega | Condición | Efecto en Mercado |
|--------|-----------|-------------------|
| **Gamma+** | Exposición neta positiva | Mean-reversion: dealers compran caídas, venden subidas |
| **Gamma-** | Exposición neta negativa | Momentum: dealers siguen la tendencia |
| **Vanna+** con IV↓ | IV bajando con vanna positivo | Presión compradora |
| **Vanna-** cerca expiración | Cerca de OPEX | Min Vanna actúa como imán |
| **DGEX+** alto | DGEX muy positivo | Mercado "pegajoso", precios gravitan a nivel |
| **DGEX-** alto | DGEX muy negativo | Volatilidad, movimientos acelerados |
| **Zomma+** con IV↑ | Volatilidad subiendo | Estabiliza movimientos |
| **Zomma-** con IV↑ | Volatilidad subiendo | Amplifica movimientos |

**Gestión de riesgo:**
- Stop Loss: -0.3%
- Emergency Stop: -0.5%
- Take Profit: +0.5%
- Tiempo mínimo: 5 minutos

---

## Instalación

```bash
# Instalar TinyGrad
pip install tinygrad numpy pandas python-dotenv

# Verificar instalación
python -c "from tinygrad import Tensor; print('TinyGrad OK')"
```

---

## Tickers Soportados

**Índices y ETFs:**
- SPX, SPY, QQQ, IWM, VIX

**Acciones individuales:**
- AAPL, NVDA, TSLA, AMD, MSFT, AMZN, META, GOOGL

**Futuros:**
- `/ES` → Usa griegas de SPX directamente
- `/NQ` → Usa griegas de QQQ convertidas a escala NDX

---

## Estructura de Archivos

```
Gex-Dashboard-Live/
├── bots/
│   ├── collect_training_data.py  # Recolección de datos
│   ├── tinygrad_model.py         # Definición de la red
│   ├── train_model.py            # Script de entrenamiento
│   └── tradingbot_tinygrad.py    # Bot de trading en vivo
├── models/
│   ├── trading_model.safetensors # Pesos entrenados
│   └── normalizer.npz            # Parámetros de normalización
├── training_data/
│   └── training_data.csv         # Dataset de entrenamiento
├── trades_tinygrad/              # Historial de trades
└── logs/
    └── tradingbot_tinygrad.log   # Logs del bot
```

---

## Troubleshooting

| Error | Causa | Solución |
|-------|-------|----------|
| "Model not found" | No has entrenado | Ejecuta `train_model.py` |
| "No Greek data" | gex_daemon no está corriendo | Inicia `gex_daemon.py` |
| "Greek data too old" | Datos tienen >2 min de antigüedad | Verifica que gex_daemon genera JSONs |
| "Not near key level" | Precio no está ±0.04% de nivel | Normal, el bot espera mejor entrada |
