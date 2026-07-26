# Event Option Research Selection Audit

This report audits architecture/source selection evidence. It is separate from fold chronology and profitability gates.

- Passed: False
- Strict: True
- Result dir: `research_papers\JEPA\results\event_option_mh30trail_causal1030_static_union_deploy202607_intersection_guarded_v1_walkforward`
- Evaluated months: 202601, 202602, 202603, 202604, 202605, 202606

## Interpretation

- Fold-level causality can be clean while research-level stream selection remains unproven.

## Tickers

| Ticker | Status | Selector Evidence | Source Streams | Selected Sources | Modes |
| --- | --- | ---: | --- | --- | --- |
| QQQ | multiple_streams_without_selector_evidence | False | n/a | n/a | monthly_retrain_scored_rows_fixed_policy |
| SPXW | multiple_streams_without_selector_evidence | False | n/a | n/a | monthly_retrain_scored_rows_fixed_policy |
| SPY | multiple_streams_without_selector_evidence | False | n/a | n/a | monthly_retrain_scored_rows_fixed_policy |

## Issues

- QQQ: multiple source streams are present without selector evidence
- SPXW: multiple source streams are present without selector evidence
- SPY: multiple source streams are present without selector evidence
- strict mode requires a valid research_selection_manifest.json

## Warnings

- selection manifest missing: research_selection_manifest.json

## Sources

```json
{}
```