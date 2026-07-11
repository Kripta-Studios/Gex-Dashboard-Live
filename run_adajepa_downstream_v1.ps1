$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest
$root = $PSScriptRoot
Set-Location -LiteralPath $root
$env:PYTHONHASHSEED = "20260618"
$env:CUBLAS_WORKSPACE_CONFIG = ":4096:8"

$data = "tmp/event_option_dataset_execquote_causal1030_202501_202605_v1_physics/event_option_dataset.parquet"
$spaces = "research_papers/JEPA/results/_diagnostics/adajepa_shadow_coherent_spaces_202601_202605_seed20260618_v1"
$manifest = Join-Path $spaces "manifest.json"
$script = "neural/jepa/walkforward_adajepa_downstream.py"
$adapter = "neural/jepa/evaluate_adajepa_shadow_adapter.py"
$shared = "neural/jepa/walkforward_event_option_portfolio_var_jepa.py"
$output = "research_papers/JEPA/results/_diagnostics/adajepa_downstream_frozen_vs_adapted_202601_202605_v1"
$expected = @{
    $data = "AB144DBAD1F6F103C771AE119A1172AC728BC11B6AA79DB5FB0648561673F720"
    $manifest = "F398B1105C848C45D9BEAE0C156646B8B17207BEA5D08660BB359C099337F7B8"
    $script = "B2ADE83D1EC72E5DF9EC2560682A29A81DD91C91FEDA4D2054A3565F4FF2886C"
    $adapter = "692146DD9F9A9189D97F69476B7C7EAD3782871EEEA16E849C4DF43E9EF18BB1"
    $shared = "21C011C6F66906E90B128E091794FC92497739568DC10F34EBB6F9175B45F0A1"
}
foreach ($path in $expected.Keys) {
    if ((Get-FileHash -Algorithm SHA256 -LiteralPath $path).Hash -ne $expected[$path]) {
        throw "Predeclared hash mismatch for ${path}"
    }
}
if (Test-Path -LiteralPath $output) { throw "Refusing to reuse AdaJEPA downstream output" }

python -m pytest -q tests/test_walkforward_adajepa_downstream.py tests/test_evaluate_adajepa_shadow_adapter.py tests/test_walkforward_event_option_portfolio_var_jepa.py
if ($LASTEXITCODE -ne 0) { throw "AdaJEPA downstream tests failed" }
python $script `
    --data $data --spaces-dir $spaces --output-dir $output `
    --start-month 202601 --end-month 202605 --val-months 3 `
    --min-train-rows 5000 --clip-return 2.0 `
    --hidden-dim 128 --latent-dim 16 --dropout 0.1 `
    --epochs 40 --batch-size 512 --infer-batch-size 4096 `
    --learning-rate 0.001 --weight-decay 0.000001 --grad-clip 1.0 `
    --threshold-grid -1000000000 -0.10 -0.05 0.0 0.05 0.10 0.15 0.20 `
    --threshold-quantiles 0.4 0.5 0.6 0.7 0.8 0.9 `
    --min-val-trades 54 --min-month-trades 18 `
    --min-val-pf 1.3 --min-val-win-rate 0.5 --min-val-positive-month-rate 1.0 `
    --min-call-rate 0.0 --max-call-rate 1.0 `
    --daily-win-weight 0.25 --top5-share-penalty 0.10 `
    --adapter-learning-rate 0.05 --adapter-grad-clip 1.0 --adapter-max-parameter-norm 0.5 `
    --device cuda --seed 20260618 --deterministic
if ($LASTEXITCODE -ne 0) { throw "AdaJEPA downstream experiment failed" }
Write-Output "AdaJEPA downstream v1 completed: $output"
