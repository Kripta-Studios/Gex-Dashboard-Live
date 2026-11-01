$ErrorActionPreference = 'Stop'

$Repo = 'C:\Users\Álvaro Schwiedop\Desktop\KriptaStudios\Gex-Dashboard-Live'
$Week = Join-Path $Repo 'research_papers\JEPA\weekly_multiday_20261101'
$Code = 'evaluate_weekly_daily_adaptation.py'
$Tests = 'test_evaluate_weekly_daily_adaptation.py'
$GateHelper = Join-Path $Repo 'research_papers\JEPA\level_oracle_20261018\launch_monthly_test_index_v2_audit_20261024.py'
$Preparation = 'D:\GexResearchArtifacts\weekly_multiday_20261101\daily_adaptation_preparation_01'
$Attempt01 = Join-Path $Preparation 'attempt01'
$Attempt = Join-Path $Preparation 'attempt02'
$ExpectedCode = '536a581d8295362b3374dd8c5db2224095f8afe66c5b0e9ae895cf08b18d4f2e'
$ExpectedTests = 'fa199a2a6339cf73911cc6f818c73f655cce1931e222733c041bff82b23e661e'
$ExpectedGate = '3cfe55a6a2926007d91d44215c8a7c0a28801efaca189fcf306c275e352ed046'

if (-not (Test-Path -LiteralPath $Attempt01 -PathType Container)) {
    throw 'Preserved attempt01 is required.'
}
if (Test-Path -LiteralPath $Attempt) {
    throw 'attempt02 already exists; automatic retry/adoption is forbidden.'
}
New-Item -ItemType Directory -Path $Attempt | Out-Null

$CodePath = Join-Path $Week $Code
$TestsPath = Join-Path $Week $Tests
if ((Get-FileHash -LiteralPath $CodePath -Algorithm SHA256).Hash.ToLowerInvariant() -ne $ExpectedCode) {
    throw 'Producer code pin mismatch.'
}
if ((Get-FileHash -LiteralPath $TestsPath -Algorithm SHA256).Hash.ToLowerInvariant() -ne $ExpectedTests) {
    throw 'Producer tests pin mismatch.'
}
if ((Get-FileHash -LiteralPath $GateHelper -Algorithm SHA256).Hash.ToLowerInvariant() -ne $ExpectedGate) {
    throw 'Official gate helper pin mismatch.'
}

Copy-Item -LiteralPath $CodePath -Destination (Join-Path $Attempt "$Code.before_test")
Copy-Item -LiteralPath $TestsPath -Destination (Join-Path $Attempt "$Tests.before_test")
Copy-Item -LiteralPath $PSCommandPath -Destination (Join-Path $Attempt 'launch_attempt02.ps1.snapshot')

$ThreadVariables = [ordered]@{
    ARROW_NUM_THREADS = '1'
    BLIS_NUM_THREADS = '1'
    MKL_NUM_THREADS = '1'
    NUMEXPR_NUM_THREADS = '1'
    OMP_NUM_THREADS = '1'
    OPENBLAS_NUM_THREADS = '1'
    POLARS_MAX_THREADS = '1'
    VECLIB_MAXIMUM_THREADS = '1'
}
foreach ($Entry in $ThreadVariables.GetEnumerator()) {
    [Environment]::SetEnvironmentVariable($Entry.Key, $Entry.Value, 'Process')
}
[Environment]::SetEnvironmentVariable('CUDA_VISIBLE_DEVICES', '-1', 'Process')
$Parent = [System.Diagnostics.Process]::GetCurrentProcess()
$Parent.ProcessorAffinity = [IntPtr]1
$Parent.ProcessorAffinity.ToInt64() | Out-File -LiteralPath (Join-Path $Attempt 'actual_affinity_mask.txt') -Encoding ascii

$GateCode = "import importlib.util,json; p=r'''$GateHelper'''; s=importlib.util.spec_from_file_location('official_gate',p); m=importlib.util.module_from_spec(s); s.loader.exec_module(m); v=m.observation(); print(json.dumps(v,sort_keys=True)); m.gate(v)"
& python -c $GateCode 1> (Join-Path $Attempt 'preflight_stdout.txt') 2> (Join-Path $Attempt 'preflight_stderr.txt')
$GateExit = $LASTEXITCODE
$GateExit | Out-File -LiteralPath (Join-Path $Attempt 'preflight_exit_code.txt') -Encoding ascii
$Resources = Get-Content -LiteralPath (Join-Path $Attempt 'preflight_stdout.txt') -Raw | ConvertFrom-Json
$Preflight = [ordered]@{
    observed_utc = (Get-Date).ToUniversalTime().ToString('o')
    gate_helper = [ordered]@{ path = $GateHelper; sha256 = $ExpectedGate }
    resources = $Resources
    parent_pid = $PID
    parent_cpu_affinity = @(0)
    cuda_visible_devices = '-1'
    thread_variables = $ThreadVariables
    pins = [ordered]@{
        code = [ordered]@{ path = $CodePath; bytes = (Get-Item -LiteralPath $CodePath).Length; sha256 = $ExpectedCode }
        tests = [ordered]@{ path = $TestsPath; bytes = (Get-Item -LiteralPath $TestsPath).Length; sha256 = $ExpectedTests }
        launcher = [ordered]@{ path = $PSCommandPath; bytes = (Get-Item -LiteralPath $PSCommandPath).Length; sha256 = (Get-FileHash -LiteralPath $PSCommandPath -Algorithm SHA256).Hash.ToLowerInvariant() }
    }
}
$Preflight | ConvertTo-Json -Depth 8 | Out-File -LiteralPath (Join-Path $Attempt 'preflight_metadata.json') -Encoding utf8
if ($GateExit -ne 0) {
    [ordered]@{
        status = 'RESOURCE_GATE_REJECTED_BEFORE_FIXTURES'
        attempt = 'attempt02'
        gate_exit_code = $GateExit
        resources = $Resources
        compile_executed = $false
        ruff_executed = $false
        pytest_executed = $false
        retry = $false
        recorded_utc = (Get-Date).ToUniversalTime().ToString('o')
    } | ConvertTo-Json -Depth 6 | Out-File -LiteralPath (Join-Path $Attempt 'failure_receipt.json') -Encoding utf8
    throw "Official resource gate rejected attempt02 with exit $GateExit."
}

$RetainedProcesses = [System.Collections.Generic.List[System.Diagnostics.Process]]::new()

function Invoke-RetainedChild {
    param(
        [Parameter(Mandatory = $true)][string]$Name,
        [Parameter(Mandatory = $true)][string[]]$Arguments
    )
    $Stdout = Join-Path $Attempt "$Name`_stdout.txt"
    $Stderr = Join-Path $Attempt "$Name`_stderr.txt"
    $Started = (Get-Date).ToUniversalTime()
    $Process = Start-Process -FilePath 'python' -ArgumentList $Arguments -WorkingDirectory $Week -WindowStyle Hidden -RedirectStandardOutput $Stdout -RedirectStandardError $Stderr -PassThru -Wait
    $RetainedProcesses.Add($Process)
    $Ended = (Get-Date).ToUniversalTime()
    [ordered]@{
        name = $Name
        pid = $Process.Id
        start_utc = $Started.ToString('o')
        end_utc = $Ended.ToString('o')
        exit_code = $Process.ExitCode
        arguments = $Arguments
        handle_retained = $true
        cpu_affinity_inherited = @(0)
    } | ConvertTo-Json -Depth 6 | Out-File -LiteralPath (Join-Path $Attempt "$Name`_exit.json") -Encoding utf8
    return $Process.ExitCode
}

$CompileExit = Invoke-RetainedChild -Name 'compile' -Arguments @('-m', 'py_compile', $Code, $Tests)
if ($CompileExit -ne 0) {
    throw "Compile failed with exit $CompileExit; preserved without retry."
}
$RuffExit = Invoke-RetainedChild -Name 'ruff' -Arguments @('-m', 'ruff', 'check', $Code, $Tests)
if ($RuffExit -ne 0) {
    throw "Ruff failed with exit $RuffExit; preserved without retry."
}
$PytestExit = Invoke-RetainedChild -Name 'pytest' -Arguments @('-m', 'pytest', '-q', $Tests)
if ($PytestExit -ne 0) {
    throw "Pytest failed with exit $PytestExit; preserved without retry."
}

$ClosingCode = (Get-FileHash -LiteralPath $CodePath -Algorithm SHA256).Hash.ToLowerInvariant()
$ClosingTests = (Get-FileHash -LiteralPath $TestsPath -Algorithm SHA256).Hash.ToLowerInvariant()
if ($ClosingCode -ne $ExpectedCode -or $ClosingTests -ne $ExpectedTests) {
    throw 'Closing implementation pin mismatch.'
}
[ordered]@{
    status = 'PASS_FORMAL_SYNTHETIC_DAILY_ADAPTATION_FIXTURES'
    attempt = 'attempt02'
    code_sha256 = $ClosingCode
    tests_sha256 = $ClosingTests
    compile_exit = $CompileExit
    ruff_exit = $RuffExit
    pytest_exit = $PytestExit
    attempt01_preserved = $true
    retry = $false
    real_runtime_executed = $false
    closed_utc = (Get-Date).ToUniversalTime().ToString('o')
} | ConvertTo-Json -Depth 5 | Out-File -LiteralPath (Join-Path $Attempt 'receipt.json') -Encoding utf8
