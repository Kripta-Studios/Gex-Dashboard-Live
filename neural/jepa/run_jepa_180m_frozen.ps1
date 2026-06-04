param(
  [string]$Experiment = "jepa_180m_frozen_march",
  [double]$CostBps = 1.0,
  [double]$MinAbsBps = 0.0,
  [string]$TrainEndDate = "20260331",
  [string]$TestStartDate = "20260401",
  [string]$TestEndDate = ""
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

$DataPath = Join-Path $ProjectRoot "training_data\training_data_spx_qqq_spy_jepa_xinput_v3.parquet"
$JepaFeatureNamesPath = Join-Path $NeuralDir "models\jepa\xinput_v3\jepa_feature_names.json"
$ResultsRoot = Join-Path $ProjectRoot "research_papers\JEPA\results\$Experiment"
$ModelRoot = Join-Path $NeuralDir "models\jepa\$Experiment"

New-Item -ItemType Directory -Force -Path $ResultsRoot | Out-Null
New-Item -ItemType Directory -Force -Path $ModelRoot | Out-Null

$Args = @(
  (Join-Path $ScriptDir "train_backtest_180m_frozen.py"),
  "--data", $DataPath,
  "--jepa-feature-names", $JepaFeatureNamesPath,
  "--output-dir", $ResultsRoot,
  "--model-dir", $ModelRoot,
  "--modes", "base", "jepa_only", "base_jepa",
  "--train-end-date", $TrainEndDate,
  "--test-start-date", $TestStartDate,
  "--horizon-steps", "36",
  "--min-abs-bps", "$MinAbsBps",
  "--val-months", "3",
  "--cost-bps", "$CostBps",
  "--cooldown-steps", "36",
  "--notional", "100000",
  "--min-val-trades", "4",
  "--n-estimators", "180",
  "--n-jobs", "20",
  "--seed", "777"
)
if (-not [string]::IsNullOrWhiteSpace($TestEndDate)) {
  $Args += @("--test-end-date", $TestEndDate)
}

Invoke-PythonStep "Train/backtest frozen JEPA 180m candidate" $Args (Join-Path $ResultsRoot "01_train_backtest_frozen.log")

Write-Host "`nDone. Summary: $ResultsRoot\SUMMARY.md" -ForegroundColor Green
