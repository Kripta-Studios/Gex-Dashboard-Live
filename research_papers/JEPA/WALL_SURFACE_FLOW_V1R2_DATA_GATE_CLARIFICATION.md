# WALL_SURFACE_FLOW V1R2 — data-gate clarification

Status: frozen after the full outcome-free data build and before any physical
label, model score, option payoff or PnL was built or inspected. It does not
modify the immutable V1R2 exact-spot repair predeclaration or its captured hash.

The complete 2,519-session V1R2 build passed source coverage, exact clocks,
schedule grids, spot parity, missingness and every control gate. One feasibility
cell alone failed: QQQ 2022 `role_break_pressure_w1m` has six observed states,
range `[-1,1]`, zero rate 6.09% and no missing values.

The code had interpreted the predeclared term "nondegenerate" as at least ten
distinct values. Ten was not stated in the predeclaration and is inappropriate
for a one-minute wall-local pressure ratio, which is often one-sided and thus
near-binary by construction.

Before labels, nondegenerate is frozen as all of:

- at least two finite distinct states in every ticker-year core cell;
- zero rate below 99.5%;
- zero missing values.

This clarification changes no feature formula, feature allowlist, row, source,
candidate, label or outcome. It was not chosen from model metrics or PnL. A
one-state, missing or effectively-all-zero feature still fails closed.
