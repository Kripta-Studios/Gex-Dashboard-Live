[CmdletBinding()]
param()
$ErrorActionPreference = "Stop"
$PSNativeCommandUseErrorActionPreference = $true
$Dataset = "tmp/event_option_dataset_execquote_causal1030_202201_202512_pairwise_v1/event_option_dataset.parquet"
$ExpectedHash = "d3c37b5f4511787ec19cf4478790377562b2b6c913185a2425f1b0cef7a3a408"
$Script = "neural/jepa/walkforward_pairwise_magnitude_weighted_side_v1.py"
$Test = "tests/test_pairwise_magnitude_weighted_side.py"
$Output = "research_papers/JEPA/results/_diagnostics/pairwise_magnitude_weighted_side_v1"
if ((git rev-parse HEAD).Trim() -ne (git rev-parse origin/main).Trim()) { throw "HEAD != origin/main" }
git diff --quiet HEAD
git diff --cached --quiet
if (Test-Path -LiteralPath $Output) { throw "Output exists" }
if ((Get-FileHash $Dataset -Algorithm SHA256).Hash.ToLowerInvariant() -ne $ExpectedHash) { throw "Dataset hash mismatch" }
python -m py_compile $Script $Test
python -m pytest -q $Test --basetemp C:\tmp\pytest-pairwise-weighted-v1
python $Script --dataset $Dataset --output-dir $Output
$manifest = [ordered]@{
    git_head = (git rev-parse HEAD).Trim()
    dataset_sha256 = $ExpectedHash
    script_sha256 = (Get-FileHash $Script -Algorithm SHA256).Hash.ToLowerInvariant()
    test_sha256 = (Get-FileHash $Test -Algorithm SHA256).Hash.ToLowerInvariant()
    runner_sha256 = (Get-FileHash $PSCommandPath -Algorithm SHA256).Hash.ToLowerInvariant()
    contains_2026 = $false
    production_modified = $false
    adaptive_reuse_not_promotable = $true
    exit_code = 0
}
$manifest | ConvertTo-Json | Set-Content (Join-Path $Output "execution_manifest.json") -Encoding utf8
