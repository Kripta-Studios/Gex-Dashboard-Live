# run_option_value_jepa.ps1
# Isolated OptionValueJEPA experiment for 0DTE strike/delta selection and 5m learned exits.

Param(
  [string]$DataPath = "",
  [string]$CandidateLabels = "",
  [string]$OutputDir = "",
  [string]$ModelDir = "",
  [string]$TrainStartDate = "20250101",
  [string]$TrainEndDate = "20260331",
  [string]$TestStartDate = "20260401",
  [int]$Epochs = 35,
  [int]$MaxHoldMinutes = 180,
  [double]$RiskCapital = 1000.0,
  [double]$HardStopPct = -0.60,
  [int]$MinExitHoldMinutes = 15,
  [switch]$RebuildStateRows,
  [string]$Device = ""
)

$ErrorActionPreference = "Stop"
$ScriptDir = Split-Path $MyInvocation.MyCommand.Path -Parent
$NeuralRoot = Split-Path $ScriptDir -Parent
$ProjectRoot = Split-Path $NeuralRoot -Parent

if ([string]::IsNullOrWhiteSpace($DataPath)) {
  $DataPath = Join-Path $ProjectRoot "training_data\training_data_spx_qqq_spy_jepa_xinput_v3.parquet"
}
if ([string]::IsNullOrWhiteSpace($CandidateLabels)) {
  $CandidateLabels = Join-Path $ProjectRoot "research_papers\JEPA\results\jepa_option_policy\candidate_labels.parquet"
}
if ([string]::IsNullOrWhiteSpace($OutputDir)) {
  $OutputDir = Join-Path $ProjectRoot "research_papers\JEPA\results\option_value_jepa"
}
if ([string]::IsNullOrWhiteSpace($ModelDir)) {
  $ModelDir = Join-Path $NeuralRoot "models\jepa\option_value_jepa_frozen_march"
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

Write-Host "`n=== OPTION VALUE JEPA 0DTE ===" -ForegroundColor Magenta
Write-Host "DataPath          : $DataPath"
Write-Host "CandidateLabels   : $CandidateLabels"
Write-Host "OutputDir         : $OutputDir"
Write-Host "ModelDir          : $ModelDir"
Write-Host "TrainStartDate    : $TrainStartDate"
Write-Host "TrainEndDate      : $TrainEndDate"
Write-Host "TestStartDate     : $TestStartDate"
Write-Host "Epochs            : $Epochs"
Write-Host "RebuildStateRows  : $RebuildStateRows"

$ExtraArgs = @()
if ($RebuildStateRows) {
  $ExtraArgs += "--rebuild-state-rows"
}
if (-not [string]::IsNullOrWhiteSpace($Device)) {
  $ExtraArgs += @("--device", $Device)
}

python -u (Join-Path $NeuralRoot "jepa\train_option_value_jepa.py") `
  --data $DataPath `
  --candidate-labels $CandidateLabels `
  --output-dir $OutputDir `
  --model-dir $ModelDir `
  --train-start-date $TrainStartDate `
  --train-end-date $TrainEndDate `
  --test-start-date $TestStartDate `
  --epochs $Epochs `
  --max-hold-minutes $MaxHoldMinutes `
  --risk-capital $RiskCapital `
  --hard-stop-pct $HardStopPct `
  --min-exit-hold-minutes $MinExitHoldMinutes `
  @ExtraArgs

if ($LASTEXITCODE -ne 0) {
  throw "OptionValueJEPA experiment failed with exit code $LASTEXITCODE"
}

Write-Host "`n=== OPTION VALUE JEPA COMPLETE ===" -ForegroundColor Green
