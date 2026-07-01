# run_pipeline.ps1
# Isolated JEPA pipeline: data collection -> XInputJEPA -> GBT+JEPA 180m ->
# supervised 0DTE option policy -> OptionValueJEPA walk-forward -> visual reports.

Param(
  [switch]$jepa,      # Start at Step 1: train/append JEPA features.
  [switch]$gbt,       # Start at Step 3: train/backtest GBT+JEPA 180m.
  [switch]$bt,        # Start at Step 4: standalone GBT+JEPA OOS backtest.
  [switch]$options,   # Start at Step 5: 0DTE option-policy experiments.
  [switch]$wf,        # Start at Step 7: OptionValueJEPA monthly walk-forward.
  [switch]$v,         # Start at Step 8: visualizer.

  [switch]$QuickSmoke,
  [switch]$SkipCollect,
  [switch]$SkipCutoff,
  [switch]$SkipJepaTrain,
  [switch]$SkipAppend,
  [switch]$SkipGbt180,
  [switch]$SkipGbtOof,
  [switch]$SkipStandaloneBacktest,
  [switch]$SkipGbtExitResearch,
  [switch]$SkipOptionPolicy,
  [switch]$SkipOptionValueSplit,
  [switch]$SkipWalkForward,
  [switch]$SkipExitGrid,
  [switch]$SkipFullVisualizerBacktests,
  [switch]$SkipVisualizer,
  [switch]$ReuseOptionCandidates,
  [switch]$RebuildOptionStateRows,
  [switch]$ProductionTrain,
  [switch]$DailyProduction,
  [switch]$HighWinRateOptionsProfile,

  [string]$Experiment = "jepa_full_pipeline",
  [string]$JepaFeatureExperiment = "xinput_v3_pipeline",
  [string]$Jepa180Experiment = "",
  [string]$ProductionDeployMonth = (Get-Date -Format "yyyyMM"),
  [string]$StartDate = "20220801",
  [string]$EndDate = "20261230",
  [string]$TrainEndDate = "20260331",
  [string]$TestStartDate = "20260401",
  [string]$TestEndDate = "",
  [string]$WalkForwardStartMonth = "",
  [string]$WalkForwardEndMonth = "",
  [int]$Workers = 20,
  [string]$Device = "cuda",
  [int]$CooldownMinutes = 180,
  [int]$MaxHoldMinutes = 180,
  [double]$RiskCapital = 5000.0,
  [double]$HardStopPct = -0.60,
  [double]$TakeProfitPct = 2.50,
  [int]$MinExitHoldMinutes = 15,
  [int]$OptionPolicyNEstimators = 260,
  [int]$OptionPolicyExitNEstimators = 220,
  [int]$OptionValueEpochs = 20,
  [int]$WalkForwardEpochs = 8,
  [int]$GbtOofMinTrainMonths = 24,
  [int]$GbtOofValMonths = 6,
  [int]$MaxDynamicTrainRows = 260000,
  [int]$NJobs = 20,
  [double]$GbtExitTrailStopBps = -50.0,
  [double]$GbtExitTrailActivationBps = 30.0,
  [double]$GbtExitTrailDrawdownBps = 5.0,
  [double]$GbtExitTrailTakeProfitBps = 100.0,
  [string]$OptionValueVisualizerPolicy = "option_value_blended_score_trail_cutoff_trades.csv",
  [string]$OptionValueVisualizerLabel = "JEPA 0DTE OptionValue Blended Trail",
  [string]$FeatureVizGbtModel = "",
  [string]$FeatureVizNormalizer = ""
)

$ErrorActionPreference = "Stop"
$env:PYTHONUNBUFFERED = "1"

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$NeuralRoot = Split-Path -Parent $ScriptDir
$ProjectRoot = Split-Path -Parent $NeuralRoot

function Join-NeuralPath([string]$RelativePath) {
  return Join-Path $NeuralRoot $RelativePath
}

function Join-ProjectPath([string]$RelativePath) {
  return Join-Path $ProjectRoot $RelativePath
}

function Invoke-PythonStep {
  param(
    [string]$Name,
    [string[]]$PythonArgs,
    [string]$LogPath
  )
  Write-Host "`n=== $Name ===" -ForegroundColor Cyan
  New-Item -ItemType Directory -Force -Path (Split-Path $LogPath) | Out-Null
  $oldErrorActionPreference = $ErrorActionPreference
  $ErrorActionPreference = "Continue"
  & python -u @PythonArgs 2>&1 | Tee-Object -FilePath $LogPath
  $exitCode = $LASTEXITCODE
  $ErrorActionPreference = $oldErrorActionPreference
  if ($exitCode -ne 0) {
    throw "Step failed: $Name (exit $exitCode). See $LogPath"
  }
}

function Invoke-PythonInline {
  param(
    [string]$Name,
    [string]$Code,
    [string[]]$PythonArgs,
    [string]$LogPath
  )
  $argsForPython = @("-c", $Code) + $PythonArgs
  Invoke-PythonStep $Name $argsForPython $LogPath
}

function Assert-PathExists {
  param(
    [string]$Path,
    [string]$Description
  )
  if (-not (Test-Path $Path)) {
    throw "$Description not found: $Path"
  }
}

$PathSeparator = [System.IO.Path]::PathSeparator
$PythonPathParts = @($NeuralRoot, $ProjectRoot)
if (-not [string]::IsNullOrWhiteSpace($env:PYTHONPATH)) {
  $PythonPathParts += $env:PYTHONPATH
}
$env:PYTHONPATH = ($PythonPathParts -join $PathSeparator)

if ($DailyProduction) {
  $DailyPipeline = Join-Path $ScriptDir "run_daily_production_pipeline.ps1"
  Assert-PathExists $DailyPipeline "Daily production pipeline"
  & $DailyPipeline -DeployMonth $ProductionDeployMonth -Workers $Workers -RiskCapital $RiskCapital
  if ($LASTEXITCODE -ne 0) {
    throw "Daily production pipeline failed with exit code $LASTEXITCODE"
  }
  exit 0
}

if ($ProductionTrain) {
  if ($Experiment -eq "jepa_full_pipeline") {
    $Experiment = "jepa_production_final"
  }
  if ($JepaFeatureExperiment -eq "xinput_v3_pipeline") {
    $JepaFeatureExperiment = "xinput_v3_production"
  }
  if ([string]::IsNullOrWhiteSpace($Jepa180Experiment)) {
    $Jepa180Experiment = "${Experiment}_180m"
  }
  $TrainEndDate = "20261230"
  $TestStartDate = ""
  $SkipStandaloneBacktest = $true
  $SkipGbtExitResearch = $true
  # Keep option candidate generation and OptionValue final-fit enabled so live
  # production has its own option selector artifact.
  $SkipWalkForward = $true
  $SkipExitGrid = $true
  $SkipFullVisualizerBacktests = $true
  $SkipVisualizer = $true
}

if ($HighWinRateOptionsProfile) {
  # Validated on the high-precision QQQ/SPY long-only signal:
  # Jan-Jun 2025 validation: delta 0.60, WR 71.9%, PF 1.85.
  # Jul-2025..Jun-2026 test: delta 0.60, WR 76.5%, PF 2.08.
  # This profile prioritizes win-rate over the old home-run objective.
  $HardStopPct = -0.30
  $TakeProfitPct = 0.15
}

if ([string]::IsNullOrWhiteSpace($Jepa180Experiment)) {
  $Jepa180Experiment = "${Experiment}_180m_frozen_march"
}

$skip_to_step = 0
if ($jepa) { $skip_to_step = 1 }
if ($gbt) { $skip_to_step = 3 }
if ($bt) { $skip_to_step = 4 }
if ($options) { $skip_to_step = 5 }
if ($wf) { $skip_to_step = 7 }
if ($v) { $skip_to_step = 8 }

$LogsDir = Join-ProjectPath "logs"
$ResultsRoot = Join-ProjectPath "research_papers\JEPA\results\$Experiment"
$JepaFeatureModelDir = Join-NeuralPath "models\jepa\$JepaFeatureExperiment"
$JepaFeatureNamesPath = Join-Path $JepaFeatureModelDir "jepa_feature_names.json"
$FullBaseDataPath = Join-ProjectPath "training_data\training_data_spx_qqq_spy.parquet"
$TrainBaseDataPath = Join-ProjectPath "training_data\training_data_spx_qqq_spy_march_2026.parquet"
$FullJepaDataPath = Join-ProjectPath "training_data\training_data_spx_qqq_spy_jepa_$JepaFeatureExperiment.parquet"
$TrainJepaDataPath = Join-ProjectPath "training_data\training_data_spx_qqq_spy_march_2026_jepa_$JepaFeatureExperiment.parquet"
if ($ProductionTrain) {
  $TrainBaseDataPath = Join-ProjectPath "training_data\training_data_spx_qqq_spy_production_$TrainEndDate.parquet"
  $TrainJepaDataPath = Join-ProjectPath "training_data\training_data_spx_qqq_spy_production_${TrainEndDate}_jepa_$JepaFeatureExperiment.parquet"
  $FullJepaDataPath = $TrainJepaDataPath
}

$Jepa180ResultsDir = Join-ProjectPath "research_papers\JEPA\results\$Jepa180Experiment"
$Jepa180ModelDir = Join-NeuralPath "models\jepa\$Jepa180Experiment"
$OofGbtPredictionsPath = Join-Path $Jepa180ResultsDir "oof_gbt_predictions.parquet"
$Jepa180StandaloneResultsDir = Join-ProjectPath "research_papers\JEPA\results\${Experiment}_180m_standalone"
$Jepa180FullResultsDir = Join-ProjectPath "research_papers\JEPA\results\${Experiment}_180m_full"
$GbtExitResearchResultsDir = Join-ProjectPath "research_papers\JEPA\results\${Experiment}_180m_continuation_exit"
$OptionPolicyResultsDir = Join-ProjectPath "research_papers\JEPA\results\${Experiment}_option_policy"
$OptionPolicyModelDir = Join-NeuralPath "models\jepa\${Experiment}_option_policy"
$OptionValueSplitResultsDir = Join-ProjectPath "research_papers\JEPA\results\${Experiment}_option_value_split"
$OptionValueSplitModelDir = Join-NeuralPath "models\jepa\${Experiment}_option_value_split"
if ($ProductionTrain) {
  $OptionValueSplitResultsDir = Join-ProjectPath "research_papers\JEPA\results\${Experiment}_option_value_production"
  $OptionValueSplitModelDir = Join-NeuralPath "models\jepa\${Experiment}_option_value"
}
$OptionValueWalkForwardResultsDir = Join-ProjectPath "research_papers\JEPA\results\${Experiment}_option_value_walkforward"
$FixedExitGridResultsDir = Join-ProjectPath "research_papers\JEPA\results\${Experiment}_fixed_delta_exit_grid"
$CandidateLabelsPath = Join-Path $OptionPolicyResultsDir "candidate_labels.parquet"
$VisualizerBacktestDir = Join-ProjectPath "backtest_results\jepa\$Experiment"
$VisualizerAnalysisDir = Join-ProjectPath "visualizer\analysis\jepa\$Experiment"

if ([string]::IsNullOrWhiteSpace($FeatureVizGbtModel)) {
  $FeatureVizGbtModel = Join-NeuralPath "models\codex_exp\gbt_candidate_top2_rec1_march2026.joblib"
}
if ([string]::IsNullOrWhiteSpace($FeatureVizNormalizer)) {
  $FeatureVizNormalizer = Join-NeuralPath "models\codex_exp\gbt_candidate_top2_rec1_march2026_norm.npz"
}

New-Item -ItemType Directory -Force -Path $LogsDir | Out-Null
New-Item -ItemType Directory -Force -Path $ResultsRoot | Out-Null
New-Item -ItemType Directory -Force -Path $JepaFeatureModelDir | Out-Null
New-Item -ItemType Directory -Force -Path $Jepa180ResultsDir | Out-Null
New-Item -ItemType Directory -Force -Path $Jepa180ModelDir | Out-Null

$Timestamp = Get-Date -Format "yyyy-MM-dd_HH-mm"
$TranscriptPath = Join-Path $LogsDir "jepa_pipeline_$Timestamp.txt"
try {
  Stop-Transcript -ErrorAction Stop | Out-Null
} catch {
}
try {
  Start-Transcript -Path $TranscriptPath -Force | Out-Null
  $global:JepaTranscriptStarted = $true
} catch {
  Write-Host "Warning: could not start transcript: $_" -ForegroundColor Yellow
  $global:JepaTranscriptStarted = $false
}

function Exit-JepaPipeline([int]$Code) {
  if ($global:JepaTranscriptStarted) {
    Stop-Transcript | Out-Null
    $global:JepaTranscriptStarted = $false
  }
  exit $Code
}

$JepaEpochs = if ($QuickSmoke) { "1" } else { "40" }
$JepaBatchSize = if ($QuickSmoke) { "1024" } else { "512" }
$Gbt180Estimators = if ($QuickSmoke) { "30" } else { "180" }
$OptionPolicyTrees = if ($QuickSmoke) { "40" } else { "$OptionPolicyNEstimators" }
$OptionPolicyExitTrees = if ($QuickSmoke) { "30" } else { "$OptionPolicyExitNEstimators" }
$OptionValueEpochsEffective = if ($QuickSmoke) { "1" } else { "$OptionValueEpochs" }
$WalkForwardEpochsEffective = if ($QuickSmoke) { "1" } else { "$WalkForwardEpochs" }
$MaxDynamicTrainRowsEffective = if ($QuickSmoke) { "50000" } else { "$MaxDynamicTrainRows" }
$OptionMaxSignals = if ($QuickSmoke) { "40" } else { "0" }
$WalkForwardMaxFolds = if ($QuickSmoke) { "2" } else { "0" }
if ($QuickSmoke) {
  $SkipGbtExitResearch = $true
}

Write-Host "`n=== JEPA PIPELINE CONFIGURATION ===" -ForegroundColor Green
Write-Host "ProjectRoot              : $ProjectRoot"
Write-Host "Experiment               : $Experiment"
Write-Host "JepaFeatureExperiment    : $JepaFeatureExperiment"
Write-Host "Jepa180Experiment        : $Jepa180Experiment"
Write-Host "FullBaseDataPath         : $FullBaseDataPath"
Write-Host "TrainBaseDataPath        : $TrainBaseDataPath"
Write-Host "FullJepaDataPath         : $FullJepaDataPath"
Write-Host "TrainJepaDataPath        : $TrainJepaDataPath"
Write-Host "ProductionTrain          : $ProductionTrain"
Write-Host "HighWinRateOptionsProfile: $HighWinRateOptionsProfile"
Write-Host "TrainEndDate             : $TrainEndDate"
Write-Host "TestStartDate            : $TestStartDate"
Write-Host "QuickSmoke               : $QuickSmoke"
Write-Host "Workers                  : $Workers"
Write-Host "NJobs                    : $NJobs"
Write-Host "GbtExitTrailBps          : stop=$GbtExitTrailStopBps activation=$GbtExitTrailActivationBps drawdown=$GbtExitTrailDrawdownBps takeProfit=$GbtExitTrailTakeProfitBps"
Write-Host "Transcript               : $TranscriptPath"

try {
  # Step 0: data collection and cutoff generation.
  if ($skip_to_step -le 0) {
    if (-not $SkipCollect) {
      Invoke-PythonStep "Step 0A - collect SPX/QQQ/SPY training data" @(
        (Join-NeuralPath "collect_training_data_spx_qqq.py"),
        "--start", $StartDate,
        "--end", $EndDate,
        "--workers", "$Workers",
        "--tickers", "SPX", "QQQ", "SPY",
        "--output", $FullBaseDataPath
      ) (Join-Path $ResultsRoot "00_collect_data.log")
    } else {
      Write-Host "`n=== Step 0A - data collection skipped ===" -ForegroundColor Yellow
    }

    if (-not $SkipCutoff) {
      Assert-PathExists $FullBaseDataPath "Full base parquet"
      $CutoffCode = "import sys; from pathlib import Path; import pandas as pd; src=Path(sys.argv[1]); dst=Path(sys.argv[2]); cutoff=int(sys.argv[3]); df=pd.read_parquet(src); date_col='date' if 'date' in df.columns else None; assert date_col is not None, 'date column missing'; out=df[df[date_col].astype('int64') <= cutoff].copy(); dst.parent.mkdir(parents=True, exist_ok=True); out.to_parquet(dst, index=False); print(f'wrote {len(out):,} rows to {dst} from {src} with cutoff <= {cutoff}')"
      $CutoffStepName = if ($ProductionTrain) { "Step 0B - create production training cutoff parquet" } else { "Step 0B - create March 2026 training cutoff parquet" }
      Invoke-PythonInline $CutoffStepName $CutoffCode @(
        $FullBaseDataPath,
        $TrainBaseDataPath,
        $TrainEndDate
      ) (Join-Path $ResultsRoot "00_create_cutoff.log")
    } else {
      Write-Host "`n=== Step 0B - cutoff generation skipped ===" -ForegroundColor Yellow
    }
  }

  # Step 1: train the exogenous-input JEPA market state model on the cutoff only.
  if (($skip_to_step -le 1) -and (-not $SkipJepaTrain)) {
    Assert-PathExists $TrainBaseDataPath "Training cutoff parquet"
    $JepaTrainArgs = @(
      (Join-Path $ScriptDir "train_xinput_jepa.py"),
      "--data", $TrainBaseDataPath,
      "--output-dir", $JepaFeatureModelDir,
      "--context-len", "24",
      "--horizons", "1,3,6,12,24,36",
      "--z-dim", "16",
      "--u-dim", "12",
      "--hidden-dim", "96",
      "--lambda-sigreg", "0.15",
      "--lambda-vicreg", "0.20",
      "--lambda-ce", "0.35",
      "--balanced-sampler",
      "--epochs", $JepaEpochs,
      "--batch-size", $JepaBatchSize,
      "--device", $Device
    )
    if ($ProductionTrain) {
      $JepaTrainArgs += "--final-fit-all-dates"
    }
    Invoke-PythonStep "Step 1 - train XInputJEPA market-state model" $JepaTrainArgs (Join-Path $ResultsRoot "01_train_xinput_jepa.log")
  } elseif ($skip_to_step -le 1) {
    Write-Host "`n=== Step 1 - XInputJEPA training skipped ===" -ForegroundColor Yellow
  }

  # Step 2: append frozen JEPA features to both train-cutoff and full OOS data.
  if (($skip_to_step -le 2) -and (-not $SkipAppend)) {
    Assert-PathExists $JepaFeatureNamesPath "JEPA feature-name export"
    Assert-PathExists $TrainBaseDataPath "Training cutoff parquet"
    Invoke-PythonStep "Step 2A - append XInputJEPA features to training cutoff" @(
      (Join-Path $ScriptDir "append_xinput_jepa_features.py"),
      "--data", $TrainBaseDataPath,
      "--model-dir", $JepaFeatureModelDir,
      "--output", $TrainJepaDataPath,
      "--device", $Device
    ) (Join-Path $ResultsRoot "02_append_jepa_train_cutoff.log")

    if ($ProductionTrain) {
      Write-Host "`n=== Step 2B - full backtest append skipped in ProductionTrain; production data is train data ===" -ForegroundColor Yellow
    } else {
      Assert-PathExists $FullBaseDataPath "Full base parquet"
      Invoke-PythonStep "Step 2B - append XInputJEPA features to full backtest data" @(
        (Join-Path $ScriptDir "append_xinput_jepa_features.py"),
        "--data", $FullBaseDataPath,
        "--model-dir", $JepaFeatureModelDir,
        "--output", $FullJepaDataPath,
        "--device", $Device
      ) (Join-Path $ResultsRoot "02_append_jepa_full.log")
    }
  } elseif ($skip_to_step -le 2) {
    Write-Host "`n=== Step 2 - JEPA feature append skipped ===" -ForegroundColor Yellow
  }

  # Step 3: train/backtest frozen 180m LightGBM models: base, jepa_only, base_jepa.
  if (($skip_to_step -le 3) -and (-not $SkipGbt180)) {
    Assert-PathExists $FullJepaDataPath "Full JEPA parquet"
    Assert-PathExists $JepaFeatureNamesPath "JEPA feature-name export"
    if ($ProductionTrain) {
      $Gbt180Args = @(
        (Join-Path $ScriptDir "train_180m_production.py"),
        "--data", $FullJepaDataPath,
        "--jepa-feature-names", $JepaFeatureNamesPath,
        "--output-dir", $Jepa180ResultsDir,
        "--model-dir", $Jepa180ModelDir,
        "--modes", "base", "jepa_only", "base_jepa",
        "--train-end-date", $TrainEndDate,
        "--horizon-steps", "36",
        "--truncate-eod-horizon",
        "--min-abs-bps", "0.0",
        "--val-months", "3",
        "--cost-bps", "1.0",
        "--cooldown-steps", "36",
        "--notional", "100000",
        "--min-val-trades", "4",
        "--n-estimators", $Gbt180Estimators,
        "--n-jobs", "$NJobs",
        "--seed", "777"
      )
      Invoke-PythonStep "Step 3 - train production GBT+JEPA 180m models" $Gbt180Args (Join-Path $ResultsRoot "03_train_production_gbt_jepa_180m.log")
    } else {
      $Gbt180Args = @(
        (Join-Path $ScriptDir "train_backtest_180m_frozen.py"),
        "--data", $FullJepaDataPath,
        "--jepa-feature-names", $JepaFeatureNamesPath,
        "--output-dir", $Jepa180ResultsDir,
        "--model-dir", $Jepa180ModelDir,
        "--modes", "base", "jepa_only", "base_jepa",
        "--train-end-date", $TrainEndDate,
        "--test-start-date", $TestStartDate,
        "--horizon-steps", "36",
        "--truncate-eod-horizon",
        "--min-abs-bps", "0.0",
        "--val-months", "3",
        "--cost-bps", "1.0",
        "--cooldown-steps", "36",
        "--notional", "100000",
        "--min-val-trades", "4",
        "--n-estimators", $Gbt180Estimators,
        "--n-jobs", "$NJobs",
        "--seed", "777"
      )
      if (-not [string]::IsNullOrWhiteSpace($TestEndDate)) {
        $Gbt180Args += @("--test-end-date", $TestEndDate)
      }
      Invoke-PythonStep "Step 3 - train/backtest GBT+JEPA 180m models" $Gbt180Args (Join-Path $ResultsRoot "03_train_backtest_gbt_jepa_180m.log")
    }
  } elseif ($skip_to_step -le 3) {
    Write-Host "`n=== Step 3 - GBT+JEPA 180m training skipped ===" -ForegroundColor Yellow
  }

  # Step 3B: generate walk-forward out-of-fold GBT predictions for unbiased
  # option candidate generation. Step 5 must use this parquet in research mode;
  # otherwise a frozen March-2026 model would score pre-March-2026 rows it had
  # already trained on.
  if (($skip_to_step -le 3) -and (-not $ProductionTrain) -and (-not $SkipGbtOof)) {
    Assert-PathExists $FullJepaDataPath "Full JEPA parquet"
    Assert-PathExists $JepaFeatureNamesPath "JEPA feature-name export"
    Invoke-PythonStep "Step 3B - walk-forward OOF GBT predictions" @(
      (Join-Path $ScriptDir "walkforward_gbt_oof.py"),
      "--data", $FullJepaDataPath,
      "--jepa-feature-names", $JepaFeatureNamesPath,
      "--output", $OofGbtPredictionsPath,
      "--output-dir", $Jepa180ResultsDir,
      "--mode", "base_jepa",
      "--tickers", "SPX", "QQQ", "SPY",
      "--min-train-months", "$GbtOofMinTrainMonths",
      "--val-months", "$GbtOofValMonths",
      "--horizon-steps", "36",
      "--truncate-eod-horizon",
      "--min-abs-bps", "0.0",
      "--cost-bps", "1.0",
      "--cooldown-steps", "36",
      "--notional", "100000",
      "--min-val-trades", "4",
      "--n-estimators", $Gbt180Estimators,
      "--n-jobs", "$NJobs",
      "--seed", "777"
    ) (Join-Path $ResultsRoot "03b_walkforward_gbt_oof.log")
  } elseif (($skip_to_step -le 3) -and (-not $ProductionTrain)) {
    Write-Host "`n=== Step 3B - OOF GBT predictions skipped ===" -ForegroundColor Yellow
  }

  # Step 4: run the standalone OOS backtest for the promoted base_jepa signal.
  if (($skip_to_step -le 4) -and (-not $SkipStandaloneBacktest)) {
    Assert-PathExists $FullJepaDataPath "Full JEPA parquet"
    Assert-PathExists $Jepa180ModelDir "JEPA 180m model directory"
    $StandaloneArgs = @(
      (Join-Path $ScriptDir "backtest_jepa_180m.py"),
      "--data", $FullJepaDataPath,
      "--model-dir", $Jepa180ModelDir,
      "--mode", "base_jepa",
      "--output-dir", $Jepa180StandaloneResultsDir,
      "--start-date", $TestStartDate,
      "--tickers", "SPX", "QQQ", "SPY",
      "--horizon-steps", "36",
      "--truncate-eod-horizon",
      "--cooldown-minutes", "$CooldownMinutes",
      "--cost-bps", "1.0",
      "--notional", "100000"
    )
    if (-not [string]::IsNullOrWhiteSpace($TestEndDate)) {
      $StandaloneArgs += @("--end-date", $TestEndDate)
    }
    Invoke-PythonStep "Step 4 - standalone base_jepa 180m OOS backtest" $StandaloneArgs (Join-Path $ResultsRoot "04_backtest_base_jepa_180m_standalone.log")
  } elseif ($skip_to_step -le 4) {
    Write-Host "`n=== Step 4 - standalone base_jepa backtest skipped ===" -ForegroundColor Yellow
  }

  # Step 4B: full-period base_jepa backtest for visualizer-compatible reports.
  # This is a model-history report. Rows before TestStartDate are in-sample for the
  # final frozen model; the OOS report above remains the promotion gate.
  if (($skip_to_step -le 4) -and (-not $SkipStandaloneBacktest) -and (-not $SkipFullVisualizerBacktests)) {
    Assert-PathExists $FullJepaDataPath "Full JEPA parquet"
    Assert-PathExists $Jepa180ModelDir "JEPA 180m model directory"
    $FullStandaloneArgs = @(
      (Join-Path $ScriptDir "backtest_jepa_180m.py"),
      "--data", $FullJepaDataPath,
      "--model-dir", $Jepa180ModelDir,
      "--mode", "base_jepa",
      "--output-dir", $Jepa180FullResultsDir,
      "--start-date", $StartDate,
      "--tickers", "SPX", "QQQ", "SPY",
      "--horizon-steps", "36",
      "--truncate-eod-horizon",
      "--cooldown-minutes", "$CooldownMinutes",
      "--cost-bps", "1.0",
      "--notional", "100000"
    )
    if (-not [string]::IsNullOrWhiteSpace($TestEndDate)) {
      $FullStandaloneArgs += @("--end-date", $TestEndDate)
    }
    Invoke-PythonStep "Step 4B - full-period base_jepa 180m backtest for visualizer" $FullStandaloneArgs (Join-Path $ResultsRoot "04b_backtest_base_jepa_180m_full.log")
  } elseif (($skip_to_step -le 4) -and (-not $SkipStandaloneBacktest)) {
    Write-Host "`n=== Step 4B - full-period visualizer backtest skipped ===" -ForegroundColor Yellow
  }

  # Step 4C: validate the promoted mechanical GBT+JEPA spot/proxy exit.
  # This is research/OOS evidence only. Production uses the trained 180m signal
  # plus the option execution contract in the live bot.
  if (($skip_to_step -le 4) -and (-not $SkipStandaloneBacktest) -and (-not $SkipGbtExitResearch)) {
    Assert-PathExists $FullJepaDataPath "Full JEPA parquet"
    Assert-PathExists $Jepa180ModelDir "JEPA 180m model directory"
    New-Item -ItemType Directory -Force -Path $GbtExitResearchResultsDir | Out-Null
    $GbtExitTestStartMonth = $TestStartDate.Substring(0, 6)
    $GbtExitArgs = @(
      (Join-Path $ScriptDir "walkforward_jepa_180m_continuation_exit.py"),
      "--data", $FullJepaDataPath,
      "--model-dir", $Jepa180ModelDir,
      "--mode", "base_jepa",
      "--output-dir", $GbtExitResearchResultsDir,
      "--train-start-date", $StartDate,
      "--test-start-month", $GbtExitTestStartMonth,
      "--tickers", "SPX", "QQQ", "SPY",
      "--horizon-steps", "36",
      "--truncate-eod-horizon",
      "--cooldown-minutes", "$CooldownMinutes",
      "--cost-bps", "1.0",
      "--notional", "100000",
      "--val-months", "3",
      "--min-fit-trades", "100",
      "--min-val-trades", "25",
      "--min-hold-minutes", "15",
      "--n-estimators", "160",
      "--n-jobs", "$NJobs",
      "--reuse-state-rows",
      "--skip-trailing",
      "--skip-learned",
      "--fixed-trail-stop-bps", "$GbtExitTrailStopBps",
      "--fixed-trail-activation-bps", "$GbtExitTrailActivationBps",
      "--fixed-trail-drawdown-bps", "$GbtExitTrailDrawdownBps",
      "--fixed-trail-take-profit-bps", "$GbtExitTrailTakeProfitBps"
    )
    if (-not [string]::IsNullOrWhiteSpace($TestEndDate)) {
      $GbtExitArgs += @("--test-end-month", $TestEndDate.Substring(0, 6))
    }
    Invoke-PythonStep "Step 4C - GBT+JEPA fixed trailing exit OOS check" $GbtExitArgs (Join-Path $ResultsRoot "04c_gbt_jepa_fixed_trailing_exit.log")
  } elseif (($skip_to_step -le 4) -and (-not $SkipStandaloneBacktest)) {
    Write-Host "`n=== Step 4C - GBT+JEPA exit research skipped ===" -ForegroundColor Yellow
  }

  # Step 5: build 0DTE option candidates and compare fixed delta, learned selectors, and oracle.
  if (($skip_to_step -le 5) -and (-not $SkipOptionPolicy)) {
    Assert-PathExists $FullJepaDataPath "Full JEPA parquet"
    Assert-PathExists $Jepa180ModelDir "JEPA 180m model directory"
    if (-not $ProductionTrain) {
      Assert-PathExists $OofGbtPredictionsPath "Walk-forward OOF GBT predictions"
    }
    New-Item -ItemType Directory -Force -Path $OptionPolicyResultsDir | Out-Null
    New-Item -ItemType Directory -Force -Path $OptionPolicyModelDir | Out-Null
    $OptionPolicyArgs = @(
      (Join-Path $ScriptDir "train_backtest_option_policy.py"),
      "--data", $FullJepaDataPath,
      "--signal-model-dir", $Jepa180ModelDir,
      "--signal-mode", "base_jepa",
      "--output-dir", $OptionPolicyResultsDir,
      "--model-dir", $OptionPolicyModelDir,
      "--tickers", "SPX", "QQQ", "SPY",
      "--train-start-date", $StartDate,
      "--train-end-date", $TrainEndDate,
      "--horizon-steps", "36",
      "--truncate-eod-horizon",
      "--cooldown-minutes", "$CooldownMinutes",
      "--max-hold-minutes", "$MaxHoldMinutes",
      "--risk-capital", "$RiskCapital",
      "--hard-stop-pct", "$HardStopPct",
      "--take-profit-pct", "$TakeProfitPct",
      "--min-exit-hold-minutes", "$MinExitHoldMinutes",
      "--n-estimators", $OptionPolicyTrees,
      "--exit-n-estimators", $OptionPolicyExitTrees,
      "--n-jobs", "$NJobs",
      "--max-signals", $OptionMaxSignals
    )
    if (-not [string]::IsNullOrWhiteSpace($TestStartDate)) {
      $OptionPolicyArgs += @("--test-start-date", $TestStartDate)
    }
    if (-not $ProductionTrain) {
      $OptionPolicyArgs += @("--oof-predictions", $OofGbtPredictionsPath)
    }
    if ($ProductionTrain) {
      $OptionPolicyArgs += "--labels-only"
    }
    if ($ReuseOptionCandidates) {
      $OptionPolicyArgs += "--reuse-candidates"
    }
    Invoke-PythonStep "Step 5 - train/backtest supervised 0DTE option policy" $OptionPolicyArgs (Join-Path $ResultsRoot "05_train_backtest_option_policy.log")
  } elseif ($skip_to_step -le 5) {
    Write-Host "`n=== Step 5 - 0DTE option policy skipped ===" -ForegroundColor Yellow
  }

  # Step 6: fixed train/test OptionValueJEPA split for April/May OOS diagnostics.
  if (($skip_to_step -le 6) -and (-not $SkipOptionValueSplit)) {
    Assert-PathExists $FullJepaDataPath "Full JEPA parquet"
    Assert-PathExists $CandidateLabelsPath "Option candidate labels"
    New-Item -ItemType Directory -Force -Path $OptionValueSplitResultsDir | Out-Null
    New-Item -ItemType Directory -Force -Path $OptionValueSplitModelDir | Out-Null
    $OptionValueArgs = @(
      (Join-Path $ScriptDir "train_option_value_jepa.py"),
      "--data", $FullJepaDataPath,
      "--candidate-labels", $CandidateLabelsPath,
      "--output-dir", $OptionValueSplitResultsDir,
      "--model-dir", $OptionValueSplitModelDir,
      "--train-start-date", $StartDate,
      "--train-end-date", $TrainEndDate,
      "--risk-capital", "$RiskCapital",
      "--max-hold-minutes", "$MaxHoldMinutes",
      "--hard-stop-pct", "$HardStopPct",
      "--min-exit-hold-minutes", "$MinExitHoldMinutes",
      "--epochs", $OptionValueEpochsEffective,
      "--dynamic-target", "future_edge",
      "--entry-cutoff-time", "14:30",
      "--trail-activation-pct", "0.50",
      "--trail-drawdown-pct", "0.25",
      "--trail-take-profit-pct", "10.0",
      "--blended-selector-score-base", "ovjepa_pred_rule_best_mean",
      "--blended-selector-delta-bonus", "2.0",
      "--blended-selector-min-delta", "0.0",
      "--device", $Device
    )
    if (-not [string]::IsNullOrWhiteSpace($TestStartDate)) {
      $OptionValueArgs += @("--test-start-date", $TestStartDate)
    }
    if ($ProductionTrain) {
      $OptionValueArgs += "--production-train"
    }
    if ($RebuildOptionStateRows) {
      $OptionValueArgs += "--rebuild-state-rows"
    }
    Invoke-PythonStep "Step 6 - train/backtest OptionValueJEPA fixed OOS split" $OptionValueArgs (Join-Path $ResultsRoot "06_train_option_value_jepa_split.log")
  } elseif ($skip_to_step -le 6) {
    Write-Host "`n=== Step 6 - OptionValueJEPA fixed split skipped ===" -ForegroundColor Yellow
  }

  # Step 7: monthly walk-forward OptionValueJEPA from the 2022 candidate set.
  if (($skip_to_step -le 7) -and (-not $SkipWalkForward)) {
    Assert-PathExists $FullJepaDataPath "Full JEPA parquet"
    Assert-PathExists $CandidateLabelsPath "Option candidate labels"
    New-Item -ItemType Directory -Force -Path $OptionValueWalkForwardResultsDir | Out-Null
    $WalkForwardArgs = @(
      (Join-Path $ScriptDir "walkforward_option_value_jepa.py"),
      "--data", $FullJepaDataPath,
      "--candidate-labels", $CandidateLabelsPath,
      "--output-dir", $OptionValueWalkForwardResultsDir,
      "--train-start-date", $StartDate,
      "--min-train-months", "12",
      "--risk-capital", "$RiskCapital",
      "--max-hold-minutes", "$MaxHoldMinutes",
      "--hard-stop-pct", "$HardStopPct",
      "--min-exit-hold-minutes", "$MinExitHoldMinutes",
      "--epochs", $WalkForwardEpochsEffective,
      "--production-like",
      "--val-months", "3",
      "--dynamic-target", "future_edge",
      "--entry-cutoff-time", "14:30",
      "--trail-activation-pct", "0.50",
      "--trail-drawdown-pct", "0.25",
      "--trail-take-profit-pct", "10.0",
      "--blended-selector-score-base", "ovjepa_pred_rule_best_mean",
      "--blended-selector-delta-bonus", "2.0",
      "--blended-selector-min-delta", "0.0",
      "--max-dynamic-train-rows", $MaxDynamicTrainRowsEffective,
      "--device", $Device
    )
    if (-not [string]::IsNullOrWhiteSpace($WalkForwardStartMonth)) {
      $WalkForwardArgs += @("--start-month", $WalkForwardStartMonth)
    }
    if (-not [string]::IsNullOrWhiteSpace($WalkForwardEndMonth)) {
      $WalkForwardArgs += @("--end-month", $WalkForwardEndMonth)
    }
    if ($WalkForwardMaxFolds -gt 0) {
      $WalkForwardArgs += @("--max-folds", "$WalkForwardMaxFolds")
    }
    if ($RebuildOptionStateRows) {
      $WalkForwardArgs += "--rebuild-state-rows"
    }
    Invoke-PythonStep "Step 7 - monthly OptionValueJEPA walk-forward" $WalkForwardArgs (Join-Path $ResultsRoot "07_walkforward_option_value_jepa.log")
  } elseif ($skip_to_step -le 7) {
    Write-Host "`n=== Step 7 - OptionValueJEPA walk-forward skipped ===" -ForegroundColor Yellow
  }

  # Step 7B: validate the fixed-delta option exit contract from cached 5m paths.
  if (($skip_to_step -le 7) -and (-not $SkipExitGrid)) {
    $WalkForwardStateRows = Join-Path $OptionValueWalkForwardResultsDir "option_value_state_rows.parquet"
    Assert-PathExists $CandidateLabelsPath "Option candidate labels"
    Assert-PathExists $WalkForwardStateRows "OptionValueJEPA walk-forward state rows"
    New-Item -ItemType Directory -Force -Path $FixedExitGridResultsDir | Out-Null
    Invoke-PythonStep "Step 7B - fixed 0.70 exit-contract grid" @(
      (Join-Path $ScriptDir "research_fixed_delta_exit_grid.py"),
      "--candidate-labels", $CandidateLabelsPath,
      "--state-rows", $WalkForwardStateRows,
      "--output-dir", $FixedExitGridResultsDir,
      "--fixed-delta", "0.70",
      "--meta-train-start", "202308",
      "--meta-train-end", $TrainEndDate.Substring(0, 6),
      "--oos-start", $TestStartDate.Substring(0, 6)
    ) (Join-Path $ResultsRoot "07b_fixed_delta_exit_grid.log")
  } elseif ($skip_to_step -le 7) {
    Write-Host "`n=== Step 7B - fixed-delta exit grid skipped ===" -ForegroundColor Yellow
  }

  # Step 8: existing visualizer/reporting scripts.
  if (($skip_to_step -le 8) -and (-not $SkipVisualizer)) {
    $GbtVisualizerTrades = Join-Path $Jepa180FullResultsDir "trades.csv"
    if (-not (Test-Path $GbtVisualizerTrades)) {
      $GbtVisualizerTrades = Join-Path $Jepa180StandaloneResultsDir "trades.csv"
    }

    $OptionValueVisualizerTrades = Join-Path $OptionValueWalkForwardResultsDir $OptionValueVisualizerPolicy
    if (-not (Test-Path $OptionValueVisualizerTrades)) {
      $OptionValueVisualizerTrades = Join-Path $OptionValueSplitResultsDir $OptionValueVisualizerPolicy
    }
    if (-not (Test-Path $OptionValueVisualizerTrades)) {
      $OptionValueVisualizerTrades = Join-Path $OptionValueSplitResultsDir "option_value_best_select_learned_exit_5m_trades.csv"
    }
    if (-not (Test-Path $OptionValueVisualizerTrades)) {
      $OptionValueVisualizerTrades = Join-Path $OptionPolicyResultsDir "fixed_delta_0.70_hard_trades.csv"
      Write-Host "OptionValueJEPA trades not found; falling back to fixed_delta_0.70_hard for visualizer export." -ForegroundColor Yellow
    }

    Assert-PathExists $GbtVisualizerTrades "GBT+JEPA visualizer trade CSV"
    Assert-PathExists $OptionValueVisualizerTrades "OptionValueJEPA visualizer trade CSV"
    New-Item -ItemType Directory -Force -Path $VisualizerBacktestDir | Out-Null
    New-Item -ItemType Directory -Force -Path $VisualizerAnalysisDir | Out-Null

    Invoke-PythonStep "Step 8A - export JEPA trades to backtest_rl-compatible CSVs" @(
      (Join-Path $ScriptDir "export_visualizer_backtests.py"),
      "--gbt-jepa-trades", $GbtVisualizerTrades,
      "--option-value-trades", $OptionValueVisualizerTrades,
      "--candidate-labels", $CandidateLabelsPath,
      "--output-dir", $VisualizerBacktestDir,
      "--label", $Experiment,
      "--base-balance", "10000",
      "--notional", "100000"
    ) (Join-Path $ResultsRoot "08_export_visualizer_backtests.log")

    $ManifestPath = Join-Path $VisualizerBacktestDir "latest_manifest.json"
    Assert-PathExists $ManifestPath "Visualizer export manifest"
    $Manifest = Get-Content -Raw -Path $ManifestPath | ConvertFrom-Json
    $JepaGbtCsv = [string]$Manifest.gbt_file
    $OptionValueCsv = [string]$Manifest.rl_file

    $VisualizerMonths = @("", "202601", "202602", "202603", "202604", "202605", "202503", "202504")
    foreach ($Month in $VisualizerMonths) {
      $MonthLabel = if ([string]::IsNullOrWhiteSpace($Month)) { "all" } else { $Month }
      $AnalyzeArgs = @(
        (Join-ProjectPath "visualizer\analyze_backtests.py"),
        "--mlp-file", $JepaGbtCsv,
        "--rl-file", $OptionValueCsv,
        "--training-data", $FullBaseDataPath,
        "--output-dir", $VisualizerAnalysisDir,
        "--report-prefix", $Experiment,
        "--mlp-label", "GBT+JEPA 180m",
        "--rl-label", $OptionValueVisualizerLabel
      )
      if (-not [string]::IsNullOrWhiteSpace($Month)) {
        $AnalyzeArgs += @("--month", $Month)
      }
      Invoke-PythonStep "Step 8B - visualizer analyze_backtests $MonthLabel" $AnalyzeArgs (Join-Path $ResultsRoot "08_visualizer_analyze_${MonthLabel}.log")
    }

    if ((Test-Path $FeatureVizGbtModel) -and (Test-Path $FeatureVizNormalizer)) {
      Invoke-PythonStep "Step 8C - visualizer feature report" @(
        (Join-ProjectPath "visualizer\visualize_features.py"),
        "--mode", "all",
        "--gbt-model", $FeatureVizGbtModel,
        "--normalizer", $FeatureVizNormalizer,
        "--save"
      ) (Join-Path $ResultsRoot "08_visualizer_features.log")
    } else {
      Write-Host "Skipping feature visualizer because model/normalizer are missing." -ForegroundColor Yellow
      Write-Host "  FeatureVizGbtModel  : $FeatureVizGbtModel"
      Write-Host "  FeatureVizNormalizer: $FeatureVizNormalizer"
    }
  } elseif ($skip_to_step -le 8) {
    Write-Host "`n=== Step 8 - visualizer skipped ===" -ForegroundColor Yellow
  }

  Write-Host "`n=== JEPA PIPELINE COMPLETE ===" -ForegroundColor Green
  Write-Host "Main run logs/results: $ResultsRoot"
  Write-Host "GBT+JEPA 180m results: $Jepa180ResultsDir"
  Write-Host "GBT+JEPA exit research results: $GbtExitResearchResultsDir"
  Write-Host "0DTE option-policy results: $OptionPolicyResultsDir"
  Write-Host "OptionValueJEPA walk-forward results: $OptionValueWalkForwardResultsDir"
  Exit-JepaPipeline 0
} catch {
  Write-Host "`nJEPA pipeline failed: $_" -ForegroundColor Red
  Exit-JepaPipeline 1
}
