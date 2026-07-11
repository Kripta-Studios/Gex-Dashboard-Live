$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$root = $PSScriptRoot
Set-Location -LiteralPath $root
$env:PYTHONPATH = "."
$env:PYTHONHASHSEED = "20260618"
$env:CUBLAS_WORKSPACE_CONFIG = ":4096:8"

$data = "tmp/event_option_dataset_execquote_causal1030_202501_202605_v1_physics/event_option_dataset.parquet"
$trainer = "neural/jepa/walkforward_event_phys_td_jepa_oof.py"
$exporter = "neural/jepa/export_event_phys_td_shadow_transitions.py"
$output = "research_papers/JEPA/results/_diagnostics/adajepa_shadow_coherent_spaces_202601_202605_seed20260618_v1"
$expectedHashes = @{
    $data = "AB144DBAD1F6F103C771AE119A1172AC728BC11B6AA79DB5FB0648561673F720"
    $trainer = "C5F47AF154413FD1ADCDC651D7FD7460155A59E64D958EEBEAF4961E2E003AF5"
    $exporter = "C1C0CDA63488BE6C2E665E6285A1FBD88B192BB655344FE0BE494661EADF98EC"
}
foreach ($path in $expectedHashes.Keys) {
    $actual = (Get-FileHash -Algorithm SHA256 -LiteralPath $path).Hash
    if ($actual -ne $expectedHashes[$path]) {
        throw "Predeclared SHA-256 mismatch for ${path}: expected $($expectedHashes[$path]), got ${actual}"
    }
}
if (Test-Path -LiteralPath $output) { throw "Refusing to reuse coherent-space output: ${output}" }

python -m pytest -q tests/test_event_phys_td_jepa_causality.py tests/test_export_event_phys_td_shadow_transitions.py
if ($LASTEXITCODE -ne 0) { throw "AdaJEPA coherent-space focused tests failed" }
python -c "import torch; assert torch.cuda.is_available(); free,total=torch.cuda.mem_get_info(); assert free >= 2*1024**3, f'insufficient CUDA memory: {free/1024**3:.2f} GiB'; print({'device':torch.cuda.get_device_name(0),'free_gib':round(free/1024**3,2),'total_gib':round(total/1024**3,2)})"
if ($LASTEXITCODE -ne 0) { throw "AdaJEPA CUDA preflight failed" }

$folds = @(
    @{ Test = "202601"; TrainEnd = "202509" },
    @{ Test = "202602"; TrainEnd = "202510" },
    @{ Test = "202603"; TrainEnd = "202511" },
    @{ Test = "202604"; TrainEnd = "202512" },
    @{ Test = "202605"; TrainEnd = "202601" }
)
$manifest = @()
foreach ($fold in $folds) {
    $foldRoot = Join-Path $output ("fold_" + $fold.Test)
    $trainerOut = Join-Path $foldRoot "trainer"
    $encoderOut = Join-Path $foldRoot "encoder"
    $transitionOut = Join-Path $foldRoot "transitions"
    $trainerArgs = @(
        $trainer,
        "--data", $data,
        "--output-dir", $trainerOut,
        "--tickers", "SPXW", "SPY", "QQQ",
        "--expiry-modes", "zero_dte",
        "--start-month", "202505",
        "--end-month", "202605",
        "--horizons", "1,3,6,12",
        "--encoder-input-mode", "flat",
        "--live-observable-features-only",
        "--entry-start-minute-et", "630",
        "--entry-end-minute-et", "870",
        "--entry-grid-anchor-minute-et", "600",
        "--expected-step-minutes", "5",
        "--seed", "20260618",
        "--device", "cuda",
        "--deterministic",
        "--epochs", "8",
        "--batch-size", "1024",
        "--infer-batch-size", "4096",
        "--context-len", "6",
        "--z-dim", "32",
        "--phys-dim", "12",
        "--delta-dim", "16",
        "--hidden-dim", "128",
        "--num-layers", "2",
        "--num-workers", "0",
        "--skip-oof",
        "--export-deploy-model",
        "--deploy-month", $fold.Test,
        "--deploy-train-end-month", $fold.TrainEnd,
        "--deploy-output-dir", $encoderOut
    )
    python @trainerArgs
    if ($LASTEXITCODE -ne 0) { throw "Frozen encoder training failed for $($fold.Test)" }

    $model = Join-Path $encoderOut "event_phys_td_jepa_encoder.pt"
    python $exporter `
        --model $model `
        --data $data `
        --output-dir $transitionOut `
        --start-month 202501 `
        --end-month $fold.Test `
        --device cuda
    if ($LASTEXITCODE -ne 0) { throw "Transition export failed for $($fold.Test)" }
    $meta = Get-Content -LiteralPath (Join-Path $transitionOut "metadata.json") -Raw | ConvertFrom-Json
    if (-not $meta.june_2026_sealed -or $meta.encoder_training_months[-1] -ne $fold.TrainEnd) {
        throw "Transition metadata cutoff failed for $($fold.Test)"
    }
    $manifest += [pscustomobject]@{
        test_month = $fold.Test
        train_end_month = $fold.TrainEnd
        encoder_path = $model
        encoder_sha256 = $meta.model_sha256
        transitions_path = $meta.output_path
        transitions_sha256 = $meta.output_sha256
        transition_rows = $meta.rows
        date_min = $meta.date_min
        date_max = $meta.date_max
    }
    Write-Output "[ADAJEPA_SPACE] test=$($fold.Test) train_end=$($fold.TrainEnd) rows=$($meta.rows)"
}

New-Item -ItemType Directory -Path $output -Force | Out-Null
$manifest | ConvertTo-Json -Depth 5 | Set-Content -LiteralPath (Join-Path $output "manifest.json") -Encoding utf8
Write-Output "AdaJEPA coherent spaces v1 completed: $output"
