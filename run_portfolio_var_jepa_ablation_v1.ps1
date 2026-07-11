$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$root = $PSScriptRoot
Set-Location -LiteralPath $root
$env:CUBLAS_WORKSPACE_CONFIG = ":4096:8"
$env:PYTHONHASHSEED = "20260618"

$data = "research_papers/JEPA/results/_diagnostics/ptdj_ablation_flat_history_2025_h1_3_6_12_causal_202505_202605_v1/event_option_dataset.parquet"
$trainer = "neural/jepa/walkforward_event_option_portfolio_var_jepa.py"
$analyzer = "neural/jepa/analyze_event_option_portfolio_var_jepa.py"
$deterministicOut = "research_papers/JEPA/results/_diagnostics/portfolio_var_jepa_deterministic_flat_oof_202601_202605_seed20260618_v1"
$variationalOut = "research_papers/JEPA/results/_diagnostics/portfolio_var_jepa_variational_flat_oof_202601_202605_seed20260618_v1"
$analysisOut = "research_papers/JEPA/results/_diagnostics/portfolio_var_jepa_deterministic_vs_variational_analysis_202601_202605_seed20260618_v1"

$expectedHashes = @{
    $data = "39203C83F47A60AFB2AB7951201CBEB3B9098F4238169F0D716649571667DA2F"
    $trainer = "21C011C6F66906E90B128E091794FC92497739568DC10F34EBB6F9175B45F0A1"
    $analyzer = "A5635C14FF39A66C4573A80F1C75165A30D50273F66887B25D8316606D9C35B2"
}
foreach ($path in $expectedHashes.Keys) {
    $actual = (Get-FileHash -Algorithm SHA256 -LiteralPath $path).Hash
    if ($actual -ne $expectedHashes[$path]) {
        throw "Predeclared SHA-256 mismatch for ${path}: expected $($expectedHashes[$path]), got ${actual}"
    }
}
foreach ($path in @($deterministicOut, $variationalOut, $analysisOut)) {
    if (Test-Path -LiteralPath $path) {
        throw "Refusing to reuse predeclared output directory: ${path}"
    }
}

python -m pytest -q tests/test_walkforward_event_option_portfolio_var_jepa.py tests/test_analyze_event_option_portfolio_var_jepa.py
if ($LASTEXITCODE -ne 0) { throw "Portfolio Var-JEPA focused tests failed" }

$common = @(
    "--data", $data,
    "--start-month", "202601",
    "--end-month", "202605",
    "--val-months", "3",
    "--min-train-rows", "5000",
    "--clip-return", "2.0",
    "--hidden-dim", "128",
    "--latent-dim", "16",
    "--dropout", "0.1",
    "--epochs", "40",
    "--batch-size", "512",
    "--infer-batch-size", "4096",
    "--learning-rate", "0.001",
    "--weight-decay", "0.000001",
    "--grad-clip", "1.0",
    "--kl-weight", "1.0",
    "--kl-anneal-epochs", "20",
    "--threshold-grid", "-1000000000", "-0.10", "-0.05", "0.0", "0.05", "0.10", "0.15", "0.20",
    "--threshold-quantiles", "0.4", "0.5", "0.6", "0.7", "0.8", "0.9",
    "--min-val-trades", "54",
    "--min-month-trades", "18",
    "--min-val-pf", "1.3",
    "--min-val-win-rate", "0.5",
    "--min-val-positive-month-rate", "1.0",
    "--min-call-rate", "0.0",
    "--max-call-rate", "1.0",
    "--daily-win-weight", "0.25",
    "--top5-share-penalty", "0.10",
    "--device", "cuda",
    "--seed", "20260618",
    "--deterministic"
)

foreach ($arm in @("deterministic", "variational")) {
    $output = if ($arm -eq "deterministic") { $deterministicOut } else { $variationalOut }
    python $trainer --arm $arm --output-dir $output @common
    if ($LASTEXITCODE -ne 0) { throw "Portfolio Var-JEPA arm failed: ${arm}" }
}

python $analyzer --deterministic-dir $deterministicOut --variational-dir $variationalOut --output-dir $analysisOut
if ($LASTEXITCODE -ne 0) { throw "Portfolio Var-JEPA paired analysis failed" }

Write-Output "Portfolio Var-JEPA v1 completed: $analysisOut"
