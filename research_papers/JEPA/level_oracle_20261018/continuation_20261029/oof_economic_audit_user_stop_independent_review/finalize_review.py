"""Publish local review documents after all independent evidence gates close."""
from pathlib import Path
from datetime import datetime, timezone
import hashlib
import json
import os
import re
import shutil
import sys
import psutil

psutil.Process().cpu_affinity([0])
assert psutil.Process().cpu_affinity()==[0]
os.environ.update(OMP_NUM_THREADS='1',OPENBLAS_NUM_THREADS='1',MKL_NUM_THREADS='1',PYTHONDONTWRITEBYTECODE='1')

code=Path(sys.argv[1]).resolve()
root=Path(__file__).parent
archive=code/'continuation_20261029/oof_economic_audit_user_stop_independent_review'
def sha(p): return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def read(p): return json.loads(Path(p).read_text(encoding='utf-8'))
def ref(p): return dict(path=str(p),sha256=sha(p))
test=read(root/'attempt_01/result.json')
assert test['exit_code']==0 and test['cpu_affinity']==[0] and test['threads']==1
assert test['available_ram_bytes']>=2_000_000_000 and test['free_commit_bytes']>=2_000_000_000
stdout=(root/'attempt_01/stdout.log').read_text(encoding='utf-8')
match=re.search(r'18 passed in ([0-9.]+)s',stdout)
assert match and not (root/'attempt_01/stderr.log').read_bytes()
seconds=float(match.group(1))
static=read(root/'static_verification_01.json')
mapping=read(root/'final_map_01.json')
assert static['status']=='PASS_INDEPENDENT_STATIC_AND_COMPACT_EVIDENCE_REVIEW'
assert mapping['status']=='PASS_EXACT_FINAL_IMPLEMENTATION_REVIEW_FILES_MAP'
for name,h in mapping['files'].items(): assert sha(code/name)==h
for sub in ('attempt_01','attempt_02_static','attempt_03_final_map'):
    result=read(root/sub/'result.json')
    assert result['exit_code']==0
    for p,h in result['logs'].items(): assert sha(p)==h
    for p,h in result['files'].items():
        # Sources may evolve only among this reviewer's own scripts; snapshot pins remain exact.
        assert sha(root/sub/Path(p).name)==h
author=read(code/'OOF_ECONOMIC_AUDIT_USER_STOP_IMPLEMENTATION_RESULT_20261029.json')
assert static['cpu_evidence_externally_verified']==author['cpu0_inheritance_test']
assert sha(author['cpu0_inheritance_test']['evidence']['path'])==author['cpu0_inheritance_test']['evidence']['sha256']

archive.mkdir(parents=True,exist_ok=False)
sources=list(p for p in root.iterdir() if p.is_file())
for sub in ('attempt_01','attempt_02_static','attempt_03_final_map'):
    sources.extend(p for p in (root/sub).iterdir() if p.is_file())
copies=[]
for source in sorted(sources):
    target=archive/source.relative_to(root)
    target.parent.mkdir(parents=True,exist_ok=True)
    shutil.copyfile(source,target)
    h=sha(source)
    assert sha(target)==h
    copies.append(dict(original=str(source),copy=str(target),sha256=h,size=source.stat().st_size))
manifest=dict(status='PASS_INDEPENDENT_REVIEW_COMPACT_COPIES',files=len(copies),bytes=sum(p['size'] for p in copies),copies=copies,artificial_fixture_trees_local_only=True)
manifest_path=archive/'archive_manifest.json'
manifest_path.write_text(json.dumps(manifest,indent=2),encoding='utf-8')
root_manifest=root/'archive_manifest.json'
with root_manifest.open('x',encoding='utf-8') as f: json.dump(manifest,f,indent=2)
assert sha(root_manifest)==sha(manifest_path)

md=code/'OOF_ECONOMIC_AUDIT_USER_STOP_IMPLEMENTATION_REVIEW_20261029.md'
report=code/'OOF_ECONOMIC_AUDIT_USER_STOP_IMPLEMENTATION_REVIEW_20261029.json'
text=f'''# Revisión independiente del supervisor económico tras la continuación OOF

29 de octubre de 2026. **CLEAR, exclusivamente IMPLEMENTATION_ONLY**.
`runtime_authorized=false`. No se ejecutó admisión real de fuentes o prefijo,
continuación científica, auditoría económica, API o publicación Git.

Se revisaron íntegramente los bloques nuevos de autoridad, ambas cadenas de
proceso, snapshot, cronología y monitor, además del delta contra el supervisor
V2R1 congelado. Código económico revisado: `48169acfe736a55855f742a26af53cc262a0450b57cc7bea3ce43a623ac7bfa7`;
tests del autor: `5a2cdbe7d1a8fb376da0d01ef9aeeb5073115921cf1b06ec7939e59a4fd35304`.
El JSON compañero fija el mapa exacto de {mapping['files_count']} miembros devuelto por
`review_files()` después de sellarse la review independiente del productor.

Las tres observaciones preliminares quedaron resueltas y verificadas:

- A1: el validador consume el esquema real `INDEPENDENT_METADATA_HASH_REVIEW_V1`,
  sus ocho referencias, estado, source-admission SHA, tail y resultado fuente.
  Se contrastó el documento existente como metadata; no se readmitieron payloads.
- A2: snapshot sellado con manifests local/repositorio idénticos, membresía
  exacta de los 39 compactos previos, cinco locks, request/binding originales y
  todos los logs y observer históricos. Cada original exige una copia distinta
  en cada una de las dos raíces, con tamaño y SHA exactos.
- A3: ambas reviews operativas enlazan artefactos externos de herencia CPU0,
  cuyos bytes, pins de código/tests y observaciones se verifican y forman parte
  de la publicación exigida. La evidencia del autor se verificó externamente
  contra su probe nativo, stdout, stderr y exit0; no se tomó sólo su estado PASS.

La tanda independiente `attempt_01` terminó **18 PASS**, exit0, {seconds:.2f}s,
con CPU0, threads1 y gate RAM/commit2GB observado antes del proceso. Sus casos
cubren admisión artificial sin escritura/Popen, revisión de prefijo incompatible,
copias faltantes/duplicadas/tamaño/membresía extra, failure con idéntico hash en
otra ruta, PID/creation/exit falsificados, omisión de evidencia CPU en publicación,
drift posterior a admisión, lock ocupado, herencia nativa CPU0/threads1 y exit
retenido tras fallo de observación psutil. Este último caso reutiliza un focal
del autor; los otros diecisiete son probes independientes nuevos. El constructor
de árboles artificiales se reutiliza del test del autor. No se repitió la suite
de 53 casos ni suites científicas antiguas.

La comparación AST independiente encuentra **20 nodos idénticos**. La cola
científica que valida doce fases y 27 controles conserva el AST al sustituir
únicamente `finished.pipeline_closure` por el argumento `closure`, descontar su
asignación local de `source_sha` y separar la nueva llamada de cronología.
El hash normalizado es `31ed13147f057221fa28e2d2b0492bb12133ae83c09ce156ce8f57a17cc1fd28`.
Los quince pins congelados, incluido el auditor `e7481fbe…`, coinciden.
No cambiaron costes, políticas, modelos, selección o alcance FULL_H1.

Se rehashearon las **50 parejas** compactas del autor, **668.246 bytes**, y los
ocho recibos de intento con sus logs. El intento final del autor conserva
53 PASS; sus intentos anteriores y fallos no se suman como otra suite.
Las verificaciones estática y de mapa final terminaron exit0 en intentos
separados; no se cuentan como pruebas pytest.

La evidencia independiente compacta conserva {len(copies)} copias, {manifest['bytes']} bytes,
en `continuation_20261029/oof_economic_audit_user_stop_independent_review/`,
con mapas original/copia/SHA. Los árboles artificiales de fixtures permanecen
locales. Cada ejecución conserva fuentes previas, comando, gate, afinidad,
stdout/stderr y exit real observado por `Popen.wait()` del harness; ese recibo
del harness no se presenta como un recibo de proceso científico.

No quedan hallazgos de implementación abiertos. Esta review mantiene el
exit15/failure original y exige un exit0 posterior distinto, las doce fases,
la preservación del snapshot y nuevos request/binding económicos revisados y
publicados antes del único auditor separado. Publicación de esta implementación
y admisión real siguen pendientes. `winner_selected=null`,
`technical_ready=false` y `promotion_approved=false` permanecen vigentes.
'''
with md.open('x',encoding='utf-8') as f: f.write(text)
result=dict(status='PASS_OOF_ECONOMIC_AUDIT_USER_STOP_IMPLEMENTATION_REVIEW',decision='CLEAR',scope='IMPLEMENTATION_ONLY',runtime_authorized=False,reviewer='independent_subagent_review_audit_continuation',reviewed_utc=datetime.now(timezone.utc).isoformat(),files=mapping['files'],files_count=mapping['files_count'],review_report=ref(md),cpu0_inheritance_test=author['cpu0_inheritance_test'],cpu_evidence_externally_verified=True,producer_review=mapping['producer_review'],independent_tests=dict(passed=18,failed=0,seconds=seconds,new_independent_cases=17,reused_author_focal_cases=1,receipt=ref(archive/'attempt_01/result.json'),exit_code=0,cpu_affinity=[0],threads=1),static_verification=ref(archive/'static_verification_01.json'),final_map_verification=ref(archive/'final_map_01.json'),archive_manifest=ref(manifest_path),author_result=ref(code/'OOF_ECONOMIC_AUDIT_USER_STOP_IMPLEMENTATION_RESULT_20261029.json'),author_evidence_pairs_verified=50,unchanged_ast_nodes=static['unchanged_ast_nodes'],scientific_validation_tail_identical=True,frozen_pins=static['frozen_pins'],resolved_findings=['A1_actual_independent_prefix_review_schema','A2_exact_snapshot_full_old_logs_two_copies','A3_external_CPU0_evidence_verified_and_published'],unresolved_findings=[],real_prefix_admitted=False,real_source_admission_executed=False,real_preflight_executed=False,scientific_pipeline_executed=False,economic_auditor_executed=False,economics_interpreted=False,api_accessed=False,git_publication_performed=False,real_payloads_rehashed=False,pending_gates=['Publish exact implementation/tests/reviews and evidence.','Actual continuation closes all twelve phases with retained new exit0 and immutable baseline.','New real FULL_H1 economic request/binding reviewed and published.','Default economic metadata admission inspected before one separate audit.'],winner_selected=None,technical_ready=False,promotion_approved=False)
with report.open('x',encoding='utf-8') as f: json.dump(result,f,indent=2)
print(json.dumps(dict(review=ref(report),report=ref(md),archive_manifest=ref(manifest_path),files_count=mapping['files_count'],compact_copies=len(copies),compact_bytes=manifest['bytes']),indent=2))
