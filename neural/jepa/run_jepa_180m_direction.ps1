param(
  [string]$Experiment = "jepa_180m_direction",
  [double]$CostBps = 1.0,
  [double]$MinAbsBps = 0.0,
  [string]$TestStartMonth = "202604",
  [string]$TestEndMonth = ""
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

New-Item -ItemType Directory -Force -Path $ResultsRoot | Out-Null

Invoke-PythonStep "Evaluate JEPA 180m direction" @(
  (Join-Path $ScriptDir "evaluate_180m_direction.py"),
  "--data", $DataPath,
  "--jepa-feature-names", $JepaFeatureNamesPath,
  "--output-dir", $ResultsRoot,
  "--modes", "base", "jepa_only", "base_jepa",
  "--horizon-steps", "36",
  "--min-abs-bps", "$MinAbsBps",
  "--min-train-months", "12",
  "--val-months", "3",
  "--cost-bps", "$CostBps",
  "--cooldown-steps", "36",
  "--notional", "100000",
  "--min-val-trades", "4",
  "--oos-start", "20260401",
  "--n-estimators", "160",
  "--n-jobs", "1",
  "--test-start-month", $TestStartMonth,
  "--seed", "777"
) (Join-Path $ResultsRoot "01_evaluate_180m_direction.log")

Write-Host "`nDone. Summary: $ResultsRoot\SUMMARY.md" -ForegroundColor Green
