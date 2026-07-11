$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$root = $PSScriptRoot
Set-Location -LiteralPath $root
$env:PYTHONHASHSEED = "20260618"
$env:CUBLAS_WORKSPACE_CONFIG = ":4096:8"

$spaces = "research_papers/JEPA/results/_diagnostics/adajepa_shadow_coherent_spaces_202601_202605_seed20260618_v1"
$manifestPath = Join-Path $spaces "manifest.json"
$script = "neural/jepa/evaluate_adajepa_shadow_adapter.py"
$output = "research_papers/JEPA/results/_diagnostics/adajepa_shadow_adapter_202601_202605_lr005_v1"
$expectedHashes = @{
    $manifestPath = "F398B1105C848C45D9BEAE0C156646B8B17207BEA5D08660BB359C099337F7B8"
    $script = "DE4BFBD9D3D324EF342B153A78A2398B8598AA2F50EDAE673DB1AF8A421AADEB"
}
foreach ($path in $expectedHashes.Keys) {
    $actual = (Get-FileHash -Algorithm SHA256 -LiteralPath $path).Hash
    if ($actual -ne $expectedHashes[$path]) { throw "Predeclared hash mismatch for ${path}" }
}
$manifest = Get-Content -LiteralPath $manifestPath -Raw | ConvertFrom-Json
if ($manifest.Count -ne 5) { throw "Expected five coherent-space folds" }
foreach ($fold in $manifest) {
    $actual = (Get-FileHash -Algorithm SHA256 -LiteralPath $fold.transitions_path).Hash
    if ($actual -ne $fold.transitions_sha256) { throw "Transition hash mismatch for $($fold.test_month)" }
}
if (Test-Path -LiteralPath $output) { throw "Refusing to reuse AdaJEPA shadow output: ${output}" }

python -m pytest -q tests/test_evaluate_adajepa_shadow_adapter.py tests/test_export_event_phys_td_shadow_transitions.py
if ($LASTEXITCODE -ne 0) { throw "AdaJEPA shadow adapter tests failed" }
python $script `
    --spaces-dir $spaces `
    --output-dir $output `
    --learning-rate 0.05 `
    --grad-clip 1.0 `
    --max-parameter-norm 0.5 `
    --device cuda
if ($LASTEXITCODE -ne 0) { throw "AdaJEPA shadow adapter evaluation failed" }

Write-Output "AdaJEPA shadow adapter v1 completed: $output"
