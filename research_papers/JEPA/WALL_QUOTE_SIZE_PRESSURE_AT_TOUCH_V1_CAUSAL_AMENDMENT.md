# H-QSIZE1 causal geometry amendment

Status: frozen before completion of the 1,078-session complement capture, before
building the H-QSIZE1 dataset, before joining physical outcomes and before any
model fit.

The original predeclaration fixes exact contracts at `t,t-1,t-5,t-15`, a local
radius of 150 bps and explicit invalid/missing surfaces, but it does not state
the minimum geometry needed for a numeric local measurement. This amendment
closes that ambiguity without using outcomes:

- a right needs at least 5 identical local contracts present at all four clocks;
- at least 2 of those contracts must lie strictly below the current wall and at
  least 2 strictly above it;
- at each clock at least 3 shared local contracts must be signable;
- at each clock at least 5 contracts on the contemporaneous same-right surface
  must be signable for the relative-imbalance control;
- equality to the wall counts as neither below nor above;
- failure at any clock preserves the candidate, sets that right's 20 numerical
  measurements to missing and sets its validity flag false;
- contracts may never be substituted, remapped, forward-filled or zero-filled.

The F1 model receives exactly the 40 fields in `QSIZE_FEATURES`. The five
`QSIZE_QUALITY_FIELDS` remain in the dataset solely for coverage/data-gate audit
and do not enter either LR or LightGBM. This makes the original term
"quality-only" executable rather than treating validity flags as alpha.

The same rule applies to implicit validity. The original generic preprocessing
clause is narrowed as follows: LR and LightGBM both use train-only median
imputation with **no missing indicators and no native missing-value branches**.
The imputer is frozen with each model. Therefore a row cannot win merely because
quote size was unavailable, crossed, or came from one sidecar origin.

For the physical comparison, F0 and F1 are fitted and scored on the identical
`qsize_both_valid == True` complete-case rows. Invalid candidates remain in the
sealed/labeled dataset and their monthly absence counts against the frozen
minimum resolved-episode gate; they are never silently imputed into the model
sample. This paired restriction prevents even a tree from recovering
missingness through a median sentinel while keeping selection causal and
outcome-free.

Contract membership is also timestamp-exact. A quote at a clock is eligible
only if the frozen historical Greek source contains that exact
expiration/right/strike key at that clock. For the 1,441 sessions whose Greek
file lacks option `timestamp`, this membership is the stored row set already
bound to the native clock by the sealed sidecar's exact key-coverage proof; the
underlying clock is not accepted as a new quote timestamp. A daily union of
contracts is forbidden because it could admit a contract before its stored
appearance.

The sealed quote captures end at 14:29 regular and 12:54 half-day while the
candidate universe contains 88 decisions at 14:30/12:55. Those 88 candidates
must be preserved, must have both rights invalid and all 40 measurements
missing, and cannot create missingness features under the preprocessing above.
No terminal quote is inferred, forward-filled or recaptured after outcomes.

These constants are frozen because medians and a local-versus-surface contrast
are not identifiable from a one-sided or nearly empty strike set. They are not
tunable parameters and may not be relaxed after inspecting coverage, labels or
outer results. The original sequential physical gate remains unchanged,
including one-sided paired Wilcoxon `p < 0.0167`.
