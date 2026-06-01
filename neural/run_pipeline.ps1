# run_pipeline.ps1
# Pipeline completo: recolección SPX+QQQ → GBT → RL → Backtest → Visualización
Param(
  [switch]$gbt, # Paso 1 en adelante (GBT Training + Episode Index + Preprocess + RL)
  [switch]$rl,  # Paso 2 en adelante (Episode Index + Preprocess + RL)
  [switch]$tr,  # Paso 4 en adelante (RL)
  [switch]$a,   # Paso 4.5 en adelante (Diagnosis)
  [switch]$bt_gbt, # Paso 6 en adelante (Backtest GBT solo + RL + Visualizacion)
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
$BacktestDataPath = Join-ProjectPath "training_data\training_data_spx_qqq_spy.parquet"
$TrainingDataMarchPath = Join-ProjectPath "training_data\training_data_spx_qqq_spy_march_2026.parquet"
$TrainingDataPath = $TrainingDataMarchPath
$RlEpisodeIndexPath = Join-ProjectPath "rl_data\episode_index_march2026.parquet"
$RlOptionsCachePath = Join-ProjectPath "rl_data\rl_options_cache_chunks_march2026_tickersig"
$RlModelsDir = Join-ProjectPath "rl_models\march2026_oos_v12_chainctx_oracle_holdexit"
$RlBestModelPath = Join-ProjectPath "rl_models\march2026_oos_v12_chainctx_oracle_holdexit\best_rl_agent.pt"
# Codex research candidate, 2026-05-30 03:38.
# Status: GBT true OOS passed. Default training data is the March-2026 cutoff;
# backtests still run against the full parquet through May 2026.
#
# Structural fixes already in code:
#   - labels and economic scorer use exact OHLC target/stop mechanics;
#   - model features include current-row S/R flags, not future outcome fields;
#   - selection/backtest use broad nearest_level_dist when available, matching
#     IB/fib/Greek-level support/resistance labels;
#   - strict-WF top-N/min-trades are explicit env vars.
#
# Current GBT command parameters reproduced below in Paso 1:
#   --train-months 12 --test-months 1 --ensemble 3 --top-n-windows 10
#   --hold-ratio 2.0 --min-window 5 --class-weight balanced
#   --min-pf-floor 1.20 --selection-metric economic
#   --min-selection-trades 12 --selection-base-confidence 0.450
#   --min-selection-win-rate 0.45 --selection-cooldown 8
#   --sample-weight-decay-days SPX=0, QQQ=30, SPY=30
#   --min-entry-minute 580 --min-short-entry-minute 615
#   --min-short-price-vs-ib-high -150.0
#   SPX target-long/short 0.010 stop 0.0025
#   QQQ target-long/short 0.006 label stop 0.0025, execution stop 0.0030
#   SPY target-long/short 0.006 stop 0.0035
#   SPX objective multiclass; QQQ/SPY objective binary_ovr.
#
# Strict-WF deployment policy:
#   Global: MIN_AVG_PF=1.25, MIN_VALIDATION_TRADES=12, TOP_N=3, RECENCY_POWER=2.0
#   QQQ override: MIN_AVG_PF=1.25, TOP_N=2, RECENCY_POWER=0.5
#   SPY deployment context: DEPLOYMENT_TICKER_MAX_VIX_SPOT=SPY:0.4108
#
# True OOS backtest log:
#   logs\codex_bt_combined_march2026_true_oos_qqq_rec05_20260530_0925.txt
# Result: QQQ 1295 trades WR 48.8 PF 1.233; SPX 1291 trades WR 47.6 PF 1.370;
# SPY 959 trades WR 53.4 PF 1.333; all positive in Apr/May 2026.
# Home-run/duration audit log:
#   logs\codex_bt_gbt_full_home_run_profile_fixed180_20260530_1555.txt
# Result: 3545 trades, WR 49.6, PF 1.31, avg hold 95.4m, median hold 85.0m,
# winner median hold 135.0m, 59.3% of trades >=60m and 40.6% >=120m.
$GbtModelPath = Join-NeuralPath "models\codex_exp\gbt_candidate_top2_rec1_march2026.joblib"
$GbtNormalizerPath = Join-NeuralPath "models\codex_exp\gbt_candidate_top2_rec1_march2026_norm.npz"
$GbtModelSize = "small"
$GbtTrainMonths = 12
$GbtTestMonths = 1
$GbtTrainMaxTimeMinutes = 390
$GbtEnsemble = 3
$GbtTopNWindows = 10
$GbtHoldRatioArg = "2.0"
$GbtMinWindow = 5
$GbtClassWeight = "balanced"
$GbtMinPfFloorArg = "1.20"
$GbtSelectionMetric = "economic"
$GbtMinSelectionTrades = 12
$GbtMinSelectionWinRateArg = "0.45"
$GbtSelectionCooldownMinutes = 8
$GbtSampleWeightDecayDaysArg = "30"
$GbtSampleWeightDecayDaysByTicker = @{
  "SPX" = "0"
  "QQQ" = "30"
  "SPY" = "30"
}
$GbtObjectiveModeByTicker = @{
  "SPX" = "multiclass"
  "QQQ" = "binary_ovr"
  "SPY" = "binary_ovr"
}
$GbtCalibrateBinaryOvr = $false
$GbtStrictMinValidationTrades = "12"
$GbtStrictMinAvgPfArg = "1.25"
$GbtStrictTopNWindows = "3"
$GbtStrictRecencyPowerArg = "2.0"
$GbtTickerStrictMinAvgPf = "QQQ:1.25"
$GbtTickerStrictTopNWindows = "QQQ:2"
$GbtTickerStrictRecencyPowerArg = "QQQ:0.5"
$DeploymentTickerMaxVixSpot = "SPY:0.4108"

# Train-time selection and deploy-time threshold are separate on purpose.
# 0.400 is the current diagnostic deployment candidate; do not treat it as a
# clean final validation result until the next regenerated-data experiment passes.
$GbtSelectionBaseConfidenceArg = "0.450"
$BacktestBaseConfidenceArg = "0.400"
$BacktestCooldownMinutes = 8
$BacktestMaxTimeMinutes = 180
$BacktestTargetLongArg = "0.010"
$BacktestTargetShortArg = "0.010"
$BacktestStopArg = "0.0025"
$BacktestSpxTargetArg = "0.010"
$BacktestEtfTargetArg = "0.006"
$BacktestSpxStopArg = "0.0025"
$BacktestEtfStopArg = "0.0030"
$BacktestQqqTargetArg = "0.006"
$BacktestSpyTargetArg = "0.006"
$BacktestQqqStopArg = "0.0030"
$BacktestSpyStopArg = "0.0035"
$BacktestRiskCapitalArg = "1000.0"
$RlReentryLockMinutes = 0
$RlTotalUpdates = 220
$RlWorkers = 32
$RlUseEntrySkipAction = $false
$RlForceHoldExitTraining = $true
$RlStrikeOraclePretrainSamples = 6000
$RlStrikeOraclePretrainEpochs = 3
$RlStrikeOraclePretrainLrArg = "0.0001"
# RL diagnostic-only backtest overrides. Keep disabled for the promoted
# pipeline; set them explicitly when reproducing strike/exit ablations.
# Last diagnostic commands/results are documented in SUMMARY.md.
$RlDiagnosticForceStrikeBucket = ""
$RlDiagnosticForceTickerStrikeBuckets = ""
$RlDiagnosticExitPolicy = "hold"
$RlDiagnosticMaxLossPctArg = ""
$RlDiagnosticMaxProfitPctArg = ""
$BacktestTickers = @("SPX", "QQQ", "SPY")
$GbtTargetLongByTicker = @{
  "SPX" = "0.010"
  "QQQ" = "0.006"
  "SPY" = "0.006"
}
$GbtTargetShortByTicker = @{
  "SPX" = "0.010"
  "QQQ" = "0.006"
  "SPY" = "0.006"
}
$GbtStopByTicker = @{
  "SPX" = "0.0025"
  "QQQ" = "0.0025"
  "SPY" = "0.0035"
}
$MinEntryMinute = 580
$MinShortEntryMinute = 615
$MinShortPriceVsIbHighArg = "-150.0"
$MinTradesPerWeekGate = 6
$env:GBT_MIN_STRICT_WF_AVG_PF = $GbtStrictMinAvgPfArg
$env:GBT_MIN_STRICT_WF_VALIDATION_TRADES = $GbtStrictMinValidationTrades
$env:GBT_STRICT_WF_TOP_N = $GbtStrictTopNWindows
$env:GBT_STRICT_WF_RECENCY_POWER = $GbtStrictRecencyPowerArg
$env:GBT_TICKER_MIN_STRICT_WF_AVG_PF = $GbtTickerStrictMinAvgPf
$env:GBT_TICKER_STRICT_WF_TOP_N = $GbtTickerStrictTopNWindows
$env:GBT_TICKER_STRICT_WF_RECENCY_POWER = $GbtTickerStrictRecencyPowerArg
Remove-Item Env:\DEPLOYMENT_TICKER_MIN_PRICE_VS_IB_HIGH -ErrorAction SilentlyContinue
$env:DEPLOYMENT_TICKER_MAX_VIX_SPOT = $DeploymentTickerMaxVixSpot
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
Write-Host "  TrainingDataMarchPath           : $TrainingDataMarchPath"
Write-Host "  BacktestDataPath                : $BacktestDataPath"
Write-Host "  RlEpisodeIndexPath              : $RlEpisodeIndexPath"
Write-Host "  RlOptionsCachePath              : $RlOptionsCachePath"
Write-Host "  RlModelsDir                     : $RlModelsDir"
Write-Host "  RlBestModelPath                 : $RlBestModelPath"
Write-Host "  GbtModelPath                    : $GbtModelPath"
Write-Host "  GbtNormalizerPath               : $GbtNormalizerPath"
Write-Host "GBT Configuration:"
Write-Host "  GbtModelSize                    : $GbtModelSize"
Write-Host "  GbtTrainMonths                  : $GbtTrainMonths"
Write-Host "  GbtTestMonths                   : $GbtTestMonths"
Write-Host "  GbtTrainMaxTimeMinutes          : $GbtTrainMaxTimeMinutes"
Write-Host "  GbtEnsemble                     : $GbtEnsemble"
Write-Host "  GbtTopNWindows                  : $GbtTopNWindows"
Write-Host "  GbtHoldRatioArg                 : $GbtHoldRatioArg"
Write-Host "  GbtMinWindow                    : $GbtMinWindow"
Write-Host "  GbtClassWeight                  : $GbtClassWeight"
Write-Host "  GbtMinPfFloorArg                : $GbtMinPfFloorArg"
Write-Host "  GbtSelectionMetric              : $GbtSelectionMetric"
Write-Host "  GbtMinSelectionTrades           : $GbtMinSelectionTrades"
Write-Host "  GbtMinSelectionWinRateArg       : $GbtMinSelectionWinRateArg"
Write-Host "  GbtSelectionCooldownMinutes     : $GbtSelectionCooldownMinutes"
Write-Host "  GbtSampleWeightDecayDaysArg     : $GbtSampleWeightDecayDaysArg"
Write-Host "  GbtSampleWeightDecayDaysByTicker: SPX=$($GbtSampleWeightDecayDaysByTicker['SPX']), QQQ=$($GbtSampleWeightDecayDaysByTicker['QQQ']), SPY=$($GbtSampleWeightDecayDaysByTicker['SPY'])"
Write-Host "  GbtObjectiveModeByTicker        : SPX=$($GbtObjectiveModeByTicker['SPX']), QQQ=$($GbtObjectiveModeByTicker['QQQ']), SPY=$($GbtObjectiveModeByTicker['SPY'])"
Write-Host "  GbtCalibrateBinaryOvr           : $GbtCalibrateBinaryOvr"
Write-Host "  GbtStrictMinAvgPfArg            : $GbtStrictMinAvgPfArg"
Write-Host "  GbtStrictMinValidationTrades    : $GbtStrictMinValidationTrades"
Write-Host "  GbtStrictTopNWindows            : $GbtStrictTopNWindows"
Write-Host "  GbtStrictRecencyPowerArg        : $GbtStrictRecencyPowerArg"
Write-Host "  GbtTickerStrictMinAvgPf         : $GbtTickerStrictMinAvgPf"
Write-Host "  GbtTickerStrictTopNWindows      : $GbtTickerStrictTopNWindows"
Write-Host "  GbtTickerStrictRecencyPowerArg  : $GbtTickerStrictRecencyPowerArg"
Write-Host "Backtest & Execution Parameters:"
Write-Host "  BaseConfidence (RL_CONFIG)      : $BaseConfidenceArg"
Write-Host "  BacktestBaseConfidenceArg       : $BacktestBaseConfidenceArg"
Write-Host "  GbtSelectionBaseConfidenceArg   : $GbtSelectionBaseConfidenceArg"
Write-Host "  BacktestCooldownMinutes         : $BacktestCooldownMinutes"
Write-Host "  BacktestMaxTimeMinutes          : $BacktestMaxTimeMinutes"
Write-Host "  BacktestTargetLongArg           : $BacktestTargetLongArg"
Write-Host "  BacktestTargetShortArg          : $BacktestTargetShortArg"
Write-Host "  BacktestStopArg                 : $BacktestStopArg"
Write-Host "  BacktestSpxTargetArg            : $BacktestSpxTargetArg"
Write-Host "  BacktestEtfTargetArg            : $BacktestEtfTargetArg"
Write-Host "  BacktestSpxStopArg              : $BacktestSpxStopArg"
Write-Host "  BacktestEtfStopArg              : $BacktestEtfStopArg"
Write-Host "  BacktestQqqTargetArg            : $BacktestQqqTargetArg"
Write-Host "  BacktestSpyTargetArg            : $BacktestSpyTargetArg"
Write-Host "  BacktestQqqStopArg              : $BacktestQqqStopArg"
Write-Host "  BacktestSpyStopArg              : $BacktestSpyStopArg"
Write-Host "  BacktestRiskCapitalArg          : $BacktestRiskCapitalArg"
Write-Host "  RlReentryLockMinutes            : $RlReentryLockMinutes"
Write-Host "  RlTotalUpdates                  : $RlTotalUpdates"
Write-Host "  RlWorkers                       : $RlWorkers"
Write-Host "  RlUseEntrySkipAction            : $RlUseEntrySkipAction"
Write-Host "  RlForceHoldExitTraining         : $RlForceHoldExitTraining"
Write-Host "  RlStrikeOraclePretrainSamples   : $RlStrikeOraclePretrainSamples"
Write-Host "  RlStrikeOraclePretrainEpochs    : $RlStrikeOraclePretrainEpochs"
Write-Host "  RlStrikeOraclePretrainLrArg     : $RlStrikeOraclePretrainLrArg"
Write-Host "  RlDiagnosticForceStrikeBucket   : $RlDiagnosticForceStrikeBucket"
Write-Host "  RlDiagnosticForceTickerBuckets  : $RlDiagnosticForceTickerStrikeBuckets"
Write-Host "  RlDiagnosticExitPolicy          : $RlDiagnosticExitPolicy"
Write-Host "  RlDiagnosticMaxLossPctArg       : $RlDiagnosticMaxLossPctArg"
Write-Host "  RlDiagnosticMaxProfitPctArg     : $RlDiagnosticMaxProfitPctArg"
Write-Host "  BacktestTickers                 : $($BacktestTickers -join ', ')"
Write-Host "  MinEntryMinute                  : $MinEntryMinute"
Write-Host "  MinShortEntryMinute             : $MinShortEntryMinute"
Write-Host "  MinShortPriceVsIbHighArg        : $MinShortPriceVsIbHighArg"
Write-Host "  DeploymentTickerMaxVixSpot      : $DeploymentTickerMaxVixSpot"
Write-Host "  MinTradesPerWeekGate            : $MinTradesPerWeekGate"
Write-Host "==============================================`n" -ForegroundColor Green

# Determine starting stage
$skip_to_step = 0
if ($gbt) { $skip_to_step = 1 }
if ($rl) { $skip_to_step = 2 }
if ($tr) { $skip_to_step = 4 }
if ($a) { $skip_to_step = 4.5 }
if ($bt_gbt) { $skip_to_step = 6 }
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

  Write-Host "`n=== CREANDO CORTE TRUE OOS HASTA MARZO 2026 ===" -ForegroundColor Cyan
  python -c "import pandas as pd; src=r'$BacktestDataPath'; dst=r'$TrainingDataMarchPath'; df=pd.read_parquet(src); out=df[df['date'].astype(str) <= '20260331'].copy(); out.to_parquet(dst, index=False); print(f'rows_full={len(df)} rows_march={len(out)}'); print(out.groupby('ticker')['date'].agg(['min','max','nunique','count']))"

  if ($LASTEXITCODE -ne 0) {
    Write-Host "ERROR creando training_data_spx_qqq_spy_march_2026.parquet." -ForegroundColor Red
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
    $TickerTargetLong = $GbtTargetLongByTicker[$Ticker]
    $TickerTargetShort = $GbtTargetShortByTicker[$Ticker]
    $TickerStop = $GbtStopByTicker[$Ticker]
    $TickerObjectiveMode = $GbtObjectiveModeByTicker[$Ticker]
    $TickerSampleWeightDecayDays = $GbtSampleWeightDecayDaysByTicker[$Ticker]
    $TickerCalibrationArgs = @()
    if ($GbtCalibrateBinaryOvr -and $TickerObjectiveMode -eq "binary_ovr") {
      $TickerCalibrationArgs += "--calibrate-binary-ovr"
    }
    Write-Host "Using specific settings for $($Ticker): Objective $($TickerObjectiveMode), Target $($TickerTargetLong), Stop $($TickerStop), SampleDecayDays $($TickerSampleWeightDecayDays)" -ForegroundColor Cyan
    Write-Host "`n--> Entrenando modelo especializado para: $Ticker" -ForegroundColor Yellow
    python -u (Join-NeuralPath "train_walkforward.py") `
      --data $TrainingDataPath `
      --ticker $Ticker `
      --model-size $GbtModelSize `
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
      --selection-cooldown $GbtSelectionCooldownMinutes `
      --min-selection-win-rate $GbtMinSelectionWinRateArg `
      --min-entry-minute $MinEntryMinute `
      --max-time $GbtTrainMaxTimeMinutes `
        --target-long $TickerTargetLong `
        --target-short $TickerTargetShort `
        --stop-pct $TickerStop `
      --min-short-entry-minute $MinShortEntryMinute `
      --min-short-price-vs-ib-high $MinShortPriceVsIbHighArg `
      --objective-mode $TickerObjectiveMode `
      @TickerCalibrationArgs `
      --sample-weight-decay-days $TickerSampleWeightDecayDays `
      --model_path $GbtModelPath `
      --norm_path $GbtNormalizerPath

    if ($LASTEXITCODE -ne 0) {
      Write-Host "ERROR: El entrenamiento del GBT para $Ticker fallo." -ForegroundColor Red
      Exit-Pipeline 1
    }
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
    --output $RlEpisodeIndexPath `
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

  python -u (Join-NeuralPath "rl\compute_recovery_stats.py") `
    --episode-index $RlEpisodeIndexPath `
    --options-cache $RlOptionsCachePath `
    --output (Join-ProjectPath "rl_data\recovery_stats.pkl")

  if ($LASTEXITCODE -ne 0) {
    Write-Host "ERROR: compute_recovery_stats.py fallo tras el preprocess." -ForegroundColor Red
    Exit-Pipeline 1
  }
}

if ($skip_to_step -le 4) {
  # ─────────────────────────────────────────────────────────────────────────────
  # PASO 4 — RL TRAINING (Policy Optimization sobre señales GBT)
  # ─────────────────────────────────────────────────────────────────────────────
  Write-Host "`n=== RL Training (Policy Optimization sobre senales GBT) ===" -ForegroundColor Cyan
  $RlTrainingExtraArgs = @()
  if ($RlUseEntrySkipAction) {
    $RlTrainingExtraArgs += "--entry-skip-action"
  }
  if ($RlForceHoldExitTraining) {
    $RlTrainingExtraArgs += "--force-hold-exit"
  }
  if ($RlStrikeOraclePretrainSamples -gt 0) {
    $RlTrainingExtraArgs += "--strike-oracle-pretrain-samples"
    $RlTrainingExtraArgs += "$RlStrikeOraclePretrainSamples"
    $RlTrainingExtraArgs += "--strike-oracle-pretrain-epochs"
    $RlTrainingExtraArgs += "$RlStrikeOraclePretrainEpochs"
    $RlTrainingExtraArgs += "--strike-oracle-pretrain-lr"
    $RlTrainingExtraArgs += "$RlStrikeOraclePretrainLrArg"
  }

  python -u -m rl.training `
    --episode-index $RlEpisodeIndexPath `
    --options-cache $RlOptionsCachePath `
    --save-dir $RlModelsDir `
    --total-updates $RlTotalUpdates `
    --min-confidence $BacktestBaseConfidenceArg `
    --workers $RlWorkers `
    @RlTrainingExtraArgs

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
    --model-size $GbtModelSize --ensemble `
    --threshold $BacktestBaseConfidenceArg --cooldown $BacktestCooldownMinutes `
    --max-time $BacktestMaxTimeMinutes `
    --target_long $BacktestTargetLongArg --target_short $BacktestTargetShortArg --stop $BacktestStopArg `
    --spx-target $BacktestSpxTargetArg --etf-target $BacktestEtfTargetArg `
    --spx-stop $BacktestSpxStopArg --etf-stop $BacktestEtfStopArg `
    --qqq-target $BacktestQqqTargetArg --spy-target $BacktestSpyTargetArg `
    --qqq-stop $BacktestQqqStopArg --spy-stop $BacktestSpyStopArg `
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
  $RlBacktestExtraArgs = @()
  if (-not [string]::IsNullOrWhiteSpace($RlDiagnosticForceStrikeBucket)) {
    $RlBacktestExtraArgs += @("--force-rl-strike-bucket", $RlDiagnosticForceStrikeBucket)
  }
  if (-not [string]::IsNullOrWhiteSpace($RlDiagnosticForceTickerStrikeBuckets)) {
    $RlBacktestExtraArgs += @("--force-rl-ticker-strike-buckets", $RlDiagnosticForceTickerStrikeBuckets)
  }
  if (-not [string]::IsNullOrWhiteSpace($RlDiagnosticExitPolicy) -and $RlDiagnosticExitPolicy -ne "agent") {
    $RlBacktestExtraArgs += @("--rl-exit-policy", $RlDiagnosticExitPolicy)
  }
  if (-not [string]::IsNullOrWhiteSpace($RlDiagnosticMaxLossPctArg)) {
    $RlBacktestExtraArgs += @("--rl-max-loss-pct", $RlDiagnosticMaxLossPctArg)
  }
  if (-not [string]::IsNullOrWhiteSpace($RlDiagnosticMaxProfitPctArg)) {
    $RlBacktestExtraArgs += @("--rl-max-profit-pct", $RlDiagnosticMaxProfitPctArg)
  }
  if ($RlUseEntrySkipAction) {
    $RlBacktestExtraArgs += "--rl-entry-skip-action"
  }

  python -u (Join-ProjectPath "backtest\backtest_rl.py") `
    --data $BacktestDataPath `
    --model $GbtModelPath `
    --normalizer $GbtNormalizerPath `
    --rl-model $RlBestModelPath `
    --model-size $GbtModelSize --ensemble `
    --threshold $BacktestBaseConfidenceArg --cooldown $BacktestCooldownMinutes `
    --max-time $BacktestMaxTimeMinutes `
    --target-long $BacktestTargetLongArg --target-short $BacktestTargetShortArg --stop $BacktestStopArg `
    --spx-target $BacktestSpxTargetArg --etf-target $BacktestEtfTargetArg `
    --spx-stop $BacktestSpxStopArg --etf-stop $BacktestEtfStopArg `
    --qqq-target $BacktestQqqTargetArg --spy-target $BacktestSpyTargetArg `
    --qqq-stop $BacktestQqqStopArg --spy-stop $BacktestSpyStopArg `
    --risk-capital $BacktestRiskCapitalArg `
    --min-entry-minute $MinEntryMinute `
    --min-short-entry-minute $MinShortEntryMinute `
    --min-short-price-vs-ib-high $MinShortPriceVsIbHighArg `
    --rl-reentry-lock-minutes $RlReentryLockMinutes `
    --filter-by-greeks `
    --single-step-eval `
    --strict-wf `
    --tickers $BacktestTickers `
    @RlBacktestExtraArgs

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
