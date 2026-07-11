# run_regime_gate_ablation_v1.ps1
# Regime gate ablation: control (no gate) vs 4 isolated economic regime gates (R1, R2, R3, R4)
# Predeclaration: research_papers/JEPA/REGIME_GATE_ABLATION_PREDECLARATION_V1.md

$ErrorActionPreference = "Stop"
Set-Location -Path $PSScriptRoot

# ── Physically Sealed Dataset ──
$dataset = "tmp/event_option_dataset_execquote_causal1030_202501_202605_regime_v1.parquet"

# Verify dataset exists, otherwise create it
if (-not (Test-Path $dataset)) {
    Write-Host "Creating physically sealed dataset (excluding June 2026)..."
    python neural/jepa/create_sealed_regime_dataset.py
}

$outputC0 = "research_papers/JEPA/results/_diagnostics/regime_gate_ablation_c0_202601_202605_seed20260618_v1"
$outputR1 = "research_papers/JEPA/results/_diagnostics/regime_gate_ablation_r1_ivskew_202601_202605_seed20260618_v1"
$outputR2 = "research_papers/JEPA/results/_diagnostics/regime_gate_ablation_r2_spread_202601_202605_seed20260618_v1"
$outputR3 = "research_papers/JEPA/results/_diagnostics/regime_gate_ablation_r3_absret_202601_202605_seed20260618_v1"
$outputR4 = "research_papers/JEPA/results/_diagnostics/regime_gate_ablation_r4_ib_202601_202605_seed20260618_v1"

# ── Common arguments ──
$commonArgs = @(
    "--data", $dataset,
    "--start-month", "202601",
    "--end-month", "202605",
    "--val-months", "3",
    "--seed", "20260618",
    "--tickers", "SPXW", "QQQ", "SPY",
    "--profile-kind", "production_zero_dte",
    "--ticker-profile-allowlists", "SPXW=target_zero_dte_d25_win", "QQQ=target_zero_dte_d35_win", "SPY=target_zero_dte_d35_win",
    "--ticker-cooldown-minutes", "SPXW=0", "QQQ=30", "SPY=0",
    "--ticker-max-day-grids", "SPXW=4,999", "QQQ=2,999", "SPY=1,999",
    "--min-val-trades", "45",
    "--min-month-trades", "18",
    "--min-val-pf", "1.3",
    "--min-val-win-rate", "0.50",
    "--min-val-positive-month-rate", "1.0",
    "--direction-modes", "model",
    "--live-observable-features-only",
    "--entry-time-min-et", "10:30",
    "--lgb-device-type", "cpu",
    "--profile-workers", "1",
    "--no-resume"
)

# ── Hash scripts and dataset before execution ──
Write-Host "=== Hashing files ==="
$selectorHash = (Get-FileHash "neural/jepa/walkforward_event_option_profile_selector.py" -Algorithm SHA256).Hash
$datasetHash = (Get-FileHash $dataset -Algorithm SHA256).Hash
Write-Host "selector_hash=$selectorHash"
Write-Host "dataset_hash=$datasetHash"

# ── ARM C0: Control (no regime gate) ──
Write-Host ""
Write-Host "=== ARM C0: CONTROL (no regime gate) ==="
Write-Host "Output: $outputC0"
python neural/jepa/walkforward_event_option_profile_selector.py `
    @commonArgs `
    --output-dir $outputC0
if ($LASTEXITCODE -ne 0) { Write-Error "C0 failed"; exit 1 }

# ── ARM R1: IV Skew (allowed direction: any) ──
Write-Host ""
Write-Host "=== ARM R1: IV Skew (any direction) ==="
Write-Host "Output: $outputR1"
python neural/jepa/walkforward_event_option_profile_selector.py `
    @commonArgs `
    --output-dir $outputR1 `
    --regime-gate-features phys_d25_iv_skew_put_minus_call phys_d35_iv_skew_put_minus_call `
    --regime-gate-direction any
if ($LASTEXITCODE -ne 0) { Write-Error "R1 failed"; exit 1 }

# ── ARM R2: Spread (allowed direction: below - Primary) ──
Write-Host ""
Write-Host "=== ARM R2: Spread (below only - Primary) ==="
Write-Host "Output: $outputR2"
python neural/jepa/walkforward_event_option_profile_selector.py `
    @commonArgs `
    --output-dir $outputR2 `
    --regime-gate-features phys_d25_spread_mean phys_d35_spread_mean `
    --regime-gate-direction below
if ($LASTEXITCODE -ne 0) { Write-Error "R2 failed"; exit 1 }

# ── ARM R3: Abs Return 5m (allowed direction: below) ──
Write-Host ""
Write-Host "=== ARM R3: Abs Return 5m (below only) ==="
Write-Host "Output: $outputR3"
python neural/jepa/walkforward_event_option_profile_selector.py `
    @commonArgs `
    --output-dir $outputR3 `
    --regime-gate-features phys_abs_ret_5m_bps `
    --regime-gate-direction below
if ($LASTEXITCODE -ne 0) { Write-Error "R3 failed"; exit 1 }

# ── ARM R4: IB Range (allowed direction: any) ──
Write-Host ""
Write-Host "=== ARM R4: IB Range (any direction) ==="
Write-Host "Output: $outputR4"
python neural/jepa/walkforward_event_option_profile_selector.py `
    @commonArgs `
    --output-dir $outputR4 `
    --regime-gate-features ib_range_bps `
    --regime-gate-direction any
if ($LASTEXITCODE -ne 0) { Write-Error "R4 failed"; exit 1 }

Write-Host ""
Write-Host "=== ALL FIVE ARMS COMPLETE ==="
Write-Host "C0: $outputC0"
Write-Host "R1: $outputR1"
Write-Host "R2: $outputR2"
Write-Host "R3: $outputR3"
Write-Host "R4: $outputR4"
