[CmdletBinding()]
param()

$ErrorActionPreference = "Stop"
$PSNativeCommandUseErrorActionPreference = $true
$Dataset = "tmp/event_option_dataset_execquote_causal1030_202201_202512_pairwise_v1/event_option_dataset.parquet"
$ExpectedHash = "d3c37b5f4511787ec19cf4478790377562b2b6c913185a2425f1b0cef7a3a408"
$Script = "neural/jepa/diagnose_pairwise_inner_grid_v1.py"
$Test = "tests/test_pairwise_inner_grid_diagnostic.py"
$Output = "research_papers/JEPA/results/_diagnostics/pairwise_inner_grid_failure_decomposition_v1"

$head = (git rev-parse HEAD).Trim()
$origin = (git rev-parse origin/main).Trim()
if ($head -ne $origin) { throw "HEAD must equal origin/main" }
git diff --quiet HEAD
git diff --cached --quiet
if (Test-Path -LiteralPath $Output) { throw "Output exists: $Output" }
$actualHash = (Get-FileHash -LiteralPath $Dataset -Algorithm SHA256).Hash.ToLowerInvariant()
if ($actualHash -ne $ExpectedHash) { throw "Dataset hash mismatch" }
python -m py_compile $Script $Test
python -m pytest -q $Test --basetemp C:\tmp\pytest-pairwise-inner-grid-v1
python $Script --dataset $Dataset --output-dir $Output

$manifestPath = Join-Path $Output "execution_manifest.json"
$manifest = [ordered]@{
    git_head = $head
    dataset_sha256 = $actualHash
    script_sha256 = (Get-FileHash -LiteralPath $Script -Algorithm SHA256).Hash.ToLowerInvariant()
    test_sha256 = (Get-FileHash -LiteralPath $Test -Algorithm SHA256).Hash.ToLowerInvariant()
    runner_sha256 = (Get-FileHash -LiteralPath $PSCommandPath -Algorithm SHA256).Hash.ToLowerInvariant()
    outer_labels_scored = $false
    contains_2026 = $false
    production_modified = $false
    exit_code = 0
}
$manifest | ConvertTo-Json -Depth 4 | Set-Content -LiteralPath $manifestPath -Encoding utf8
Write-Host "Diagnostic complete: $Output"
