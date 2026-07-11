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
$exporter = "neural/jepa/export_event_phys_td_current_horizons.py"
$downstream = "neural/jepa/walkforward_phys_td_horizon_downstream.py"
$horizonRoot = "research_papers/JEPA/results/_diagnostics/phys_td_current_h1_h6_features_202601_202605_v1"
$horizonManifest = Join-Path $horizonRoot "manifest.json"
$output = "research_papers/JEPA/results/_diagnostics/phys_td_h1_vs_h6_downstream_202601_202605_seed20260618_v1"

$expectedHashes = @{
    $data = "AB144DBAD1F6F103C771AE119A1172AC728BC11B6AA79DB5FB0648561673F720"
    $spacesManifest = "F398B1105C848C45D9BEAE0C156646B8B17207BEA5D08660BB359C099337F7B8"
    $exporter = "884E743E0CB994B21E6BA51E233B0B21F820AD5BE88148120A8F285C071C5BAF"
    $downstream = "0ECFEA3767225098C96EE137F86DE0A5DFFD005CBCBF969B655518CF65427F52"
}
foreach ($path in $expectedHashes.Keys) {
    $actual = (Get-FileHash -Algorithm SHA256 -LiteralPath $path).Hash
    if ($actual -ne $expectedHashes[$path]) {
        throw "Predeclared SHA-256 mismatch for ${path}: expected $($expectedHashes[$path]), got ${actual}"
    }
}
if (Test-Path -LiteralPath $horizonRoot) { throw "Refusing to reuse horizon feature output: ${horizonRoot}" }
if (Test-Path -LiteralPath $output) { throw "Refusing to reuse horizon downstream output: ${output}" }

python -m pytest -q `
  tests/test_export_event_phys_td_current_horizons.py `
  tests/test_walkforward_phys_td_horizon_downstream.py `
  tests/test_walkforward_event_option_portfolio_var_jepa.py
if ($LASTEXITCODE -ne 0) { throw "Phys-TD h1/h6 focused tests failed" }
python -c "import torch; assert torch.cuda.is_available(); free,total=torch.cuda.mem_get_info(); assert free >= 2*1024**3, f'insufficient CUDA memory: {free/1024**3:.2f} GiB'; print({'device':torch.cuda.get_device_name(0),'free_gib':round(free/1024**3,2),'total_gib':round(total/1024**3,2)})"
if ($LASTEXITCODE -ne 0) { throw "Phys-TD h1/h6 CUDA preflight failed" }

New-Item -ItemType Directory -Path $horizonRoot -Force | Out-Null
$spaces = Get-Content -LiteralPath $spacesManifest -Raw | ConvertFrom-Json
$horizonRows = @()
foreach ($fold in $spaces) {
    $foldRoot = Join-Path $horizonRoot ("fold_" + $fold.test_month)
    python $exporter `
      --model $fold.encoder_path `
      --data $data `
      --output-dir $foldRoot `
      --start-month 202501 `
      --end-month $fold.test_month `
      --horizons 1 6 `
      --device cuda
    if ($LASTEXITCODE -ne 0) { throw "Current horizon export failed for $($fold.test_month)" }
    $meta = Get-Content -LiteralPath (Join-Path $foldRoot "metadata.json") -Raw | ConvertFrom-Json
    if (-not $meta.june_2026_sealed -or $meta.uses_future_target -or $meta.model_sha256 -ne $fold.encoder_sha256) {
        throw "Current horizon metadata audit failed for $($fold.test_month)"
    }
    if ($meta.rows -lt $fold.transition_rows) {
        throw "Current horizon export lost h1 rows for $($fold.test_month)"
    }
    $horizonRows += [pscustomobject]@{
        test_month = $fold.test_month
        encoder_sha256 = $meta.model_sha256
        features_path = $meta.output_path
        features_sha256 = $meta.output_sha256
        feature_rows = $meta.rows
        date_min = $meta.date_min
        date_max = $meta.date_max
        horizons = @($meta.horizons)
    }
}
$horizonRows | ConvertTo-Json -Depth 5 | Set-Content -LiteralPath $horizonManifest -Encoding utf8

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
if ($LASTEXITCODE -ne 0) { throw "Phys-TD h1/h6 downstream failed" }

Write-Output "Phys-TD h1 vs h6 v1 completed: $output"
