"""Archive existing stopped-research evidence; never import or run research code."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import shutil

HERE = Path(__file__).resolve().parent
ROOTS = {
    "level_oracle_20261018": Path("D:/GexResearchArtifacts/level_oracle_20261018"),
    "restart_20261018": Path("D:/GexResearchArtifacts/restart_20261018"),
}
MAX_BYTES = 8_000_000


def sha(path):
    with path.open("rb") as handle:
        return hashlib.file_digest(handle, "sha256").hexdigest()


def main():
    candidates = set()
    # Compact terminal evidence only, not bulk raw, matrices or per-day labels.
    names = {"summary.json", "audit.json", "completion.json", "audit_binding.json",
             "payoff_sign_diagnostics.json", "process_exit.json", "training_comparison.json",
             "train_fit_diagnostic.json", "train_comparison.json", "final_verification.json"}
    for family, root in ROOTS.items():
        for folder in [root] + [p for p in root.iterdir() if p.is_dir()]:
            candidates.update((family, p) for p in folder.iterdir()
                              if p.is_file() and p.name in names)
            for sub in ("validation", "test", "independent_audit_01"):
                child = folder / sub
                if child.is_dir():
                    candidates.update((family, p) for p in child.iterdir()
                                      if p.is_file() and p.name in names)
    root = ROOTS["level_oracle_20261018"]
    special = [
        "market_cue_comparison_v1/freeze.json", "market_cue_comparison_v1/period2025.json",
        "market_cue_comparison_v1/period2026.json", "monthly_walk_forward_v1/run_contract.json",
        "monthly_walk_forward_v1/months/202501/economics.json",
        "monthly_walk_forward_v1/months/202501/economics.complete.json",
        "monthly_walk_forward_v1/months/202501/daily.json",
        "monthly_walk_forward_v1/months/202501/daily.complete.json",
        "monthly_resource_transition_v1/before_stop.json",
        "monthly_resource_transition_v1/stopped.json",
        "monthly_resource_transition_v1/wrapper_process.json",
        "tcn_row_mixed_v1/training_complete.json", "tcn_row_mixed_v1/latest_checkpoint.json",
        "tcn_row_mixed_v1_train_logs_01/runtime.json",
        "common_greek_control_resource_v1/run_contract.json",
        "common_greek_control_resource_v1/model.complete.json",
        "common_greek_control_resource_v1/export.complete.json",
        "market_cue_control_v1/run_contract.json", "market_cue_control_v1/model.complete.json",
        "causal_rollout_v1/validation_freeze.json",
    ]
    for relative in special:
        path = root / relative
        if not path.is_file():
            raise FileNotFoundError(path)
        candidates.add(("level_oracle_20261018", path))
    for model_root in ("learners_v1", "episode_learners_v1", "tcn_flags_v1",
                       "tcn_row_mixed_v1", "market_cue_control_v1",
                       "common_greek_control_resource_v1", "causal_rollout_v1/models",
                       "monthly_walk_forward_v1/models"):
        for path in (root / model_root).iterdir():
            if path.is_file() and (path.suffix in (".pt", ".txt")
                                  or path.name in ("normalizers.json", "feature_schema.json",
                                                   "gbt_config.json", "neural_training.json")
                                  or path.name.endswith(".complete.json") and "models" in model_root):
                candidates.add(("level_oracle_20261018", path))
    records, oversized = [], []
    for family, source in sorted(candidates, key=lambda pair: (pair[0], str(pair[1]))):
        relative = source.relative_to(ROOTS[family])
        if source.stat().st_size > MAX_BYTES:
            oversized.append(dict(source=str(source), bytes=source.stat().st_size,
                                  reason="SIZE_LIMIT_PRESERVED_LOCAL"))
            continue
        target = HERE / "evidence" / family / relative
        expected = sha(source)
        target.parent.mkdir(parents=True, exist_ok=True)
        if target.exists():
            if sha(target) != expected:
                raise ValueError("Immutable archive differs: " + str(target))
        else:
            shutil.copyfile(source, target)
        if sha(target) != expected or sha(source) != expected:
            raise ValueError("Source/copy changed: " + str(source))
        records.append(dict(source=str(source), copy=target.relative_to(HERE).as_posix(),
                            bytes=target.stat().st_size, sha256=expected))
    result = dict(scope="EXISTING_EVIDENCE_COPY_ONLY_NO_RESEARCH_EXECUTION", files=records,
                  not_copied=oversized, total_bytes=sum(row["bytes"] for row in records),
                  full_dataset_archived=False)
    (HERE / "evidence_manifest.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    lines = ["# Archivo de evidencia al detener", "",
             "Copias exactas de artefactos existentes. No recalcula resultados ni acredita todos los archivos referenciados dentro de cada manifest.",
             "Los datasets grandes y las predicciones por día permanecen en las rutas locales originales.", "",
             f"Archivos copiados: {len(records)}. Bytes: {result['total_bytes']}. Límite por archivo: {MAX_BYTES}.", "",
             "| Copia | Bytes | SHA256 | Origen |", "|---|---:|---|---|"]
    for row in records:
        lines.append(f"| [{row['copy']}]({row['copy']}) | {row['bytes']} | `{row['sha256']}` | `{row['source']}` |")
    if oversized:
        lines += ["", "## Archivos grandes conservados sólo localmente", ""]
        lines += [f"- `{row['source']}`: {row['bytes']} bytes." for row in oversized]
    (HERE / "ARTIFACTS.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(json.dumps({"copied": len(records), "bytes": result["total_bytes"],
                      "oversized": len(oversized), "manifest_sha256": sha(HERE / "evidence_manifest.json")}))


if __name__ == "__main__":
    main()
