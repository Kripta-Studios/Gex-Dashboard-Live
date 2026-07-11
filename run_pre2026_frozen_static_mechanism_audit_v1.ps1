$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$root = $PSScriptRoot
Set-Location -LiteralPath $root
$env:PYTHONPATH = "."
$env:PYTHONHASHSEED = "20260617"
$env:OMP_NUM_THREADS = "28"
$env:MKL_NUM_THREADS = "28"

$data = "tmp/event_option_dataset_execquote_causal1030_202501_202606_v3_physics/event_option_dataset.parquet"
$script = "neural/jepa/audit_pre2026_frozen_static_mechanism.py"
$test = "tests/test_audit_pre2026_frozen_static_mechanism.py"
$output = "research_papers/JEPA/results/_diagnostics/pre2026_frozen_static_mechanism_reverse_audit_202510_202512_v1"
$expected = @{
    $data = "E6A19EFBA1EDB055C733AAB4967843F7A4B5F1D2C8238A7A243FC5BBC2251903"
    $script = "1501013CF4B8FF0BD66F308DFF89003D341C4B6A86650CD15B084F7CCD6F25BD"
    $test = "95FD037FBDEA0398706E49C8AF513E077620E8999165F96F37D936A2678D8BDF"
}
foreach ($path in $expected.Keys) {
    $actual = (Get-FileHash -Algorithm SHA256 -LiteralPath $path).Hash
    if ($actual -ne $expected[$path]) {
        throw "Predeclared SHA-256 mismatch for ${path}: expected $($expected[$path]), got ${actual}"
    }
}
if (Test-Path -LiteralPath $output) { throw "Refusing to reuse output: $output" }

python -m pytest -q $test
if ($LASTEXITCODE -ne 0) { throw "Pre-2026 static mechanism audit test failed" }

python $script --data $data --output-dir $output --jobs 28 --seed 20260617
if ($LASTEXITCODE -ne 0) { throw "Pre-2026 frozen static mechanism audit failed" }

Write-Output "Pre-2026 frozen static mechanism reverse audit completed: $output"
