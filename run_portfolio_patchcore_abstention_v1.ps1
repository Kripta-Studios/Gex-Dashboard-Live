$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$root = $PSScriptRoot
Set-Location -LiteralPath $root
$env:CUBLAS_WORKSPACE_CONFIG = ":4096:8"
$env:PYTHONHASHSEED = "20260618"

$data = "research_papers/JEPA/results/_diagnostics/ptdj_ablation_flat_history_2025_h1_3_6_12_causal_202505_202605_v1/event_option_dataset.parquet"
$script = "neural/jepa/walkforward_event_option_patchcore_abstention.py"
$shared = "neural/jepa/walkforward_event_option_portfolio_var_jepa.py"
$output = "research_papers/JEPA/results/_diagnostics/portfolio_patchcore_abstention_exact_runtime_202601_202605_seed20260618_v1"
$expectedHashes = @{
    $data = "39203C83F47A60AFB2AB7951201CBEB3B9098F4238169F0D716649571667DA2F"
    $script = "2649D8ED77A7A43F07BE0E67FC47B51FC5ADF6F5E9FC9D304DA4C09A693D29E9"
    $shared = "21C011C6F66906E90B128E091794FC92497739568DC10F34EBB6F9175B45F0A1"
}
foreach ($path in $expectedHashes.Keys) {
    $actual = (Get-FileHash -Algorithm SHA256 -LiteralPath $path).Hash
    if ($actual -ne $expectedHashes[$path]) {
        throw "Predeclared SHA-256 mismatch for ${path}: expected $($expectedHashes[$path]), got ${actual}"
    }
}
if (Test-Path -LiteralPath $output) { throw "Refusing to reuse output: ${output}" }

python -m pytest -q tests/test_walkforward_event_option_patchcore_abstention.py tests/test_walkforward_event_option_portfolio_var_jepa.py
if ($LASTEXITCODE -ne 0) { throw "PatchCore focused tests failed" }

python $script `
    --data $data `
    --output-dir $output `
    --start-month 202601 --end-month 202605 --val-months 3 `
    --min-train-rows 5000 --clip-return 2.0 `
    --hidden-dim 128 --latent-dim 16 --dropout 0.1 `
    --epochs 40 --batch-size 512 --infer-batch-size 4096 `
    --learning-rate 0.001 --weight-decay 0.000001 --grad-clip 1.0 `
    --coreset-size 128 --distance-quantiles 0.50 0.60 0.70 0.80 0.90 0.95 1.0 `
    --threshold-grid -1000000000 -0.10 -0.05 0.0 0.05 0.10 0.15 0.20 `
    --threshold-quantiles 0.4 0.5 0.6 0.7 0.8 0.9 `
    --min-val-trades 54 --min-month-trades 18 `
    --min-val-pf 1.3 --min-val-win-rate 0.5 --min-val-positive-month-rate 1.0 `
    --min-call-rate 0.0 --max-call-rate 1.0 `
    --daily-win-weight 0.25 --top5-share-penalty 0.10 `
    --device cuda --seed 20260618 --deterministic
if ($LASTEXITCODE -ne 0) { throw "PatchCore abstention experiment failed" }

Write-Output "PatchCore abstention v1 completed: $output"
