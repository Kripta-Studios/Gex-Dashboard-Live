$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$root = $PSScriptRoot
Set-Location -LiteralPath $root
$env:PYTHONPATH = "."
$env:PYTHONHASHSEED = "20260618"
$env:OMP_NUM_THREADS = "28"
$env:MKL_NUM_THREADS = "28"

$data = "tmp/event_option_dataset_execquote_causal1030_202201_202605_v1_physics/event_option_dataset.parquet"
$selector = "neural/jepa/walkforward_event_option_profile_selector.py"
$analyzer = "neural/jepa/analyze_exact_objective_ablation.py"
$test = "tests/test_walkforward_event_option_profile_selector.py"
$output = "research_papers/JEPA/results/_diagnostics/exact_objective_return_vs_win_202601_202605_seed20260618_v1"

$expectedHashes = @{
    $data = "11E26AADDD91FD441222D552E0362C1D4C2C4489A08D7A6DE66479D6EB454FB1"
    $selector = "95279496D6C0A1820522AB2244F70EEEEEA916300486AE87BD7A76D628B8C2AA"
    $analyzer = "47FDEDACE21A053DC703AD4E991662739CC5C320FD301C4F05DB3D0575B4FB75"
    $test = "EA4F3A99EF07C1BCCDE03F6A48A175AA65A5E39F079E735F425005CAD783E3B3"
}
foreach ($path in $expectedHashes.Keys) {
    $actual = (Get-FileHash -Algorithm SHA256 -LiteralPath $path).Hash
    if ($actual -ne $expectedHashes[$path]) {
        throw "Predeclared SHA-256 mismatch for ${path}: expected $($expectedHashes[$path]), got ${actual}"
    }
}
if (Test-Path -LiteralPath $output) { throw "Refusing to reuse exact objective output: ${output}" }

python -m pytest -q `
  tests/test_walkforward_event_option_profile_selector.py `
  tests/test_event_option_live_causality.py `
  tests/test_event_option_non_overlap.py
if ($LASTEXITCODE -ne 0) { throw "Exact objective focused tests failed" }

$cpu = Get-CimInstance Win32_Processor | Select-Object -First 1 Name,NumberOfCores,NumberOfLogicalProcessors
$memoryGiB = [math]::Round((Get-CimInstance Win32_ComputerSystem).TotalPhysicalMemory / 1GB, 2)
Write-Output ([ordered]@{cpu=$cpu.Name; cores=$cpu.NumberOfCores; threads=$cpu.NumberOfLogicalProcessors; memory_gib=$memoryGiB; lgb_threads=28})

$cells = @(
    [ordered]@{Arm="return"; Ticker="SPXW"; Bucket=25; Cap=4; Cooldown=0},
    [ordered]@{Arm="return"; Ticker="QQQ";  Bucket=35; Cap=2; Cooldown=30},
    [ordered]@{Arm="return"; Ticker="SPY";  Bucket=35; Cap=1; Cooldown=0},
    [ordered]@{Arm="win";    Ticker="SPXW"; Bucket=25; Cap=4; Cooldown=0},
    [ordered]@{Arm="win";    Ticker="QQQ";  Bucket=35; Cap=2; Cooldown=30},
    [ordered]@{Arm="win";    Ticker="SPY";  Bucket=35; Cap=1; Cooldown=0}
)

foreach ($cell in $cells) {
    $arm = [string]$cell.Arm
    $ticker = [string]$cell.Ticker
    $bucket = [int]$cell.Bucket
    $cap = [int]$cell.Cap
    $cooldown = [int]$cell.Cooldown
    $profile = "target_zero_dte_d$($bucket.ToString('00'))_${arm}"
    $cellOutput = Join-Path $output "${arm}/${ticker}"
    python $selector `
      --data $data `
      --output-dir $cellOutput `
      --tickers $ticker `
      --train-universe $ticker `
      --profile-kind production_zero_dte `
      --profile-allowlist $profile `
      --start-month 202601 `
      --end-month 202605 `
      --val-months 3 `
      --clip-return 2.0 `
      --min-train-rows 5000 `
      --min-val-rows 500 `
      --min-val-trades 54 `
      --min-month-trades 18 `
      --min-val-pf 1.3 `
      --min-val-win-rate 0.5 `
      --min-val-positive-month-rate 1.0 `
      --min-call-rate 0.0 `
      --max-call-rate 1.0 `
      --ticker-cooldown-minutes "${ticker}=${cooldown}" `
      --ticker-max-day-grids "${ticker}=${cap}" `
      --live-observable-features-only `
      --entry-time-min-et 10:30 `
      --objective regression_l1 `
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
    if ($LASTEXITCODE -ne 0) { throw "Exact objective cell failed: ${arm}/${ticker}" }
}

python $analyzer --root $output --data $data
if ($LASTEXITCODE -ne 0) { throw "Exact objective analysis failed" }

Write-Output "Exact objective ablation v1 completed: $output"
