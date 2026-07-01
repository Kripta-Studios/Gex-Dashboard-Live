Param(
  [string]$StartMonth = "202205",
  [string]$EndMonth = "202312",
  [string]$OutputTag = "2022_2023",
  [string[]]$Variants = @("d80", "d65win", "d65ret", "d50ret", "d80_zero", "d80_front"),
  [int]$Workers = 32
)

$ErrorActionPreference = "Stop"
$env:PYTHONUNBUFFERED = "1"

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$NeuralRoot = Split-Path -Parent $ScriptDir
$ProjectRoot = Split-Path -Parent $NeuralRoot
$ResultsRoot = Join-Path $ProjectRoot "research_papers\JEPA\results"
$DataPath = Join-Path $ResultsRoot "event_option_dataset_full20_spxstandard_2022_2026_v1_physics_combined\event_option_dataset.parquet"

if (-not (Test-Path $DataPath)) {
  throw "Event option dataset not found: $DataPath"
}

$TrainTickers = @(
  "AAPL", "AMZN", "GLD", "GOOGL", "HOOD", "IWM", "META", "MSFT", "NFLX", "NVDA",
  "PLTR", "QQQ", "SLV", "SPX", "SPXW", "SPY", "TLT", "TSLA", "UNH", "VIX"
)

function Invoke-Variant {
  param(
    [string]$Name,
    [int]$DeltaBucket,
    [string]$LabelMode,
    [double[]]$ThresholdGrid,
    [string[]]$ExpiryModes = @()
  )

  $OutputDir = Join-Path $ResultsRoot "event_option_gate_full20_physics_pooled_$($OutputTag)_$($Name)_v1"
  $Args = @(
    (Join-Path $ScriptDir "walkforward_event_option_gate.py"),
    "--data", $DataPath,
    "--output-dir", $OutputDir,
    "--tickers", "SPXW", "SPY", "QQQ",
    "--train-tickers"
  ) + $TrainTickers + @(
    "--start-month", $StartMonth,
    "--end-month", $EndMonth,
    "--val-months", "3",
    "--pooled-train",
    "--delta-bucket", [string]$DeltaBucket,
    "--label-mode", $LabelMode,
    "--clip-return", "2.0",
    "--min-train-rows", "500",
    "--min-val-rows", "30",
    "--min-val-trades", "54",
    "--min-month-trades", "18",
    "--min-val-pf", "1.0",
    "--min-val-win-rate", "0.45",
    "--min-call-rate", "0.05",
    "--max-call-rate", "0.95",
    "--cooldown-minutes", "30",
    "--objective", "regression_l1",
    "--n-estimators", "260",
    "--learning-rate", "0.035",
    "--num-leaves", "31",
    "--min-child-samples", "100",
    "--subsample", "0.85",
    "--colsample-bytree", "0.85",
    "--reg-lambda", "8.0",
    "--lgb-jobs", [string]$Workers,
    "--threshold-grid"
  ) + ($ThresholdGrid | ForEach-Object { [string]$_ }) + @(
    "--threshold-quantiles", "0.2", "0.3", "0.4", "0.5", "0.6", "0.7", "0.8", "0.9",
    "--max-day-grid", "999", "8", "4", "2", "1",
    "--resume",
    "--seed", "20260617"
  )

  if ($ExpiryModes.Count -gt 0) {
    $Args += @("--expiry-modes") + $ExpiryModes
  }

  Write-Host "`n=== Build $Name $StartMonth-$EndMonth ===" -ForegroundColor Cyan
  & python @Args
  if ($LASTEXITCODE -ne 0) {
    throw "Variant build failed: $Name (exit $LASTEXITCODE)"
  }
}

$ReturnThresholds = @(-0.1, -0.05, 0.0, 0.05, 0.1, 0.15, 0.2, 0.25)
$WinThresholds = @(0.5, 0.52, 0.55, 0.58, 0.6, 0.62, 0.65, 0.68, 0.7)

foreach ($Variant in $Variants) {
  switch ($Variant) {
    "d80" {
      Invoke-Variant -Name "d80_return_fullgrid_call05_minmonth18" -DeltaBucket 80 -LabelMode "return" -ThresholdGrid $ReturnThresholds
    }
    "d65win" {
      Invoke-Variant -Name "d65_win_fullgrid_call05_minmonth18" -DeltaBucket 65 -LabelMode "win" -ThresholdGrid $WinThresholds
    }
    "d65ret" {
      Invoke-Variant -Name "d65_return_minmonth18" -DeltaBucket 65 -LabelMode "return" -ThresholdGrid $ReturnThresholds
    }
    "d50ret" {
      Invoke-Variant -Name "d50_return_minmonth18" -DeltaBucket 50 -LabelMode "return" -ThresholdGrid $ReturnThresholds
    }
    "d80_zero" {
      Invoke-Variant -Name "d80_return_zero_dte_minmonth18" -DeltaBucket 80 -LabelMode "return" -ThresholdGrid $ReturnThresholds -ExpiryModes @("zero_dte")
    }
    "d80_front" {
      Invoke-Variant -Name "d80_return_front_weekly_minmonth18" -DeltaBucket 80 -LabelMode "return" -ThresholdGrid $ReturnThresholds -ExpiryModes @("front_weekly")
    }
    default {
      throw "Unknown variant: $Variant"
    }
  }
}
