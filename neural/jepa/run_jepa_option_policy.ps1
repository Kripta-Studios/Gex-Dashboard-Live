# run_jepa_option_policy.ps1
# Isolated supervised JEPA 0DTE option-policy experiment.

Param(
  [string]$DataPath = "",
  [string]$SignalModelDir = "",
  [string]$OutputDir = "",
  [string]$ModelDir = "",
  [string]$TrainStartDate = "20250101",
  [string]$TrainEndDate = "20260331",
  [string]$TestStartDate = "20260401",
  [int]$CooldownMinutes = 180,
  [int]$MaxHoldMinutes = 180,
  [double]$RiskCapital = 1000.0,
  [double]$HardStopPct = -0.60,
  [double]$TakeProfitPct = 2.50,
  [int]$MinExitHoldMinutes = 15,
  [int]$NEstimators = 180,
  [int]$ExitNEstimators = 100,
  [int]$NJobs = 20,
  [switch]$ReuseCandidates
)

$ErrorActionPreference = "Stop"
$ScriptDir = Split-Path $MyInvocation.MyCommand.Path -Parent
$NeuralRoot = Split-Path $ScriptDir -Parent
$ProjectRoot = Split-Path $NeuralRoot -Parent

if ([string]::IsNullOrWhiteSpace($DataPath)) {
  $DataPath = Join-Path $ProjectRoot "training_data\training_data_spx_qqq_spy_jepa_xinput_v3.parquet"
}
if ([string]::IsNullOrWhiteSpace($SignalModelDir)) {
  $SignalModelDir = Join-Path $NeuralRoot "models\jepa\jepa_180m_frozen_march"
}
if ([string]::IsNullOrWhiteSpace($OutputDir)) {
  $OutputDir = Join-Path $ProjectRoot "research_papers\JEPA\results\jepa_option_policy"
}
if ([string]::IsNullOrWhiteSpace($ModelDir)) {
  $ModelDir = Join-Path $NeuralRoot "models\jepa\jepa_option_policy_frozen_march"
}

$PathSeparator = [System.IO.Path]::PathSeparator
$PythonPathParts = @($NeuralRoot, $ProjectRoot)
if (-not [string]::IsNullOrWhiteSpace($env:PYTHONPATH)) {
  $PythonPathParts += $env:PYTHONPATH
}
$env:PYTHONPATH = ($PythonPathParts -join $PathSeparator)
$env:PYTHONUNBUFFERED = "1"

New-Item -ItemType Directory -Force -Path $OutputDir | Out-Null
New-Item -ItemType Directory -Force -Path $ModelDir | Out-Null

Write-Host "`n=== JEPA SUPERVISED 0DTE OPTION POLICY ===" -ForegroundColor Magenta
Write-Host "DataPath        : $DataPath"
Write-Host "SignalModelDir  : $SignalModelDir"
Write-Host "OutputDir       : $OutputDir"
Write-Host "ModelDir        : $ModelDir"
Write-Host "TrainStartDate  : $TrainStartDate"
Write-Host "TrainEndDate    : $TrainEndDate"
Write-Host "TestStartDate   : $TestStartDate"
Write-Host "CooldownMinutes : $CooldownMinutes"
Write-Host "MaxHoldMinutes  : $MaxHoldMinutes"
Write-Host "RiskCapital     : $RiskCapital"
Write-Host "NJobs           : $NJobs"
Write-Host "ReuseCandidates : $ReuseCandidates"

$ExtraArgs = @()
if ($ReuseCandidates) {
  $ExtraArgs += "--reuse-candidates"
}

python -u (Join-Path $NeuralRoot "jepa\train_backtest_option_policy.py") `
  --data $DataPath `
  --signal-model-dir $SignalModelDir `
  --signal-mode base_jepa `
  --output-dir $OutputDir `
  --model-dir $ModelDir `
  --tickers SPX QQQ SPY `
  --train-start-date $TrainStartDate `
  --train-end-date $TrainEndDate `
  --test-start-date $TestStartDate `
  --cooldown-minutes $CooldownMinutes `
  --max-hold-minutes $MaxHoldMinutes `
  --risk-capital $RiskCapital `
  --hard-stop-pct $HardStopPct `
  --take-profit-pct $TakeProfitPct `
  --min-exit-hold-minutes $MinExitHoldMinutes `
  --n-estimators $NEstimators `
  --exit-n-estimators $ExitNEstimators `
  --n-jobs $NJobs `
  @ExtraArgs

if ($LASTEXITCODE -ne 0) {
  throw "JEPA option-policy experiment failed with exit code $LASTEXITCODE"
}

Write-Host "`n=== JEPA OPTION POLICY COMPLETE ===" -ForegroundColor Green
