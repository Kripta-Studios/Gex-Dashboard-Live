param(
    [switch]$Resume
)

$ErrorActionPreference = "Stop"
$env:PYTHONPATH = "."
$env:PYTHONHASHSEED = "20260618"
$env:CUBLAS_WORKSPACE_CONFIG = ":4096:8"

$FullData = "tmp/event_option_dataset_execquote_causal1030_202201_202605_v1_physics/event_option_dataset.parquet"
$RecentData = "tmp/event_option_dataset_execquote_causal1030_202501_202605_v1_physics/event_option_dataset.parquet"
$Trainer = "neural/jepa/walkforward_event_phys_td_jepa_oof.py"
$Appender = "neural/jepa/append_xinput_oof_to_event_option_dataset.py"
$Selector = "neural/jepa/walkforward_event_option_profile_selector.py"

$ExpectedHashes = @{
    $FullData = "11E26AADDD91FD441222D552E0362C1D4C2C4489A08D7A6DE66479D6EB454FB1"
    $RecentData = "AB144DBAD1F6F103C771AE119A1172AC728BC11B6AA79DB5FB0648561673F720"
    $Trainer = "703FFE983428283622CE92F95505C2E9DF352144359D3623D1856BEA33F23AF8"
    $Appender = "077E250DDF01C06E7647D03B43047F958F6BFF7C0C929B49D599DDB1BF674A7E"
    $Selector = "16A51B1C0DE6099A9D22DCDB26DFE28B4A3F3B4EBDD615F6AAD96C7691970300"
}

foreach ($path in $ExpectedHashes.Keys) {
    $observed = (Get-FileHash -Algorithm SHA256 -LiteralPath $path).Hash
    if ($observed -ne $ExpectedHashes[$path]) {
        throw "Input hash mismatch for ${path}: expected $($ExpectedHashes[$path]), observed $observed"
    }
}

python -c "import torch; assert torch.cuda.is_available(), 'CUDA unavailable'; free,total=torch.cuda.mem_get_info(); assert free >= 2*1024**3, f'insufficient CUDA memory: {free/1024**3:.2f} GiB'; print({'device':torch.cuda.get_device_name(0),'free_gib':round(free/1024**3,2),'total_gib':round(total/1024**3,2)})"
if ($LASTEXITCODE -ne 0) {
    throw "CUDA preflight failed"
}

$Arms = @(
    @{
        Name = "history_2025"
        Data = $RecentData
        Encoder = "research_papers/JEPA/results/_diagnostics/ptdj_ablation_flat_history_2025_h1_3_6_12_causal_202505_202605_v1"
        Walkforward = "research_papers/JEPA/results/_diagnostics/ptdj_ablation_flat_history_2025_h1_3_6_12_causal_202505_202605_v1_walkforward_runtime_contract_v1"
    },
    @{
        Name = "history_2022"
        Data = $FullData
        Encoder = "research_papers/JEPA/results/_diagnostics/ptdj_ablation_flat_history_2022_h1_3_6_12_causal_202505_202605_v1"
        Walkforward = "research_papers/JEPA/results/_diagnostics/ptdj_ablation_flat_history_2022_h1_3_6_12_causal_202505_202605_v1_walkforward_runtime_contract_v1"
    }
)

foreach ($arm in $Arms) {
    if ((Test-Path -LiteralPath $arm.Encoder) -and -not $Resume) {
        throw "Encoder output already exists for $($arm.Name): $($arm.Encoder)"
    }
    if ((Test-Path -LiteralPath $arm.Walkforward) -and -not $Resume) {
        throw "Walk-forward output already exists for $($arm.Name): $($arm.Walkforward)"
    }
}

foreach ($arm in $Arms) {
    $trainerArgs = @(
        $Trainer,
        "--data", $arm.Data,
        "--output-dir", $arm.Encoder,
        "--tickers", "SPXW", "SPY", "QQQ",
        "--expiry-modes", "zero_dte",
        "--start-month", "202505",
        "--end-month", "202605",
        "--data-cutoff-month", "202605",
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
        "--context-len", "6",
        "--z-dim", "32",
        "--phys-dim", "12",
        "--delta-dim", "16",
        "--hidden-dim", "128",
        "--num-layers", "2",
        "--num-workers", "0"
    )
    python @trainerArgs
    if ($LASTEXITCODE -ne 0) {
        throw "Phys-TD training failed for $($arm.Name) with exit code $LASTEXITCODE"
    }

    $folds = Import-Csv -LiteralPath (Join-Path $arm.Encoder "fold_configs.csv")
    if ($folds.Count -ne 13 -or $folds[0].month -ne "202505" -or $folds[-1].month -ne "202605") {
        throw "Unexpected OOF fold coverage for $($arm.Name)"
    }

    $joined = Join-Path $arm.Encoder "event_option_dataset.parquet"
    if (-not (Test-Path -LiteralPath $joined)) {
        python $Appender `
            --event-data $RecentData `
            --xinput-features (Join-Path $arm.Encoder "oof_event_phys_td_jepa_features.parquet") `
            --output-dir $arm.Encoder `
            --output-name "event_option_dataset.parquet" `
            --feature-prefix "ptdj_" `
            --ticker-key-mode "identity"
        if ($LASTEXITCODE -ne 0) {
            throw "Feature append failed for $($arm.Name)"
        }
    }

    $selectorArgs = @(
        $Selector,
        "--data", $joined,
        "--output-dir", $arm.Walkforward,
        "--tickers", "SPXW", "SPY", "QQQ",
        "--start-month", "202601",
        "--end-month", "202605",
        "--profile-kind", "production_zero_dte",
        "--live-observable-features-only",
        "--ticker-cooldown-minutes", "SPXW=0", "QQQ=30", "SPY=0",
        "--ticker-max-day-grids", "SPXW=4", "QQQ=2", "SPY=1",
        "--seed", "20260618",
        "--lgb-device-type", "cpu",
        "--profile-workers", "2",
        "--lgb-jobs", "12"
    )
    if (-not $Resume -or -not (Test-Path -LiteralPath $arm.Walkforward)) {
        $selectorArgs += "--no-resume"
    }
    python @selectorArgs
    if ($LASTEXITCODE -ne 0) {
        throw "Nested selector failed for $($arm.Name) with exit code $LASTEXITCODE"
    }

    $provenance = Get-Content -LiteralPath (Join-Path $arm.Walkforward "policy_selection_provenance.json") -Raw | ConvertFrom-Json
    if (-not $provenance.passed -or $provenance.evaluation_months.Count -ne 5) {
        throw "Nested provenance failed for $($arm.Name)"
    }
}

Write-Output "Flat history ablation completed for both arms."
