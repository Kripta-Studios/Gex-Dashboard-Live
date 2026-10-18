"""Fixed-bin descriptive calibration of saved scores; never fits or predicts."""
from __future__ import annotations

import os

for _var in ('OMP_NUM_THREADS', 'OPENBLAS_NUM_THREADS', 'MKL_NUM_THREADS', 'NUMEXPR_NUM_THREADS'):
    os.environ[_var] = '1'

import argparse  # noqa: E402
from datetime import datetime, timezone  # noqa: E402
import hashlib  # noqa: E402
import json  # noqa: E402
from pathlib import Path  # noqa: E402
import shutil  # noqa: E402

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
import pyarrow as pa  # noqa: E402

ROOT = Path('D:/GexResearchArtifacts/level_oracle_20261018')
CUTS = np.array([-.1, -.05, -.02, 0., .02, .05, .1], dtype=np.float64)
BIN_LABELS = ('[-inf,-0.1)', '[-0.1,-0.05)', '[-0.05,-0.02)', '[-0.02,0)',
              '[0,0.02)', '[0.02,0.05)', '[0.05,0.1)', '[0.1,inf)')
TARGETS = {'gbt_net': 'net_base', 'gbt_advantage': 'dp_advantage', 'tcn_teacher': 'net_base'}


def sha(path):
    digest = hashlib.sha256()
    with Path(path).open('rb') as handle:
        for block in iter(lambda: handle.read(8 * 1024 * 1024), b''):
            digest.update(block)
    return digest.hexdigest()


def write_json(path, value):
    Path(path).write_text(json.dumps(value, indent=2, allow_nan=False), encoding='utf-8')


def bin_indices(scores):
    scores = np.asarray(scores, dtype=np.float64)
    if not np.isfinite(scores).all():
        raise ValueError('Nonfinite saved score')
    return np.searchsorted(CUTS, scores, side='right')


class Accumulator:
    def __init__(self):
        self.n = self.positive = self.zero = self.days = 0
        self.sum_pred = self.sum_target = self.sum_error = self.sse = 0.
        self.target_mean = self.target_m2 = 0.
        self.target_min, self.target_max = np.inf, -np.inf
        self.bin_n = np.zeros(8, dtype=np.int64)
        self.bin_pred = np.zeros(8, dtype=np.float64)
        self.bin_target = np.zeros(8, dtype=np.float64)

    def update(self, scores, targets):
        p, y = np.asarray(scores, dtype=np.float64), np.asarray(targets, dtype=np.float64)
        if p.ndim != 1 or y.shape != p.shape or not np.isfinite(y).all():
            raise ValueError('Invalid/nonfinite target or incompatible shape')
        indices = bin_indices(p)
        self.days += 1
        if not len(p):
            return
        n = len(y)
        mean = float(y.mean())
        m2 = float(np.square(y - mean).sum())
        delta = mean - self.target_mean
        total = self.n + n
        self.target_m2 += m2 + delta * delta * self.n * n / total
        self.target_mean += delta * n / total
        self.n = total
        self.target_min = min(self.target_min, float(y.min()))
        self.target_max = max(self.target_max, float(y.max()))
        self.sum_pred += float(p.sum())
        self.sum_target += float(y.sum())
        error = p - y
        self.sum_error += float(error.sum())
        self.sse += float(np.square(error).sum())
        self.positive += int((p > 0).sum())
        self.zero += int((p == 0).sum())
        self.bin_n += np.bincount(indices, minlength=8)
        self.bin_pred += np.bincount(indices, weights=p, minlength=8)
        self.bin_target += np.bincount(indices, weights=y, minlength=8)

    def result(self):
        n = self.n
        constant = n == 0 or self.target_min == self.target_max
        group = dict(actions=n, days=self.days, mean_prediction=self.sum_pred / n if n else None,
                     mean_target=self.sum_target / n if n else None,
                     bias=self.sum_error / n if n else None, rmse=float(np.sqrt(self.sse / n)) if n else None,
                     r2=None if constant else 1 - self.sse / self.target_m2,
                     r2_undefined_reason='NO_ACTIONS' if not n else ('CONSTANT_TARGET' if constant else None),
                     positive_score_count=self.positive, positive_score_share=self.positive / n if n else None,
                     zero_score_count=self.zero)
        bins = [dict(bin_index=i, interval=BIN_LABELS[i], actions=int(self.bin_n[i]),
                     mean_prediction=float(self.bin_pred[i] / self.bin_n[i]) if self.bin_n[i] else None,
                     mean_target=float(self.bin_target[i] / self.bin_n[i]) if self.bin_n[i] else None)
                for i in range(8)]
        return group, bins


def aligned_target(frame, ids, column):
    if frame.action_id.duplicated().any() or len(frame) != len(ids) or set(frame.action_id) != set(ids):
        raise ValueError('Target/action identity mismatch')
    return frame.set_index('action_id')[column].reindex(ids).to_numpy(dtype=np.float64)


def verify_file_coverage(expected, manifest_names, actual_names):
    if set(expected) != set(manifest_names) or set(expected) != set(actual_names):
        raise ValueError('Prediction file/manifest/day coverage mismatch')


def verify_audit_binding(audit, learners, top_hashes, index_hash, completion_hash):
    if audit['status'] != 'PASS_INDEPENDENT_LEARNER_ECONOMIC_EXECUTION_AUDIT':
        raise ValueError('Learner execution audit has not passed')
    binding = audit['binding']
    if Path(binding['learner_root']).resolve() != Path(learners).resolve():
        raise ValueError('Learner audit belongs to another root')
    expected = {'learner_summary_sha256': top_hashes['summary.json'],
                'freeze_sha256': top_hashes['freeze.json'],
                'validation_prediction_manifest_sha256': top_hashes['validation/prediction_hashes.json'],
                'test_prediction_manifest_sha256': top_hashes['test/prediction_hashes.json'],
                'oracle_index_sha256': index_hash, 'oracle_completion_sha256': completion_hash}
    if any(binding.get(key) != value for key, value in expected.items()):
        raise ValueError('Learner execution audit hash binding mismatch')


def render_report(summary):
    lines = ['# Calibración descriptiva de scores guardados', '',
             'No se ha ajustado ningún modelo, generado nuevas predicciones ni cambiado la selección. Todos los resultados son desarrollo histórico ya visto.', '',
             'Se evalúan **todas las acciones ofrecidas**, no trades ejecutados. Las filas comparten estados y trayectorias; sus millones de valores no son millones de observaciones independientes. No se calculan significaciones iid ni bootstrap por acción.', '',
             'Score y target se dividen por la misma escala de riesgo congelada de entrenamiento. El sesgo es predicción menos target. `gbt_advantage` se contrasta con ventaja DP privilegiada; sus métricas no representan calibración de retorno esperado.', '',
             '| Periodo | Ticker | Modelo / target | Acciones | Media score | Media target | Sesgo | RMSE | R² | Score > 0 |',
             '|---|---|---|---:|---:|---:|---:|---:|---:|---:|']
    for row in summary['groups']:
        r2 = f"{row['r2']:.4f}" if row['r2'] is not None else 'indefinido'
        lines.append(f"| {row['period']} | {row['ticker']} | {row['model']} / {row['target']} | {row['actions']:,} | {row['mean_prediction']:.5f} | {row['mean_target']:.5f} | {row['bias']:.5f} | {row['rmse']:.5f} | {r2} | {100 * row['positive_score_share']:.2f}% |")
    lines += ['', 'Los ocho bins fijados antes de abrir scores son `[-inf,-.1,-.05,-.02,0,.02,.05,.1,inf]`, cerrados a izquierda y abiertos a derecha. `bins.csv` conserva n/media score/media target de los 144 grupos-bin, incluidos bins vacíos. Un cero pertenece a `[0,.02)` pero no cuenta como score positivo.', '',
              'Un RMSE bajo no demuestra rentabilidad de la política. Un sesgo positivo no demuestra que restar una constante mejore su economía. Este diagnóstico no selecciona bins, filtros, modelos o umbrales; la política congelada y sus resultados ejecutados se evalúan por separado.', '',
              f"Escalas USD congeladas: `{summary['risk_scales_usd']}`. Salida: `{summary['output']}`.", '',
              'Se verificaron completion del motor, índice auditado, binding de freeze, normalizers y manifests, hashes de cada NPZ y de los sidecars consumidos, y el orden exacto de action_ids. Esto no refittea modelos ni sustituye la auditoría independiente de ejecución de los aprendices.', '',
              f"Estado de auditoría independiente de aprendices al arrancar: `{summary['learner_audit']['status']}`. Si no se proporcionó un audit PASS con binding comprobado, el estado es UNVERIFIED y no se afirma validación independiente. Código SHA `{summary['script_sha256']}`; especificación SHA `{summary['spec_sha256']}`."]
    return '\n'.join(lines) + '\n'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--learners', type=Path, required=True)
    parser.add_argument('--engine', type=Path, default=ROOT / 'engine_v1')
    parser.add_argument('--output', type=Path, default=ROOT / 'score_calibration_v1')
    parser.add_argument('--learner-audit', type=Path)
    args = parser.parse_args()
    pa.set_cpu_count(1)
    pa.set_io_thread_count(1)
    completed = json.loads((args.learners / 'summary.json').read_text(encoding='utf-8'))
    if completed['status'] != 'COMPLETED_CAUSAL_LEARNER_DEVELOPMENT':
        raise RuntimeError('Do not read scores before learners COMPLETED')
    freeze = json.loads((args.learners / 'freeze.json').read_text(encoding='utf-8'))
    top_hashes = {name: sha(args.learners / name) for name in ('summary.json', 'freeze.json', 'normalizers.json', 'validation/prediction_hashes.json', 'test/prediction_hashes.json')}
    for name in ('normalizers.json', 'validation/prediction_hashes.json'):
        if top_hashes[name] != freeze['artifacts'][name]:
            raise ValueError('Frozen artifact changed: ' + name)
    scales = json.loads((args.learners / 'normalizers.json').read_text(encoding='utf-8'))['risk_scales_usd']
    if (set(scales) != {'SPXW', 'SPY', 'QQQ'} or scales != completed['risk_scales_usd']
            or any(not np.isfinite(v) or v <= 0 for v in scales.values())):
        raise ValueError('Invalid or changed frozen risk scales')
    index_path = args.engine / 'index.parquet'
    index_hash = sha(index_path)
    completion = json.loads((args.engine / 'completion.json').read_text(encoding='utf-8'))
    if (completion['status'] != 'COMPLETE' or completion['index_sha256'] != index_hash
            or freeze['oracle_audit']['binding']['index_sha256'] != index_hash
            or Path(freeze['oracle_audit']['binding']['engine_root']).resolve() != args.engine.resolve()):
        raise ValueError('Audited engine identity mismatch')
    index = pd.read_parquet(index_path)
    if len(index) != 2601 or index.status.value_counts().to_dict() != {'COMPLETE': 2595, 'MISSING_SOURCE': 6}:
        raise ValueError('Unexpected oracle universe')
    expected_days = int(((index.status == 'COMPLETE') & index.split.isin(['validation', 'test'])).sum())
    learner_audit = {'status': 'UNVERIFIED_AT_DIAGNOSTIC_RUN', 'path': None, 'sha256': None}
    if args.learner_audit is not None:
        audit = json.loads(args.learner_audit.read_text(encoding='utf-8'))
        verify_audit_binding(audit, args.learners, top_hashes, index_hash, sha(args.engine / 'completion.json'))
        learner_audit = dict(status=audit['status'], path=str(args.learner_audit), sha256=sha(args.learner_audit),
                             binding_verified=True)
    args.output.mkdir(parents=True, exist_ok=False)
    spec = Path(__file__).with_name('SCORE_CALIBRATION_SPEC.md')
    script_hash, spec_hash = sha(__file__), sha(spec)
    shutil.copy2(__file__, args.output / 'score_calibration.executed.py')
    shutil.copy2(spec, args.output / spec.name)
    write_json(args.output / 'execution.json', dict(status='RUNNING', script_sha256=script_hash,
               spec_sha256=spec_hash, started_utc=datetime.now(timezone.utc).isoformat(), source_hashes=top_hashes))
    accumulators = {(period, ticker, model): Accumulator() for period in ('validation', 'test')
                    for ticker in ('SPXW', 'SPY', 'QQQ') for model in TARGETS}
    consumed = 0
    with (args.output / 'input_manifest.jsonl').open('w', encoding='utf-8') as handle:
        for period in ('validation', 'test'):
            days = index.loc[(index.split == period) & (index.status == 'COMPLETE')]
            manifest = json.loads((args.learners / period / 'prediction_hashes.json').read_text(encoding='utf-8'))
            expected = {f'{row.ticker}_{row.date}.npz' for row in days.itertuples(index=False)}
            actual = {path.name for path in (args.learners / period).glob('*.npz')}
            verify_file_coverage(expected, manifest, actual)
            for day in days.itertuples(index=False):
                file = f'{day.ticker}_{day.date}.npz'
                path = args.learners / period / file
                if sha(path) != manifest[file]:
                    raise ValueError('Saved prediction changed')
                frames, hashes = {}, {'scores': manifest[file]}
                for name, columns in (('actions', ['action_id']), ('labels', ['action_id', 'net_base']),
                                      ('advantages', ['action_id', 'dp_advantage'])):
                    source = Path(day.day_root) / f'{name}.parquet'
                    hashes[name] = sha(source)
                    if hashes[name] != getattr(day, name + '_sha256'):
                        raise ValueError('Audited sidecar changed: ' + str(source))
                    frames[name] = pd.read_parquet(source, columns=columns)
                ids = frames['actions'].action_id.to_numpy()
                if len(np.unique(ids)) != len(ids):
                    raise ValueError('Duplicate canonical action IDs')
                values = {'net_base': aligned_target(frames['labels'], ids, 'net_base'),
                          'dp_advantage': aligned_target(frames['advantages'], ids, 'dp_advantage')}
                with np.load(path, allow_pickle=False) as saved:
                    if set(saved.files) != {'action_ids', *TARGETS} or not np.array_equal(ids, saved['action_ids']):
                        raise ValueError('Saved score schema/order mismatch')
                    for model, target in TARGETS.items():
                        scale = scales[day.ticker]
                        scores = np.asarray(saved[model], dtype=np.float64) / scale
                        accumulators[period, day.ticker, model].update(scores, values[target] / scale)
                handle.write(json.dumps(dict(period=period, ticker=day.ticker, date=day.date, actions=len(ids), hashes=hashes)) + '\n')
                consumed += 1
                if consumed % 100 == 0:
                    handle.flush()
                    print(json.dumps(dict(status='RUNNING', days=consumed)), flush=True)
    groups, bins = [], []
    for (period, ticker, model), accumulator in accumulators.items():
        group, grouped_bins = accumulator.result()
        keys = dict(period=period, ticker=ticker, model=model, target=TARGETS[model])
        groups.append(dict(**keys, **group))
        bins.extend(dict(**keys, **row) for row in grouped_bins)
    for name, digest in top_hashes.items():
        if sha(args.learners / name) != digest:
            raise ValueError('Learner binding changed during analysis')
    if consumed != expected_days:
        raise ValueError('Consumed prediction-day count differs from complete index')
    summary = dict(status='COMPLETED_DESCRIPTIVE_SCORE_CALIBRATION', groups=groups,
                   bins=BIN_LABELS, risk_scales_usd=scales, days=consumed,
                   script_sha256=script_hash, spec_sha256=spec_hash, learner_bindings=top_hashes,
                   engine_index_sha256=index_hash, learner_audit=learner_audit,
                   all_actions_not_executed_trades=True, models_or_selection_changed=False,
                   completed_utc=datetime.now(timezone.utc).isoformat(), output=str(args.output))
    pd.DataFrame(groups).to_csv(args.output / 'groups.csv', index=False)
    pd.DataFrame(bins).to_csv(args.output / 'bins.csv', index=False)
    write_json(args.output / 'summary.json', summary)
    (args.output / 'SCORE_CALIBRATION.md').write_text(render_report(summary), encoding='utf-8')
    write_json(args.output / 'execution.json', dict(status='COMPLETE', script_sha256=script_hash,
               spec_sha256=spec_hash, days=consumed, summary_sha256=sha(args.output / 'summary.json')))
    print(json.dumps(dict(status=summary['status'], days=consumed, groups=len(groups), bins=len(bins))), flush=True)


if __name__ == '__main__':
    main()
