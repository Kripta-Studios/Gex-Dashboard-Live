# Trading Bot con PyTorch - Guía Completa

Bot de day trading basado en redes neuronales con **PyTorch**. Utiliza exposiciones de griegas (Gamma, Vanna, Charm, DGEX, Zomma) y niveles de Initial Balance (IB) para generar señales de trading precisas.

> **Nota**: Este proyecto migró de TinyGrad a PyTorch por mejor compatibilidad con CUDA 12.x en Windows.

---

## Instalación Rápida

```powershell
# PyTorch con CUDA (RTX 5070 Ti / RTX 40xx / RTX 30xx)
pip3 install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu128

# Verificar GPU
python -c "import torch; print('CUDA:', torch.cuda.is_available(), '|', torch.cuda.get_device_name(0))"
```

---

## Flujo de Trabajo

```
1. Recolectar datos    →    2. Entrenar modelo    →    3. Ejecutar bot
   collect_training_data.py     train_pytorch.py         tradingbot_pytorch.py
```

### 1. Recolectar Datos de Entrenamiento

```powershell
cd bots
python collect_training_data.py --days 5 --tickers SPX SPY QQQ NVDA
```

Genera: `training_data/training_data.csv`

### 2. Entrenar el Modelo (GPU)

```powershell
# Modelo XL recomendado para RTX 5070 Ti (~602K params)
python train_pytorch.py --model-size xl --epochs 300 --batch-size 256 --lr 0.0005

# Modelo Large para GPUs más pequeñas (~155K params)
python train_pytorch.py --model-size large --epochs 200 --batch-size 128

# Modelo Small para testing rápido (~5K params)
python train_pytorch.py --model-size small --epochs 50 --batch-size 64
```

Genera: `models/trading_model.pt` y `models/normalizer.npz`

### 3. Ejecutar el Bot

```powershell
python tradingbot_pytorch.py
```

---

## Arquitectura del Modelo XL

```
Input (32 features)
        ↓
Linear(512) + BatchNorm + ReLU + Dropout(0.3)
        ↓
Linear(512) + ReLU + Dropout(0.3)
        ↓                              ← Skip connection
Linear(256) + BatchNorm + ReLU + Dropout(0.3)
        ↓
Linear(128) + ReLU + Dropout(0.3)
        ↓
Linear(64) + BatchNorm + ReLU + Dropout(0.3)
        ↓
Linear(32) + ReLU + Dropout(0.3)
        ↓
Linear(3) + Softmax
        ↓
Output: [P(SHORT), P(HOLD), P(LONG)]
```

**Parámetros por modelo:**

| Modelo | Parámetros | GPU recomendada |
|--------|------------|-----------------|
| small | ~5,000 | CPU / cualquier GPU |
| large | ~155,000 | RTX 3060+ |
| **xl** | **~602,000** | **RTX 5070 Ti, 4080+** |

---

## Features Utilizados (32 total)

| Categoría | Features |
|-----------|----------|
| **Griegas netas** | net_gamma, net_vanna, net_charm, net_dgex, net_zomma |
| **Señales binarias** | gamma_regime, vanna_bullish, charm_bullish, dgex_sticky, zomma_stabilizing |
| **Distancias a niveles** | dist_to_max_gamma, dist_to_min_gamma, dist_to_min_vanna, dist_to_zero_gamma |
| **Proximidad (±0.04%)** | near_max_gamma, near_min_gamma, near_min_vanna, near_zero_gamma |
| **Contexto IB** | price_vs_ib_high, price_vs_ib_low, ib_range_pct, near_ib_high, near_ib_low, above_ib, below_ib, in_ib_range |
| **Fibonacci** | dist_fib_127_up, dist_fib_161_up |
| **Mercado** | hour, minute, rsi, vol_relative |

---

## Lógica de Señales de Griegas

| Griega | Señal | Efecto en Mercado |
|--------|-------|-------------------|
| **Gamma+** | Exposición neta positiva | Mean-reversion: dealers compran caídas |
| **Gamma-** | Exposición neta negativa | Momentum: dealers siguen la tendencia |
| **Vanna+** con IV↓ | IV bajando | Presión compradora |
| **Min Vanna** | Cerca de OPEX | Actúa como imán de precio |
| **DGEX alto** | Mercado pegajoso | Precios gravitan al nivel |
| **Zomma+** con IV↑ | Volatilidad subiendo | Estabiliza movimientos |

---

## Tickers Soportados

**Índices/ETFs:** SPX, SPY, QQQ, IWM, VIX

**Acciones:** AAPL, NVDA, TSLA, AMD, MSFT, AMZN, META, GOOGL

**Futuros:**
- `/ES` → Usa griegas de SPX directamente
- `/NQ` → Usa griegas de QQQ convertidas a NDX

---

## Estructura de Archivos

```
bots/
├── pytorch_model.py        # Definición de modelos PyTorch
├── train_pytorch.py        # Script de entrenamiento GPU
├── tradingbot_pytorch.py   # Bot de trading en tiempo real
└── collect_training_data.py # Recolección de datos

models/
├── trading_model.pt        # Modelo entrenado
└── normalizer.npz          # Parámetros de normalización

training_data/
└── training_data.csv       # Dataset de entrenamiento

trades_pytorch/             # Historial de trades
logs/                       # Logs del bot
```

---

## Parámetros de Trading

| Parámetro | Valor | Descripción |
|-----------|-------|-------------|
| Confianza mínima | 65% | Umbral para abrir trade |
| Tolerancia precio | ±0.04% | Proximidad a nivel clave |
| Stop Loss | -0.3% | Cierre por pérdida |
| Take Profit | +0.5% | Cierre por ganancia |
| Loop interval | 30s | Frecuencia de análisis |

---

## Troubleshooting

| Error | Solución |
|-------|----------|
| "Model not found" | Ejecuta `train_pytorch.py` primero |
| "CUDA not available" | Reinstala PyTorch con CUDA: `pip3 install torch --index-url https://download.pytorch.org/whl/cu128` |
| "No Greek data" | Verifica que `gex_daemon.py` está generando JSONs |
| Out of memory | Reduce `--batch-size` o usa modelo `large` en vez de `xl` |
