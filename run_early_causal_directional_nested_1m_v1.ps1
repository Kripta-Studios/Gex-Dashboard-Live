$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$root = $PSScriptRoot
Set-Location -LiteralPath $root
$env:PYTHONPATH = "."
$env:PYTHONHASHSEED = "20260618"
$env:OMP_NUM_THREADS = "28"
$env:MKL_NUM_THREADS = "28"

$data = "tmp/event_option_dataset_execquote_causal1000_noib_early_1m_202201_202605_v2_physics/event_option_dataset.parquet"
$buildSummary = "tmp/event_option_dataset_execquote_causal1000_noib_early_1m_202201_202605_v2/SUMMARY.json"
$selector = "neural/jepa/walkforward_event_option_profile_selector.py"
$auditor = "neural/jepa/audit_early_causal_option_dataset.py"
$selectorTest = "tests/test_walkforward_event_option_profile_selector.py"
$causalityTest = "tests/test_event_option_live_causality.py"
$result = "research_papers/JEPA/results/_diagnostics/early_causal_directional_nested_1m_202601_202605_seed20260618_v1"

$expectedHashes = @{
    $data = "804BF0CC98576351126926C2B6A3C0DB1A195E9A6D51CB6306F49B3377B7CBE9"
    $buildSummary = "5F333D0B75BC3978CB82D8A26A38A2A0BF0C96E11E366CFDE1F274541B9DAF52"
    $selector = "5143742008C84BAED9E1FFB69739E01422ACD92B1D626CB769E691BB1DE014EC"
    $auditor = "C5B47C9FA31926C02CD41C9E1FB3615B94101A9B39C6E755072F144C29C95E5D"
    $selectorTest = "93E8B17D9C35D5ABDEB4DF5AEDD034C17D8B151060DCD2BB7FFA0D01D6073317"
    $causalityTest = "23076B9481411D0CB0941197B0B8F6AE01C0BBCEB593577AC9CC42AA5266546B"
}
foreach ($path in $expectedHashes.Keys) {
    $actual = (Get-FileHash -Algorithm SHA256 -LiteralPath $path).Hash
    if ($actual -ne $expectedHashes[$path]) {
        throw "Predeclared SHA-256 mismatch for ${path}: expected $($expectedHashes[$path]), got ${actual}"
    }
}
if (Test-Path -LiteralPath $result) {
    throw "Refusing to reuse directional nested output: ${result}"
}

python -m pytest -q `
  $selectorTest `
  $causalityTest
if ($LASTEXITCODE -ne 0) { throw "Directional nested focused tests failed" }

python $auditor `
  --data $data `
  --build-summary $buildSummary `
  --expected-step-minutes 1 `
  --output (Join-Path $result "dataset_audit_pretrain.json")
if ($LASTEXITCODE -ne 0) { throw "Frozen one-minute dataset causal audit failed" }

python $selector `
  --data $data `
  --output-dir $result `
  --tickers SPXW QQQ SPY `
  --train-universe SPXW QQQ SPY `
  --profile-kind production_zero_dte `
  --profile-allowlist target_zero_dte_d25_return target_zero_dte_d25_win target_zero_dte_d35_return target_zero_dte_d35_win `
  --ticker-profile-allowlists `
    "SPXW=target_zero_dte_d25_return,target_zero_dte_d25_win" `
    "QQQ=target_zero_dte_d35_return,target_zero_dte_d35_win" `
    "SPY=target_zero_dte_d35_return,target_zero_dte_d35_win" `
  --direction-modes model spot_5m_trend spot_5m_counter spot_15m_trend spot_15m_counter `
  --start-month 202601 `
  --end-month 202605 `
  --val-months 3 `
  --min-train-rows 2500 `
  --min-val-rows 250 `
  --min-val-trades 54 `
  --min-month-trades 18 `
  --min-val-pf 1.3 `
  --min-val-win-rate 0.5 `
  --min-val-positive-month-rate 1.0 `
  --min-call-rate 0.0 `
  --max-call-rate 1.0 `
  --ticker-cooldown-minutes SPXW=0 QQQ=30 SPY=0 `
  --ticker-max-day-grids SPXW=4 QQQ=2 SPY=1 `
  --live-observable-features-only `
  --entry-time-min-et 10:00 `
  --n-estimators 240 `
  --learning-rate 0.035 `
  --num-leaves 31 `
  --min-child-samples 80 `
  --subsample 0.85 `
  --colsample-bytree 0.85 `
  --reg-lambda 5.0 `
  --lgb-device-type cpu `
  --lgb-jobs 28 `
  --profile-workers 1 `
  --risk-capital 5000 `
  --seed 20260618 `
  --no-resume
if ($LASTEXITCODE -ne 0) { throw "Directional nested selector failed" }

python $auditor `
  --data $data `
  --build-summary $buildSummary `
  --expected-step-minutes 1 `
  --result-dir $result `
  --output (Join-Path $result "audit.json")
if ($LASTEXITCODE -ne 0) { throw "Directional nested final audit failed" }

Write-Output "Early causal directional nested 1m v1 completed: $result"
