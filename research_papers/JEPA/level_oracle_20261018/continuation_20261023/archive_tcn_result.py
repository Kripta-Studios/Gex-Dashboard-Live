"""Copy the completed TCN evidence; never evaluates or changes source artifacts."""
from pathlib import Path
import hashlib
import json

BASE = Path("D:/GexResearchArtifacts/level_oracle_20261018")
HERE = Path(__file__).resolve().parent
EVALUATION = BASE / "tcn_row_mixed_calendar_v1_evaluation"
AUDIT = BASE / "tcn_row_mixed_calendar_v1_economic_audit_01/audit.json"
AUDIT_SHA = "09b416926fe1da455d8507f0b28e24a8ed8a2ae42845ecbb9326ebf442ca85e5"


def sha(data):
    return hashlib.sha256(data).hexdigest()


def write_preserved(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        if path.read_bytes() != data:
            raise ValueError(f"Preserve existing different bytes: {path}")
    else:
        with path.open("xb") as stream:
            stream.write(data)
    if path.read_bytes() != data:
        raise ValueError(f"Copy verification failed: {path}")


def main():
    audit_bytes = AUDIT.read_bytes()
    if sha(audit_bytes) != AUDIT_SHA:
        raise ValueError("External audit binding changed")
    audit = json.loads(audit_bytes)
    if audit["status"] != "PASS_INDEPENDENT_TCN_ROW_MIXED_CALENDAR_ECONOMIC_AUDIT":
        raise ValueError("Audit status")
    members = {Path(k).resolve(): v for k, v in audit["verified_files"].items()}
    scientific = [EVALUATION / name for name in (
        "summary.json", "completion.json", "freeze.json", "source_inputs.json",
        "identity.json", "session_calendar.json", "expected_full_calendar.csv",
        "feature_schema.json", "normalizers.json", "training_complete.json",
        "tcn_control.pt", "tcn_variant.pt")]
    policies = [f"{arm}__{threshold}" for arm in ("control", "variant")
                for threshold in (0, 5, 10)]
    for period in ("validation", "test"):
        scientific.append(EVALUATION / period / "summary.json")
        for policy in policies:
            for suffix in ("attempts", "ledger", "daily_coverage"):
                scientific.append(EVALUATION / period / f"{policy}_{suffix}.parquet")
    producer_log = BASE / "tcn_row_mixed_calendar_v1_evaluation_launch_20261023_01"
    auditor_log = BASE / "tcn_row_mixed_calendar_v1_economic_audit_01_launch_20261023_01"
    receipts = [producer_log / "process.json", producer_log / "monitored_exit.json",
                auditor_log / "process.json", auditor_log / "exit.json"]
    for path in (receipts[1], receipts[3]):
        if json.loads(path.read_bytes())["exit_code"] != 0:
            raise ValueError(f"Nonzero process exit: {path}")
    records = []
    for source in scientific + [AUDIT] + receipts:
        content = source.read_bytes()
        digest = sha(content)
        if source in scientific and members.get(source.resolve()) != digest:
            raise ValueError(f"Not an exact independently audited member: {source}")
        relative = Path("evidence") / source.relative_to(BASE)
        destination = HERE / relative
        write_preserved(destination, content)
        if sha(source.read_bytes()) != digest:
            raise ValueError(f"Source changed during copy: {source}")
        records.append(dict(source=str(source.resolve()), copy=relative.as_posix(),
                            bytes=len(content), sha256=digest,
                            audited_member=source in scientific))
    manifest = dict(scope="COMPLETED_TCN_EVIDENCE_COPY_ONLY", audit_sha256=AUDIT_SHA,
                    files=records, large_matrices_and_raw_remain_local=True)
    write_preserved(HERE / "tcn_evidence_manifest.json",
                    (json.dumps(manifest, indent=2) + "\n").encode())
    lines = ["# Evidencia TCN conservada el 23 de octubre", "",
             "Copias exactas del resultado terminado y auditado. Ningún ajuste o replay nuevo.",
             "Los NPZ por día, matrices y datos brutos permanecen locales. El audit completo",
             "incluye sus rutas y hashes. Los recibos de proceso se preservan por separado",
             "de los miembros de la auditoría científica.", "",
             "| Copia | Bytes | SHA256 | Fuente local |", "|---|---:|---|---|"]
    lines += [f"| [{r['copy']}]({r['copy']}) | {r['bytes']} | `{r['sha256']}` | `{r['source']}` |"
              for r in records]
    write_preserved(HERE / "TCN_ARTIFACTS.md", ("\n".join(lines) + "\n").encode())
    print(json.dumps(dict(files=len(records), bytes=sum(r["bytes"] for r in records),
                          mismatches=0, audit_sha256=AUDIT_SHA)))


if __name__ == "__main__":
    main()
