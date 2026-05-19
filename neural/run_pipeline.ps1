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
$env:PYTHONUNBUFFERED = "1"
$NeuralRoot = $PSScriptRoot
$ProjectRoot = Split-Path $NeuralRoot -Parent

# Initialize Logging
$LogsDir = Join-Path $ProjectRoot "logs"
if (-not (Test-Path $LogsDir)) {
  New-Item -ItemType Directory -Path $LogsDir -Force | Out-Null
}
$Timestamp = Get-Date -Format "yyyy-MM-dd_HH-mm"
$LogFile = Join-Path $LogsDir "run_$Timestamp.txt"

Write-Host "Iniciando registro en: $LogFile" -ForegroundColor Yellow
Start-Transcript -Path $LogFile -Force | Out-Null
$global:TranscriptStarted = $true

function Exit-Pipeline([int]$code) {
  if ($global:TranscriptStarted) {
    Stop-Transcript | Out-Null
    $global:TranscriptStarted = $false
  }
  exit $code
}
$PathSeparator = [System.IO.Path]::PathSeparator
$PythonPathParts = @($NeuralRoot, $ProjectRoot)
if (-not [string]::IsNullOrWhiteSpace($env:PYTHONPATH)) {
  $PythonPathParts += $env:PYTHONPATH
}
$env:PYTHONPATH = ($PythonPathParts -join $PathSeparator)

function Join-NeuralPath([string]$RelativePath) {
  return Join-Path $NeuralRoot $RelativePath
}

function Join-ProjectPath([string]$RelativePath) {
  return Join-Path $ProjectRoot $RelativePath
}

function Get-RLBaseConfidence {
  $confidenceRaw = & python -c "from rl.config import RL_CONFIG; print(RL_CONFIG['min_confidence'])"
  if ($LASTEXITCODE -ne 0 -or [string]::IsNullOrWhiteSpace($confidenceRaw)) {
    throw "No se pudo leer RL_CONFIG['min_confidence']"
  }

  $confidenceText = ($confidenceRaw | Select-Object -Last 1).Trim()
  return [double]::Parse($confidenceText, [System.Globalization.CultureInfo]::InvariantCulture)
}

$BaseConfidence = Get-RLBaseConfidence
$BaseConfidenceArg = [string]::Format(
  [System.Globalization.CultureInfo]::InvariantCulture,
  "{0:0.###}",
  $BaseConfidence
)
Write-Host "[CONFIG] Base confidence cargada desde RL_CONFIG: $BaseConfidenceArg" -ForegroundColor DarkCyan

# Best validated configuration for the Apr/May 2026 recent gate.
# Avoid post-hoc ticker/direction blocks: they improved diagnostics but were
# hindsight-fit. Promoted filters are broad time/IB-context guards.
# Fecha más reciente en training_data_spx_qqq_spy.parquet: 20260518
# Fecha más reciente en training_data_TRAIN.parquet: 20260430
$TrainingDataPath = Join-ProjectPath "training_data\training_data_TRAIN.parquet"
$BacktestDataPath = Join-ProjectPath "training_data\training_data_spx_qqq_spy.parquet"
$RlEpisodeIndexPath = Join-ProjectPath "rl_data\episode_index.parquet"
$RlOptionsCachePath = Join-ProjectPath "rl_data\rl_options_cache_chunks"
$RlModelsDir = Join-ProjectPath "rl_models"
$RlBestModelPath = Join-ProjectPath "rl_models\best_rl_agent.pt"
$GbtModelPath = Join-NeuralPath "models\codex_exp\gbt_18m_econ_pf150_minsel10_avail.joblib"
$GbtNormalizerPath = Join-NeuralPath "models\codex_exp\gbt_18m_econ_pf150_minsel10_avail_norm.npz"
$GbtTrainMonths = 18
$GbtTestMonths = 1
$GbtEnsemble = 3
$GbtTopNWindows = 10
$GbtHoldRatioArg = "1.2"
$GbtMinWindow = 15
$GbtClassWeight = "none"
$GbtMinPfFloorArg = "1.50"
$GbtSelectionMetric = "economic"
$GbtMinSelectionTrades = 10

# This is an explicit validated deployment override, not a hidden drift from RL_CONFIG.
# It is passed consistently to GBT selection, episode extraction, preprocess and backtests.
$BacktestBaseConfidenceArg = "0.475"
$GbtSelectionBaseConfidenceArg = $BacktestBaseConfidenceArg
$BacktestCooldownMinutes = 15
$BacktestTargetLongArg = "0.010"
$BacktestTargetShortArg = "0.010"
$BacktestStopArg = "0.0025"
$BacktestRiskCapitalArg = "1000.0"
$BacktestTickers = @("SPX", "QQQ", "SPY")
$MinEntryMinute = 580
$MinShortEntryMinute = 615
$MinShortPriceVsIbHighArg = "-40.0"
$MinTradesPerWeekGate = 6
Write-Host "`n=== PIPELINE CONFIGURATION & RUN VARIABLES ===" -ForegroundColor Green
Write-Host "Parameters / Switches:"
Write-Host "  -gbt                            : $gbt"
Write-Host "  -rl                             : $rl"
Write-Host "  -a                              : $a"
Write-Host "  -bt                             : $bt"
Write-Host "  -v                              : $v"
Write-Host "  -u                              : $u"
Write-Host "Directories & Paths:"
Write-Host "  NeuralRoot                      : $NeuralRoot"
Write-Host "  ProjectRoot                     : $ProjectRoot"
Write-Host "  TrainingDataPath                : $TrainingDataPath"
Write-Host "  BacktestDataPath                : $BacktestDataPath"
Write-Host "  RlEpisodeIndexPath              : $RlEpisodeIndexPath"
Write-Host "  RlOptionsCachePath              : $RlOptionsCachePath"
Write-Host "  RlModelsDir                     : $RlModelsDir"
Write-Host "  RlBestModelPath                 : $RlBestModelPath"
Write-Host "  GbtModelPath                    : $GbtModelPath"
Write-Host "  GbtNormalizerPath               : $GbtNormalizerPath"
Write-Host "GBT Configuration:"
Write-Host "  GbtTrainMonths                  : $GbtTrainMonths"
Write-Host "  GbtTestMonths                   : $GbtTestMonths"
Write-Host "  GbtEnsemble                     : $GbtEnsemble"
Write-Host "  GbtTopNWindows                  : $GbtTopNWindows"
Write-Host "  GbtHoldRatioArg                 : $GbtHoldRatioArg"
Write-Host "  GbtMinWindow                    : $GbtMinWindow"
Write-Host "  GbtClassWeight                  : $GbtClassWeight"
Write-Host "  GbtMinPfFloorArg                : $GbtMinPfFloorArg"
Write-Host "  GbtSelectionMetric              : $GbtSelectionMetric"
Write-Host "  GbtMinSelectionTrades           : $GbtMinSelectionTrades"
Write-Host "Backtest & Execution Parameters:"
Write-Host "  BaseConfidence (RL_CONFIG)      : $BaseConfidenceArg"
Write-Host "  BacktestBaseConfidenceArg       : $BacktestBaseConfidenceArg"
Write-Host "  GbtSelectionBaseConfidenceArg   : $GbtSelectionBaseConfidenceArg"
Write-Host "  BacktestCooldownMinutes         : $BacktestCooldownMinutes"
Write-Host "  BacktestTargetLongArg           : $BacktestTargetLongArg"
Write-Host "  BacktestTargetShortArg          : $BacktestTargetShortArg"
Write-Host "  BacktestStopArg                 : $BacktestStopArg"
Write-Host "  BacktestRiskCapitalArg          : $BacktestRiskCapitalArg"
Write-Host "  BacktestTickers                 : $($BacktestTickers -join ', ')"
Write-Host "  MinEntryMinute                  : $MinEntryMinute"
Write-Host "  MinShortEntryMinute             : $MinShortEntryMinute"
Write-Host "  MinShortPriceVsIbHighArg        : $MinShortPriceVsIbHighArg"
Write-Host "  MinTradesPerWeekGate            : $MinTradesPerWeekGate"
Write-Host "==============================================`n" -ForegroundColor Green

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
  if ($LASTEXITCODE -ne 0) { Write-Host "ERROR: options_bulk.py fallo." -ForegroundColor Red; Exit-Pipeline 1 }

  Write-Host "Ejecutando D:\ThetaData\script4_underlying_from_options.py..." -ForegroundColor Yellow
  python D:\ThetaData\script4_underlying_from_options.py
  if ($LASTEXITCODE -ne 0) { Write-Host "ERROR: script4_underlying_from_options.py fallo." -ForegroundColor Red; Exit-Pipeline 1 }
  
  $skip_to_step = 0
}

# ─────────────────────────────────────────────────────────────────────────────
# PASO 0 — RECOLECCIÓN DE DATOS (SPX base + QQQ como contexto)
# ─────────────────────────────────────────────────────────────────────────────
if ($skip_to_step -le 0) {
  Write-Host "`n=== RECOLECTANDO DATOS SPX+QQQ+SPY ===" -ForegroundColor Cyan
  python -u (Join-NeuralPath "collect_training_data_spx_qqq.py") `
    --start 20220801 --end 20261230 `
    --workers 20 --tickers SPX QQQ SPY `
    --output $BacktestDataPath

  if ($LASTEXITCODE -ne 0) {
    Write-Host "ERROR en la recoleccion de datos SPX+QQQ+SPY." -ForegroundColor Red
    Exit-Pipeline 1
  }
}

# ─────────────────────────────────────────────────────────────────────────────
# PASO 1 — ENTRENAMIENTO GBT (Walk-Forward LightGBM)
# ─────────────────────────────────────────────────────────────────────────────
if ($skip_to_step -le 1) {
  Write-Host "`n=== ENTRENAMIENTO GBT Walk-Forward (LightGBM Ensemble) ===" -ForegroundColor Cyan
  New-Item -ItemType Directory -Force -Path (Split-Path $GbtModelPath) | Out-Null
  python -u (Join-NeuralPath "train_walkforward.py") `
    --data $TrainingDataPath `
    --model-size small `
    --train-months $GbtTrainMonths `
    --test-months $GbtTestMonths `
    --ensemble $GbtEnsemble `
    --top-n-windows $GbtTopNWindows `
    --hold-ratio $GbtHoldRatioArg `
    --min-window $GbtMinWindow `
    --class-weight $GbtClassWeight `
    --min-pf-floor $GbtMinPfFloorArg `
    --selection-metric $GbtSelectionMetric `
    --min-selection-trades $GbtMinSelectionTrades `
    --selection-base-confidence $GbtSelectionBaseConfidenceArg `
    --min-entry-minute $MinEntryMinute `
    --min-short-entry-minute $MinShortEntryMinute `
    --min-short-price-vs-ib-high $MinShortPriceVsIbHighArg `
    --model_path $GbtModelPath `
    --norm_path $GbtNormalizerPath

  if ($LASTEXITCODE -ne 0) {
    Write-Host "ERROR: El entrenamiento del GBT fallo. Revisa los candados matematicos o el LR." -ForegroundColor Red
    Exit-Pipeline 1
  }
}

# ─────────────────────────────────────────────────────────────────────────────
# PASO 2 — GENERACIÓN DE ÍNDICE DE EPISODIOS (para RL)
# ─────────────────────────────────────────────────────────────────────────────
if ($skip_to_step -le 2) {
  Write-Host "`n=== Generando Indice de Episodios ===" -ForegroundColor Cyan
  $env:MODEL_PATH = $GbtModelPath
  $env:NORM_PATH = $GbtNormalizerPath
  python -u (Join-NeuralPath "generate_episode_index.py") `
    --data $TrainingDataPath `
    --strict-wf `
    --min-confidence $BacktestBaseConfidenceArg `
    --min-entry-minute $MinEntryMinute `
    --min-short-entry-minute $MinShortEntryMinute `
    --min-short-price-vs-ib-high $MinShortPriceVsIbHighArg

  if ($LASTEXITCODE -ne 0) {
    Write-Host "ERROR: generate_episode_index.py fallo." -ForegroundColor Red
    Exit-Pipeline 1
  }

  # ─────────────────────────────────────────────────────────────────────────────
  # PASO 3 — PREPROCESSING (inferencia GBT → cache RL)
  # ─────────────────────────────────────────────────────────────────────────────
  Write-Host "`n=== Preprocessing con GBT SPX+QQQ (Inferencia de Senales) ===" -ForegroundColor Cyan
  
  # Limpiar la cache corrupta por precaucion tras el crash OOM original
  # If (Test-Path "..\rl_data\rl_options_cache_chunks") {
  #   Remove-Item "..\rl_data\rl_options_cache_chunks\*" -Recurse -Force -ErrorAction SilentlyContinue
  # }

  python -u (Join-NeuralPath "run_preprocess.py") `
    --training-data $TrainingDataPath `
    --options-dir D:\ThetaData\data_options `
    --output $RlOptionsCachePath `
    --mlp-model $GbtModelPath `
    --mlp-normalizer $GbtNormalizerPath `
    --num-workers 22 `
    --strict-wf `
    --min-confidence $BacktestBaseConfidenceArg `
    --min-entry-minute $MinEntryMinute `
    --min-short-entry-minute $MinShortEntryMinute `
    --min-short-price-vs-ib-high $MinShortPriceVsIbHighArg

  if ($LASTEXITCODE -ne 0) {
    Write-Host "ERROR: run_preprocess.py fallo. No se continuara con artefactos viejos." -ForegroundColor Red
    Exit-Pipeline 1
  }

  python -u (Join-NeuralPath "rl\compute_recovery_stats.py")

  if ($LASTEXITCODE -ne 0) {
    Write-Host "ERROR: compute_recovery_stats.py fallo tras el preprocess." -ForegroundColor Red
    Exit-Pipeline 1
  }

  # ─────────────────────────────────────────────────────────────────────────────
  # PASO 4 — RL TRAINING (Policy Optimization sobre señales GBT)
  # ─────────────────────────────────────────────────────────────────────────────
  Write-Host "`n=== RL Training (Policy Optimization sobre senales GBT) ===" -ForegroundColor Cyan
  python -u -m rl.training `
    --episode-index $RlEpisodeIndexPath `
    --options-cache $RlOptionsCachePath `
    --save-dir $RlModelsDir `
    --total-updates 500 `
    --min-confidence $BacktestBaseConfidenceArg `
    --workers 32

  if ($LASTEXITCODE -ne 0) {
    Write-Host "ERROR: RL Training fallo." -ForegroundColor Red
    Exit-Pipeline 1
  }
}

# ─────────────────────────────────────────────────────────────────────────────
# PASO 4.5 — PIPELINE DIAGNOSIS (Check Health & Overfitting)
# ─────────────────────────────────────────────────────────────────────────────
if ($skip_to_step -le 4.5) {
  Write-Host "`n=== Pipeline Diagnosis (Health & Performance Check) ===" -ForegroundColor Cyan
  python -u (Join-NeuralPath "diagnose_pipeline.py") `
    --train-months $GbtTrainMonths `
    --test-months $GbtTestMonths `
    --data $TrainingDataPath `
    --model $GbtModelPath `
    --normalizer $GbtNormalizerPath `
    --options-cache $RlOptionsCachePath

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
  python -u (Join-ProjectPath "backtest\backtest_gbt_parquet.py") `
    --data $BacktestDataPath `
    --model $GbtModelPath `
    --normalizer $GbtNormalizerPath `
    --model-size small --ensemble `
    --threshold $BacktestBaseConfidenceArg --cooldown $BacktestCooldownMinutes `
    --target_long $BacktestTargetLongArg --target_short $BacktestTargetShortArg --stop $BacktestStopArg `
    --risk-capital $BacktestRiskCapitalArg `
    --min-entry-minute $MinEntryMinute `
    --min-short-entry-minute $MinShortEntryMinute `
    --min-short-price-vs-ib-high $MinShortPriceVsIbHighArg `
    --tickers $BacktestTickers `
    --strict-wf
        
  if ($LASTEXITCODE -ne 0) {
    Write-Host "ERROR: Backtest GBT fallo." -ForegroundColor Red
    Exit-Pipeline 1
  }
}

# ─────────────────────────────────────────────────────────────────────────────
# PASO 7 — BACKTESTING GBT + RL
# ─────────────────────────────────────────────────────────────────────────────
if ($skip_to_step -le 7) {
  Write-Host "`n=== BACKTESTING GBT+RL ===" -ForegroundColor DarkGreen
  python -u (Join-ProjectPath "backtest\backtest_rl.py") `
    --data $BacktestDataPath `
    --model $GbtModelPath `
    --normalizer $GbtNormalizerPath `
    --rl-model $RlBestModelPath `
    --model-size small --ensemble `
    --threshold $BacktestBaseConfidenceArg --cooldown $BacktestCooldownMinutes `
    --target-long $BacktestTargetLongArg --target-short $BacktestTargetShortArg --stop $BacktestStopArg `
    --risk-capital $BacktestRiskCapitalArg `
    --min-entry-minute $MinEntryMinute `
    --min-short-entry-minute $MinShortEntryMinute `
    --min-short-price-vs-ib-high $MinShortPriceVsIbHighArg `
    --filter-by-greeks `
    --single-step-eval `
    --strict-wf `
    --tickers $BacktestTickers

  if ($LASTEXITCODE -ne 0) {
    Write-Host "ERROR: Backtest GBT+RL fallo." -ForegroundColor Red
    Exit-Pipeline 1
  }

  python -u (Join-ProjectPath "backtest\analyze_trade_gaps.py")
}

# ─────────────────────────────────────────────────────────────────────────────
# PASO 8 — VISUALIZACIÓN
# ─────────────────────────────────────────────────────────────────────────────
if ($skip_to_step -le 8) {
  Write-Host "`n=== VISUALIZACION ===" -ForegroundColor Cyan
  python -u (Join-ProjectPath "visualizer\analyze_backtests.py")
  python -u (Join-ProjectPath "visualizer\analyze_backtests.py") --month 202601
  python -u (Join-ProjectPath "visualizer\analyze_backtests.py") --month 202602
  python -u (Join-ProjectPath "visualizer\analyze_backtests.py") --month 202603
  python -u (Join-ProjectPath "visualizer\analyze_backtests.py") --month 202604
  python -u (Join-ProjectPath "visualizer\analyze_backtests.py") --month 202605
  python -u (Join-ProjectPath "visualizer\analyze_backtests.py") --month 202503
  python -u (Join-ProjectPath "visualizer\analyze_backtests.py") --month 202504

  python -u (Join-ProjectPath "visualizer\visualize_features.py") `
    --mode all `
    --gbt-model $GbtModelPath `
    --normalizer $GbtNormalizerPath `
    --save

  Write-Host "`n=== PIPELINE COMPLETO CON EXITO ===" -ForegroundColor Green
}

Exit-Pipeline 0
