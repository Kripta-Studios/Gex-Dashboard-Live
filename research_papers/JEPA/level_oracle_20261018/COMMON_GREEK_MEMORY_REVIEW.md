# Read-only resource review for the424-column fit

Reviewed2026-10-18 21:06:03UTC. No benchmark, fit, source mutation, gate change or process intervention was performed. The current supervisorPID49024 has not launched its trainer and no424 FIT_STARTED exists according to the owner's status. Its12GiB physical/16GiB commit gate is inherited verbatim from the152-column control.

## Measured evidence already available

The completed152-column control used the same270,377 rows,200 trees,31 leaves, maximum depth6, max_bin63, force_col_wise and four LightGBM threads. Its launcher reported exit0 after30.038294seconds, peak private1,234,886,656bytes and peak RSS752,410,624bytes. Sampling interval was1second. RSS takes the maximum of sampled RSS and the Windows peak-working-set field when exposed; private memory remains sampled. These are observations of that execution, not hard bounds.

Authority: `D:/GexResearchArtifacts/level_oracle_20261018/market_cue_control_v1_fit_launch/exit.json`, SHA `308f7424d3b2c594f454ab5dd17f419b639e523e7617d4dec69bb1951c8a9658`. Process record SHA `7dc6c760c5c3a95a5ba3cd39bec9bf67393a70c24463418f5fca5182b614c5ce`; launcher SHA `10820ce06e487a8cc9122e82bc5cd246a78c5c9add710ef63dfeb2d8c03ff481`. Control model completion remains pinned SHA `9d5e0bbc5744fbdbf909e4f43c11796b9aa42c418cfcf7c0e85018a82783f97a`.

A much wider completed causal-rollout fit provides additional context:285,286×1,955 float32, same LightGBM configuration, recorded6,573,084,672private bytes and7,488,806,912RSS for the residual model. Its input matrix is2,230,936,520bytes. This process imports a different, heavier training stack, so this is not an exact scaling experiment. The47,430×1,954 teacher peaked at2,619,752,448private bytes. Those five-second observations are preserved in the memory log SHA `70c186af047231a5fa51554c6f6b26411327b02ad55e0748b257301482e26379` and described in `CAUSAL_ROLLOUT_RESOURCE_NOTE.md`.

## Allocation analysis, not a formal native-memory bound

| Quantity | Control152 | Proposed424 |
|---|---:|---:|
| Float32 matrix array bytes | 164,389,216 | 458,559,392 |
| One dense uint8 bin per row/feature, estimate | 41,097,304 | 114,639,848 |
|31×columns×63×16 histogram bytes, illustrative estimate | 4,749,696 | 13,249,152 |

The additional input is294,170,176bytes; the illustrative additional dense-bin allocation is73,542,544bytes. The424 `.npy` file is458,559,520bytes including its header, rather than a multi-gigabyte tensor. Input targets and weights together occupy about4.33MB. The current trainer checks the152-column prefix in8,192-row blocks and deletes both comparison mappings before entering the fit. Full TRAIN readback predictions add2.16MB; model readback runs in8,192-row batches after deleting the fit object. There is one model fit, with no simultaneous training policy or GPU allocation in this process.

LightGBM/scikit-learn may create validation, native binning, histogram and allocator copies. The exact number depends on data sparsity, library version and implementation details; neither an unsigned-bin estimate nor a linear extrapolation is a proven upper bound. Nevertheless, even multiplying the entire observed152 private peak by424/152 gives about3.45GB (3.21GiB), whereas many interpreter and library costs do not scale with feature count. A provisional **4GiB total private-process budget** is conservative relative to that extrapolation and the inspected allocations, but is not a guarantee or an enforced cap.

The snapshot at21:05:06UTC reported14,804,951,040available physical bytes and15,562,571,776free commit bytes. Physical headroom passes the inherited gate; free commit falls below16GiB. Other jobs and Windows can change these quantities independently of this fit. The424 process's own future increment must therefore be considered separately from the reserve kept for the host and other jobs.

## Recommendation

There is **no measured evidence that this424-column fit requires16GiB of free commit or12GiB of free physical RAM**. These thresholds are a broad inherited safeguard. There is measured evidence supporting a smaller, explicitly budgeted admission policy, although no exact424 peak yet exists.

If an already running owned job is about to free memory, finishing that job and retaining the current gate is operationally simplest. If free commit remains stably around14–15GiB, indefinite waiting for16GiB is not justified by the inspected fit's allocations alone. A separately reviewed operational launcher could admit this specific fit at **8GiB available RAM and10GiB free commit**, representing a provisional4GiB total-process budget plus4GiB physical and6GiB commit reserves. Require several consecutive resource samples, no simultaneous launch of another large owned job, and1second private/RSS/host-commit monitoring through completion. Record the realized peak and preserve the exact model/data/config/checkpoint rules. Do not automatically terminate or refit a started fit on a temporary threshold crossing.

This is a proposed admission policy, **not an activated override**. It would need its own bound launcher/review and explicit coordination by the root agent. The existing scientific trainer and its method stay unchanged. If the estimated4GiB budget proves too small, the evidence should revise future operational budgets; it must not be retroactively described as a measured bound. No process belonging to another task should be stopped or modified to meet either threshold.
