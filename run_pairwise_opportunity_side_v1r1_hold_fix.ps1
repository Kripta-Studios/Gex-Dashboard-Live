[CmdletBinding()]
param()

$ErrorActionPreference = "Stop"
$PSNativeCommandUseErrorActionPreference = $true
$Dataset = "tmp/event_option_dataset_execquote_causal1030_202201_202512_pairwise_v1/event_option_dataset.parquet"
$ExpectedHash = "d3c37b5f4511787ec19cf4478790377562b2b6c913185a2425f1b0cef7a3a408"
$Walkforward = "neural/jepa/walkforward_pairwise_opportunity_side.py"
$Tests = @("tests/test_pairwise_opportunity_side.py", "tests/test_pairwise_inner_grid_diagnostic.py")
$Output = "research_papers/JEPA/results/_diagnostics/pairwise_opportunity_side_v1r1_hold_fix"

$head = (git rev-parse HEAD).Trim()
$origin = (git rev-parse origin/main).Trim()
if ($head -ne $origin) { throw "HEAD must equal origin/main" }
git diff --quiet HEAD
git diff --cached --quiet
if (Test-Path -LiteralPath $Output) { throw "Output exists: $Output" }
$datasetHash = (Get-FileHash -LiteralPath $Dataset -Algorithm SHA256).Hash.ToLowerInvariant()
if ($datasetHash -ne $ExpectedHash) { throw "Dataset hash mismatch" }

python -m py_compile $Walkforward $Tests
python -m pytest -q $Tests --basetemp C:\tmp\pytest-pairwise-v1r1-hold-fix
python $Walkforward --dataset $Dataset --output-dir $Output

$manifest = [ordered]@{
    correction = "PAIRWISE_V1R1_HOLD_DURATION_CORRECTION"
    git_head = $head
    dataset_sha256 = $datasetHash
    walkforward_sha256 = (Get-FileHash -LiteralPath $Walkforward -Algorithm SHA256).Hash.ToLowerInvariant()
    tests_sha256 = @($Tests | ForEach-Object { (Get-FileHash -LiteralPath $_ -Algorithm SHA256).Hash.ToLowerInvariant() })
    runner_sha256 = (Get-FileHash -LiteralPath $PSCommandPath -Algorithm SHA256).Hash.ToLowerInvariant()
    exit_minutes_semantics = "elapsed_duration_minutes"
    full_run_executed = $true
    contains_2026 = $false
    production_modified = $false
    exit_code = 0
}
$manifest | ConvertTo-Json -Depth 4 | Set-Content -LiteralPath (Join-Path $Output "v1r1_manifest.json") -Encoding utf8
Write-Host "V1r1 completed: $Output"
