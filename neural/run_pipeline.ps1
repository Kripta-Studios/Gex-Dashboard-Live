# run_pipeline.ps1
# Pipeline completo: recolección SPX+QQQ → GBT → RL → Backtest → Visualización
$ErrorActionPreference = "Continue"

# ─────────────────────────────────────────────────────────────────────────────
# PASO 0 — RECOLECCIÓN DE DATOS (SPX base + QQQ como contexto)
# El script descarta automáticamente días donde falte SPX o QQQ.
# ─────────────────────────────────────────────────────────────────────────────
Write-Host "`n=== RECOLECTANDO DATOS SPX+QQQ ===" -ForegroundColor Cyan
python collect_training_data_spx_qqq.py `
  --start 20220801 --end 20260328 `
  --workers 28 --tickers SPX QQQ `
  --output training_data_spx_qqq.parquet

if ($LASTEXITCODE -ne 0) {
  Write-Host "ERROR en la recoleccion de datos SPX+QQQ." -ForegroundColor Red
  exit 1
}

# ─────────────────────────────────────────────────────────────────────────────
# PASO 1 — ENTRENAMIENTO GBT (Walk-Forward LightGBM)
# ─────────────────────────────────────────────────────────────────────────────
Write-Host "`n=== ENTRENAMIENTO GBT Walk-Forward (LightGBM Ensemble) ===" -ForegroundColor Cyan
python train_walkforward.py `
  --data ..\training_data\training_data_spx_qqq.parquet `
  --model-size small `
  --train-months 3 `
  --test-months 1 `
  --ensemble 5 `
  --top-n-windows 10 `
  --min-window 20 `
  --model_path models\trading_hybrid_wf.joblib `
  --norm_path models\hybrid_normalizer_wf.npz

if ($LASTEXITCODE -ne 0) {
  Write-Host "ERROR: El entrenamiento del GBT fallo. Revisa los candados matematicos o el LR." -ForegroundColor Red
  exit 1
}

# ─────────────────────────────────────────────────────────────────────────────
# PASO 5 — DIAGNÓSTICO POST-ENTRENAMIENTO
# ─────────────────────────────────────────────────────────────────────────────
Write-Host "`n=== DIAGNOSTICO POST-ENTRENAMIENTO ===" -ForegroundColor Magenta
python diagnose_pipeline.py `
  --train-months 3 `
  --test-months 1 `
  --data ..\training_data\training_data_spx_qqq.parquet `
  --model models\trading_hybrid_wf.joblib `
  --normalizer models\hybrid_normalizer_wf.npz `
  --options-cache ..\rl_data\rl_options_cache_chunks

if ($LASTEXITCODE -ne 0) {
  Write-Host "ADVERTENCIA: Diagnostico fallo o encontro problemas." -ForegroundColor Yellow
}

# ─────────────────────────────────────────────────────────────────────────────
# PASO 2 — GENERACIÓN DE ÍNDICE DE EPISODIOS (para RL)
# ─────────────────────────────────────────────────────────────────────────────
Write-Host "`n=== Generando Indice de Episodios ===" -ForegroundColor Cyan
python .\generate_episode_index.py

if ($LASTEXITCODE -ne 0) {
  Write-Host "ERROR: generate_episode_index.py fallo." -ForegroundColor Red
  exit 1
}

# ─────────────────────────────────────────────────────────────────────────────
# PASO 3 — PREPROCESSING (inferencia GBT → cache RL)
# ─────────────────────────────────────────────────────────────────────────────
Write-Host "`n=== Preprocessing con GBT SPX+QQQ (Inferencia de Senales) ===" -ForegroundColor Cyan
python run_preprocess.py `
  --training-data ..\training_data\training_data_spx_qqq.parquet `
  --options-dir D:\ThetaData\data_options `
  --output ..\rl_data\rl_options_cache_chunks `
  --mlp-model models\trading_hybrid_wf.joblib `
  --mlp-normalizer models\hybrid_normalizer_wf.npz `
  --num-workers 28

if ($LASTEXITCODE -ne 0) {
  Write-Host "ERROR: Preprocessing fallo. Posible error de OOM o lectura de ThetaData." -ForegroundColor Red
  exit 1
}

# ─────────────────────────────────────────────────────────────────────────────
# PASO 4 — RL TRAINING (Policy Optimization sobre señales GBT)
# ─────────────────────────────────────────────────────────────────────────────
Write-Host "`n=== RL Training (Policy Optimization sobre senales GBT) ===" -ForegroundColor Cyan
python -m rl.training `
  --episode-index ..\rl_data\episode_index.parquet `
  --options-cache ..\rl_data\rl_options_cache_chunks `
  --save-dir ..\rl_models `
  --total-updates 400 `
  --workers 28

if ($LASTEXITCODE -ne 0) {
  Write-Host "ERROR: RL Training fallo." -ForegroundColor Red
  exit 1
}

Write-Host "`n=== PIPELINE PRINCIPAL COMPLETO CON EXITO ===" -ForegroundColor Green
Write-Host "Modelo GBT Hibrido y Agente RL listos para Gex-Dashboard-Live." -ForegroundColor Green



# ─────────────────────────────────────────────────────────────────────────────
# PASO 6 — BACKTESTING GBT solo
# ─────────────────────────────────────────────────────────────────────────────
Write-Host "`n=== BACKTESTING GBT only ===" -ForegroundColor Yellow
python ..\backtest\backtest_hybrid_parquet.py `
  --data ..\training_data\training_data_spx_qqq.parquet `
  --model models\trading_hybrid_wf.joblib `
  --normalizer models\hybrid_normalizer_wf.npz `
  --model-size small --ensemble `
  --threshold 0.50 --cooldown 10 `
  --target_long 0.010 --target_short 0.010 --stop 0.003 `
  --uncertainty 150
  
if ($LASTEXITCODE -ne 0) {
  Write-Host "ERROR: Backtest GBT fallo." -ForegroundColor Red
  exit 1
}

# ─────────────────────────────────────────────────────────────────────────────
# PASO 7 — BACKTESTING GBT + RL
# ─────────────────────────────────────────────────────────────────────────────
Write-Host "`n=== BACKTESTING GBT+RL ===" -ForegroundColor DarkGreen
python ..\backtest\backtest_rl.py `
  --data ..\training_data\training_data_spx_qqq.parquet `
  --model models\trading_hybrid_wf.joblib `
  --normalizer models\hybrid_normalizer_wf.npz `
  --rl-model ..\rl_models\best_rl_agent.pt `
  --model-size small --ensemble `
  --threshold 0.50 --cooldown 10 `
  --target-long 0.010 --target-short 0.010 --stop 0.003 `
  --risk-capital 500.0

if ($LASTEXITCODE -ne 0) {
  Write-Host "ERROR: Backtest GBT+RL fallo." -ForegroundColor Red
  exit 1
}

python ..\backtest\analyze_trade_gaps.py

# ─────────────────────────────────────────────────────────────────────────────
# PASO 8 — VISUALIZACIÓN
# NOTA: Si plt.show() está activo, cada ventana bloqueará el script hasta cerrarla.
# ─────────────────────────────────────────────────────────────────────────────
Write-Host "`n=== VISUALIZACION ===" -ForegroundColor Cyan
python ..\visualizer\analyze_backtests.py
python ..\visualizer\analyze_backtests.py --month 202601
python ..\visualizer\analyze_backtests.py --month 202602
python ..\visualizer\analyze_backtests.py --month 202603
python ..\visualizer\analyze_backtests.py --month 202503
python ..\visualizer\analyze_backtests.py --month 202504

Write-Host "`n=== PIPELINE COMPLETO CON EXITO ===" -ForegroundColor Green