# run_regime_gate_ablation_v1.ps1
# Regime gate ablation: control (no gate) vs variant (4 predeclared regime features)
# Predeclaration: research_papers/JEPA/REGIME_GATE_ABLATION_PREDECLARATION_V1.md

$ErrorActionPreference = "Stop"
Set-Location -Path $PSScriptRoot

$dataset = "tmp/event_option_dataset_execquote_causal1030_202501_202606_v3_physics/event_option_dataset.parquet"
$outputControl = "research_papers/JEPA/results/_diagnostics/regime_gate_ablation_control_202601_202605_seed20260618_v1"
$outputVariant = "research_papers/JEPA/results/_diagnostics/regime_gate_ablation_gated_202601_202605_seed20260618_v1"

# ── Common arguments ──
$commonArgs = @(
    "--data", $dataset,
    "--start-month", "202601",
    "--end-month", "202605",
    "--val-months", "3",
    "--seed", "20260618",
    "--tickers", "SPXW", "QQQ", "SPY",
    "--profile-kind", "win",
    "--ticker-profile-allowlists", "SPXW=d25-win", "QQQ=d35-win", "SPY=d35-win",
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

# ── Hash scripts before execution ──
Write-Host "=== Hashing scripts ==="
$selectorHash = (Get-FileHash "neural/jepa/walkforward_event_option_profile_selector.py" -Algorithm SHA256).Hash
Write-Host "selector_hash=$selectorHash"

# ── ARM 1: Control (no regime gate) ──
Write-Host ""
Write-Host "=== ARM 1: CONTROL (no regime gate) ==="
Write-Host "Output: $outputControl"

python neural/jepa/walkforward_event_option_profile_selector.py `
    @commonArgs `
    --output-dir $outputControl
if ($LASTEXITCODE -ne 0) {
    Write-Error "Control arm failed with exit code $LASTEXITCODE"
    exit 1
}

# ── ARM 2: Variant (4 predeclared regime features) ──
Write-Host ""
Write-Host "=== ARM 2: VARIANT (regime gate with 4 features) ==="
Write-Host "Output: $outputVariant"

# Per-ticker regime features:
# SPXW uses d25 bucket features, QQQ/SPY use d35
# Common: phys_abs_ret_5m_bps, ib_range_bps
# The selector runs per-ticker, so we include both d25 and d35 variants;
# whichever column exists in the ticker's prepared frame will be used.
python neural/jepa/walkforward_event_option_profile_selector.py `
    @commonArgs `
    --output-dir $outputVariant `
    --regime-gate-features `
        phys_d25_iv_skew_put_minus_call `
        phys_d35_iv_skew_put_minus_call `
        phys_d25_spread_mean `
        phys_d35_spread_mean `
        phys_abs_ret_5m_bps `
        ib_range_bps
if ($LASTEXITCODE -ne 0) {
    Write-Error "Variant arm failed with exit code $LASTEXITCODE"
    exit 1
}

# ── Summary ──
Write-Host ""
Write-Host "=== BOTH ARMS COMPLETE ==="
Write-Host "Control: $outputControl"
Write-Host "Variant: $outputVariant"
Write-Host ""
Write-Host "Next: run paired analysis comparing the two arms."
