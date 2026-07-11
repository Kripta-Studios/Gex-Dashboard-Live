# PAIRWISE_OPPORTUNITY_AND_SIDE_SELECTION_V1 — Results

- Dataset SHA-256: `d3c37b5f4511787ec19cf4478790377562b2b6c913185a2425f1b0cef7a3a408`
- Feature hash: `fa2057653ed0327b7f84a165c25f6e6d31e31b3b05c5591593e9c0bd3056d50e`
- Scientific cells: `99`
- Degenerate scientific cells: `0`
- Scientific pass: `False`
- C0 economic passing cells: `0/99`
- P1 economic passing cells: `0/99`
- C0 pooled PF: `undefined (0 trades)`
- P1 pooled PF: `undefined (0 trades)`
- Production modified: `false`
- 2026 opened: `false`

## Scientific result

- P1 balanced-accuracy delta positive: `57/99` (`57.58%`; required `>=60%`).
- Median balanced-accuracy delta: `+0.0040`.
- Wilcoxon paired p-value: `0.1171`.
- P1 Spearman positive: `58/99` (`58.59%`; required `>=60%`).
- Median P1 Spearman with side advantage: `+0.0303`.
- Annual median delta: positive in 2023, 2024 and 2025.
- Degenerate cells: `0`; no cells were removed from the denominator.

Ticker medians (`C0 BA`, `P1 BA`, `P1-C0 delta`, `P1 Spearman`):

| Ticker | C0 BA | P1 BA | Delta | Spearman |
| --- | ---: | ---: | ---: | ---: |
| QQQ | 0.4931 | 0.4924 | -0.0091 | 0.0073 |
| SPXW | 0.5051 | 0.5060 | +0.0053 | 0.0331 |
| SPY | 0.5180 | 0.5183 | +0.0104 | 0.0462 |

The pairwise formulation does not extract a stable CALL/PUT signal and degrades QQQ.

## Economic result

**INVALIDATED AFTER RUN.** V1 treated `opt_exit_minutes` as an absolute clock minute
inside the inner gate and subtracted the entry minute, although the builder stores
elapsed duration and the shared scheduler already adds it to entry. This forced all
holds to fail. The scientific model-level section above is unaffected. Authoritative
economic metrics require the separately predeclared V1r1 hold-duration correction.

## Failure localization

Post-run, non-promotional scheduler diagnostics show that always CALL, always PUT,
30-minute momentum and 30-minute contrarian rules are negative across the evaluated
years/tickers. A non-causal oracle that chooses the better side on every row obtains
annual ticker PF `4.55..11.73`, WR `73.5%..86.7%`, minimum monthly frequency `>=19`
and 100% positive months. Thus the labels contain substantial payoff headroom, while
the V1 side objective/features fail to predict it.

V1 is rejected and must not be retuned. The next analysis must persist all 63 inner
configurations per fold to identify the eliminating gates. A subsequent experiment,
if predeclared, may change only the side target from an unweighted binary label to
direct `side_advantage = call_return - put_return` regression while freezing the
opportunity head, feature matrix, folds, scheduler and economic contract.
