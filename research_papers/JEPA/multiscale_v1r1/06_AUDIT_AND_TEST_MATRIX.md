# Audit and test matrix
Synthetic tests only by default; importing/collecting tests cannot open D:/ThetaData.
AUDIT-001: import independence, semantic reconstruction, rehashed perturbations.
Contract:59/39/24/18/92048/488; calendar holiday/half-day/DST/date-vs-expiration;
bars gap/duplicate/subminute/future/16:00; SPXW causal repair, late repair and
unauthorized repair; snapshots60s boundary/future/duplicate/OI join; walls ties,
zero-gamma absent/multiple roots; states approach/precedence/history before tensor;
zero vs missing masks; ablation invariant to all walls; entry first q/ties/no retry;
exit identity/deadline/penalty; costs+1.40/-0.60; scheduler equality and independence;
18 folds; premature payoff/hash/resume; metrics empty/zero/infinite/strict gates;
incremental underperformance fails; SSL clock shortcut/projection/uniform NCE/
same-trajectory candidates/causal residual; registry denial; resource bounds.
Semantic mutations: strike with unchanged PnL, late quote, absent commission,
rejection changed to execution, overlap, premature access, copied adverse WR,
level information in ablation. Detect semantic errors even after hashes updated.
Float64 tolerance1e-10 relative/1e-12 absolute; exact discrete/Decimal/model outputs.
Real integration commands require explicit manifests and are excluded from pytest.
