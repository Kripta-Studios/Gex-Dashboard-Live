# Feature and artifact schema
FEAT-001/002: canonical X5[12,59,39], X15[8,59,39], uint8 masks, eight finite
float32 statics. Flatten values5,masks5,values15,masks15,statics=92048.
SSL token interleaves slot-major 39 values then39 masks=4602. Ablation controls
12x12+8x12 values, same masks, eight statics=488. Schema enumerates all names.
event_id=ticker|trade_date|D (never strike or future exit); ordered actions
CALL/PUT x25/35/50 x60/90/120/180. Contract identity is a separate field.

Artifacts: runtime_manifest.json; source_manifest.parquet; coverage.parquet;
events.parquet; feature_schema.json; tensor_shards/YYYYMM/ticker/*.npy;
data_gate_summary.json; data_gate_audit.json; payoffs/YYYYMM/;
folds/YYYYMM/frozen/; folds/YYYYMM/ledger.parquet; access_log.jsonl;
evaluation_summary.json; audit_summary.json. Raw never overwritten.
Use atomic new-directory finalization; store byte hashes and canonical-content
hashes. Big artifacts remain D:/GexResearchArtifacts/multiscale_v1r1/; Git keeps
compact manifests/localization, no raw/tensors/large models. Read-only memmaps.
