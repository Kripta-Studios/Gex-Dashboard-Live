$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$root = $PSScriptRoot
Set-Location -LiteralPath $root
$env:PYTHONPATH = "."
$env:PYTHONHASHSEED = "20260618"
$env:CUBLAS_WORKSPACE_CONFIG = ":4096:8"
$env:OMP_NUM_THREADS = "16"
$env:MKL_NUM_THREADS = "16"

$data = "tmp/event_option_dataset_execquote_causal1030_202501_202605_v1_physics/event_option_dataset.parquet"
$spacesDir = "research_papers/JEPA/results/_diagnostics/adajepa_shadow_coherent_spaces_202601_202605_seed20260618_v1"
$spacesManifest = Join-Path $spacesDir "manifest.json"
$horizonManifest = "research_papers/JEPA/results/_diagnostics/phys_td_current_h1_h6_features_202601_202605_v1/manifest.json"
$downstream = "neural/jepa/walkforward_phys_td_spot_skip.py"
$output = "research_papers/JEPA/results/_diagnostics/phys_td_spot_skip_202601_202605_seed20260618_v1"

$expectedHashes = @{
    $data = "AB144DBAD1F6F103C771AE119A1172AC728BC11B6AA79DB5FB0648561673F720"
    $spacesManifest = "F398B1105C848C45D9BEAE0C156646B8B17207BEA5D08660BB359C099337F7B8"
    $horizonManifest = "F21336B1941508E382B6097CE44CEA9863253F07E5899374A5B9CC59BD361BDE"
    $downstream = "EC4B683704B83878895FB82AC026F6FDD2942A949EB1A1EC9A734C03915B06B9"
}
foreach ($path in $expectedHashes.Keys) {
    $actual = (Get-FileHash -Algorithm SHA256 -LiteralPath $path).Hash
    if ($actual -ne $expectedHashes[$path]) {
        throw "Predeclared SHA-256 mismatch for ${path}: expected $($expectedHashes[$path]), got ${actual}"
    }
}
if (Test-Path -LiteralPath $output) { throw "Refusing to reuse spot skip output: ${output}" }

python -m pytest -q `
  tests/test_walkforward_phys_td_spot_skip.py `
  tests/test_walkforward_phys_td_horizon_downstream.py `
  tests/test_walkforward_event_option_portfolio_var_jepa.py
if ($LASTEXITCODE -ne 0) { throw "Phys-TD spot skip focused tests failed" }
python -c "import torch; assert torch.cuda.is_available(); free,total=torch.cuda.mem_get_info(); assert free >= 2*1024**3, f'insufficient CUDA memory: {free/1024**3:.2f} GiB'; print({'device':torch.cuda.get_device_name(0),'free_gib':round(free/1024**3,2),'total_gib':round(total/1024**3,2)})"
if ($LASTEXITCODE -ne 0) { throw "Phys-TD spot skip CUDA preflight failed" }

python $downstream `
  --data $data `
  --spaces-dir $spacesDir `
  --horizon-manifest $horizonManifest `
  --output-dir $output `
  --start-month 202601 `
  --end-month 202605 `
  --val-months 3 `
  --min-train-rows 5000 `
  --clip-return 2.0 `
  --hidden-dim 128 `
  --latent-dim 16 `
  --dropout 0.1 `
  --epochs 40 `
  --batch-size 512 `
  --infer-batch-size 4096 `
  --learning-rate 0.001 `
  --weight-decay 0.000001 `
  --grad-clip 1.0 `
  --min-val-trades 54 `
  --min-month-trades 18 `
  --min-val-pf 1.3 `
  --min-val-win-rate 0.5 `
  --min-val-positive-month-rate 1.0 `
  --daily-win-weight 0.25 `
  --top5-share-penalty 0.1 `
  --device cuda `
  --seed 20260618 `
  --deterministic
if ($LASTEXITCODE -ne 0) { throw "Phys-TD spot skip downstream failed" }

Write-Output "Phys-TD spot skip v1 completed: $output"
