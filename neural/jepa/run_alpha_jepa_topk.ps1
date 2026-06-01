param(
  [string]$Experiment = "alpha_v2",
  [string]$Candidate = "alpha_v2_topk8"
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

$TrainingDataPath = Join-Path $ProjectRoot "training_data\training_data_spx_qqq_spy_march_2026_jepa_$Experiment.parquet"
$BacktestDataPath = Join-Path $ProjectRoot "training_data\training_data_spx_qqq_spy_jepa_$Experiment.parquet"
$BaselineDataPath = Join-Path $ProjectRoot "training_data\training_data_spx_qqq_spy.parquet"
$ResultsRoot = Join-Path $ProjectRoot "research_papers\JEPA\results\$Candidate"
$SourceResultsRoot = Join-Path $ProjectRoot "research_papers\JEPA\results\$Experiment"
$JepaModelDir = Join-Path $NeuralDir "models\jepa\$Experiment"
$TopSelectedPath = Join-Path $JepaModelDir "selected_features_topk8.json"
$TopJepaPath = Join-Path $JepaModelDir "topk8_jepa_feature_names.json"

$ModelPath = Join-Path $NeuralDir "models\jepa\$Candidate\gbt_${Candidate}.joblib"
$NormPath = Join-Path $NeuralDir "models\jepa\$Candidate\gbt_${Candidate}_norm.npz"
$BaselineModelPath = Join-Path $NeuralDir "models\codex_exp\gbt_candidate_top2_rec1_march2026.joblib"
$BaselineNormPath = Join-Path $NeuralDir "models\codex_exp\gbt_candidate_top2_rec1_march2026_norm.npz"
$JepaOnlyModelPath = Join-Path $NeuralDir "models\jepa\$Experiment\gbt_${Experiment}_jepa_only.joblib"
$JepaOnlyNormPath = Join-Path $NeuralDir "models\jepa\$Experiment\gbt_${Experiment}_jepa_only_norm.npz"

$env:GBT_MIN_STRICT_WF_AVG_PF = "1.25"
$env:GBT_MIN_STRICT_WF_VALIDATION_TRADES = "12"
$env:GBT_STRICT_WF_TOP_N = "3"
$env:GBT_STRICT_WF_RECENCY_POWER = "2.0"
$env:GBT_TICKER_MIN_STRICT_WF_AVG_PF = "QQQ:1.25"
$env:GBT_TICKER_STRICT_WF_TOP_N = "QQQ:2"
$env:GBT_TICKER_STRICT_WF_RECENCY_POWER = "QQQ:0.5"
$env:DEPLOYMENT_TICKER_MAX_VIX_SPOT = "SPY:0.4108"

New-Item -ItemType Directory -Force -Path $ResultsRoot | Out-Null
New-Item -ItemType Directory -Force -Path (Split-Path $ModelPath) | Out-Null

$Tickers = @("SPX", "QQQ", "SPY")
$ObjectiveByTicker = @{ "SPX" = "multiclass"; "QQQ" = "binary_ovr"; "SPY" = "binary_ovr" }
$SampleDecayByTicker = @{ "SPX" = "0"; "QQQ" = "30"; "SPY" = "30" }
$TargetByTicker = @{ "SPX" = "0.010"; "QQQ" = "0.006"; "SPY" = "0.006" }
$StopByTicker = @{ "SPX" = "0.0025"; "QQQ" = "0.0025"; "SPY" = "0.0035" }

$CommonTrainArgs = @(
  "--model-size", "small", "--train-months", "12", "--test-months", "1",
  "--ensemble", "3", "--top-n-windows", "10", "--hold-ratio", "2.0",
  "--min-window", "5", "--class-weight", "balanced", "--min-pf-floor", "1.20",
  "--selection-metric", "economic", "--min-selection-trades", "12",
  "--selection-base-confidence", "0.450", "--selection-cooldown", "8",
  "--min-selection-win-rate", "0.45", "--min-entry-minute", "580",
  "--max-time", "390", "--min-short-entry-minute", "615",
  "--min-short-price-vs-ib-high", "-150.0"
)
$CommonBacktestArgs = @(
  "--model-size", "small", "--ensemble", "--threshold", "0.400",
  "--cooldown", "8", "--max-time", "180", "--target_long", "0.010",
  "--target_short", "0.010", "--stop", "0.0025", "--spx-target", "0.010",
  "--etf-target", "0.006", "--spx-stop", "0.0025", "--etf-stop", "0.0030",
  "--qqq-target", "0.006", "--spy-target", "0.006", "--qqq-stop", "0.0030",
  "--spy-stop", "0.0035", "--risk-capital", "1000.0",
  "--min-entry-minute", "580", "--min-short-entry-minute", "615",
  "--min-short-price-vs-ib-high", "-150.0", "--tickers", "SPX", "QQQ", "SPY",
  "--strict-wf"
)

Invoke-PythonStep "Select Top-K AlphaJEPA features" @(
  (Join-Path $ScriptDir "select_top_jepa_features.py"),
  "--data", $TrainingDataPath,
  "--usage-json", (Join-Path $SourceResultsRoot "jepa_feature_usage.json"),
  "--top-k-per-ticker", "8",
  "--selected-output", $TopSelectedPath,
  "--top-jepa-output", $TopJepaPath
) (Join-Path $ResultsRoot "01_select_topk.log")

foreach ($Ticker in $Tickers) {
  $ArgsTrain = @(
    (Join-Path $ScriptDir "train_walkforward_jepa.py"),
    "--data", $TrainingDataPath,
    "--ticker", $Ticker,
    "--feature-mode", "custom",
    "--custom-feature-names", $TopSelectedPath
  ) + $CommonTrainArgs + @(
    "--target-long", $TargetByTicker[$Ticker],
    "--target-short", $TargetByTicker[$Ticker],
    "--stop-pct", $StopByTicker[$Ticker],
    "--objective-mode", $ObjectiveByTicker[$Ticker],
    "--sample-weight-decay-days", $SampleDecayByTicker[$Ticker],
    "--model_path", $ModelPath,
    "--norm_path", $NormPath
  )
  Invoke-PythonStep "Train GBT+TopK AlphaJEPA $Ticker" $ArgsTrain (Join-Path $ResultsRoot "02_train_topk_$Ticker.log")
}

$Runs = @(
  @("baseline_gbt", $BaselineDataPath, $BaselineModelPath, $BaselineNormPath, ""),
  @("gbt_ajepa_topk", $BacktestDataPath, $ModelPath, $NormPath, ""),
  @("ajepa_only", $BacktestDataPath, $JepaOnlyModelPath, $JepaOnlyNormPath, ""),
  @("gbt_ajepa_topk_permuted", $BacktestDataPath, $ModelPath, $NormPath, $TopJepaPath)
)
foreach ($Run in $Runs) {
  $Label = $Run[0]
  $Data = $Run[1]
  $Model = $Run[2]
  $Norm = $Run[3]
  $Permute = $Run[4]
  $ArgsFull = @(
    (Join-Path $ScriptDir "run_gbt_backtest.py"),
    "--data", $Data, "--model", $Model, "--normalizer", $Norm,
    "--output-dir", $ResultsRoot, "--label", $Label
  )
  if (-not [string]::IsNullOrWhiteSpace($Permute)) {
    $ArgsFull += @("--permute-feature-names", $Permute, "--permute-seed", "123")
  }
  Invoke-PythonStep "Backtest $Label full" ($ArgsFull + $CommonBacktestArgs) (Join-Path $ResultsRoot "03_backtest_${Label}.log")

  $ArgsOos = @(
    (Join-Path $ScriptDir "run_gbt_backtest.py"),
    "--data", $Data, "--model", $Model, "--normalizer", $Norm,
    "--output-dir", $ResultsRoot, "--label", "${Label}_oos",
    "--start-date", "20260401"
  )
  if (-not [string]::IsNullOrWhiteSpace($Permute)) {
    $ArgsOos += @("--permute-feature-names", $Permute, "--permute-seed", "123")
  }
  Invoke-PythonStep "Backtest $Label OOS" ($ArgsOos + $CommonBacktestArgs) (Join-Path $ResultsRoot "04_backtest_${Label}_oos.log")
}

Invoke-PythonStep "Evaluate TopK AlphaJEPA full" @(
  (Join-Path $ScriptDir "evaluate_jepa_alpha.py"),
  "--baseline", (Join-Path $ResultsRoot "baseline_gbt_metrics.json"),
  "--jepa", (Join-Path $ResultsRoot "gbt_ajepa_topk_metrics.json"),
  "--jepa-only", (Join-Path $ResultsRoot "ajepa_only_metrics.json"),
  "--jepa-permuted", (Join-Path $ResultsRoot "gbt_ajepa_topk_permuted_metrics.json"),
  "--output-md", (Join-Path $ResultsRoot "alpha_report.md"),
  "--output-json", (Join-Path $ResultsRoot "alpha_report.json")
) (Join-Path $ResultsRoot "05_evaluate_full.log")

Invoke-PythonStep "Evaluate TopK AlphaJEPA OOS" @(
  (Join-Path $ScriptDir "evaluate_jepa_alpha.py"),
  "--baseline", (Join-Path $ResultsRoot "baseline_gbt_oos_metrics.json"),
  "--jepa", (Join-Path $ResultsRoot "gbt_ajepa_topk_oos_metrics.json"),
  "--jepa-only", (Join-Path $ResultsRoot "ajepa_only_oos_metrics.json"),
  "--jepa-permuted", (Join-Path $ResultsRoot "gbt_ajepa_topk_permuted_oos_metrics.json"),
  "--output-md", (Join-Path $ResultsRoot "alpha_report_oos.md"),
  "--output-json", (Join-Path $ResultsRoot "alpha_report_oos.json")
) (Join-Path $ResultsRoot "06_evaluate_oos.log")

Invoke-PythonStep "Diagnose TopK AlphaJEPA feature usage" @(
  (Join-Path $ScriptDir "diagnose_jepa_features.py"),
  "--model-base", $ModelPath,
  "--normalizer-base", $NormPath,
  "--jepa-feature-names", $TopJepaPath,
  "--output-json", (Join-Path $ResultsRoot "jepa_feature_usage.json"),
  "--output-md", (Join-Path $ResultsRoot "jepa_feature_usage.md")
) (Join-Path $ResultsRoot "07_diagnose_feature_usage.log")

Write-Host "`nTopK AlphaJEPA run complete: $ResultsRoot" -ForegroundColor Green

