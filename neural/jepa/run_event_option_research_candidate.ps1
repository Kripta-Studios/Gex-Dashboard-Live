# Rebuild the current causal event-option research candidate.
#
# This is intentionally separate from run_daily_production_pipeline.ps1.
# It does not write neural/models/jepa/production_manifest.json and does not
# promote the event-option path to the live bot.

Param(
  [switch]$SkipBuildInputs,
  [switch]$IncludeJunePartial,
  [switch]$UseDailySpyRouter,
  [switch]$FreezeForwardManifest,
  [string]$FreezeBeforeMonth = "202607",
  [int]$DailySpyMinSourceTrainDays = 0,
  [int]$DailySpyMinSourceTrainTrades = 0,
  [switch]$DailySpyAllowAllSourcesIfNoneEligible,
  [int]$Workers = 32,
  [double]$RiskCapital = 5000.0
)

$ErrorActionPreference = "Stop"
$env:PYTHONUNBUFFERED = "1"

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$NeuralRoot = Split-Path -Parent $ScriptDir
$ProjectRoot = Split-Path -Parent $NeuralRoot

function Join-ProjectPath([string]$RelativePath) {
  return Join-Path $ProjectRoot $RelativePath
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

function Invoke-PythonStepAllowFail {
  param(
    [string]$Name,
    [string[]]$PythonArgs
  )
  Write-Host "`n=== $Name ===" -ForegroundColor Cyan
  & python @PythonArgs
  if ($LASTEXITCODE -ne 0) {
    Write-Host "Non-fatal step failed: $Name (exit $LASTEXITCODE)" -ForegroundColor Yellow
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

$PathSeparator = [System.IO.Path]::PathSeparator
$PythonPathParts = @($ProjectRoot, $NeuralRoot, $ScriptDir)
if (-not [string]::IsNullOrWhiteSpace($env:PYTHONPATH)) {
  $PythonPathParts += $env:PYTHONPATH
}
$env:PYTHONPATH = ($PythonPathParts -join $PathSeparator)

$ResultsRoot = Join-ProjectPath "research_papers\JEPA\results"
$EventDataset = Join-ProjectPath "research_papers\JEPA\results\event_phys_td_jepa_oof_2025_2026_core_through202606\event_option_dataset.parquet"

$SpxwCurrent = Join-ProjectPath "research_papers\JEPA\results\event_option_current_best_causal_qqqcircuit_sidecircuits_tdvp_meta_s2_m18_pf11_wr42_2026janjun_risk5000\candidate_trade_meta_trades.csv"
$SpxwTdvpOnly = Join-ProjectPath "research_papers\JEPA\results\event_option_gate_spxw_front_weekly_delta35_return_tdvp_only_v1_2025h2_2026jun"
$SpxwWideZdte = Join-ProjectPath "research_papers\JEPA\results\event_option_gate_wide_delta35_quantile_zero_dte_2026janmay"
$SpxwProfile = Join-ProjectPath "research_papers\JEPA\results\event_option_profile_selector_narrow_13ticker_regimegate_m18_2026janmay\regime_gate_trades.csv"
$SpxwOut = Join-ProjectPath "research_papers\JEPA\results\event_option_spxw_branch_router_topk_current_tdvp_widezdte_profile_maxday7_s1_m19_export202510_202606_risk5000"
$SpxwLegacyMaxday7Export = Join-ProjectPath "research_papers\JEPA\results\event_option_spxw_branch_router_topk_current_tdvp_widezdte_profile_maxday7_2025h2export_202510_202606_risk5000"
$SpxwBaseSide = Join-ProjectPath "research_papers\JEPA\results\event_option_spxw_base_intraday_side_circuit_m19_2025h2hist_v2_2026janjun_risk5000\intraday_circuit_trades.csv"
$SpxwBaseTdvp = Join-ProjectPath "research_papers\JEPA\results\event_option_spxw_union_base_tdvp_topk_reg_s3_m19_wr20_2026janjun_risk5000\trade_union_topk_regressor_trades.csv"
$SpxwOuterSelectorOut = Join-ProjectPath "research_papers\JEPA\results\event_option_spxw_stream_selector_s1_maxday7_base_s1_2026janmay_risk5000"
$SpxwOuterSelectorJuneOut = Join-ProjectPath "research_papers\JEPA\results\event_option_spxw_stream_selector_s1_maxday7_base_s1_2026janjun_partial_risk5000"

$QqqBalanced = Join-ProjectPath "research_papers\JEPA\results\event_option_qqq_branch_router_topk_balanced_call065_2025h2export_202510_202606_risk5000\trade_union_topk_regressor_trades.csv"
$QqqD65 = Join-ProjectPath "research_papers\JEPA\results\event_option_gate_qqq_alltrain_delta65_wincls_min18_2025h2_2026"
$QqqCurrent = Join-ProjectPath "research_papers\JEPA\results\event_option_qqq_nested_config_intraday_side_circuit_m18_pf11_wr42_2025h2hist_v2_2026janjun_risk5000\intraday_circuit_trades.csv"
$QqqOut = Join-ProjectPath "research_papers\JEPA\results\event_option_qqq_union_balanced_d65_current_topk_s2_m19_maxday5_recent202510_export_202510_202606_risk5000"
$QqqOuterSelectorOut = Join-ProjectPath "research_papers\JEPA\results\event_option_qqq_stream_selector_recenttopk_d65_current_s2_call50_2026janmay_risk5000"
$QqqOuterSelectorJuneOut = Join-ProjectPath "research_papers\JEPA\results\event_option_qqq_stream_selector_recenttopk_d65_current_s2_call50_2026janjun_partial_risk5000"

$SpyWincls = Join-ProjectPath "research_papers\JEPA\results\event_option_gate_spy_mixed_delta35_wincls_min18_2025h2_2026jun"
$SpyCurrent = Join-ProjectPath "research_papers\JEPA\results\event_option_spy_topk_intraday_side_circuit_m19_2025h2hist_v2_2025h2_2026janjun_risk5000\intraday_circuit_trades.csv"
$SpyVariant = Join-ProjectPath "research_papers\JEPA\results\event_option_variant_selector_2025h2_history_2026janmay_risk5000\selected_variant_trades.csv"
$SpyJanMayOut = Join-ProjectPath "research_papers\JEPA\results\event_option_spy_nested_wincls_primary_fallback_m19_2026janmay_risk5000"
$SpyJunPartialOut = Join-ProjectPath "research_papers\JEPA\results\event_option_spy_nested_wincls_primary_fallback_m19_2026janjun_partial_risk5000"
$SpyJuneSelectorOut = Join-ProjectPath "research_papers\JEPA\results\event_option_spy_june_selector_nested_vs_topk_s2_202606_partial_risk5000"
$SpyDailyRouterJanMayOut = Join-ProjectPath "research_papers\JEPA\results\event_option_spy_daily_source_router_d660_topk_nested_janmaynested_formal_2026janmay_risk5000"
$SpyDailyRouterBackfillJanMayOut = Join-ProjectPath "research_papers\JEPA\results\event_option_spy_daily_router_topk_nested_janmaynested_backfill_topk_t24_md4_2026janmay_risk5000"
$SpyDailyRouterJanJunOut = Join-ProjectPath "research_papers\JEPA\results\event_option_spy_daily_source_router_d660_topk_nested_formal_2026janjun_risk5000"
$SpyDailyRouterBackfillJanJunOut = Join-ProjectPath "research_papers\JEPA\results\event_option_spy_daily_router_topk_nested_backfill_topk_t24_md4_2026janjun_risk5000"

$LegacyCanonicalCombined = Join-ProjectPath "research_papers\JEPA\results\event_option_current_best_causal_spxw_outer_s1_qqq_outer_call50_2026janmay_risk5000"
$LegacyJuneCombined = Join-ProjectPath "research_papers\JEPA\results\event_option_current_best_causal_spxw_outer_s1_qqq_outer_call50_spy_junes2_2026janjun_partial_risk5000"
$LegacyForwardFreezeOut = Join-ProjectPath "research_papers\JEPA\results\event_option_forward_freeze_spxw_outer_s1_qqq_outer_call50_spy_junes2_$FreezeBeforeMonth"
$DailyRouterCanonicalCombined = Join-ProjectPath "research_papers\JEPA\results\event_option_candidate_spxw_outer_s1_qqq_outer_call50_spy_dailyrouter_bftopk_janmaynested_2026janmay_risk5000"
$DailyRouterJuneCombined = Join-ProjectPath "research_papers\JEPA\results\event_option_candidate_spxw_outer_s1_qqq_outer_call50_spy_dailyrouter_bftopk_2026janjun_partial_risk5000"
$DailyRouterForwardFreezeOut = Join-ProjectPath "research_papers\JEPA\results\event_option_forward_freeze_spxw_outer_s1_qqq_outer_call50_spy_dailyrouter_bftopk_$FreezeBeforeMonth"

$DailySpySourceHistoryTag = ""
if ($DailySpyMinSourceTrainDays -gt 0 -or $DailySpyMinSourceTrainTrades -gt 0) {
  $DailySpySourceHistoryTag = "srchist$($DailySpyMinSourceTrainDays)d$($DailySpyMinSourceTrainTrades)t"
  $SpyDailyRouterJanMayOut = Join-ProjectPath "research_papers\JEPA\results\event_option_spy_daily_source_router_d660_topk_nested_janmaynested_$($DailySpySourceHistoryTag)_2026janmay_risk5000"
  $SpyDailyRouterBackfillJanMayOut = Join-ProjectPath "research_papers\JEPA\results\event_option_spy_daily_router_topk_nested_$($DailySpySourceHistoryTag)_backfill_topk_t24_md4_2026janmay_risk5000"
  $SpyDailyRouterJanJunOut = Join-ProjectPath "research_papers\JEPA\results\event_option_spy_daily_source_router_d660_topk_nested_$($DailySpySourceHistoryTag)_2026janjun_partial_risk5000"
  $SpyDailyRouterBackfillJanJunOut = Join-ProjectPath "research_papers\JEPA\results\event_option_spy_daily_router_topk_nested_$($DailySpySourceHistoryTag)_backfill_topk_t24_md4_2026janjun_partial_risk5000"
  $DailyRouterCanonicalCombined = Join-ProjectPath "research_papers\JEPA\results\event_option_candidate_spxw_outer_s1_qqq_outer_call50_spy_dailyrouter_$($DailySpySourceHistoryTag)_bftopk_2026janmay_risk5000"
  $DailyRouterJuneCombined = Join-ProjectPath "research_papers\JEPA\results\event_option_candidate_spxw_outer_s1_qqq_outer_call50_spy_dailyrouter_$($DailySpySourceHistoryTag)_bftopk_2026janjun_partial_risk5000"
  $DailyRouterForwardFreezeOut = Join-ProjectPath "research_papers\JEPA\results\event_option_forward_freeze_spxw_outer_s1_qqq_outer_call50_spy_dailyrouter_$($DailySpySourceHistoryTag)_bftopk_$FreezeBeforeMonth"
}

if ($UseDailySpyRouter) {
  $CanonicalCombined = $DailyRouterCanonicalCombined
  $JuneCombined = $DailyRouterJuneCombined
  $ForwardFreezeOut = $DailyRouterForwardFreezeOut
} else {
  $CanonicalCombined = $LegacyCanonicalCombined
  $JuneCombined = $LegacyJuneCombined
  $ForwardFreezeOut = $LegacyForwardFreezeOut
}

$DailySpyRouterExtraArgs = @(
  "--min-source-train-days", [string]$DailySpyMinSourceTrainDays,
  "--min-source-train-trades", [string]$DailySpyMinSourceTrainTrades
)
if ($DailySpyAllowAllSourcesIfNoneEligible) {
  $DailySpyRouterExtraArgs += "--allow-all-sources-if-none-eligible"
}

Assert-PathExists $EventDataset "Event option dataset"
Assert-PathExists $SpxwCurrent "SPXW current source"
Assert-PathExists $SpxwTdvpOnly "SPXW TDVP-only source"
Assert-PathExists $SpxwWideZdte "SPXW wide ZDTE source"
Assert-PathExists $SpxwProfile "SPXW profile source"
Assert-PathExists $SpxwLegacyMaxday7Export "SPXW legacy maxday7 export source"
Assert-PathExists $SpxwBaseSide "SPXW base side source"
Assert-PathExists $SpxwBaseTdvp "SPXW base TDVP source"
Assert-PathExists $QqqBalanced "QQQ balanced source"
Assert-PathExists $QqqD65 "QQQ d65 source"
Assert-PathExists $QqqCurrent "QQQ current source"
Assert-PathExists $SpyWincls "SPY wincls source"
Assert-PathExists $SpyCurrent "SPY current/top-K source"
Assert-PathExists $SpyVariant "SPY variant source"

if (-not $SkipBuildInputs) {
  Invoke-PythonStep "Build SPXW s1/m19 top-K router" @(
    (Join-Path $ScriptDir "apply_event_trade_union_topk_regressor.py"),
    "--trade-source", "current=$SpxwCurrent",
    "--trade-source", "tdvp_only=$SpxwTdvpOnly",
    "--trade-source", "wide_zdte=$SpxwWideZdte",
    "--trade-source", "profile_regime=$SpxwProfile",
    "--data", $EventDataset,
    "--output-dir", $SpxwOut,
    "--ticker", "SPXW",
    "--history-start-month", "202507",
    "--start-month", "202510",
    "--end-month", "202606",
    "--max-day", "7",
    "--cooldown-minutes", "30",
    "--risk-capital", [string]$RiskCapital,
    "--include-latent-vectors",
    "--select-months", "1",
    "--min-train-trades", "40",
    "--min-select-trades", "19",
    "--min-select-month-trades", "19",
    "--topk-grid", "19", "20", "22", "24", "26", "28", "30", "35", "40", "45", "50", "60", "70", "999",
    "--score-pf-weight", "3.0",
    "--score-pf-cap", "4.0",
    "--score-win-weight", "20.0",
    "--score-return-weight", "0.1",
    "--score-positive-month-weight", "4.0",
    "--score-volume-weight", "0.1",
    "--clip-target", "2.5",
    "--objective", "regression_l1",
    "--n-estimators", "260",
    "--learning-rate", "0.03",
    "--num-leaves", "15",
    "--min-child-samples", "16",
    "--subsample", "0.85",
    "--colsample-bytree", "0.8",
    "--reg-lambda", "8.0",
    "--lgb-jobs", [string]$Workers,
    "--seed", "20260620"
  )

  Invoke-PythonStep "Build QQQ recent-window top-K S2" @(
    (Join-Path $ScriptDir "apply_event_trade_union_topk_regressor.py"),
    "--trade-source", "balanced=$QqqBalanced",
    "--trade-source", "d65=$QqqD65",
    "--trade-source", "current=$QqqCurrent",
    "--data", $EventDataset,
    "--output-dir", $QqqOut,
    "--ticker", "QQQ",
    "--history-start-month", "202510",
    "--start-month", "202510",
    "--end-month", "202606",
    "--max-day", "5",
    "--cooldown-minutes", "30",
    "--risk-capital", [string]$RiskCapital,
    "--include-latent-vectors",
    "--select-months", "2",
    "--min-train-trades", "50",
    "--min-select-trades", "38",
    "--min-select-month-trades", "19",
    "--min-select-call-rate", "0.20",
    "--max-select-call-rate", "0.80",
    "--topk-grid", "19", "20", "22", "24", "26", "28", "30", "35", "40", "45", "50", "60", "70", "999",
    "--score-pf-weight", "3.0",
    "--score-pf-cap", "4.0",
    "--score-win-weight", "20.0",
    "--score-return-weight", "0.1",
    "--score-positive-month-weight", "4.0",
    "--score-volume-weight", "0.1",
    "--clip-target", "2.5",
    "--objective", "regression_l1",
    "--n-estimators", "260",
    "--learning-rate", "0.03",
    "--num-leaves", "15",
    "--min-child-samples", "16",
    "--subsample", "0.85",
    "--colsample-bytree", "0.8",
    "--reg-lambda", "8.0",
    "--lgb-jobs", [string]$Workers,
    "--seed", "20260620"
  )

  Invoke-PythonStep "Build SPY nested wincls primary fallback Jan-May" @(
    (Join-Path $ScriptDir "apply_event_nested_volume_backfill.py"),
    "--source", "wincls=$SpyWincls",
    "--source", "current=$SpyCurrent",
    "--source", "variant=$SpyVariant",
    "--pair", "wincls=current",
    "--pair", "wincls=variant",
    "--output-dir", $SpyJanMayOut,
    "--ticker", "SPY",
    "--history-start-month", "202507",
    "--start-month", "202601",
    "--end-month", "202605",
    "--select-months", "3",
    "--target-month-trades", "19",
    "--max-day", "8",
    "--cooldown-minutes", "30",
    "--risk-capital", [string]$RiskCapital,
    "--min-select-trades", "54",
    "--min-select-month-trades", "19",
    "--min-select-win-rate", "0.45",
    "--min-select-pf", "1.3",
    "--require-select-positive-months",
    "--min-call-rate", "0.20",
    "--max-call-rate", "0.80"
  )
}

if ($UseDailySpyRouter) {
  if (-not $SkipBuildInputs) {
    Invoke-PythonStep "Build SPY daily source router Jan-May" (@(
      (Join-Path $ScriptDir "apply_event_daily_source_router.py"),
      "--source", "topk=$SpyCurrent",
      "--source", "nested=$(Join-Path $SpyJanMayOut 'nested_volume_backfill_trades.csv')",
      "--data", $EventDataset,
      "--output-dir", $SpyDailyRouterJanMayOut,
      "--ticker", "SPY",
      "--history-start-month", "202507",
      "--start-month", "202601",
      "--end-month", "202605",
      "--decision-minute", "660",
      "--risk-capital", [string]$RiskCapital,
      "--min-train-days", "40",
      "--min-train-rows", "80",
      "--clip-target", "2.5",
      "--objective", "regression_l1",
      "--n-estimators", "220",
      "--learning-rate", "0.035",
      "--num-leaves", "7",
      "--min-child-samples", "16",
      "--subsample", "0.85",
      "--colsample-bytree", "0.75",
      "--reg-lambda", "8.0",
      "--lgb-jobs", [string]$Workers,
      "--seed", "20260621"
    ) + $DailySpyRouterExtraArgs)

    Invoke-PythonStep "Build SPY daily-router top-K volume backfill Jan-May" @(
      (Join-Path $ScriptDir "apply_event_monthly_volume_backfill.py"),
      "--primary-trades", (Join-Path $SpyDailyRouterJanMayOut "daily_source_router_trades.csv"),
      "--fallback-trades", $SpyCurrent,
      "--output-dir", $SpyDailyRouterBackfillJanMayOut,
      "--primary-name", "daily_router",
      "--fallback-name", "topk",
      "--start-month", "202601",
      "--end-month", "202605",
      "--min-month-trades", "24",
      "--max-day", "4",
      "--cooldown-minutes", "30",
      "--min-entry-minute", "660",
      "--risk-capital", [string]$RiskCapital
    )
  }

  Assert-PathExists (Join-Path $SpyDailyRouterJanMayOut "daily_source_router_trades.csv") "SPY daily router Jan-May trades"
  Assert-PathExists (Join-Path $SpyDailyRouterJanMayOut "daily_source_router_folds.csv") "SPY daily router Jan-May folds"
  Assert-PathExists (Join-Path $SpyDailyRouterBackfillJanMayOut "monthly_volume_backfill_trades.csv") "SPY daily-router backfill Jan-May trades"
}

Invoke-PythonStep "Build SPXW outer stream selector Jan-May" @(
  (Join-Path $ScriptDir "apply_event_stream_selector.py"),
  "--source", "s1export=$(Join-Path $SpxwOut 'trade_union_topk_regressor_trades.csv')",
  "--source", "maxday7export=$(Join-Path $SpxwLegacyMaxday7Export 'trade_union_topk_regressor_trades.csv')",
  "--source", "base_side=$SpxwBaseSide",
  "--source", "base_tdvp=$SpxwBaseTdvp",
  "--output-dir", $SpxwOuterSelectorOut,
  "--ticker", "SPXW",
  "--history-start-month", "202510",
  "--start-month", "202601",
  "--end-month", "202605",
  "--select-months", "1",
  "--risk-capital", [string]$RiskCapital,
  "--min-select-trades", "19",
  "--min-select-month-trades", "19",
  "--min-select-win-rate", "0.40",
  "--min-select-pf", "0.50",
  "--min-call-rate", "0.20",
  "--max-call-rate", "0.80"
)

Invoke-PythonStep "Build QQQ outer stream selector Jan-May" @(
  (Join-Path $ScriptDir "apply_event_stream_selector.py"),
  "--source", "topk_recent=$(Join-Path $QqqOut 'trade_union_topk_regressor_trades.csv')",
  "--source", "d65=$QqqD65",
  "--source", "current=$QqqCurrent",
  "--output-dir", $QqqOuterSelectorOut,
  "--ticker", "QQQ",
  "--history-start-month", "202510",
  "--start-month", "202601",
  "--end-month", "202605",
  "--select-months", "2",
  "--risk-capital", [string]$RiskCapital,
  "--min-select-trades", "38",
  "--min-select-month-trades", "19",
  "--min-select-win-rate", "0.42",
  "--min-select-pf", "1.10",
  "--require-select-positive-months",
  "--min-call-rate", "0.50",
  "--max-call-rate", "0.85"
)

if ($UseDailySpyRouter) {
  Invoke-PythonStep "Combine daily-router Jan-May candidate" @(
    (Join-Path $ScriptDir "combine_event_option_trade_streams.py"),
    "--trade-file", "SPXW_SELECTOR=$(Join-Path $SpxwOuterSelectorOut 'stream_selector_trades.csv')",
    "--trade-file", "SPY_DAILY_ROUTER_BF=$(Join-Path $SpyDailyRouterBackfillJanMayOut 'monthly_volume_backfill_trades.csv')",
    "--trade-file", "QQQ_SELECTOR=$(Join-Path $QqqOuterSelectorOut 'stream_selector_trades.csv')",
    "--fold-file", "SPXW_OUTER_S1=$(Join-Path $SpxwOuterSelectorOut 'stream_selector_folds.csv')",
    "--fold-file", "SPY_DAILY_ROUTER=$(Join-Path $SpyDailyRouterJanMayOut 'daily_source_router_folds.csv')",
    "--fold-file", "SPY_TOPK_FALLBACK=$(Join-Path (Split-Path -Parent $SpyCurrent) 'intraday_circuit_folds.csv')",
    "--fold-file", "QQQ_OUTER_CALL50=$(Join-Path $QqqOuterSelectorOut 'stream_selector_folds.csv')",
    "--output-dir", $CanonicalCombined,
    "--start-month", "202601",
    "--end-month", "202605",
    "--risk-capital", [string]$RiskCapital
  )
} else {
  Invoke-PythonStep "Combine canonical Jan-May candidate" @(
    (Join-Path $ScriptDir "combine_event_option_trade_streams.py"),
    "--trade-file", "SPXW_SELECTOR=$(Join-Path $SpxwOuterSelectorOut 'stream_selector_trades.csv')",
    "--trade-file", "SPY=$(Join-Path $SpyJanMayOut 'nested_volume_backfill_trades.csv')",
    "--trade-file", "QQQ_SELECTOR=$(Join-Path $QqqOuterSelectorOut 'stream_selector_trades.csv')",
    "--fold-file", "SPXW_OUTER_S1=$(Join-Path $SpxwOuterSelectorOut 'stream_selector_folds.csv')",
    "--fold-file", "SPY_NESTED=$(Join-Path $SpyJanMayOut 'nested_volume_backfill_folds.csv')",
    "--fold-file", "QQQ_OUTER_CALL50=$(Join-Path $QqqOuterSelectorOut 'stream_selector_folds.csv')",
    "--output-dir", $CanonicalCombined,
    "--start-month", "202601",
    "--end-month", "202605",
    "--risk-capital", [string]$RiskCapital
  )
}

Invoke-PythonStep "Verify canonical Jan-May candidate" @(
  (Join-Path $ScriptDir "verify_event_option_result.py"),
  "--result-dir", $CanonicalCombined,
  "--tickers", "SPXW", "SPY", "QQQ",
  "--start-month", "202601",
  "--end-month", "202605",
  "--min-win-rate", "0.45",
  "--min-profit-factor", "1.30",
  "--min-month-trades", "18",
  "--strict-month-trades",
  "--require-positive-months",
  "--min-call-rate", "0.20",
  "--max-call-rate", "0.80",
  "--disallow-weak-fold-modes"
)

Invoke-PythonStep "Audit canonical Jan-May curve health" @(
  (Join-Path $ScriptDir "analyze_event_option_curve_health.py"),
  "--result-dir", $CanonicalCombined,
  "--start-month", "202601",
  "--end-month", "202605",
  "--risk-capital", [string]$RiskCapital
)

Invoke-PythonStep "Audit canonical research selection evidence" @(
  (Join-Path $ScriptDir "audit_event_option_research_selection.py"),
  "--result-dir", $CanonicalCombined,
  "--start-month", "202601",
  "--end-month", "202605"
)

if ($IncludeJunePartial) {
  if (-not $SkipBuildInputs) {
    Invoke-PythonStep "Build SPY nested Jan-Jun partial" @(
      (Join-Path $ScriptDir "apply_event_nested_volume_backfill.py"),
      "--source", "wincls=$SpyWincls",
      "--source", "current=$SpyCurrent",
      "--source", "variant=$SpyVariant",
      "--pair", "wincls=current",
      "--pair", "wincls=variant",
      "--output-dir", $SpyJunPartialOut,
      "--ticker", "SPY",
      "--history-start-month", "202507",
      "--start-month", "202601",
      "--end-month", "202606",
      "--select-months", "3",
      "--target-month-trades", "19",
      "--max-day", "8",
      "--cooldown-minutes", "30",
      "--risk-capital", [string]$RiskCapital,
      "--min-select-trades", "54",
      "--min-select-month-trades", "19",
      "--min-select-win-rate", "0.45",
      "--min-select-pf", "1.3",
      "--require-select-positive-months",
      "--min-call-rate", "0.20",
      "--max-call-rate", "0.80"
    )

    if ($UseDailySpyRouter) {
      Invoke-PythonStep "Build SPY daily source router Jan-Jun partial" (@(
        (Join-Path $ScriptDir "apply_event_daily_source_router.py"),
        "--source", "topk=$SpyCurrent",
        "--source", "nested=$(Join-Path $SpyJunPartialOut 'nested_volume_backfill_trades.csv')",
        "--data", $EventDataset,
        "--output-dir", $SpyDailyRouterJanJunOut,
        "--ticker", "SPY",
        "--history-start-month", "202507",
        "--start-month", "202601",
        "--end-month", "202606",
        "--decision-minute", "660",
        "--risk-capital", [string]$RiskCapital,
        "--min-train-days", "40",
        "--min-train-rows", "80",
        "--clip-target", "2.5",
        "--objective", "regression_l1",
        "--n-estimators", "220",
        "--learning-rate", "0.035",
        "--num-leaves", "7",
        "--min-child-samples", "16",
        "--subsample", "0.85",
        "--colsample-bytree", "0.75",
        "--reg-lambda", "8.0",
        "--lgb-jobs", [string]$Workers,
        "--seed", "20260621"
      ) + $DailySpyRouterExtraArgs)

      Invoke-PythonStep "Build SPY daily-router top-K volume backfill Jan-Jun partial" @(
        (Join-Path $ScriptDir "apply_event_monthly_volume_backfill.py"),
        "--primary-trades", (Join-Path $SpyDailyRouterJanJunOut "daily_source_router_trades.csv"),
        "--fallback-trades", $SpyCurrent,
        "--output-dir", $SpyDailyRouterBackfillJanJunOut,
        "--primary-name", "daily_router",
        "--fallback-name", "topk",
        "--start-month", "202601",
        "--end-month", "202606",
        "--min-month-trades", "24",
        "--max-day", "4",
        "--cooldown-minutes", "30",
        "--min-entry-minute", "660",
        "--risk-capital", [string]$RiskCapital
      )
    } else {
      Invoke-PythonStep "Build SPY June two-month selector" @(
        (Join-Path $ScriptDir "apply_event_stream_selector.py"),
        "--source", "nested=$(Join-Path $SpyJunPartialOut 'nested_volume_backfill_trades.csv')",
        "--source", "topk=$SpyCurrent",
        "--output-dir", $SpyJuneSelectorOut,
        "--ticker", "SPY",
        "--history-start-month", "202601",
        "--start-month", "202606",
        "--end-month", "202606",
        "--select-months", "2",
        "--risk-capital", [string]$RiskCapital,
        "--min-select-trades", "38",
        "--min-select-month-trades", "19",
        "--min-select-win-rate", "0.40",
        "--min-select-pf", "1.10",
        "--require-select-positive-months",
        "--min-call-rate", "0.20",
        "--max-call-rate", "0.80"
      )
    }
  }

  if ($UseDailySpyRouter) {
    Assert-PathExists (Join-Path $SpyDailyRouterJanJunOut "daily_source_router_trades.csv") "SPY daily router Jan-Jun trades"
    Assert-PathExists (Join-Path $SpyDailyRouterJanJunOut "daily_source_router_folds.csv") "SPY daily router Jan-Jun folds"
    Assert-PathExists (Join-Path $SpyDailyRouterBackfillJanJunOut "monthly_volume_backfill_trades.csv") "SPY daily-router backfill Jan-Jun trades"
  }

  Invoke-PythonStep "Build SPXW outer stream selector Jan-Jun partial" @(
    (Join-Path $ScriptDir "apply_event_stream_selector.py"),
    "--source", "s1export=$(Join-Path $SpxwOut 'trade_union_topk_regressor_trades.csv')",
    "--source", "maxday7export=$(Join-Path $SpxwLegacyMaxday7Export 'trade_union_topk_regressor_trades.csv')",
    "--source", "base_side=$SpxwBaseSide",
    "--source", "base_tdvp=$SpxwBaseTdvp",
    "--output-dir", $SpxwOuterSelectorJuneOut,
    "--ticker", "SPXW",
    "--history-start-month", "202510",
    "--start-month", "202601",
    "--end-month", "202606",
    "--select-months", "1",
    "--risk-capital", [string]$RiskCapital,
    "--min-select-trades", "19",
    "--min-select-month-trades", "19",
    "--min-select-win-rate", "0.40",
    "--min-select-pf", "0.50",
    "--min-call-rate", "0.20",
    "--max-call-rate", "0.80"
  )

  Invoke-PythonStep "Build QQQ outer stream selector Jan-Jun partial" @(
    (Join-Path $ScriptDir "apply_event_stream_selector.py"),
    "--source", "topk_recent=$(Join-Path $QqqOut 'trade_union_topk_regressor_trades.csv')",
    "--source", "d65=$QqqD65",
    "--source", "current=$QqqCurrent",
    "--output-dir", $QqqOuterSelectorJuneOut,
    "--ticker", "QQQ",
    "--history-start-month", "202510",
    "--start-month", "202601",
    "--end-month", "202606",
    "--select-months", "2",
    "--risk-capital", [string]$RiskCapital,
    "--min-select-trades", "38",
    "--min-select-month-trades", "19",
    "--min-select-win-rate", "0.42",
    "--min-select-pf", "1.10",
    "--require-select-positive-months",
    "--min-call-rate", "0.50",
    "--max-call-rate", "0.85"
  )

  if ($UseDailySpyRouter) {
    Invoke-PythonStep "Combine daily-router Jan-Jun partial forward check" @(
      (Join-Path $ScriptDir "combine_event_option_trade_streams.py"),
      "--trade-file", "SPXW_SELECTOR=$(Join-Path $SpxwOuterSelectorJuneOut 'stream_selector_trades.csv')",
      "--trade-file", "SPY_DAILY_ROUTER_BF=$(Join-Path $SpyDailyRouterBackfillJanJunOut 'monthly_volume_backfill_trades.csv')",
      "--trade-file", "QQQ_SELECTOR=$(Join-Path $QqqOuterSelectorJuneOut 'stream_selector_trades.csv')",
      "--fold-file", "SPXW_OUTER_S1=$(Join-Path $SpxwOuterSelectorJuneOut 'stream_selector_folds.csv')",
      "--fold-file", "SPY_DAILY_ROUTER=$(Join-Path $SpyDailyRouterJanJunOut 'daily_source_router_folds.csv')",
      "--fold-file", "SPY_TOPK_FALLBACK=$(Join-Path (Split-Path -Parent $SpyCurrent) 'intraday_circuit_folds.csv')",
      "--fold-file", "QQQ_OUTER_CALL50=$(Join-Path $QqqOuterSelectorJuneOut 'stream_selector_folds.csv')",
      "--output-dir", $JuneCombined,
      "--start-month", "202601",
      "--end-month", "202606",
      "--risk-capital", [string]$RiskCapital
    )
  } else {
    Invoke-PythonStep "Combine Jan-Jun partial forward check" @(
      (Join-Path $ScriptDir "combine_event_option_trade_streams.py"),
      "--trade-file", "SPXW_SELECTOR=$(Join-Path $SpxwOuterSelectorJuneOut 'stream_selector_trades.csv')",
      "--trade-file", "SPY_JANMAY=$(Join-Path $SpyJanMayOut 'nested_volume_backfill_trades.csv')",
      "--trade-file", "SPY_JUNE_S2=$(Join-Path $SpyJuneSelectorOut 'stream_selector_trades.csv')",
      "--trade-file", "QQQ_SELECTOR=$(Join-Path $QqqOuterSelectorJuneOut 'stream_selector_trades.csv')",
      "--fold-file", "SPXW_OUTER_S1=$(Join-Path $SpxwOuterSelectorJuneOut 'stream_selector_folds.csv')",
      "--fold-file", "SPY_JANMAY=$(Join-Path $SpyJanMayOut 'nested_volume_backfill_folds.csv')",
      "--fold-file", "SPY_JUNE_S2=$(Join-Path $SpyJuneSelectorOut 'stream_selector_folds.csv')",
      "--fold-file", "QQQ_OUTER_CALL50=$(Join-Path $QqqOuterSelectorJuneOut 'stream_selector_folds.csv')",
      "--output-dir", $JuneCombined,
      "--start-month", "202601",
      "--end-month", "202606",
      "--risk-capital", [string]$RiskCapital
    )
  }

  Invoke-PythonStepAllowFail "Verify Jan-Jun partial forward check (non-canonical)" @(
    (Join-Path $ScriptDir "verify_event_option_result.py"),
    "--result-dir", $JuneCombined,
    "--tickers", "SPXW", "SPY", "QQQ",
    "--start-month", "202601",
    "--end-month", "202606",
    "--min-win-rate", "0.45",
    "--min-profit-factor", "1.30",
    "--min-month-trades", "18",
    "--strict-month-trades",
    "--require-positive-months",
    "--min-call-rate", "0.20",
    "--max-call-rate", "0.80",
    "--disallow-weak-fold-modes"
  )

  Invoke-PythonStepAllowFail "Audit Jan-Jun partial curve health (non-canonical)" @(
    (Join-Path $ScriptDir "analyze_event_option_curve_health.py"),
    "--result-dir", $JuneCombined,
    "--start-month", "202601",
    "--end-month", "202606",
    "--risk-capital", [string]$RiskCapital
  )

  Invoke-PythonStep "Audit Jan-Jun partial research selection evidence" @(
    (Join-Path $ScriptDir "audit_event_option_research_selection.py"),
    "--result-dir", $JuneCombined,
    "--start-month", "202601",
    "--end-month", "202606"
  )
}

if ($FreezeForwardManifest) {
  if (-not $IncludeJunePartial) {
    throw "-FreezeForwardManifest requires -IncludeJunePartial so the frozen source includes the latest partial forward check."
  }
  $FreezeSelectionMethod = "frozen_spxw_outer_s1_qqq_outer_call50_spy_janmay_junes2"
  if ($UseDailySpyRouter) {
    $FreezeSelectionMethod = "frozen_spxw_outer_s1_qqq_outer_call50_spy_dailyrouter_bftopk"
    if (-not [string]::IsNullOrWhiteSpace($DailySpySourceHistoryTag)) {
      $FreezeSelectionMethod = "frozen_spxw_outer_s1_qqq_outer_call50_spy_dailyrouter_$($DailySpySourceHistoryTag)_bftopk"
    }
  }
  Invoke-PythonStep "Freeze forward-only research selection manifest" @(
    (Join-Path $ScriptDir "freeze_event_option_research_manifest.py"),
    "--result-dir", $JuneCombined,
    "--output-dir", $ForwardFreezeOut,
    "--frozen-before-month", $FreezeBeforeMonth,
    "--selection-method", $FreezeSelectionMethod,
    "--ticker-note", "Freeze generated by run_event_option_research_candidate.ps1 for future-only validation."
  )
}

Write-Host "`nResearch candidate artifacts ready:" -ForegroundColor Green
Write-Host "  Canonical Jan-May: $CanonicalCombined"
if ($IncludeJunePartial) {
  Write-Host "  Jan-Jun partial: $JuneCombined"
}
if ($FreezeForwardManifest) {
  Write-Host "  Forward freeze: $ForwardFreezeOut"
}
