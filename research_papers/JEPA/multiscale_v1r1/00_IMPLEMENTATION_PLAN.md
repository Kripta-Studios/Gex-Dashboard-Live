# Implementation and verification plan
Authoritative intent: user plan dated 2026-09-17, net USD utility for one contract.
Starting HEAD 29724f857185a046a09680b8edf9708d89949619; V1 immutable.
Question: do histories of interactions with levels improve executable dollar PnL
over a no-level ablation under identical opportunities, costs and restrictions?

Stages: A publish binding contract, registry and five handoffs; B implement pure
contract, inventory/restricted reader, features/gate, accounting/replay/models/SSL,
freeze/runner/eligibility/CLI and separate semantic auditor; synthetic tests, lint,
compile, resource preflight; publish code. C inventory and outcome-free source gate;
D independent audit and published compact evidence; E/F prepare and publish first
fold freeze; G evaluate/audit; H repeat exact 18-fold calendar; I bootstrap/final
audit; J terminal evidence and synchronized handoffs. No generic tuning CLI.

Stop with precise evidence on data/dependency/resource/publication/causality/audit
block. A blocked upstream stage keeps downstream stages unexecuted, not PASS.
No winner stops before test. Global economic gates wait for all 18 months. No rescue.
Terminal success is only DEVELOPMENT_PASS_REQUIRES_SHADOW. No production changes.
Raw and user untracked files preserved; explicit paths only, no clean/reset/add-all.
The remaining numbered documents spell out deliverables and acceptance rules.
