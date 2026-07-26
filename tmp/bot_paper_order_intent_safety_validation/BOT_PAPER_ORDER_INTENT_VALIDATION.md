# Bot Paper Order Intent Validation

- Passed: True
- Orders: 2/2
- JSONL: `tmp\bot_paper_order_intent_safety_validation\paper_order_intents_jepa.jsonl`

This validates local paper order intent generation only. It does not submit orders to a broker.

## Checks

```json
{
  "two_orders_written": true,
  "all_are_paper_only": true,
  "all_have_option_contract": true,
  "all_have_limit_orders": true,
  "bto_side": true,
  "stc_side": true,
  "bto_limit_ceil_cent": true,
  "stc_limit_floor_cent": true,
  "bto_max_debit_under_risk": true,
  "stc_estimated_credit_positive": true
}
```
