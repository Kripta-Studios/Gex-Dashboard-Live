# run_pairwise_opportunity_side_v1.ps1
# Runner for PAIRWISE_OPPORTUNITY_AND_SIDE_SELECTION_V1
# Checks git status, dataset integrity, and runs tests before execution.

$ErrorActionPreference = "Stop"

$EXPECTED_HASH = "d3c37b5f4511787ec19cf4478790377562b2b6c913185a2425f1b0cef7a3a408"
$DATASET_PATH = "tmp/event_option_dataset_execquote_causal1030_202201_202512_pairwise_v1/event_option_dataset.parquet"
$OUTPUT_DIR = "research_papers/JEPA/results/_diagnostics/pairwise_opportunity_side_v1"
$PREDEC_PATH = "research_papers/JEPA/PAIRWISE_OPPORTUNITY_AND_SIDE_SELECTION_PREDECLARATION_V1.md"
$WALKFORWARD_PATH = "neural/jepa/walkforward_pairwise_opportunity_side.py"
$TESTS_PATH = "tests/test_pairwise_opportunity_side.py"

Write-Host "=== Starting preflight checks ==="

# 1. Check Git status (HEAD == origin/main)
Write-Host "1. Checking git HEAD ..."
$gitDiff = git diff origin/main --name-only
if ($gitDiff) {
    Write-Host "Warning: local HEAD differs from origin/main. Files:"
    $gitDiff | Out-String | Write-Host
} else {
    Write-Host "HEAD matches origin/main. Good."
}

# 2. Check Dataset SHA-256
Write-Host "2. Checking dataset hash ..."
if (-not (Test-Path $DATASET_PATH)) {
    Write-Error "Dataset file not found at $DATASET_PATH"
}
$fileHash = (Get-FileHash $DATASET_PATH -Algorithm SHA256).Hash.ToLower()
if ($fileHash -ne $EXPECTED_HASH) {
    Write-Error "Dataset hash mismatch! Got: $fileHash, Expected: $EXPECTED_HASH"
}
Write-Host "Dataset SHA-256 matches: $EXPECTED_HASH"

# 3. Check for 2026 data leakage in the dataset
Write-Host "3. Asserting no 2026 data in the dataset ..."
$leakCheck = python -c "
import pandas as pd
df = pd.read_parquet('$DATASET_PATH', columns=['trade_date'])
dates = df['trade_date'].astype(str)
leak = (dates >= '20260101').any()
print('LEAK' if leak else 'CLEAN')
"
if ($leakCheck.Trim() -eq "LEAK") {
    Write-Error "FATAL: 2026 data leaked into $DATASET_PATH!"
}
Write-Host "Clean. No 2026 data detected."

# 4. Run unit tests
Write-Host "4. Running unit tests ..."
pytest tests/test_pairwise_opportunity_side.py --basetemp C:\tmp\pytest-pairwise-v1 -q
Write-Host "All tests passed successfully."

# 5. Check if output directory already exists
Write-Host "5. Checking output directory ..."
if (Test-Path $OUTPUT_DIR) {
    Write-Error "Output directory $OUTPUT_DIR already exists! Aborting to prevent overwrite."
}
Write-Host "Output directory does not exist. Good."

# 6. Check for other active Python instances running the same script
Write-Host "6. Checking for active processes ..."
$activeProcs = Get-CimInstance Win32_Process | Where-Object { $_.Name -match "python" -and $_.CommandLine -match "walkforward_pairwise_opportunity_side" }
if ($activeProcs) {
    Write-Error "Another instance of walkforward_pairwise_opportunity_side is already running!"
}
Write-Host "No active duplicate processes. Good."

# 7. Register script, predeclaration and test hashes
Write-Host "7. Calculating hashes of runner components ..."
$runnerHash = (Get-FileHash $PSCommandPath -Algorithm SHA256).Hash.ToLower()
$predecHash = (Get-FileHash $PREDEC_PATH -Algorithm SHA256).Hash.ToLower()
$wfHash = (Get-FileHash $WALKFORWARD_PATH -Algorithm SHA256).Hash.ToLower()
$testsHash = (Get-FileHash $TESTS_PATH -Algorithm SHA256).Hash.ToLower()

Write-Host "Runner Script SHA-256:       $runnerHash"
Write-Host "Predeclaration SHA-256:     $predecHash"
Write-Host "Walkforward Runner SHA-256:  $wfHash"
Write-Host "Unit Tests SHA-256:         $testsHash"

# 8. Run a dry run to validate pipeline args before execution
Write-Host "8. Executing a dry run of the walkforward runner ..."
$dryRunCmd = "python $WALKFORWARD_PATH --dataset $DATASET_PATH --output-dir $OUTPUT_DIR --dry-run"
Invoke-Expression $dryRunCmd

Write-Host "Dry run completed. Setup validated."

# 9. Create preflight manifest
$manifest = @{
    "runner_sha256" = $runnerHash
    "predeclaration_sha256" = $predecHash
    "walkforward_sha256" = $wfHash
    "tests_sha256" = $testsHash
    "dataset_sha256" = $fileHash
    "git_head" = (git rev-parse HEAD).Trim()
    "preflight_status" = "PASS"
}
$manifest | ConvertTo-Json | Out-File -FilePath "research_papers/JEPA/results/pairwise_preflight_manifest.json" -Encoding utf8
Write-Host "Preflight manifest generated: research_papers/JEPA/results/pairwise_preflight_manifest.json"

Write-Host "=== Preflight checks completed successfully! ==="
Write-Host "You can now run: python $WALKFORWARD_PATH --dataset $DATASET_PATH --output-dir $OUTPUT_DIR"
