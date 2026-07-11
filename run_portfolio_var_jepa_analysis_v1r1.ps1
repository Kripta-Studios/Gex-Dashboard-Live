$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$root = $PSScriptRoot
Set-Location -LiteralPath $root

$deterministicOut = "research_papers/JEPA/results/_diagnostics/portfolio_var_jepa_deterministic_flat_oof_202601_202605_seed20260618_v1"
$variationalOut = "research_papers/JEPA/results/_diagnostics/portfolio_var_jepa_variational_flat_oof_202601_202605_seed20260618_v1"
$analysisOut = "research_papers/JEPA/results/_diagnostics/portfolio_var_jepa_deterministic_vs_variational_analysis_202601_202605_seed20260618_v1"
$analyzer = "neural/jepa/analyze_event_option_portfolio_var_jepa.py"

$expectedHashes = @{
    $analyzer = "EC213650670060170F18505C833CE54CA6FEE77DD4D778822092040C4C3E515C"
    "$deterministicOut/metadata.json" = "7417D6CC427E100607F05B96B8627C31FD979268A8333FF66648AB6EA3B0013A"
    "$deterministicOut/selected_folds.csv" = "0D89FC8E22D8C65816CA16A473E1878D55F7C378FB8E8997A7F531DDC1070AD7"
    "$deterministicOut/representation_ticker_month.csv" = "4DE4481361863617FD622AE0373F5E4447C4349330B78CB5BB80BB1A8C351271"
    "$variationalOut/metadata.json" = "EC211E50CA541E8A9FB3373DFC7352D9F2C30163F307D853B59D104D92DE6FAC"
    "$variationalOut/selected_folds.csv" = "F6A7E33EFDE8BFFF23F7927294595BE76B167519F11D8C9E1E74A42F84A9D45E"
    "$variationalOut/representation_ticker_month.csv" = "E4D5E1C35EFBA0A6429EE62EF4A1D0AC801E024B768BF645FBC94633373B12DD"
}
foreach ($path in $expectedHashes.Keys) {
    $actual = (Get-FileHash -Algorithm SHA256 -LiteralPath $path).Hash
    if ($actual -ne $expectedHashes[$path]) {
        throw "Frozen analysis input mismatch for ${path}: expected $($expectedHashes[$path]), got ${actual}"
    }
}
if (Test-Path -LiteralPath $analysisOut) {
    throw "Refusing to reuse analysis output directory: ${analysisOut}"
}

python -m pytest -q tests/test_analyze_event_option_portfolio_var_jepa.py
if ($LASTEXITCODE -ne 0) { throw "Portfolio Var-JEPA analyzer tests failed" }
python $analyzer --deterministic-dir $deterministicOut --variational-dir $variationalOut --output-dir $analysisOut
if ($LASTEXITCODE -ne 0) { throw "Portfolio Var-JEPA paired analysis failed" }

Write-Output "Portfolio Var-JEPA analysis v1r1 completed: $analysisOut"
