"""Descriptive hindsight-only profile, streaming completed oracle day artifacts.

Never trains a model or changes the action universe/selection. Real runs require
the complete 2,595-day producer output. Prices are projected from sealed caches;
this analysis does not replace independent raw-source or economic audits.
"""
from __future__ import annotations

import os

for _var in ('OMP_NUM_THREADS', 'OPENBLAS_NUM_THREADS', 'MKL_NUM_THREADS',
             'NUMEXPR_NUM_THREADS', 'VECLIB_MAXIMUM_THREADS', 'BLIS_NUM_THREADS'):
    os.environ[_var] = '1'

import argparse  # noqa: E402
from concurrent.futures import ProcessPoolExecutor  # noqa: E402
from datetime import datetime, timezone  # noqa: E402
import hashlib  # noqa: E402
import json  # noqa: E402
from pathlib import Path  # noqa: E402
import shutil  # noqa: E402
from types import SimpleNamespace  # noqa: E402

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
import pyarrow as pa  # noqa: E402

ROOT = Path('D:/GexResearchArtifacts/level_oracle_20261018')
SOURCE_BITS = {1: 'FIB', 2: 'CALL_OI', 4: 'PUT_OI', 8: 'CALL_GAMMA', 16: 'PUT_GAMMA'}
GEOMETRY = ('contract_i', 'right', 'target_center', 'stop_center', 'band')


def sha(path):
    digest = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(8 * 1024 * 1024), b''):
            digest.update(block)
    return digest.hexdigest()


def write_json(path, value):
    Path(path).write_text(json.dumps(value, indent=2, allow_nan=False), encoding='utf-8')


def exact_neighbor(joined, action, offset, lookup=None):
    """Only an actually offered identical frozen action at adjacent decision time."""
    if lookup is not None:
        key = (int(action.state_i) + offset, *(getattr(action, field) for field in GEOMETRY))
        return lookup.get(key)
    candidate = joined.loc[joined.state_i == int(action.state_i) + offset]
    for field in GEOMETRY:
        candidate = candidate.loc[candidate[field] == getattr(action, field)]
    if len(candidate) > 1:
        raise ValueError('Identical geometry/contract offered more than once')
    return candidate.iloc[0] if len(candidate) else None


def direct_rank(values, selected):
    values = np.asarray(values, dtype=float)
    return 1 + int(np.sum(values > float(selected) + 1e-8))


def process_day(record):
    if isinstance(record, dict):
        record = SimpleNamespace(**record)
    day = Path(record.day_root)
    summary_path = day / 'summary.json'
    if sha(summary_path) != record.summary_sha256:
        raise ValueError('Published summary hash mismatch')
    summary = json.loads(summary_path.read_text(encoding='utf-8'))
    if summary['status'] != 'COMPLETED_HINDSIGHT_ORACLE_DAY':
        raise ValueError('Incomplete oracle day')
    projections = {
        'states': ['state_i', 'spot', 'ib_range', 'eligible'],
        'levels': ['state_i', 'level_id', 'center', 'source_mask'],
        'actions': ['action_id', 'state_i', 'contract_i', 'right', 'target_center', 'stop_center', 'band'],
        'labels': ['action_id', 'status', 'net_base'],
        'advantages': ['action_id', 'q_value', 'wait_value', 'dp_advantage'],
        'oracle_ledger': None,
    }
    frames, hashes = {}, {}
    for name, columns in projections.items():
        path = day / f'{name}.parquet'
        digest = sha(path)
        if digest != summary['artifact_hashes'][path.name]:
            raise ValueError('Artifact hash mismatch: ' + str(path))
        before = path.stat()
        frames[name] = pd.read_parquet(path, columns=columns)
        after = path.stat()
        if (before.st_size, before.st_mtime_ns) != (after.st_size, after.st_mtime_ns):
            raise ValueError('Artifact changed during read')
        hashes[name] = digest
    ledger = frames['oracle_ledger']
    if len(ledger) != int(record.trades) or not np.isclose(ledger.net_base.sum(), record.net_base, rtol=0, atol=1e-6):
        raise ValueError('Producer index/ledger disagreement')
    cache = Path(record.cache_path)
    metadata_path = cache.with_suffix('.json')
    if sha(metadata_path) != record.cache_meta_sha256:
        raise ValueError('Cache metadata hash mismatch')
    metadata = json.loads(metadata_path.read_text(encoding='utf-8'))
    if metadata['sha256'] != record.cache_npz_sha256:
        raise ValueError('Cache identity mismatch')
    # Deliberately read only two arrays, not option matrices or raw sources.
    with np.load(cache, allow_pickle=False) as stored:
        spot = stored['spot']
        valid = stored['spot_valid'] & np.isfinite(spot) & (spot > 0)
    hashes['spot_arrays_sha256'] = hashlib.sha256(spot.tobytes() + valid.tobytes()).hexdigest()
    joined = frames['actions'].merge(frames['labels'], on='action_id', validate='one_to_one')
    if len(joined) != int(record.actions_count):
        raise ValueError('Action count mismatch')
    states = frames['states'].set_index('state_i', verify_integrity=True)
    levels = frames['levels'].set_index(['state_i', 'level_id'], verify_integrity=True)
    by_state = {int(i): part for i, part in joined.groupby('state_i', sort=False)}
    level_groups = {int(i): part for i, part in frames['levels'].groupby('state_i', sort=False)}
    neighbor_states = set(ledger.state_i.astype(int) - 1) | set(ledger.state_i.astype(int) + 1)
    neighbor_lookup = {}
    for candidate in joined.loc[joined.state_i.isin(neighbor_states)].itertuples(index=False):
        key = (int(candidate.state_i), *(getattr(candidate, field) for field in GEOMETRY))
        if key in neighbor_lookup:
            raise ValueError('Identical geometry/contract offered more than once')
        neighbor_lookup[key] = candidate
    q = frames['advantages'].set_index('action_id', verify_integrity=True)
    rows = []
    for action in ledger.itertuples(index=False):
        minute = int(action.state_i)
        state = states.loc[minute]
        width = float(state.ib_range)
        if not width > 0:
            raise ValueError('Oracle trade with invalid IB')
        entry_level = levels.loc[(minute, int(action.entry_level_id))]
        candidates = by_state[minute]
        alternatives = candidates.loc[candidates.action_id != action.action_id]
        values = alternatives.net_base.to_numpy(float)
        same_levels = level_groups[minute]
        direction = 1 if int(action.right) == 0 else -1
        distance = direction * (same_levels.center.to_numpy(float) - float(state.spot))
        target_distance = direction * (float(action.target_center) - float(state.spot))
        intermediate = ((distance > 1e-10) & (distance < target_distance - 1e-10)
                        & (same_levels.level_id.to_numpy(int) != int(action.entry_level_id)))
        offered_closer = intermediate & (distance > 2 * action.band) & (distance <= 3 * width)
        fill_i, exit_i = int(action.entry_i), int(action.exit_i)
        fill_observed, exit_observed = bool(valid[fill_i]), bool(valid[exit_i])
        signed_move = direction * (float(spot[exit_i]) - float(spot[fill_i])) if fill_observed and exit_observed else None
        approach = 'missing'
        if valid[minute - 5]:
            earlier_spot = float(spot[minute - 5])
            approach = ('below' if earlier_spot < entry_level.center - action.band else
                        ('above' if earlier_spot > entry_level.center + action.band else 'inside'))
        intent = 'unclassified'
        if approach in ('below', 'above'):
            intent = 'continuation' if (approach == 'below') == (direction == 1) else 'rejection'
        selected_q = float(q.loc[action.action_id, 'q_value'])
        other_q = q.loc[alternatives.action_id, 'q_value'].to_numpy(float)
        wait_value = float(q.loc[action.action_id, 'wait_value'])
        second_q = max(float(other_q.max()) if len(other_q) else -np.inf, wait_value)
        row = dict(ticker=str(record.ticker), date=str(record.date), split=str(record.split),
                   action_id=int(action.action_id), state_i=minute, entry_i=fill_i, exit_i=exit_i,
                   right='CALL' if direction == 1 else 'PUT', delta_bucket=float(action.delta_bucket),
                   selected_delta=float(action.selected_delta), strike=float(action.strike),
                   entry_source_mask=int(entry_level.source_mask), target_source_mask=int(action.target_source_mask),
                   approach_5m=approach, geometric_intent=intent,
                   stop_source_mask=int(action.stop_source_mask), hold_minutes=int(action.hold_minutes), reason=str(action.reason),
                   net_base=float(action.net_base), net_adverse=float(action.net_adverse),
                   target_distance_ib=target_distance / width, stop_distance_ib=abs(action.stop_center - state.spot) / width,
                   target_rank_offered=1 + int(offered_closer.sum()), known_nonentry_centers_to_target=int(intermediate.sum()),
                   decision_distance_bands=abs(state.spot - entry_level.center) / action.band,
                   fill_distance_bands=abs(spot[fill_i] - entry_level.center) / action.band if fill_observed else None,
                   spot_direction_move=signed_move, positive_option_wrong_spot=bool(signed_move < 0 and action.net_base > 0) if signed_move is not None else None,
                   alternative_actions=len(alternatives), alternative_winners=int((values > 0).sum()),
                   alternative_losers=int((values < 0).sum()), alternative_no_fills=int((alternatives.status == 'NO_FILL').sum()),
                   alternative_net_sum=float(values.sum()), alternative_mean=float(values.mean()) if len(values) else None,
                   alternative_median=float(np.median(values)) if len(values) else None,
                   alternative_p10=float(np.quantile(values, .1)) if len(values) else None,
                   alternative_p90=float(np.quantile(values, .9)) if len(values) else None,
                   alternative_min=float(values.min()) if len(values) else None,
                   alternative_max=float(values.max()) if len(values) else None,
                   selected_direct_rank=direct_rank(candidates.net_base, action.net_base),
                   same_state_max_direct=float(candidates.net_base.max()), dp_value=selected_q,
                   dp_advantage_over_wait=selected_q - wait_value, dp_margin_over_runnerup=selected_q - second_q)
        if row['decision_distance_bands'] > 1 + 1e-9:
            raise ValueError('Oracle selected a decision outside entry zone')
        for offset, name in ((-1, 'earlier'), (1, 'later')):
            neighbor = exact_neighbor(joined, action, offset, neighbor_lookup)
            row[name + '_offered'] = neighbor is not None
            row[name + '_filled'] = bool(neighbor.status == 'FILLED') if neighbor is not None else None
            row[name + '_net'] = float(neighbor.net_base) if neighbor is not None else None
            row[name + '_net_change'] = float(neighbor.net_base - action.net_base) if neighbor is not None else None
        rows.append(row)
    day_stats = dict(ticker=str(record.ticker), date=str(record.date), split=str(record.split),
                     actions=len(joined), action_winners=int((joined.net_base > 0).sum()),
                     action_losers=int((joined.net_base < 0).sum()), no_fill_actions=int((joined.status == 'NO_FILL').sum()),
                     action_net_sum=float(joined.net_base.sum()), trades=len(rows), net_base=float(ledger.net_base.sum()),
                     eligible_states=int(states.eligible.sum()), scheduled_states=len(states))
    return rows, day_stats, dict(ticker=str(record.ticker), date=str(record.date), inputs=hashes)


def distribution(values):
    array = pd.Series(values).dropna().to_numpy(float)
    if not len(array):
        return dict(n=0)
    return dict(n=len(array), mean=float(array.mean()), min=float(array.min()),
                p10=float(np.quantile(array, .1)), median=float(np.median(array)),
                p90=float(np.quantile(array, .9)), max=float(array.max()))


def counts(values):
    return {str(key): int(value) for key, value in pd.Series(values).value_counts().sort_index().items()}


def aggregate(trades, days, calendar_rows):
    n = len(trades)
    result = dict(trades=n, available_days=len(days), calendar_days=calendar_rows,
                  net_base=float(trades.net_base.sum()), net_adverse=float(trades.net_adverse.sum()),
                  positive_trades=int((trades.net_base > 0).sum()), losing_trades=int((trades.net_base < 0).sum()),
                  zero_trades=int((trades.net_base == 0).sum()), min_net_base=float(trades.net_base.min()),
                  min_net_adverse=float(trades.net_adverse.min()),
                  side=counts(trades.right), delta_bucket=counts(trades.delta_bucket), exits=counts(trades.reason),
                  approach_5m=counts(trades.approach_5m), geometric_intent=counts(trades.geometric_intent),
                  holding=distribution(trades.hold_minutes), holding_counts=counts(trades.hold_minutes),
                  target_distance_ib=distribution(trades.target_distance_ib), stop_distance_ib=distribution(trades.stop_distance_ib),
                  target_rank_offered=counts(trades.target_rank_offered), known_nonentry_centers_to_target=counts(trades.known_nonentry_centers_to_target),
                  farther_than_nearest_offered=int((trades.target_rank_offered > 1).sum()),
                  has_intermediate_nonentry_centers_to_target=int((trades.known_nonentry_centers_to_target > 0).sum()),
                  fill_observed=int(trades.fill_distance_bands.notna().sum()),
                  fill_near_entry_zone=int((trades.fill_distance_bands <= 1 + 1e-10).sum()),
                  fill_distance_bands=distribution(trades.fill_distance_bands),
                  direction_observed=int(trades.spot_direction_move.notna().sum()),
                  profitable_against_spot=int(trades.positive_option_wrong_spot.fillna(False).sum()),
                  profitable_against_spot_net=float(trades.loc[trades.positive_option_wrong_spot == True, 'net_base'].sum()),  # noqa: E712
                  direct_rank=counts(trades.selected_direct_rank),
                  not_best_standalone=int((trades.selected_direct_rank > 1).sum()),
                  standalone_sacrifice=distribution(trades.same_state_max_direct - trades.net_base),
                  dp_advantage_over_wait=distribution(trades.dp_advantage_over_wait),
                  dp_margin_over_runnerup=distribution(trades.dp_margin_over_runnerup),
                  all_action_count=int(days.actions.sum()), all_action_winners=int(days.action_winners.sum()),
                  all_action_losers=int(days.action_losers.sum()), all_action_no_fills=int(days.no_fill_actions.sum()),
                  all_action_mean=float(days.action_net_sum.sum() / days.actions.sum()),
                  eligible_states=int(days.eligible_states.sum()), scheduled_states=int(days.scheduled_states.sum()))
    for which in ('entry', 'target', 'stop'):
        mask = trades[which + '_source_mask']
        result[which + '_source_combinations'] = counts(mask)
        result[which + '_source_memberships'] = {name: int(((mask.astype(int) & bit) != 0).sum()) for bit, name in SOURCE_BITS.items()}
        result[which + '_fib_only'] = int((mask == 1).sum())
        result[which + '_walls_only'] = int(((mask.astype(int) & 1) == 0).sum())
        result[which + '_fib_and_walls'] = int(((mask.astype(int) & 1 != 0) & (mask != 1)).sum())
    alternative_count = int(trades.alternative_actions.sum())
    result['same_state_alternatives'] = dict(
        actions=alternative_count, winners=int(trades.alternative_winners.sum()), losers=int(trades.alternative_losers.sum()),
        no_fills=int(trades.alternative_no_fills.sum()),
        action_weighted_mean=float(trades.alternative_net_sum.sum() / alternative_count) if alternative_count else None,
        state_weighted_mean=float(trades.alternative_mean.mean()),
        per_state_median=distribution(trades.alternative_median),
        per_state_p90_minus_p10=distribution(trades.alternative_p90 - trades.alternative_p10),
        per_state_min=distribution(trades.alternative_min), per_state_max=distribution(trades.alternative_max))
    for name in ('earlier', 'later'):
        subset = trades.loc[trades[name + '_offered']]
        result[name + '_one_minute'] = dict(
            matched=len(subset), filled=int(subset[name + '_filled'].fillna(False).sum()),
            positive_net=int((subset[name + '_net'] > 0).sum()),
            direct_pnl_change=distribution(subset[name + '_net_change']),
            selected_net=float(subset.net_base.sum()), neighbor_net=float(subset[name + '_net'].sum()))
    return result


def pct(value, total):
    return f'{100 * value / total:.1f}%' if total else 'n/a'


def render_report(summary):
    out = ['# Qué hizo el oracle de niveles', '',
           '**Análisis descriptivo retrospectivo: todas las decisiones del oracle usan el futuro. No es un modelo operable.**', '',
           f"Estado de auditoría económica independiente al redactar: **{summary['audit_status']}**. Este analizador verifica hashes de los artefactos diarios que consume y reconstruye estadísticas; no sustituye esa auditoría.", '',
           'Universo completo disponible: 2.595 ticker-días; calendario 2.601, con seis ausencias de fuente. Se separan 2023–2024 (ajuste), 2025 (selección) y 2026H1 (desarrollo cronológico ya visto). Ninguna tabla selecciona filtros o modelos usando 2026.', '',
           '## Magnitud y duración', '',
           '| Ticker | Periodo | Días disponibles | Trades | Neto base USD | Neto adverso USD | Holding p10 / mediana / p90 (min) | TARGET / STOP / EOD |',
           '|---|---|---:|---:|---:|---:|---|---|']
    labels = {'train': '2023–24', 'validation': '2025', 'test': '2026H1'}
    for group in summary['groups']:
        x, ticker, split = group['statistics'], group['ticker'], group['split']
        h, e = x['holding'], x['exits']
        out.append(f"| {ticker} | {labels[split]} | {x['available_days']} | {x['trades']:,} | {x['net_base']:,.2f} | {x['net_adverse']:,.2f} | {h['p10']:g} / {h['median']:g} / {h['p90']:g} | {e.get('TARGET', 0)} / {e.get('STOP', 0)} / {e.get('EOD', 0)} |")
    out += ['', 'Un contrato por operación. Son sumas de PnL, no rentabilidad porcentual de una cuenta ni una cartera con capital dimensionado. El escenario adverso aplica más costes a la misma trayectoria elegida con costes base; no reoptimiza el oracle.', '',
            'WAIT permite alcanzar cualquier estado futuro sin perder dinero. Una acción con neto base ≤0 no mejora el valor frente a esperar, y WAIT gana los empates. Por construcción, una solución exacta selecciona solo netos base positivos; una elevada tasa de acierto o PF infinito del oracle no es evidencia de edge. El JSON conserva positivos/cero/negativos y mínimos base/adverso como diagnóstico.', '',
            '## Qué zonas eligió y qué distancia se propuso recorrer', '',
            '| Ticker | Periodo | Entrada Fib sola / walls solas / mezcla | Objetivo Fib solo / walls solas / mezcla | Objetivo más lejano que el primero ofrecido | Niveles intermedios conocidos | Distancia objetivo mediana / p90 (IB) | Stop mediano (IB) |',
            '|---|---|---|---|---:|---:|---|---:|']
    for g in summary['groups']:
        x, n = g['statistics'], g['statistics']['trades']
        def src(k):
            return ' / '.join(pct(x[k + '_' + suffix], n) for suffix in ('fib_only', 'walls_only', 'fib_and_walls'))
        out.append(f"| {g['ticker']} | {labels[g['split']]} | {src('entry')} | {src('target')} | {pct(x['farther_than_nearest_offered'], n)} | {pct(x['has_intermediate_nonentry_centers_to_target'], n)} | {x['target_distance_ib']['median']:.3f} / {x['target_distance_ib']['p90']:.3f} | {x['stop_distance_ib']['median']:.3f} |")
    out += ['', 'Las tres categorías de procedencia son excluyentes. El JSON también conserva cada bit CALL/PUT OI/gamma por separado; esos bits se solapan en clusters deduplicados. Gamma significa proxy Black–Scholes × OI, no gamma observado ni posición dealer. “Más lejano” compara contra objetivos realmente ofrecidos en ese estado; “intermedios” cuenta centros conocidos entre spot y objetivo, excluido el propio centro de entrada, aunque no fueran objetivos elegibles. Describe geometría proyectada, no cruces realizados: una salida STOP/EOD puede no alcanzar esos centros.', '',
            '| Ticker | Periodo | CALL / PUT | Delta bucket .35 / .50 / .65 | Fill todavía cerca de zona | PnL positivo con spot en contra |',
            '|---|---|---|---|---|---|']
    for g in summary['groups']:
        x, n = g['statistics'], g['statistics']['trades']
        buckets = ' / '.join(pct(x['delta_bucket'].get(str(v), 0), n) for v in (.35, .5, .65))
        sides = ' / '.join(pct(x['side'].get(side, 0), n) for side in ('CALL', 'PUT'))
        out.append(f"| {g['ticker']} | {labels[g['split']]} | {sides} | {buckets} | {pct(x['fill_near_entry_zone'], x['fill_observed'])} ({x['fill_observed']:,} observados) | {x['profitable_against_spot']} / {x['direction_observed']:,} |")
    out += ['', 'Todas las decisiones seleccionadas se verifican dentro de su banda de entrada. El fill llega un minuto después y puede quedar fuera. “Spot en contra” compara spot observado en entrada y salida con el signo CALL/PUT. Una opción rentable pese a ese movimiento es una discordancia descriptiva; no identifica causalmente cuánto proviene de IV, gamma, theta, spreads o calidad de quote.', '',
            'El delta bucket describe la selección entre .35/.50/.65, no un delta realizado idéntico: se elige el contrato disponible más cercano. El objetivo optimiza USD absolutos por un contrato, sin igualar prima/capital entre contratos. Por ello una preferencia por delta alto no demuestra superioridad por unidad de capital o riesgo.', '',
            '## Intención geométrica al aproximarse a la zona', '',
            '| Ticker | Periodo | Continuación | Rechazo | Sin clasificar |',
            '|---|---|---:|---:|---:|']
    for g in summary['groups']:
        x, n = g['statistics'], g['statistics']['trades']
        values = ' | '.join(pct(x['geometric_intent'].get(k, 0), n) for k in ('continuation', 'rejection', 'unclassified'))
        out.append(f"| {g['ticker']} | {labels[g['split']]} | {values} |")
    out += ['', 'Se compara el spot de cinco minutos antes con centro ± banda de la zona elegida en la decisión. Llegar desde abajo y elegir CALL, o desde arriba y elegir PUT, se etiqueta continuación; los lados opuestos, rechazo. Si estaba dentro o falta observación, queda sin clasificar. Es intención geométrica, no un rebote confirmado ni evidencia de mecanismo causal; no implica que la wall actual existiera cinco minutos antes.', '',
            '## Cuánta elección retrospectiva hay detrás', '',
            '| Ticker | Periodo | Alternativas en estados elegidos | Alternativas perdedoras | Media alternativa USD | Rango p90−p10 mediano por estado USD | Elegida NO maximiza PnL directo | Margen DP sobre segundo/WAIT mediano USD |',
            '|---|---|---:|---:|---:|---:|---:|---:|']
    for g in summary['groups']:
        x, n = g['statistics'], g['statistics']['trades']
        a = x['same_state_alternatives']
        out.append(f"| {g['ticker']} | {labels[g['split']]} | {a['actions']:,} | {pct(a['losers'], a['actions'])} | {a['action_weighted_mean']:.2f} | {a['per_state_p90_minus_p10']['median']:.2f} | {pct(x['not_best_standalone'], n)} | {x['dp_margin_over_runnerup']['median']:.2f} |")
    out += ['', 'Cada alternativa es una combinación realmente ofrecida de contrato y objetivo en el mismo estado de decisión; se excluye la elegida. No son operaciones independientes ni ejecutables simultáneamente. La media pondera acciones; el JSON incluye también la media que pondera cada estado por igual y la distribución de todas las ofertas del día.', '',
            'El DP maximiza el total de la jornada: `neto de acción + mejor continuación después de su salida`. Por ello puede elegir una acción con menor beneficio aislado para liberar inventario antes. El rango directo y el margen DP miden cosas distintas; ningún aprendiz debe tratar el máximo clarividente como expectativa causal alcanzable.', '',
            '## Sensibilidad temporal local, con cobertura explícita', '',
            '| Ticker | Periodo | −1m: acción idéntica ofrecida | Δ PnL mediana / p10 USD | +1m: acción idéntica ofrecida | Δ PnL mediana / p10 USD |',
            '|---|---|---|---|---|---|']
    for g in summary['groups']:
        x, n = g['statistics'], g['statistics']['trades']
        cells = []
        for key in ('earlier_one_minute', 'later_one_minute'):
            a = x[key]
            d = a['direct_pnl_change']
            cells += [f"{a['matched']:,} ({pct(a['matched'], n)})", f"{d['median']:.2f} / {d['p10']:.2f}" if d['n'] else 'n/a']
        out.append(f"| {g['ticker']} | {labels[g['split']]} | {' | '.join(cells)} |")
    out += ['', 'La comparación exige mismo contrato, lado y valores exactos de objetivo/stop/banda en `actions.parquet` un minuto antes/después. Sin oferta idéntica, no hay contrafactual evaluado. Se conservan no-fills como cero según el motor. Es sensibilidad aislada de esa operación, no PnL de una nueva política diaria: desplazar una operación podría alterar las siguientes.', '',
            '## Ejemplos fijos y límites de aprendizaje', '',
            'Las tres imágenes de 2023-01-03 se fijaron antes de observar sus beneficios y muestran entradas/salidas, objetivos lejanos, stops y walls: [SPXW](D:/GexResearchArtifacts/level_oracle_20261018/oracle_charts/final/SPXW_20230103_oracle.png), [SPY](D:/GexResearchArtifacts/level_oracle_20261018/oracle_charts/final/SPY_20230103_oracle.png), [QQQ](D:/GexResearchArtifacts/level_oracle_20261018/oracle_charts/final/QQQ_20230103_oracle.png). No son las mejores sesiones elegidas retrospectivamente.', '',
            'Una red o agente puede aprender a proponer contrato/objetivo y decidir esperar usando secuencias causales; este informe describe lo que debería aproximar, no demuestra que pueda anticiparlo. El oracle conoce también qué alternativa perderá y qué salida dejará espacio a otra oportunidad. La prueba pertinente sigue siendo la política completa del alumno sobre datos posteriores a su ajuste, con sus propios estados y costes. Los tres aprendices y su selección fijada permanecen intactos; este análisis no crea filtros con los ganadores de 2026.', '',
            'Artefactos completos: `summary.json`, `selected_trade_descriptors.parquet`, `daily_descriptors.csv` e `input_manifest.jsonl` en la carpeta de salida indicada abajo. Se rehashean los seis parquets de cada día; del cache se comprueba la identidad publicada de metadatos y se leen únicamente spot/máscara. No se rehashea aquí todo NPZ ni se reauditan fuentes raw.', '',
            f"Salida: `{summary['output']}`. SHA del analizador: `{summary['analyzer_sha256']}`."]
    return '\n'.join(out) + '\n'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--engine-root', type=Path, default=ROOT / 'engine_v1')
    parser.add_argument('--output', type=Path, default=ROOT / 'oracle_behavior_v2')
    parser.add_argument('--workers', type=int, choices=(1, 2), default=2)
    parser.add_argument('--report', type=Path, default=Path(__file__).with_name('ORACLE_BEHAVIOR.md'))
    parser.add_argument('--audit-status', default='PENDING_INDEPENDENT_AUDIT')
    args = parser.parse_args()
    pa.set_cpu_count(1)
    pa.set_io_thread_count(1)
    full_path = args.engine_root / 'summary.json'
    if not full_path.exists():
        raise RuntimeError('Wait for completed dataset summary.json; no partial economics')
    full = json.loads(full_path.read_text(encoding='utf-8'))
    if full['status'] != 'COMPLETE':
        raise RuntimeError('Producer not complete')
    index_path = args.engine_root / 'index.parquet'
    completion = json.loads((args.engine_root / 'completion.json').read_text(encoding='utf-8'))
    index_hash, summary_hash = sha(index_path), sha(full_path)
    if completion['index_sha256'] != index_hash or completion['summary_sha256'] != summary_hash:
        raise ValueError('Producer completion hash mismatch')
    calendar = pd.read_parquet(index_path)
    if len(calendar) != 2601 or (calendar.status == 'COMPLETE').sum() != 2595 or (calendar.status == 'MISSING_SOURCE').sum() != 6:
        raise ValueError('Fixed full-universe coverage mismatch')
    args.output.mkdir(parents=True, exist_ok=False)
    source_hash = sha(__file__)
    shutil.copy2(__file__, args.output / 'analyze_oracle_behavior.executed.py')
    write_json(args.output / 'execution.json', dict(status='RUNNING', source_sha256=source_hash,
               workers=args.workers, native_threads=1, started_utc=datetime.now(timezone.utc).isoformat()))
    selected, daily = [], []
    records = calendar.loc[calendar.status == 'COMPLETE'].to_dict('records')
    with (args.output / 'input_manifest.jsonl').open('w', encoding='utf-8') as handle, ProcessPoolExecutor(max_workers=args.workers, initializer=initialize_worker) as pool:
        for number, (rows, day_stats, manifest) in enumerate(pool.map(process_day, records, chunksize=1, buffersize=4), 1):
            selected.extend(rows)
            daily.append(day_stats)
            handle.write(json.dumps(manifest) + '\n')
            if number % 25 == 0:
                handle.flush()
                progress = dict(status='RUNNING', days=number, trades=len(selected), utc=datetime.now(timezone.utc).isoformat())
                write_json(args.output / 'progress.json', progress)
                print(json.dumps(progress), flush=True)
    trades, days = pd.DataFrame(selected), pd.DataFrame(daily)
    groups = []
    for ticker in ('SPXW', 'SPY', 'QQQ'):
        for split in ('train', 'validation', 'test'):
            t = trades.loc[(trades.ticker == ticker) & (trades.split == split)]
            d = days.loc[(days.ticker == ticker) & (days.split == split)]
            count = int(((calendar.ticker == ticker) & (calendar.split == split)).sum())
            groups.append(dict(ticker=ticker, split=split, statistics=aggregate(t, d, count)))
    trades.to_parquet(args.output / 'selected_trade_descriptors.parquet', index=False)
    days.to_csv(args.output / 'daily_descriptors.csv', index=False)
    summary = dict(status='COMPLETE_DESCRIPTIVE_HINDSIGHT', audit_status=args.audit_status,
                   oracle_uses_future=True, learning_or_selection_changed=False, groups=groups,
                   input_index_sha256=index_hash, input_summary_sha256=summary_hash,
                   analyzer_sha256=source_hash, output=str(args.output),
                   completed_utc=datetime.now(timezone.utc).isoformat())
    write_json(args.output / 'summary.json', summary)
    args.report.write_text(render_report(summary), encoding='utf-8')
    write_json(args.output / 'progress.json', dict(status='COMPLETE', days=len(days), trades=len(trades)))
    write_json(args.output / 'execution.json', dict(status='COMPLETE', source_sha256=source_hash,
               workers=args.workers, native_threads=1, completed_utc=datetime.now(timezone.utc).isoformat()))
    print(json.dumps(dict(status=summary['status'], days=len(days), trades=len(trades))), flush=True)


def initialize_worker():
    pa.set_cpu_count(1)
    pa.set_io_thread_count(1)


if __name__ == '__main__':
    main()
