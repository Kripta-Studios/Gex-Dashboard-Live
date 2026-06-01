# run_option_value_jepa_walkforward.ps1
# Monthly walk-forward OptionValueJEPA experiment.

Param(
  [string]$DataPath = "",
  [string]$CandidateLabels = "",
  [string]$OutputDir = "",
  [string]$TrainStartDate = "20220801",
  [int]$MinTrainMonths = 12,
  [string]$StartMonth = "",
  [string]$EndMonth = "",
  [int]$MaxFolds = 0,
  [int]$Epochs = 8,
  [int]$MaxDynamicTrainRows = 260000,
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
  $CandidateLabels = Join-Path $ProjectRoot "research_papers\JEPA\results\jepa_option_policy_2022\candidate_labels.parquet"
}
if ([string]::IsNullOrWhiteSpace($OutputDir)) {
  $OutputDir = Join-Path $ProjectRoot "research_papers\JEPA\results\option_value_jepa_2022_walkforward"
}

$PathSeparator = [System.IO.Path]::PathSeparator
$PythonPathParts = @($NeuralRoot, $ProjectRoot)
if (-not [string]::IsNullOrWhiteSpace($env:PYTHONPATH)) {
  $PythonPathParts += $env:PYTHONPATH
}
$env:PYTHONPATH = ($PythonPathParts -join $PathSeparator)
$env:PYTHONUNBUFFERED = "1"

New-Item -ItemType Directory -Force -Path $OutputDir | Out-Null

Write-Host "`n=== OPTION VALUE JEPA WALK-FORWARD ===" -ForegroundColor Magenta
Write-Host "DataPath            : $DataPath"
Write-Host "CandidateLabels     : $CandidateLabels"
Write-Host "OutputDir           : $OutputDir"
Write-Host "TrainStartDate      : $TrainStartDate"
Write-Host "MinTrainMonths      : $MinTrainMonths"
Write-Host "StartMonth          : $StartMonth"
Write-Host "EndMonth            : $EndMonth"
Write-Host "MaxFolds            : $MaxFolds"
Write-Host "Epochs              : $Epochs"
Write-Host "MaxDynamicTrainRows : $MaxDynamicTrainRows"

$ExtraArgs = @()
if ($RebuildStateRows) {
  $ExtraArgs += "--rebuild-state-rows"
}
if (-not [string]::IsNullOrWhiteSpace($StartMonth)) {
  $ExtraArgs += @("--start-month", $StartMonth)
}
if (-not [string]::IsNullOrWhiteSpace($EndMonth)) {
  $ExtraArgs += @("--end-month", $EndMonth)
}
if ($MaxFolds -gt 0) {
  $ExtraArgs += @("--max-folds", "$MaxFolds")
}
if (-not [string]::IsNullOrWhiteSpace($Device)) {
  $ExtraArgs += @("--device", $Device)
}

python -u (Join-Path $NeuralRoot "jepa\walkforward_option_value_jepa.py") `
  --data $DataPath `
  --candidate-labels $CandidateLabels `
  --output-dir $OutputDir `
  --train-start-date $TrainStartDate `
  --min-train-months $MinTrainMonths `
  --epochs $Epochs `
  --max-dynamic-train-rows $MaxDynamicTrainRows `
  @ExtraArgs

if ($LASTEXITCODE -ne 0) {
  throw "OptionValueJEPA walk-forward failed with exit code $LASTEXITCODE"
}

Write-Host "`n=== OPTION VALUE JEPA WALK-FORWARD COMPLETE ===" -ForegroundColor Green
