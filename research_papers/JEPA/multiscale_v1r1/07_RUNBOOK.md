# Runbook
Run from repository root, Python3.14.2, family lock only; no global installs.
Each command requires --contract research_papers/JEPA/multiscale_v1r1/01_PREDECLARATION.md
and --root D:/GexResearchArtifacts/multiscale_v1r1/<new-run>. Manifest dependencies
are explicit and verified, not inferred from directory existence. Publication
receipts identify committed paths, commit and remote ancestry before access.

```powershell
python -m pytest tests/multiscale_v1r1
python -m ruff check neural/jepa/multiscale_v1r1 neural/jepa/multiscale_v1r1_audit tests/multiscale_v1r1
python -m compileall -q neural/jepa/multiscale_v1r1 neural/jepa/multiscale_v1r1_audit
```

Stages (append required contract/root/manifests printed by --help):
```text
python -m neural.jepa.multiscale_v1r1.cli preflight
python -m neural.jepa.multiscale_v1r1.cli inventory
python -m neural.jepa.multiscale_v1r1.cli build-gate
python -m neural.jepa.multiscale_v1r1_audit.cli data-gate
python -m neural.jepa.multiscale_v1r1.cli prepare-fold --month YYYYMM
python -m neural.jepa.multiscale_v1r1.cli evaluate-fold --month YYYYMM
python -m neural.jepa.multiscale_v1r1_audit.cli fold --month YYYYMM
python -m neural.jepa.multiscale_v1r1.cli summarize
python -m neural.jepa.multiscale_v1r1_audit.cli final
```
Publish A docs; B code/tests/preflight; D gate/audit; F each frozen manifest before
corresponding test. Explicit git add paths; force-add only intended compact ignored
evidence. git commit then git push origin HEAD; no force push. Push failure means
BLOCKED_PUBLICATION and no next outcome stage. No blanket add/reset/clean.
Resume identical contract/code/runtime/inputs/artifacts only; changed post-outcome
code invalidates run. A blocker leaves subsequent stages closed, not waived.
