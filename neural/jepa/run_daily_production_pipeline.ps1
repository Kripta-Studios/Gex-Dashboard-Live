# Daily production pipeline for the live level-stability + structural-options bot.
#
# Outputs:
#   neural/models/jepa/jepa_production_level_stability/level_stability_signal.json
#   neural/models/jepa/jepa_production_structural_options/structural_option_profiles.json
#   neural/models/jepa/jepa_production_event_options/event_option_policy.json
#
# The deploy month is excluded from training/selection. For example,
# -DeployMonth 202606 uses only months < 202606.

Param(
  [string]$DeployMonth = (Get-Date -Format "yyyyMM"),
  [int]$Workers = 32,
  [double]$RiskCapital = 5000.0,
  [string]$TrainingData = "",
  [string]$CandidateLabels = "",
  [string]$CompletedThroughMonth = "",
  [string]$RawCoverageJson = "",
  [switch]$SkipSmoke
)

$ErrorActionPreference = "Stop"
$env:PYTHONUNBUFFERED = "1"

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$NeuralRoot = Split-Path -Parent $ScriptDir
$ProjectRoot = Split-Path -Parent $NeuralRoot

function Join-ProjectPath([string]$RelativePath) {
  return Join-Path $ProjectRoot $RelativePath
}

function Join-NeuralPath([string]$RelativePath) {
  return Join-Path $NeuralRoot $RelativePath
}

function Invoke-PythonStep {
  param(
    [string]$Name,
    [string[]]$PythonArgs
  )
  Write-Host "`n=== $Name ===" -ForegroundColor Cyan
  & python @PythonArgs
  if ($LASTEXITCODE -ne 0) {
    throw "Step failed: $Name (exit $LASTEXITCODE)"
  }
}

function Assert-PathExists {
  param(
    [string]$Path,
    [string]$Description
  )
  if (-not (Test-Path $Path)) {
    throw "$Description not found: $Path"
  }
}

function Remove-WorkspaceTemp {
  param([string[]]$Paths)
  $root = (Resolve-Path $ProjectRoot).Path
  foreach ($raw in $Paths) {
    $resolved = Resolve-Path $raw -ErrorAction SilentlyContinue
    if ($null -ne $resolved -and $resolved.Path.StartsWith($root)) {
      Remove-Item -LiteralPath $resolved.Path -Recurse -Force
    }
  }
}

function Convert-ToProjectRelative {
  param([string]$Path)
  $resolved = Resolve-Path $Path -ErrorAction SilentlyContinue
  if ($null -eq $resolved) {
    return $Path
  }
  $root = (Resolve-Path $ProjectRoot).Path
  $full = $resolved.Path
  if ($full.StartsWith($root)) {
    return $full.Substring($root.Length).TrimStart([char[]]@('\', '/')).Replace('\', '/')
  }
  return $full
}

function Resolve-CompletedThroughMonth {
  param(
    [string]$ExplicitMonth,
    [string]$CoveragePath,
    [string]$DeployMonth
  )
  if (-not [string]::IsNullOrWhiteSpace($ExplicitMonth)) {
    return [string]$ExplicitMonth
  }
  if ([string]::IsNullOrWhiteSpace($CoveragePath) -or -not (Test-Path $CoveragePath)) {
    return ""
  }
  try {
    $coverage = Get-Content -Path $CoveragePath -Raw | ConvertFrom-Json
    $months = @()
    if ($null -ne $coverage.completed_months) {
      $months = @($coverage.completed_months)
    } elseif ($null -ne $coverage.combined -and $null -ne $coverage.combined.completed_months) {
      $months = @($coverage.combined.completed_months)
    } elseif ($null -ne $coverage.all_tickers -and $null -ne $coverage.all_tickers.completed_months) {
      $months = @($coverage.all_tickers.completed_months)
    }
    $eligible = @($months | ForEach-Object { [string]$_ } | Where-Object { $_ -lt [string]$DeployMonth } | Sort-Object)
    if ($eligible.Count -gt 0) {
      return [string]$eligible[-1]
    }
  } catch {
    Write-Warning ("Could not infer CompletedThroughMonth from raw coverage {0}: {1}" -f $CoveragePath, $_)
  }
  return ""
}

function Resolve-PartialTrainMonths {
  param(
    [string]$CoveragePath,
    [string]$DeployMonth
  )
  if ([string]::IsNullOrWhiteSpace($CoveragePath) -or -not (Test-Path $CoveragePath)) {
    return @()
  }
  try {
    $coverage = Get-Content -Path $CoveragePath -Raw | ConvertFrom-Json
    $months = @()
    if ($null -ne $coverage.partial_months) {
      $months = @($coverage.partial_months)
    } elseif ($null -ne $coverage.combined -and $null -ne $coverage.combined.partial_months) {
      $months = @($coverage.combined.partial_months)
    } elseif ($null -ne $coverage.all_tickers -and $null -ne $coverage.all_tickers.partial_months) {
      $months = @($coverage.all_tickers.partial_months)
    }
    return @($months | ForEach-Object { [string]$_ } | Where-Object { $_ -lt [string]$DeployMonth } | Sort-Object -Unique)
  } catch {
    Write-Warning ("Could not infer partial train months from raw coverage {0}: {1}" -f $CoveragePath, $_)
  }
  return @()
}

if ([string]::IsNullOrWhiteSpace($TrainingData)) {
  $TrainingData = Join-ProjectPath "training_data\training_data_spx_qqq_spy.parquet"
}
if ([string]::IsNullOrWhiteSpace($CandidateLabels)) {
  $CandidateLabels = Join-ProjectPath "research_papers\JEPA\results\level_stability_option_candidates_level_exit_wf2025_risk5000\candidate_labels.parquet"
}
if ([string]::IsNullOrWhiteSpace($RawCoverageJson)) {
  $RawCoverageJson = Join-ProjectPath "research_papers\JEPA\results\_diagnostics\thetadata_0dte_raw_coverage_spxw_spy_qqq\raw_coverage.json"
}

$LevelSignalDir = Join-NeuralPath "models\jepa\jepa_production_level_stability"
$LevelSignalJson = Join-Path $LevelSignalDir "level_stability_signal.json"
$StructuralDir = Join-NeuralPath "models\jepa\jepa_production_structural_options"
$StructuralJson = Join-Path $StructuralDir "structural_option_profiles.json"
$EventOptionDir = Join-NeuralPath "models\jepa\jepa_production_event_options"
$EventOptionPolicyJson = Join-Path $EventOptionDir "event_option_policy.json"
$EventOptionComponentRegistryJson = Join-Path $EventOptionDir "component_registry.json"
$ManifestJson = Join-NeuralPath "models\jepa\production_manifest.json"
$CompletedThroughMonth = Resolve-CompletedThroughMonth -ExplicitMonth $CompletedThroughMonth -CoveragePath $RawCoverageJson -DeployMonth $DeployMonth
$PartialTrainMonths = @(Resolve-PartialTrainMonths -CoveragePath $RawCoverageJson -DeployMonth $DeployMonth)
if (-not [string]::IsNullOrWhiteSpace($CompletedThroughMonth)) {
  if ([string]$CompletedThroughMonth -ge [string]$DeployMonth) {
    throw "CompletedThroughMonth=$CompletedThroughMonth must be earlier than DeployMonth=$DeployMonth"
  }
  Write-Host "Using completed training cap: $CompletedThroughMonth" -ForegroundColor Yellow
} else {
  Write-Warning "No completed training cap resolved; production fit will use all months before DeployMonth=$DeployMonth."
}
if ($PartialTrainMonths.Count -gt 0) {
  Write-Host "Excluding raw-partial train months: $($PartialTrainMonths -join ',')" -ForegroundColor Yellow
}

$EventOptionPolicy = $null
$UseEventOptionPolicy = $false
$EventOptionComponentRegistry = $null
$UseEventOptionComponentRegistry = $false
if (Test-Path $EventOptionPolicyJson) {
  $EventOptionPolicy = Get-Content -Path $EventOptionPolicyJson -Raw | ConvertFrom-Json
  if ([string]$EventOptionPolicy.deploy_month -eq [string]$DeployMonth) {
    $eventLiveReady = $false
    if ($null -ne $EventOptionPolicy.live_contract -and $null -ne $EventOptionPolicy.live_contract.event_option_live_ready) {
      $eventLiveReady = [bool]$EventOptionPolicy.live_contract.event_option_live_ready
    }
    if ($eventLiveReady -and [string]$EventOptionPolicy.status -notmatch "blocked") {
      $UseEventOptionPolicy = $true
      if (Test-Path $EventOptionComponentRegistryJson) {
        $EventOptionComponentRegistry = Get-Content -Path $EventOptionComponentRegistryJson -Raw | ConvertFrom-Json
        if ([string]$EventOptionComponentRegistry.deploy_month -eq [string]$DeployMonth) {
          $UseEventOptionComponentRegistry = $true
        } else {
          Write-Warning "Event-option component registry deploy_month=$($EventOptionComponentRegistry.deploy_month) does not match pipeline DeployMonth=$DeployMonth; manifest will not advertise it."
        }
      }
    } else {
      Write-Warning "Event-option policy deploy_month matches $DeployMonth but is not live-ready (status=$($EventOptionPolicy.status)); manifest will keep it blocked."
    }
  } else {
    Write-Warning "Event-option policy deploy_month=$($EventOptionPolicy.deploy_month) does not match pipeline DeployMonth=$DeployMonth; manifest and smoke test will not advertise it."
  }
}

Assert-PathExists $TrainingData "Training data parquet"
Assert-PathExists $CandidateLabels "Risk-5000 option candidate labels"
New-Item -ItemType Directory -Force -Path $LevelSignalDir, $StructuralDir | Out-Null

$PathSeparator = [System.IO.Path]::PathSeparator
$PythonPathParts = @($ProjectRoot, $NeuralRoot, $ScriptDir)
if (-not [string]::IsNullOrWhiteSpace($env:PYTHONPATH)) {
  $PythonPathParts += $env:PYTHONPATH
}
$env:PYTHONPATH = ($PythonPathParts -join $PathSeparator)

$CompletedTrainArgs = @()
if (-not [string]::IsNullOrWhiteSpace($CompletedThroughMonth)) {
  $CompletedTrainArgs = @("--max-train-month", $CompletedThroughMonth)
}
$ExcludedTrainArgs = @()
if ($PartialTrainMonths.Count -gt 0) {
  $ExcludedTrainArgs = @("--exclude-train-months") + $PartialTrainMonths
}

$LevelSignalArgs = @(
  (Join-Path $ScriptDir "fit_production_level_stability_signal.py"),
  "--data", $TrainingData,
  "--output-dir", $LevelSignalDir,
  "--deploy-month", $DeployMonth,
  "--workers", [string]$Workers
)
$LevelSignalArgs += $CompletedTrainArgs
$LevelSignalArgs += $ExcludedTrainArgs
Invoke-PythonStep "Fit production level-stability signal" $LevelSignalArgs

$StructuralArgs = @(
  (Join-Path $ScriptDir "fit_production_structural_option_profiles.py"),
  "--candidate-labels", $CandidateLabels,
  "--output-json", $StructuralJson,
  "--output-dir", $StructuralDir,
  "--deploy-month", $DeployMonth,
  "--risk-capital", [string]$RiskCapital
)
$StructuralArgs += $CompletedTrainArgs
$StructuralArgs += $ExcludedTrainArgs
Invoke-PythonStep "Fit production structural option profiles" $StructuralArgs

Invoke-PythonStep "Compile production Python modules" @(
  "-m", "py_compile",
  (Join-ProjectPath "bots\tradingbot_wrapper_jepa.py"),
  (Join-ProjectPath "services\realtime_feed.py"),
  (Join-Path $ScriptDir "level_stability_live.py"),
  (Join-Path $ScriptDir "fit_production_level_stability_signal.py"),
  (Join-Path $ScriptDir "fit_production_structural_option_profiles.py"),
  (Join-Path $ScriptDir "export_event_option_production_policy.py"),
  (Join-Path $ScriptDir "validate_event_option_production_package.py"),
  (Join-Path $ScriptDir "event_option_component_live.py"),
  (Join-Path $ScriptDir "event_option_live_snapshot.py"),
  (Join-Path $ScriptDir "walkforward_event_phys_td_jepa_oof.py"),
  (Join-Path $ScriptDir "walkforward_event_option_gate.py"),
  (Join-Path $ScriptDir "apply_event_trade_union_topk_regressor.py"),
  (Join-Path $ScriptDir "apply_event_daily_source_router.py")
)

if ($UseEventOptionPolicy) {
  if (-not $UseEventOptionComponentRegistry) {
    throw "Event-option policy deploy_month matches $DeployMonth, but component_registry.json is missing or has a different deploy_month; refusing to advertise event-option live trading."
  }
  Invoke-PythonStep "Validate event-option production package" @(
    (Join-Path $ScriptDir "validate_event_option_production_package.py"),
    "--policy", $EventOptionPolicyJson,
    "--registry", $EventOptionComponentRegistryJson,
    "--require-live-ready"
  )
}

if (-not $SkipSmoke) {
  $SmokeRt = Join-ProjectPath "_tmp_daily_prod_rt"
  $SmokeTrades = Join-ProjectPath "_tmp_daily_prod_trades"
  Remove-WorkspaceTemp @($SmokeRt, $SmokeTrades)
  $SmokeArgs = @(
    (Join-ProjectPath "bots\tradingbot_wrapper_jepa.py"),
    "--level-signal-path", $LevelSignalJson,
    "--require-level-signal",
    "--structural-profile-path", $StructuralJson,
    "--require-structural-profile"
  )
  if ($UseEventOptionPolicy) {
    $SmokeArgs += @(
      "--event-option-policy-path", $EventOptionPolicyJson,
      "--require-event-option-policy"
    )
    if ($UseEventOptionComponentRegistry) {
      $SmokeArgs += @(
        "--event-option-component-registry-path", $EventOptionComponentRegistryJson,
        "--require-event-option-component-registry",
        "--require-event-option-live-ready",
        "--enable-event-option-scorer",
        "--strict-event-option-features"
      )
    }
  } else {
    $SmokeArgs += @(
      "--disable-event-option-policy",
      "--disable-event-option-component-registry"
    )
  }
  $SmokeArgs += @(
    "--disable-option-value",
    "--rt-data-dir", $SmokeRt,
    "--trades-dir", $SmokeTrades,
    "--tickers", "SPX", "QQQ", "SPY",
    "--dry-run",
    "--force",
    "--log-level", "INFO"
  )
  Invoke-PythonStep "Smoke live bot artifact load" $SmokeArgs
  Remove-WorkspaceTemp @($SmokeRt, $SmokeTrades)
}

$manifest = [ordered]@{
  generated_at = (Get-Date).ToString("s")
  status = "production_ready"
  deploy_month = $DeployMonth
  risk_capital_dollars = $RiskCapital
  completed_train_through_month = $CompletedThroughMonth
  excluded_train_months = $PartialTrainMonths
  raw_coverage = Convert-ToProjectRelative $RawCoverageJson
  level_signal = Convert-ToProjectRelative $LevelSignalJson
  structural_profiles = Convert-ToProjectRelative $StructuralJson
  training_data = Convert-ToProjectRelative $TrainingData
  candidate_labels = Convert-ToProjectRelative $CandidateLabels
  live_bot_service = "systemd/ai_bot.service"
  realtime_feed_service = "systemd/realtime_feed.service"
}
if ($UseEventOptionPolicy) {
  $manifest.Add("event_option_policy", (Convert-ToProjectRelative $EventOptionPolicyJson))
  $manifest.Add("event_option_status", ([string]$EventOptionPolicy.status))
  $manifest.Add("event_option_deploy_month", ([string]$EventOptionPolicy.deploy_month))
  if ($UseEventOptionComponentRegistry) {
    $manifest.Add("event_option_component_registry", (Convert-ToProjectRelative $EventOptionComponentRegistryJson))
    $manifest.Add("event_option_component_status", ([string]$EventOptionComponentRegistry.status))
  }
}
if (-not $UseEventOptionPolicy -and $null -ne $EventOptionPolicy -and [string]$EventOptionPolicy.deploy_month -eq [string]$DeployMonth) {
  $manifest.Add("event_option_blocked_reason", ("Event-option policy exists for deploy month but is not live-ready: status={0}" -f [string]$EventOptionPolicy.status))
}
$manifest | ConvertTo-Json -Depth 5 | Set-Content -Path $ManifestJson -Encoding UTF8

Write-Host "`nProduction artifacts ready:" -ForegroundColor Green
Write-Host "  $LevelSignalJson"
Write-Host "  $StructuralJson"
if ($UseEventOptionPolicy) {
  Write-Host "  $EventOptionPolicyJson"
  if ($UseEventOptionComponentRegistry) {
    Write-Host "  $EventOptionComponentRegistryJson"
  }
}
Write-Host "  $ManifestJson"
