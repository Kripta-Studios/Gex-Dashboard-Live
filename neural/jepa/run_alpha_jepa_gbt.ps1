param(
  [string]$Experiment = "alpha_v2",
  [switch]$QuickSmoke,
  [switch]$SkipJepaTrain,
  [switch]$SkipAppend,
  [switch]$SkipGbtTrain,
  [switch]$SkipBacktests,
  [switch]$SkipEvaluate
)

$ErrorActionPreference = "Stop"

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

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$NeuralDir = Split-Path -Parent $ScriptDir
$ProjectRoot = Split-Path -Parent $NeuralDir

$TrainingDataMarchPath = Join-Path $ProjectRoot "training_data\training_data_spx_qqq_spy_march_2026.parquet"
$BacktestDataPath = Join-Path $ProjectRoot "training_data\training_data_spx_qqq_spy.parquet"

$ResultsRoot = Join-Path $ProjectRoot "research_papers\JEPA\results\$Experiment"
$JepaModelDir = Join-Path $NeuralDir "models\jepa\$Experiment"
$JepaTrainingDataPath = Join-Path $ProjectRoot "training_data\training_data_spx_qqq_spy_march_2026_jepa_$Experiment.parquet"
$JepaBacktestDataPath = Join-Path $ProjectRoot "training_data\training_data_spx_qqq_spy_jepa_$Experiment.parquet"
$JepaFeatureNamesPath = Join-Path $JepaModelDir "jepa_feature_names.json"

$BaselineModelPath = Join-Path $NeuralDir "models\codex_exp\gbt_candidate_top2_rec1_march2026.joblib"
$BaselineNormPath = Join-Path $NeuralDir "models\codex_exp\gbt_candidate_top2_rec1_march2026_norm.npz"

$GbtJepaModelPath = Join-Path $NeuralDir "models\jepa\$Experiment\gbt_${Experiment}_base_jepa.joblib"
$GbtJepaNormPath = Join-Path $NeuralDir "models\jepa\$Experiment\gbt_${Experiment}_base_jepa_norm.npz"
$GbtJepaOnlyModelPath = Join-Path $NeuralDir "models\jepa\$Experiment\gbt_${Experiment}_jepa_only.joblib"
$GbtJepaOnlyNormPath = Join-Path $NeuralDir "models\jepa\$Experiment\gbt_${Experiment}_jepa_only_norm.npz"

$env:GBT_MIN_STRICT_WF_AVG_PF = "1.25"
$env:GBT_MIN_STRICT_WF_VALIDATION_TRADES = "12"
$env:GBT_STRICT_WF_TOP_N = "3"
$env:GBT_STRICT_WF_RECENCY_POWER = "2.0"
$env:GBT_TICKER_MIN_STRICT_WF_AVG_PF = "QQQ:1.25"
$env:GBT_TICKER_STRICT_WF_TOP_N = "QQQ:2"
$env:GBT_TICKER_STRICT_WF_RECENCY_POWER = "QQQ:0.5"
$env:DEPLOYMENT_TICKER_MAX_VIX_SPOT = "SPY:0.4108"

New-Item -ItemType Directory -Force -Path $ResultsRoot | Out-Null
New-Item -ItemType Directory -Force -Path $JepaModelDir | Out-Null

$Epochs = if ($QuickSmoke) { "1" } else { "40" }
$JepaBatch = if ($QuickSmoke) { "1024" } else { "512" }
$GbtTrainMonths = if ($QuickSmoke) { "3" } else { "12" }
$GbtTestMonths = "1"
$GbtEnsemble = if ($QuickSmoke) { "1" } else { "3" }
$GbtTopNWindows = if ($QuickSmoke) { "2" } else { "10" }
$GbtMinWindow = if ($QuickSmoke) { "0" } else { "5" }

$Tickers = @("SPX", "QQQ", "SPY")
$ObjectiveByTicker = @{
  "SPX" = "multiclass"
  "QQQ" = "binary_ovr"
  "SPY" = "binary_ovr"
}
$SampleDecayByTicker = @{
  "SPX" = "0"
  "QQQ" = "30"
  "SPY" = "30"
}
$TargetByTicker = @{
  "SPX" = "0.010"
  "QQQ" = "0.006"
  "SPY" = "0.006"
}
$StopByTicker = @{
  "SPX" = "0.0025"
  "QQQ" = "0.0025"
  "SPY" = "0.0035"
}

$CommonTrainArgs = @(
  "--model-size", "small",
  "--train-months", $GbtTrainMonths,
  "--test-months", $GbtTestMonths,
  "--ensemble", $GbtEnsemble,
  "--top-n-windows", $GbtTopNWindows,
  "--hold-ratio", "2.0",
  "--min-window", $GbtMinWindow,
  "--class-weight", "balanced",
  "--min-pf-floor", "1.20",
  "--selection-metric", "economic",
  "--min-selection-trades", "12",
  "--selection-base-confidence", "0.450",
  "--selection-cooldown", "8",
  "--min-selection-win-rate", "0.45",
  "--min-entry-minute", "580",
  "--max-time", "390",
  "--min-short-entry-minute", "615",
  "--min-short-price-vs-ib-high", "-150.0"
)

$CommonBacktestArgs = @(
  "--model-size", "small",
  "--ensemble",
  "--threshold", "0.400",
  "--cooldown", "8",
  "--max-time", "180",
  "--target_long", "0.010",
  "--target_short", "0.010",
  "--stop", "0.0025",
  "--spx-target", "0.010",
  "--etf-target", "0.006",
  "--spx-stop", "0.0025",
  "--etf-stop", "0.0030",
  "--qqq-target", "0.006",
  "--spy-target", "0.006",
  "--qqq-stop", "0.0030",
  "--spy-stop", "0.0035",
  "--risk-capital", "1000.0",
  "--min-entry-minute", "580",
  "--min-short-entry-minute", "615",
  "--min-short-price-vs-ib-high", "-150.0",
  "--tickers", "SPX", "QQQ", "SPY",
  "--strict-wf"
)

if (-not $SkipJepaTrain) {
  Invoke-PythonStep "Train AlphaJEPA v2" @(
    (Join-Path $ScriptDir "train_alpha_jepa.py"),
    "--data", $TrainingDataMarchPath,
    "--output-dir", $JepaModelDir,
    "--context-len", "24",
    "--horizons", "1,3,6,12,24,36",
    "--z-dim", "16",
    "--hidden-dim", "96",
    "--lambda-sigreg", "0.15",
    "--lambda-vicreg", "0.20",
    "--lambda-ce", "0.35",
    "--stop-gradient-target",
    "--balanced-sampler",
    "--epochs", $Epochs,
    "--batch-size", $JepaBatch,
    "--device", "cuda"
  ) (Join-Path $ResultsRoot "01_train_alpha_jepa.log")
}

if (-not $SkipAppend) {
  Invoke-PythonStep "Append AlphaJEPA features to March cutoff" @(
    (Join-Path $ScriptDir "append_alpha_jepa_features.py"),
    "--data", $TrainingDataMarchPath,
    "--model-dir", $JepaModelDir,
    "--output", $JepaTrainingDataPath,
    "--device", "cuda"
  ) (Join-Path $ResultsRoot "02_append_march.log")

  Invoke-PythonStep "Append AlphaJEPA features to full backtest data" @(
    (Join-Path $ScriptDir "append_alpha_jepa_features.py"),
    "--data", $BacktestDataPath,
    "--model-dir", $JepaModelDir,
    "--output", $JepaBacktestDataPath,
    "--device", "cuda"
  ) (Join-Path $ResultsRoot "03_append_full.log")
}

if (-not $SkipGbtTrain) {
  foreach ($Ticker in $Tickers) {
    $TrainGbtJepaArgs = @(
      (Join-Path $ScriptDir "train_walkforward_jepa.py"),
      "--data", $JepaTrainingDataPath,
      "--ticker", $Ticker,
      "--feature-mode", "base_jepa",
      "--jepa-feature-names", $JepaFeatureNamesPath,
      "--selected-feature-output", (Join-Path $JepaModelDir "selected_features_base_jepa.json")
    ) + $CommonTrainArgs + @(
      "--target-long", $TargetByTicker[$Ticker],
      "--target-short", $TargetByTicker[$Ticker],
      "--stop-pct", $StopByTicker[$Ticker],
      "--objective-mode", $ObjectiveByTicker[$Ticker],
      "--sample-weight-decay-days", $SampleDecayByTicker[$Ticker],
      "--model_path", $GbtJepaModelPath,
      "--norm_path", $GbtJepaNormPath
    )
    Invoke-PythonStep "Train GBT+AlphaJEPA $Ticker" $TrainGbtJepaArgs (Join-Path $ResultsRoot "04_train_gbt_ajepa_$Ticker.log")

    $TrainJepaOnlyArgs = @(
      (Join-Path $ScriptDir "train_walkforward_jepa.py"),
      "--data", $JepaTrainingDataPath,
      "--ticker", $Ticker,
      "--feature-mode", "jepa_only",
      "--jepa-feature-names", $JepaFeatureNamesPath,
      "--selected-feature-output", (Join-Path $JepaModelDir "selected_features_jepa_only.json")
    ) + $CommonTrainArgs + @(
      "--target-long", $TargetByTicker[$Ticker],
      "--target-short", $TargetByTicker[$Ticker],
      "--stop-pct", $StopByTicker[$Ticker],
      "--objective-mode", $ObjectiveByTicker[$Ticker],
      "--sample-weight-decay-days", $SampleDecayByTicker[$Ticker],
      "--model_path", $GbtJepaOnlyModelPath,
      "--norm_path", $GbtJepaOnlyNormPath
    )
    Invoke-PythonStep "Train AlphaJEPA-only GBT $Ticker" $TrainJepaOnlyArgs (Join-Path $ResultsRoot "05_train_gbt_ajepa_only_$Ticker.log")
  }
}

if (-not $SkipBacktests) {
  $Runs = @(
    @("baseline_gbt", $BacktestDataPath, $BaselineModelPath, $BaselineNormPath, ""),
    @("gbt_ajepa", $JepaBacktestDataPath, $GbtJepaModelPath, $GbtJepaNormPath, ""),
    @("ajepa_only", $JepaBacktestDataPath, $GbtJepaOnlyModelPath, $GbtJepaOnlyNormPath, ""),
    @("gbt_ajepa_permuted", $JepaBacktestDataPath, $GbtJepaModelPath, $GbtJepaNormPath, $JepaFeatureNamesPath)
  )
  foreach ($Run in $Runs) {
    $Label = $Run[0]
    $Data = $Run[1]
    $Model = $Run[2]
    $Norm = $Run[3]
    $Permute = $Run[4]
    $ArgsFull = @(
      (Join-Path $ScriptDir "run_gbt_backtest.py"),
      "--data", $Data,
      "--model", $Model,
      "--normalizer", $Norm,
      "--output-dir", $ResultsRoot,
      "--label", $Label
    )
    if (-not [string]::IsNullOrWhiteSpace($Permute)) {
      $ArgsFull += @("--permute-feature-names", $Permute, "--permute-seed", "123")
    }
    $ArgsFull = $ArgsFull + $CommonBacktestArgs
    Invoke-PythonStep "Backtest $Label full" $ArgsFull (Join-Path $ResultsRoot "06_backtest_${Label}.log")

    $ArgsOos = @(
      (Join-Path $ScriptDir "run_gbt_backtest.py"),
      "--data", $Data,
      "--model", $Model,
      "--normalizer", $Norm,
      "--output-dir", $ResultsRoot,
      "--label", "${Label}_oos",
      "--start-date", "20260401"
    )
    if (-not [string]::IsNullOrWhiteSpace($Permute)) {
      $ArgsOos += @("--permute-feature-names", $Permute, "--permute-seed", "123")
    }
    $ArgsOos = $ArgsOos + $CommonBacktestArgs
    Invoke-PythonStep "Backtest $Label OOS Apr-May" $ArgsOos (Join-Path $ResultsRoot "07_backtest_${Label}_oos.log")
  }
}

if (-not $SkipEvaluate) {
  Invoke-PythonStep "Evaluate AlphaJEPA full alpha" @(
    (Join-Path $ScriptDir "evaluate_jepa_alpha.py"),
    "--baseline", (Join-Path $ResultsRoot "baseline_gbt_metrics.json"),
    "--jepa", (Join-Path $ResultsRoot "gbt_ajepa_metrics.json"),
    "--jepa-only", (Join-Path $ResultsRoot "ajepa_only_metrics.json"),
    "--jepa-permuted", (Join-Path $ResultsRoot "gbt_ajepa_permuted_metrics.json"),
    "--output-md", (Join-Path $ResultsRoot "alpha_report.md"),
    "--output-json", (Join-Path $ResultsRoot "alpha_report.json")
  ) (Join-Path $ResultsRoot "08_evaluate_alpha_full.log")

  Invoke-PythonStep "Evaluate AlphaJEPA OOS alpha" @(
    (Join-Path $ScriptDir "evaluate_jepa_alpha.py"),
    "--baseline", (Join-Path $ResultsRoot "baseline_gbt_oos_metrics.json"),
    "--jepa", (Join-Path $ResultsRoot "gbt_ajepa_oos_metrics.json"),
    "--jepa-only", (Join-Path $ResultsRoot "ajepa_only_oos_metrics.json"),
    "--jepa-permuted", (Join-Path $ResultsRoot "gbt_ajepa_permuted_oos_metrics.json"),
    "--output-md", (Join-Path $ResultsRoot "alpha_report_oos.md"),
    "--output-json", (Join-Path $ResultsRoot "alpha_report_oos.json")
  ) (Join-Path $ResultsRoot "09_evaluate_alpha_oos.log")

  Invoke-PythonStep "Diagnose AlphaJEPA feature usage" @(
    (Join-Path $ScriptDir "diagnose_jepa_features.py"),
    "--model-base", $GbtJepaModelPath,
    "--normalizer-base", $GbtJepaNormPath,
    "--jepa-feature-names", $JepaFeatureNamesPath,
    "--output-json", (Join-Path $ResultsRoot "jepa_feature_usage.json"),
    "--output-md", (Join-Path $ResultsRoot "jepa_feature_usage.md")
  ) (Join-Path $ResultsRoot "10_diagnose_feature_usage.log")
}

Write-Host "`nAlphaJEPA GBT research run complete: $ResultsRoot" -ForegroundColor Green

