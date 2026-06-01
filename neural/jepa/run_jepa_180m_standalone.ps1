param(
  [string]$Experiment = "jepa_180m_standalone",
  [string]$Mode = "base_jepa",
  [int]$CooldownMinutes = 180,
  [double]$CostBps = 1.0,
  [string]$StartDate = "20260401",
  [string]$EndDate = ""
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
$ModelRoot = Join-Path $NeuralDir "models\jepa\jepa_180m_frozen_march"
$ResultsRoot = Join-Path $ProjectRoot "research_papers\JEPA\results\$Experiment"

New-Item -ItemType Directory -Force -Path $ResultsRoot | Out-Null

$Args = @(
  (Join-Path $ScriptDir "backtest_jepa_180m.py"),
  "--data", $DataPath,
  "--model-dir", $ModelRoot,
  "--mode", $Mode,
  "--output-dir", $ResultsRoot,
  "--start-date", $StartDate,
  "--tickers", "SPX", "QQQ", "SPY",
  "--horizon-steps", "36",
  "--cooldown-minutes", "$CooldownMinutes",
  "--cost-bps", "$CostBps",
  "--notional", "100000"
)
if (-not [string]::IsNullOrWhiteSpace($EndDate)) {
  $Args += @("--end-date", $EndDate)
}

Invoke-PythonStep "Backtest JEPA 180m standalone" $Args (Join-Path $ResultsRoot "01_backtest_jepa_180m.log")

Write-Host "`nDone. Summary: $ResultsRoot\SUMMARY.md" -ForegroundColor Green
