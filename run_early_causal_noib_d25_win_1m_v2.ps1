$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$root = $PSScriptRoot
Set-Location -LiteralPath $root
$env:PYTHONPATH = "."
$env:PYTHONHASHSEED = "20260618"
$env:OMP_NUM_THREADS = "28"
$env:MKL_NUM_THREADS = "28"

$manifest = "research_papers/JEPA/results/_diagnostics/thetadata_manifest_spxw_spy_qqq_202201_202605_sealed_v1/thetadata_option_manifest.csv"
$builder = "neural/jepa/build_event_option_dataset.py"
$enhancer = "neural/jepa/enhance_event_option_dataset_physics.py"
$selector = "neural/jepa/walkforward_event_option_profile_selector.py"
$auditor = "neural/jepa/audit_early_causal_option_dataset.py"
$pairAuditor = "neural/jepa/audit_early_cadence_pair.py"
$selectorTest = "tests/test_walkforward_event_option_profile_selector.py"
$pairTest = "tests/test_audit_early_cadence_pair.py"
$controlBaseData = "tmp/event_option_dataset_execquote_causal1000_noib_early_202201_202605_v1/event_option_dataset.parquet"
$controlMetrics = "research_papers/JEPA/results/_diagnostics/early_causal_noib_d25_win_202601_202605_seed20260618_v1/metrics.json"
$base = "tmp/event_option_dataset_execquote_causal1000_noib_early_1m_202201_202605_v2"
$physics = "tmp/event_option_dataset_execquote_causal1000_noib_early_1m_202201_202605_v2_physics"
$data = Join-Path $physics "event_option_dataset.parquet"
$result = "research_papers/JEPA/results/_diagnostics/early_causal_noib_d25_win_1m_202601_202605_seed20260618_v2"

$expectedHashes = @{
    $manifest = "88BE8A2FF44C18FB57FCA360D31DEF574DDBB0419A792FC88349942711D2974A"
    $builder = "6E89AAFED8A2BB66AA8EE80DF70644ECA189D0CE1D8C56F3812895430DAC4307"
    $enhancer = "3E420DB49315AFD9363C45B9F0FEFFA38732EFC116889D3D69B4417A94D2CB36"
    $selector = "95279496D6C0A1820522AB2244F70EEEEEA916300486AE87BD7A76D628B8C2AA"
    $auditor = "C5B47C9FA31926C02CD41C9E1FB3615B94101A9B39C6E755072F144C29C95E5D"
    $pairAuditor = "8269A4FB745B5ABB7DCEDBF4AE13721D429E5CBCDB946A8D6F9619FC6AF4E396"
    $selectorTest = "461ED65AFB1851D21A9955003D324C3DA57441AFF936743E1A238EA4D413C9F2"
    $pairTest = "2A1801421A3754B973469B408F87C0E4E312094E482544B839F9FD7EAB767487"
    $controlBaseData = "5E916EFAAEA2D89B195E481FFD5948273E1D362F146EA4E8C05C3C61EFBBEF49"
    $controlMetrics = "3E8A634855E0073B5A635F0EB01CA73D60869296286BB7F4BEB2E5B7CE3E2BA9"
}
foreach ($path in $expectedHashes.Keys) {
    $actual = (Get-FileHash -Algorithm SHA256 -LiteralPath $path).Hash
    if ($actual -ne $expectedHashes[$path]) {
        throw "Predeclared SHA-256 mismatch for ${path}: expected $($expectedHashes[$path]), got ${actual}"
    }
}
foreach ($path in @($base, $physics, $result)) {
    if (Test-Path -LiteralPath $path) { throw "Refusing to reuse one-minute early output: ${path}" }
}

python -m pytest -q `
  tests/test_audit_early_cadence_pair.py `
  tests/test_walkforward_event_option_profile_selector.py `
  tests/test_build_event_option_dataset.py `
  tests/test_event_option_live_causality.py
if ($LASTEXITCODE -ne 0) { throw "One-minute early causal focused tests failed" }

python $builder `
  --manifest $manifest `
  --output-dir $base `
  --tickers SPXW SPY QQQ `
  --expiry-modes zero_dte `
  --start-date 20220101 `
  --end-date 20260531 `
  --workers 24 `
  --bar-minutes 1 `
  --start-minute 600 `
  --end-minute 625 `
  --no-near-level-only `
  --max-rows-per-day 0 `
  --horizon-minutes 180 `
  --option-tp-pct 10.0 `
  --option-sl-pct 0.6 `
  --option-price-mode executable_quote `
  --option-exit-mode trailing `
  --option-min-hold-minutes 30 `
  --option-trail-activation-pct 0.5 `
  --option-trail-drawdown-pct 0.25 `
  --require-open-interest `
  --chunk-by ticker_month
if ($LASTEXITCODE -ne 0) { throw "One-minute executable dataset build failed" }

python $pairAuditor `
  --control-data $controlBaseData `
  --candidate-data (Join-Path $base "event_option_dataset.parquet") `
  --output (Join-Path $result "cadence_pair_pretrain.json")
if ($LASTEXITCODE -ne 0) { throw "One-minute dataset is not a strict expansion of the five-minute control" }

New-Item -ItemType Directory -Force -Path $physics | Out-Null
python $enhancer `
  --input (Join-Path $base "event_option_dataset.parquet") `
  --output $data `
  --summary (Join-Path $physics "SUMMARY.json")
if ($LASTEXITCODE -ne 0) { throw "One-minute physics enhancement failed" }

python $auditor `
  --data $data `
  --build-summary (Join-Path $base "SUMMARY.json") `
  --expected-step-minutes 1 `
  --output (Join-Path $result "dataset_audit_pretrain.json")
if ($LASTEXITCODE -ne 0) { throw "One-minute early dataset causal audit failed" }

python $selector `
  --data $data `
  --output-dir $result `
  --tickers SPXW QQQ SPY `
  --train-universe SPXW QQQ SPY `
  --profile-kind production_zero_dte `
  --profile-allowlist target_zero_dte_d25_win `
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
if ($LASTEXITCODE -ne 0) { throw "One-minute early causal d25 win selector failed" }

python $auditor `
  --data $data `
  --build-summary (Join-Path $base "SUMMARY.json") `
  --expected-step-minutes 1 `
  --result-dir $result `
  --output (Join-Path $result "audit.json")
if ($LASTEXITCODE -ne 0) { throw "One-minute early causal final audit failed" }

Write-Output "One-minute early causal no-IB d25 win v2 completed: $result"
