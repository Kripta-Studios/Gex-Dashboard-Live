# run_pipeline.ps1
# Pipeline completo: recolección SPX+QQQ → GBT → RL → Backtest → Visualización
Param(
  [switch]$gbt, # Paso 1 en adelante (GBT Training + Episode Index + Preprocess + RL)
  [switch]$rl,  # Paso 2 en adelante (Episode Index + Preprocess + RL)
  [switch]$a,   # Paso 4.5 en adelante (Diagnosis)
  [switch]$bt,  # Paso 7 en adelante (Backtest GBT+RL)
  [switch]$v,   # Paso 8 en adelante (Visualización)
  [switch]$u    # Modo Update: espera a las 22:05h, actualiza ThetaData y empieza en Paso 0
)

$ErrorActionPreference = "Continue"

function Get-RLBaseConfidence {
  Push-Location $PSScriptRoot
  try {
    $confidenceRaw = & python -c "from rl.config import RL_CONFIG; print(RL_CONFIG['min_confidence'])"
    if ($LASTEXITCODE -ne 0 -or [string]::IsNullOrWhiteSpace($confidenceRaw)) {
      throw "No se pudo leer RL_CONFIG['min_confidence']"
    }

    $confidenceText = ($confidenceRaw | Select-Object -Last 1).Trim()
    return [double]::Parse($confidenceText, [System.Globalization.CultureInfo]::InvariantCulture)
  }
  finally {
    Pop-Location
  }
}

$BaseConfidence = Get-RLBaseConfidence
$BaseConfidenceArg = [string]::Format(
  [System.Globalization.CultureInfo]::InvariantCulture,
  "{0:0.00}",
  $BaseConfidence
)
Write-Host "[CONFIG] Base confidence cargada desde RL_CONFIG: $BaseConfidenceArg" -ForegroundColor DarkCyan

# Determine starting stage
$skip_to_step = 0
if ($gbt) { $skip_to_step = 1 }
if ($rl) { $skip_to_step = 2 }
if ($a) { $skip_to_step = 4.5 }
if ($bt) { $skip_to_step = 7 }
if ($v) { $skip_to_step = 8 }

# ─────────────────────────────────────────────────────────────────────────────
# MODO UPDATE (-u): Espera a las 22:05h y descarga históricos en ThetaData
# ─────────────────────────────────────────────────────────────────────────────
if ($u) {
  $targetTime = (Get-Date).Date.AddHours(22).AddMinutes(5)
  if ((Get-Date) -gt $targetTime) {
    Write-Host "`n[UPDATE MODE] Ya son pasadas las 22:05h. Ejecutando scripts inmediatamente." -ForegroundColor Cyan
  }
  else {
    Write-Host "`n[UPDATE MODE] Esperando hasta las 22:05h para actualizar ThetaData..." -ForegroundColor Cyan
    while ((Get-Date) -lt $targetTime) {
      $timeToWait = $targetTime - (Get-Date)
      Write-Host -NoNewline "`rFaltan $($timeToWait.Hours)h $($timeToWait.Minutes)m $($timeToWait.Seconds)s...  "
      Start-Sleep -Seconds 10
    }
    Write-Host "`n¡Hora alcanzada! (22:05h) Empezando descarga...`n" -ForegroundColor Green
  }

  Write-Host "Ejecutando D:\ThetaData\options_bulk.py..." -ForegroundColor Yellow
  python D:\ThetaData\options_bulk.py
  if ($LASTEXITCODE -ne 0) { Write-Host "ERROR: options_bulk.py fallo." -ForegroundColor Red; exit 1 }

  Write-Host "Ejecutando D:\ThetaData\script4_underlying_from_options.py..." -ForegroundColor Yellow
  python D:\ThetaData\script4_underlying_from_options.py
  if ($LASTEXITCODE -ne 0) { Write-Host "ERROR: script4_underlying_from_options.py fallo." -ForegroundColor Red; exit 1 }
  
  $skip_to_step = 0
}

# ─────────────────────────────────────────────────────────────────────────────
# PASO 0 — RECOLECCIÓN DE DATOS (SPX base + QQQ como contexto)
# ─────────────────────────────────────────────────────────────────────────────
if ($skip_to_step -le 0) {
  Write-Host "`n=== RECOLECTANDO DATOS SPX+QQQ+SPY ===" -ForegroundColor Cyan
  python collect_training_data_spx_qqq.py `
    --start 20220801 --end 20261230 `
    --workers 20 --tickers SPX QQQ SPY `
    --output training_data_spx_qqq_spy.parquet

  if ($LASTEXITCODE -ne 0) {
    Write-Host "ERROR en la recoleccion de datos SPX+QQQ+SPY." -ForegroundColor Red
    exit 1
  }
}

# ─────────────────────────────────────────────────────────────────────────────
# PASO 1 — ENTRENAMIENTO GBT (Walk-Forward LightGBM)
# ─────────────────────────────────────────────────────────────────────────────
if ($skip_to_step -le 1) {
  Write-Host "`n=== ENTRENAMIENTO GBT Walk-Forward (LightGBM Ensemble) ===" -ForegroundColor Cyan
  python train_walkforward.py `
    --data ..\training_data\training_data_spx_qqq_spy.parquet `
    --model-size small `
    --train-months 9 `
    --test-months 1 `
    --ensemble 5 `
    --top-n-windows 15 `
    --hold-ratio 1.2 `
    --min-window 20 `
    --model_path models\trading_hybrid_wf.joblib `
    --norm_path models\hybrid_normalizer_wf.npz

  if ($LASTEXITCODE -ne 0) {
    Write-Host "ERROR: El entrenamiento del GBT fallo. Revisa los candados matematicos o el LR." -ForegroundColor Red
    exit 1
  }
}

# ─────────────────────────────────────────────────────────────────────────────
# PASO 2 — GENERACIÓN DE ÍNDICE DE EPISODIOS (para RL)
# ─────────────────────────────────────────────────────────────────────────────
if ($skip_to_step -le 2) {
  Write-Host "`n=== Generando Indice de Episodios ===" -ForegroundColor Cyan
  python .\generate_episode_index.py --data ..\training_data\training_data_spx_qqq_spy.parquet --strict-wf

  if ($LASTEXITCODE -ne 0) {
    Write-Host "ERROR: generate_episode_index.py fallo." -ForegroundColor Red
    exit 1
  }

  # ─────────────────────────────────────────────────────────────────────────────
  # PASO 3 — PREPROCESSING (inferencia GBT → cache RL)
  # ─────────────────────────────────────────────────────────────────────────────
  Write-Host "`n=== Preprocessing con GBT SPX+QQQ (Inferencia de Senales) ===" -ForegroundColor Cyan
  
  # Limpiar la cache corrupta por precaucion tras el crash OOM original
  If (Test-Path "..\rl_data\rl_options_cache_chunks") {
    Remove-Item "..\rl_data\rl_options_cache_chunks\*" -Recurse -Force -ErrorAction SilentlyContinue
  }

  python run_preprocess.py `
    --training-data ..\training_data\training_data_spx_qqq_spy.parquet `
    --options-dir D:\ThetaData\data_options `
    --output ..\rl_data\rl_options_cache_chunks `
    --mlp-model models\trading_hybrid_wf.joblib `
    --mlp-normalizer models\hybrid_normalizer_wf.npz `
    --num-workers 22 `
    --strict-wf

  if ($LASTEXITCODE -ne 0) {
    Write-Host "ERROR: run_preprocess.py fallo. No se continuara con artefactos viejos." -ForegroundColor Red
    exit 1
  }

  python rl/compute_recovery_stats.py

  if ($LASTEXITCODE -ne 0) {
    Write-Host "ERROR: compute_recovery_stats.py fallo tras el preprocess." -ForegroundColor Red
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
    --total-updates 500 `
    --workers 32

  if ($LASTEXITCODE -ne 0) {
    Write-Host "ERROR: RL Training fallo." -ForegroundColor Red
    exit 1
  }
}

# ─────────────────────────────────────────────────────────────────────────────
# PASO 4.5 — PIPELINE DIAGNOSIS (Check Health & Overfitting)
# ─────────────────────────────────────────────────────────────────────────────
if ($skip_to_step -le 4.5) {
  Write-Host "`n=== Pipeline Diagnosis (Health & Performance Check) ===" -ForegroundColor Cyan
  python diagnose_pipeline.py `
    --train-months 9 `
    --test-months 1 `
    --data ..\training_data\training_data_spx_qqq_spy.parquet `
    --model models\trading_hybrid_wf.joblib `
    --normalizer models\hybrid_normalizer_wf.npz `
    --options-cache ..\rl_data\rl_options_cache_chunks

  if ($LASTEXITCODE -ne 0) {
    Write-Host "WARNING: Diagnosis detecto problemas potenciales, pero continuamos..." -ForegroundColor Yellow
  }

  Write-Host "`n=== PIPELINE PRINCIPAL COMPLETO CON EXITO ===" -ForegroundColor Green
  Write-Host "Modelo GBT Hibrido y Agente RL listos para Gex-Dashboard-Live." -ForegroundColor Green
}

# ─────────────────────────────────────────────────────────────────────────────
# PASO 6 — BACKTESTING GBT solo
# ─────────────────────────────────────────────────────────────────────────────
if ($skip_to_step -le 6) {
  Write-Host "`n=== BACKTESTING GBT only ===" -ForegroundColor Yellow
  python ..\backtest\backtest_gbt_parquet.py `
    --data ..\training_data\training_data_spx_qqq_spy.parquet `
    --model models\trading_hybrid_wf.joblib `
    --normalizer models\hybrid_normalizer_wf.npz `
    --model-size small --ensemble `
    --threshold $BaseConfidenceArg --cooldown 15 `
    --target_long 0.010 --target_short 0.010 --stop 0.003 `
    --strict-wf
        
  if ($LASTEXITCODE -ne 0) {
    Write-Host "ERROR: Backtest GBT fallo." -ForegroundColor Red
    exit 1
  }
}

# ─────────────────────────────────────────────────────────────────────────────
# PASO 7 — BACKTESTING GBT + RL
# ─────────────────────────────────────────────────────────────────────────────
if ($skip_to_step -le 7) {
  Write-Host "`n=== BACKTESTING GBT+RL ===" -ForegroundColor DarkGreen
  python ..\backtest\backtest_rl.py `
    --data ..\training_data\training_data_spx_qqq_spy.parquet `
    --model models\trading_hybrid_wf.joblib `
    --normalizer models\hybrid_normalizer_wf.npz `
    --rl-model ..\rl_models\best_rl_agent.pt `
    --model-size small --ensemble `
    --threshold $BaseConfidenceArg --cooldown 15 `
    --target-long 0.010 --target-short 0.010 --stop 0.003 `
    --risk-capital 1000.0 `
    --filter-by-greeks `
    --single-step-eval `
    --strict-wf `
    --tickers SPX QQQ SPY

  if ($LASTEXITCODE -ne 0) {
    Write-Host "ERROR: Backtest GBT+RL fallo." -ForegroundColor Red
    exit 1
  }

  python ..\backtest\analyze_trade_gaps.py
}

# ─────────────────────────────────────────────────────────────────────────────
# PASO 8 — VISUALIZACIÓN
# ─────────────────────────────────────────────────────────────────────────────
if ($skip_to_step -le 8) {
  Write-Host "`n=== VISUALIZACION ===" -ForegroundColor Cyan
  python ..\visualizer\analyze_backtests.py
  python ..\visualizer\analyze_backtests.py --month 202601
  python ..\visualizer\analyze_backtests.py --month 202602
  python ..\visualizer\analyze_backtests.py --month 202603
  python ..\visualizer\analyze_backtests.py --month 202604
  python ..\visualizer\analyze_backtests.py --month 202503
  python ..\visualizer\analyze_backtests.py --month 202504

  python ..\visualizer\visualize_features.py --mode all --save

  Write-Host "`n=== PIPELINE COMPLETO CON EXITO ===" -ForegroundColor Green
}
