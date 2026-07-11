param(
    [switch]$Resume
)

$ErrorActionPreference = "Stop"
$env:PYTHONPATH = "."

$Manifest = "research_papers/JEPA/results/_diagnostics/thetadata_manifest_spxw_spy_qqq_202201_202605_sealed_v1/thetadata_option_manifest.csv"
$ExpectedManifestSha256 = "88BE8A2FF44C18FB57FCA360D31DEF574DDBB0419A792FC88349942711D2974A"
$Builder = "neural/jepa/build_event_option_dataset.py"
$ExpectedBuilderSha256 = "6E89AAFED8A2BB66AA8EE80DF70644ECA189D0CE1D8C56F3812895430DAC4307"
$Enhancer = "neural/jepa/enhance_event_option_dataset_physics.py"
$ExpectedEnhancerSha256 = "3E420DB49315AFD9363C45B9F0FEFFA38732EFC116889D3D69B4417A94D2CB36"
$BaseOutput = "tmp/event_option_dataset_execquote_causal1030_202201_202605_v1"
$PhysicsOutput = "tmp/event_option_dataset_execquote_causal1030_202201_202605_v1_physics"

foreach ($check in @(
    @($Manifest, $ExpectedManifestSha256),
    @($Builder, $ExpectedBuilderSha256),
    @($Enhancer, $ExpectedEnhancerSha256)
)) {
    $observedHash = (Get-FileHash -Algorithm SHA256 -LiteralPath $check[0]).Hash
    if ($observedHash -ne $check[1]) {
        throw "Input hash mismatch for $($check[0]): expected $($check[1]), observed $observedHash"
    }
}

if ((Test-Path -LiteralPath $BaseOutput) -and -not $Resume) {
    throw "Base output already exists; inspect it and rerun with -Resume only if it is a partial compatible build: $BaseOutput"
}
if (Test-Path -LiteralPath $PhysicsOutput) {
    throw "Physics output already exists; refusing to overwrite: $PhysicsOutput"
}

$buildArgs = @(
    $Builder,
    "--manifest", $Manifest,
    "--output-dir", $BaseOutput,
    "--tickers", "SPXW", "SPY", "QQQ",
    "--expiry-modes", "zero_dte",
    "--start-date", "20220101",
    "--end-date", "20260531",
    "--workers", "24",
    "--bar-minutes", "5",
    "--start-minute", "630",
    "--end-minute", "870",
    "--near-level-only",
    "--near-level-bps", "20",
    "--horizon-minutes", "180",
    "--spot-target-bps", "25",
    "--spot-stop-bps", "20",
    "--option-tp-pct", "10",
    "--option-sl-pct", "0.6",
    "--option-price-mode", "executable_quote",
    "--option-exit-mode", "trailing",
    "--option-min-hold-minutes", "30",
    "--option-trail-activation-pct", "0.5",
    "--option-trail-drawdown-pct", "0.25",
    "--require-open-interest",
    "--chunk-by", "ticker_month"
)
if ($Resume) {
    $buildArgs += "--skip-existing-chunks"
}

python @buildArgs
if ($LASTEXITCODE -ne 0) {
    throw "Executable-quote dataset build failed with exit code $LASTEXITCODE"
}

$baseParquet = Join-Path $BaseOutput "event_option_dataset.parquet"
$baseSummary = Join-Path $BaseOutput "SUMMARY.json"
if (-not (Test-Path -LiteralPath $baseParquet) -or -not (Test-Path -LiteralPath $baseSummary)) {
    throw "Dataset build finished without the expected parquet and summary"
}
$summary = Get-Content -LiteralPath $baseSummary -Raw | ConvertFrom-Json
if ([string]$summary.date_max -gt "20260531") {
    throw "Sealed dataset contains a date after May 2026: $($summary.date_max)"
}
if ([string]$summary.args.option_price_mode -ne "executable_quote") {
    throw "Dataset is not executable_quote"
}
if ([int]$summary.args.option_min_hold_minutes -ne 30) {
    throw "Dataset does not enforce the 30-minute minimum hold"
}

New-Item -ItemType Directory -Path $PhysicsOutput | Out-Null
python $Enhancer `
    --input $baseParquet `
    --output (Join-Path $PhysicsOutput "event_option_dataset.parquet") `
    --summary (Join-Path $PhysicsOutput "SUMMARY.json")
if ($LASTEXITCODE -ne 0) {
    throw "Physics enhancement failed with exit code $LASTEXITCODE"
}

Get-FileHash -Algorithm SHA256 -LiteralPath `
    $baseParquet, `
    (Join-Path $PhysicsOutput "event_option_dataset.parquet")
