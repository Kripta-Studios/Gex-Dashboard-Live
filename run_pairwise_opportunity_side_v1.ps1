# run_pairwise_opportunity_side_v1.ps1
# Reproducible runner for PAIRWISE_OPPORTUNITY_AND_SIDE_SELECTION_V1.

[CmdletBinding()]
param(
    [Switch]$PreflightOnly,
    [Switch]$Execute
)

$ErrorActionPreference = "Stop"
$PSNativeCommandUseErrorActionPreference = $true

if ([int]$PreflightOnly.IsPresent + [int]$Execute.IsPresent -ne 1) {
    throw "FATAL: specify exactly one explicit mode: -PreflightOnly or -Execute."
}

$ExpectedDatasetHash = "d3c37b5f4511787ec19cf4478790377562b2b6c913185a2425f1b0cef7a3a408"
$ExpectedFeatureHash = "fa2057653ed0327b7f84a165c25f6e6d31e31b3b05c5591593e9c0bd3056d50e"
$DatasetPath = "tmp/event_option_dataset_execquote_causal1030_202201_202512_pairwise_v1/event_option_dataset.parquet"
$PredeclarationPath = "research_papers/JEPA/PAIRWISE_OPPORTUNITY_AND_SIDE_SELECTION_PREDECLARATION_V1.md"
$WalkforwardPath = "neural/jepa/walkforward_pairwise_opportunity_side.py"
$TestsPath = "tests/test_pairwise_opportunity_side.py"
$RunnerPath = "run_pairwise_opportunity_side_v1.ps1"
$PreflightOutput = "research_papers/JEPA/results/_diagnostics/pairwise_opportunity_side_v1_preflight"
$RealOutput = "research_papers/JEPA/results/_diagnostics/pairwise_opportunity_side_v1"
$ExperimentManifestPath = Join-Path $PreflightOutput "experiment_file_manifest.json"
$PreflightManifestPath = Join-Path $PreflightOutput "pairwise_preflight_manifest.json"

Write-Host "=== PAIRWISE V1 reproducibility checks ==="

$head = (git rev-parse HEAD).Trim()
$originMain = (git rev-parse origin/main).Trim()
if ($head -ne $originMain) {
    throw "FATAL: HEAD ($head) does not equal origin/main ($originMain)."
}

git diff --quiet HEAD
git diff --cached --quiet
Write-Host "Git commit is clean and synchronized: $head"

if (Test-Path -LiteralPath $RealOutput) {
    throw "FATAL: real output already exists: $RealOutput"
}
if (-not (Test-Path -LiteralPath $DatasetPath)) {
    throw "FATAL: sealed dataset not found: $DatasetPath"
}

$datasetHash = (Get-FileHash -LiteralPath $DatasetPath -Algorithm SHA256).Hash.ToLowerInvariant()
if ($datasetHash -ne $ExpectedDatasetHash) {
    throw "FATAL: dataset hash mismatch. Actual=$datasetHash Expected=$ExpectedDatasetHash"
}

$datasetAudit = python -c @"
import json
import pandas as pd
p = r'$DatasetPath'
d = pd.read_parquet(p, columns=['trade_date'])['trade_date'].astype(str)
print(json.dumps({'rows': int(len(d)), 'date_min': d.min(), 'date_max': d.max(), 'contains_2026': bool((d >= '20260101').any())}))
"@
$datasetAuditObject = $datasetAudit | ConvertFrom-Json
if ($datasetAuditObject.contains_2026 -or $datasetAuditObject.date_max -gt "20251231") {
    throw "FATAL: the sealed dataset contains 2026."
}
if ($datasetAuditObject.rows -ne 97625) {
    throw "FATAL: unexpected dataset row count: $($datasetAuditObject.rows)"
}
Write-Host "Dataset sealed: $($datasetAuditObject.rows) rows, $($datasetAuditObject.date_min)..$($datasetAuditObject.date_max)"

python -m py_compile $WalkforwardPath $TestsPath
python -m pytest -q $TestsPath --basetemp C:\tmp\pytest-pairwise-v1-final

$duplicates = Get-CimInstance Win32_Process | Where-Object {
    $_.Name -match "python" -and $_.CommandLine -match "walkforward_pairwise_opportunity_side" -and $_.CommandLine -notmatch "py_compile"
}
if ($duplicates) {
    throw "FATAL: another pairwise walk-forward process is active."
}

$runnerHash = (Get-FileHash -LiteralPath $RunnerPath -Algorithm SHA256).Hash.ToLowerInvariant()
$predeclarationHash = (Get-FileHash -LiteralPath $PredeclarationPath -Algorithm SHA256).Hash.ToLowerInvariant()
$walkforwardHash = (Get-FileHash -LiteralPath $WalkforwardPath -Algorithm SHA256).Hash.ToLowerInvariant()
$testsHash = (Get-FileHash -LiteralPath $TestsPath -Algorithm SHA256).Hash.ToLowerInvariant()
$featureHash = (python -c @"
import sys
sys.path.insert(0, r'neural/jepa')
from walkforward_pairwise_opportunity_side import COMMON_FEATURES, DIFF_METRICS, CHANGE_LAGS, compute_feature_hash
diffs = [f'{name}_diff' for name in DIFF_METRICS]
changes = [f'{name}_chg_{label}' for name in diffs if name != 'oi_diff' for _, label in CHANGE_LAGS]
print(compute_feature_hash(COMMON_FEATURES + diffs + changes))
"@).Trim()
if ($featureHash -ne $ExpectedFeatureHash) {
    throw "FATAL: feature hash mismatch. Actual=$featureHash Expected=$ExpectedFeatureHash"
}

if ($PreflightOnly) {
    if (Test-Path -LiteralPath $PreflightOutput) {
        Remove-Item -LiteralPath $PreflightOutput -Recurse -Force
    }
    New-Item -ItemType Directory -Path $PreflightOutput -Force | Out-Null

    # --dry-run returns before run_fold/model construction. Tests enforce this contract.
    python $WalkforwardPath --dataset $DatasetPath --output-dir $PreflightOutput --dry-run
    $foldArtifacts = @(Get-ChildItem -LiteralPath $PreflightOutput -Directory -ErrorAction SilentlyContinue)
    if ($foldArtifacts.Count -ne 0) {
        throw "FATAL: PreflightOnly created fold/model directories."
    }

    $experimentManifest = [ordered]@{
        files = @(
            [ordered]@{ path = $WalkforwardPath; sha256 = $walkforwardHash },
            [ordered]@{ path = $TestsPath; sha256 = $testsHash },
            [ordered]@{ path = $RunnerPath; sha256 = $runnerHash },
            [ordered]@{ path = $PredeclarationPath; sha256 = $predeclarationHash }
        )
    }
    $experimentManifest | ConvertTo-Json -Depth 5 | Set-Content -LiteralPath $ExperimentManifestPath -Encoding utf8
    $experimentManifestHash = (Get-FileHash -LiteralPath $ExperimentManifestPath -Algorithm SHA256).Hash.ToLowerInvariant()

    $preflightManifest = [ordered]@{
        schema_version = 1
        experiment = "PAIRWISE_OPPORTUNITY_AND_SIDE_SELECTION_V1"
        mode = "PreflightOnly"
        git_head = $head
        origin_main = $originMain
        manifest_generated_from_clean_commit = $true
        head_equals_origin_main = $true
        tracked_working_tree_clean = $true
        dataset_sha256 = $datasetHash
        dataset_rows = [int]$datasetAuditObject.rows
        dataset_date_min = [string]$datasetAuditObject.date_min
        dataset_date_max = [string]$datasetAuditObject.date_max
        contains_2026 = $false
        runner_sha256 = $runnerHash
        walkforward_sha256 = $walkforwardHash
        tests_sha256 = $testsHash
        predeclaration_sha256 = $predeclarationHash
        feature_hash = $featureHash
        experiment_file_manifest_sha256 = $experimentManifestHash
        scientific_cells_expected = 99
        scientific_cells_evaluated = 0
        degenerate_scientific_cells_detected = 0
        degenerate_detection_exercised_by_tests = $true
        models_trained = 0
        full_run_executed = $false
        real_output_absent = -not (Test-Path -LiteralPath $RealOutput)
        preflight_status = "PASS"
        unrelated_file_in_commit = "backtest/backtest_gbt_parquet.py"
        included_in_experiment_hash_scope = $false
    }
    $preflightManifest | ConvertTo-Json -Depth 5 | Set-Content -LiteralPath $PreflightManifestPath -Encoding utf8
    Write-Host "Preflight PASS: $PreflightManifestPath"
    Write-Host "No models trained; real output remains absent."
    exit 0
}

if (-not (Test-Path -LiteralPath $PreflightManifestPath)) {
    throw "FATAL: execute requires a successful PreflightOnly manifest at $PreflightManifestPath"
}
$preflight = Get-Content -LiteralPath $PreflightManifestPath -Raw | ConvertFrom-Json
if ($preflight.preflight_status -ne "PASS" -or $preflight.full_run_executed -ne $false) {
    throw "FATAL: preflight manifest is not a clean PASS."
}
foreach ($check in @(
    @("runner_sha256", $runnerHash),
    @("walkforward_sha256", $walkforwardHash),
    @("tests_sha256", $testsHash),
    @("predeclaration_sha256", $predeclarationHash),
    @("feature_hash", $featureHash),
    @("dataset_sha256", $datasetHash)
)) {
    if ([string]$preflight.($check[0]) -ne [string]$check[1]) {
        throw "FATAL: current $($check[0]) differs from the passed preflight."
    }
}

New-Item -ItemType Directory -Path $RealOutput -Force | Out-Null
$stdoutLog = Join-Path $RealOutput "real_run_stdout.log"
$stderrLog = Join-Path $RealOutput "real_run_stderr.log"
$processInfo = [System.Diagnostics.ProcessStartInfo]::new()
$processInfo.FileName = "python"
$processInfo.ArgumentList.Add($WalkforwardPath)
$processInfo.ArgumentList.Add("--dataset")
$processInfo.ArgumentList.Add($DatasetPath)
$processInfo.ArgumentList.Add("--output-dir")
$processInfo.ArgumentList.Add($RealOutput)
$processInfo.RedirectStandardOutput = $true
$processInfo.RedirectStandardError = $true
$processInfo.UseShellExecute = $false
$process = [System.Diagnostics.Process]::new()
$process.StartInfo = $processInfo
$process.Start() | Out-Null
$stdoutTask = $process.StandardOutput.ReadToEndAsync()
$stderrTask = $process.StandardError.ReadToEndAsync()
$process.WaitForExit()
$stdoutTask.Result | Set-Content -LiteralPath $stdoutLog -Encoding utf8
$stderrTask.Result | Set-Content -LiteralPath $stderrLog -Encoding utf8
if ($process.ExitCode -ne 0) {
    throw "FATAL: pairwise walk-forward failed with exit code $($process.ExitCode). See $stderrLog"
}

$runManifest = [ordered]@{
    schema_version = 1
    experiment = "PAIRWISE_OPPORTUNITY_AND_SIDE_SELECTION_V1"
    mode = "Execute"
    git_head = $head
    dataset_sha256 = $datasetHash
    runner_sha256 = $runnerHash
    walkforward_sha256 = $walkforwardHash
    tests_sha256 = $testsHash
    predeclaration_sha256 = $predeclarationHash
    feature_hash = $featureHash
    preflight_manifest_sha256 = (Get-FileHash -LiteralPath $PreflightManifestPath -Algorithm SHA256).Hash.ToLowerInvariant()
    full_run_executed = $true
    exit_code = 0
}
$runManifest | ConvertTo-Json -Depth 5 | Set-Content -LiteralPath (Join-Path $RealOutput "run_manifest.json") -Encoding utf8
Write-Host "Execute completed: $RealOutput"
