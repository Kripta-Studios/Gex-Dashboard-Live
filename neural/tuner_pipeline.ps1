# run_pipeline.ps1
# Pipeline completo: recolección SPX+QQQ → GBT → RL → Backtest → Visualización
Param(
  [switch]$gbt, # Paso 1 en adelante (GBT Training + Episode Index + Preprocess + RL)
  [switch]$rl,  # Paso 2 en adelante (Episode Index + Preprocess + RL)
  [switch]$tr,  # Paso 4 en adelante (RL)
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

# Intentar detener cualquier transcripción previa de forma segura
try {
  Stop-Transcript -ErrorAction Stop | Out-Null
} catch {
  # Ignorar silenciosamente si no había ninguna transcripción activa
}

# Iniciar la nueva transcripción
try {
  Start-Transcript -Path $LogFile -Force | Out-Null
  $global:TranscriptStarted = $true
} catch {
  Write-Host "Warning: No se pudo iniciar la transcripción de PowerShell: $_" -ForegroundColor Yellow
  $global:TranscriptStarted = $false
}

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
$TrainingDataPath = Join-ProjectPath "training_data\training_data_spx_qqq_spy.parquet"
$BacktestDataPath = Join-ProjectPath "training_data\training_data_spx_qqq_spy.parquet"
$RlEpisodeIndexPath = Join-ProjectPath "rl_data\episode_index.parquet"
$RlOptionsCachePath = Join-ProjectPath "rl_data\rl_options_cache_chunks"
$RlModelsDir = Join-ProjectPath "rl_models"
$RlBestModelPath = Join-ProjectPath "rl_models\best_rl_agent.pt"
$GbtModelPath = Join-NeuralPath "models\codex_exp\gbt_12m_econ_pf150_minsel10_avail.joblib"
$GbtNormalizerPath = Join-NeuralPath "models\codex_exp\gbt_12m_econ_pf150_minsel10_avail_norm.npz"
$GbtTrainMonths = 6
$GbtTestMonths = 1
$GbtEnsemble = 3
$GbtTopNWindows = 10
$GbtHoldRatioArg = "0.5"
$GbtMinWindow = 5
$GbtClassWeight = "balanced"
$GbtMinPfFloorArg = "0.95"
$GbtSelectionMetric = "economic"
$GbtMinSelectionTrades = 10

# This is an explicit validated deployment override, not a hidden drift from RL_CONFIG.
# It is passed consistently to GBT selection, episode extraction, preprocess and backtests.
$BacktestBaseConfidenceArg = "0.460"
$GbtSelectionBaseConfidenceArg = "0.450"
$BacktestCooldownMinutes = 8
$BacktestTargetLongArg = "0.010"
$BacktestTargetShortArg = "0.010"
$BacktestStopArg = "0.0025"
$BacktestRiskCapitalArg = "1000.0"
$BacktestTickers = @("SPX", "QQQ", "SPY")
$MinEntryMinute = 580
$MinShortEntryMinute = 615
$MinShortPriceVsIbHighArg = "-150.0"
$MinTradesPerWeekGate = 6
Write-Host "`n=== PIPELINE CONFIGURATION & RUN VARIABLES ===" -ForegroundColor Green
Write-Host "Parameters / Switches:"
Write-Host "  -gbt                            : $gbt"
Write-Host "  -rl                             : $rl"
Write-Host "  -tr                             : $tr"
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
if ($tr) { $skip_to_step = 4 }
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
  Write-Host "`n=== ENTRENAMIENTO GBT Walk-Forward (LightGBM Ensemble por Ticker) ===" -ForegroundColor Cyan
  New-Item -ItemType Directory -Force -Path (Split-Path $GbtModelPath) | Out-Null
  
  foreach ($Ticker in $BacktestTickers) {
    if ($Ticker -eq "SPX") {
        $TickerTargetLong = "0.010"
        $TickerTargetShort = "0.010"
        $TickerStop = "0.0025"
    } elseif ($Ticker -eq "QQQ") {
        $TickerTargetLong = "0.006"
        $TickerTargetShort = "0.006"
        $TickerStop = "0.0025"
    } elseif ($Ticker -eq "SPY") {
        $TickerTargetLong = "0.006"
        $TickerTargetShort = "0.006"
        $TickerStop = "0.0025"
    }
    Write-Host "Using specific settings for $($Ticker): Target $($TickerTargetLong), Stop $($TickerStop)" -ForegroundColor Cyan
    Write-Host "`n--> Entrenando modelo especializado para: $Ticker" -ForegroundColor Yellow
    python -u (Join-NeuralPath "train_walkforward.py") `
      --data $TrainingDataPath `
      --ticker $Ticker `
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
        --target-long $TickerTargetLong `
        --target-short $TickerTargetShort `
        --stop-pct $TickerStop `
      --min-short-entry-minute $MinShortEntryMinute `
      --min-short-price-vs-ib-high $MinShortPriceVsIbHighArg `
      --model_path $GbtModelPath `
      --norm_path $GbtNormalizerPath

    if ($LASTEXITCODE -ne 0) {
      Write-Host "ERROR: El entrenamiento del GBT para $Ticker fallo." -ForegroundColor Red
      Exit-Pipeline 1
    }
  }
}

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


Exit-Pipeline 0
