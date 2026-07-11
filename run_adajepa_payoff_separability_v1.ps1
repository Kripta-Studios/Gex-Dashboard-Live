$ErrorActionPreference = "Stop"
$env:OMP_NUM_THREADS = "16"
$env:MKL_NUM_THREADS = "16"

python neural/jepa/analyze_adajepa_payoff_separability.py `
  --data tmp/event_option_dataset_execquote_causal1030_202501_202605_v1_physics/event_option_dataset.parquet `
  --spaces-dir research_papers/JEPA/results/_diagnostics/adajepa_shadow_coherent_spaces_202601_202605_seed20260618_v1 `
  --downstream-dir research_papers/JEPA/results/_diagnostics/adajepa_downstream_frozen_vs_adapted_202601_202605_v1 `
  --output-dir research_papers/JEPA/results/_diagnostics/adajepa_payoff_separability_202601_202605_v1 `
  --adapter-learning-rate 0.05 `
  --adapter-grad-clip 1.0 `
  --adapter-max-parameter-norm 0.5 `
  --infer-batch-size 4096
