"""Descriptive report of closed, audited adaptation outputs; no new strategy."""
from __future__ import annotations

import hashlib
import importlib.util
import json
import os
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

import psutil

WEEK = Path(__file__).resolve().parent
REPO = WEEK.parents[2]
BASE = Path('D:/GexResearchArtifacts/weekly_multiday_20261101')
SOURCE = BASE / 'h2_context_adaptation_01'
OUTPUT = WEEK / 'adaptation_result_01'
POLICIES = ['FROZEN_CONTEXT182', 'MONTHLY_RAW', 'WEEKLY_RAW', 'MONTHLY_GUARDED', 'WEEKLY_GUARDED']
LABELS = ['Congelado', 'Mensual inmediato', 'Semanal inmediato', 'Mensual con filtro', 'Semanal con filtro']
MONTHS = [f'2026{i:02d}' for i in range(1, 10)]


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def money(value: float) -> str:
    return f'{value:,.2f}'.replace(',', '_').replace('.', ',').replace('_', '.')


def main() -> None:
    psutil.Process().cpu_affinity([0])
    variables = ['OMP_NUM_THREADS', 'OPENBLAS_NUM_THREADS', 'MKL_NUM_THREADS',
                 'NUMEXPR_NUM_THREADS', 'VECLIB_MAXIMUM_THREADS', 'BLIS_NUM_THREADS',
                 'ARROW_NUM_THREADS', 'POLARS_MAX_THREADS']
    for name in variables:
        os.environ[name] = '1'
    helper = REPO / 'research_papers/JEPA/level_oracle_20261018/launch_monthly_test_index_v2_audit_20261024.py'
    assert sha(helper) == '3cfe55a6a2926007d91d44215c8a7c0a28801efaca189fcf306c275e352ed046'
    spec = importlib.util.spec_from_file_location('report_resource_gate', helper)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    resources = module.observation()
    module.gate(resources)
    pins = {
        BASE / 'h2_context_adaptation_audit_04/audit.json': '9a487fba18504ae4faff2c1dba17d1c000eb237436a09a7fe22747e328cb307a',
        BASE / 'h2_context_adaptation_audit_observer_04/exit.json': '5d59d1a3978d8d9aa31c7c3fab567d1ae7e901494aa8efb12377ca65f91de420',
        SOURCE / 'summary.json': '1ad1dbca873d255b431a2e097be169b0ad91913b728fbe2a2478f2d30212049f',
        WEEK / 'USER_MONTHLY_PROFITABILITY_ACCEPTANCE_20261101.md': '806f7728a2ad434bc08929d3715f307455bd37862ae4c19a2cd2cc1d64a5ee5b',
    }
    for path, expected in pins.items():
        assert sha(path) == expected, path
    audit = json.loads((BASE / 'h2_context_adaptation_audit_04/audit.json').read_text())
    assert audit['status'] == 'PASS_INDEPENDENT_NUMERIC_RECONSTRUCTION_GIVEN_SAVED_WEIGHTS_NOT_REFIT'
    assert json.loads((BASE / 'h2_context_adaptation_audit_observer_04/exit.json').read_text())['exit_code'] == 0
    summary = json.loads((SOURCE / 'summary.json').read_text())
    results = {}
    ledgers = {}
    for policy in POLICIES:
        name = f'ledger_{policy.lower()}_adverse.jsonl'
        path = SOURCE / name
        assert sha(path) == audit['producer']['outputs'][name]['sha256']
        pins[path] = sha(path)
        rows = [json.loads(line) for line in path.read_text().splitlines()]
        exits = [row for row in rows if row['event'] == 'EXIT']
        monthly = {month: 0.0 for month in MONTHS}
        for row in exits:
            monthly[row['date'][:6]] += row['net_usd']
        economic = summary['policies'][policy]['economics']['adverse']
        for month in MONTHS:
            assert abs(monthly[month] - economic['details']['monthly_net_including_zeros'][month]) < 1e-7
        assert abs(sum(monthly.values()) - economic['net_usd']) < 1e-7
        assert len(exits) == economic['trades']
        results[policy] = dict(label=LABELS[POLICIES.index(policy)], monthly=monthly,
                               full_months_positive=sum(monthly[m] > 0 for m in MONTHS[:-1]),
                               monthly_acceptance=all(monthly[m] > 0 for m in MONTHS[:-1]),
                               economics=summary['policies'][policy]['economics'],
                               probability_ev={k: {a: b for a, b in v.items() if a != 'reliability'}
                                               for k, v in summary['policies'][policy]['probability_ev'].items()})
        ledgers[policy] = rows
    assert not OUTPUT.exists()
    OUTPUT.mkdir()
    data = dict(status='DESCRIPTIVE_ALL_FIVE_FAIL_MONTHLY_CRITERION', policies=results,
                monthly_convention='closed_trade_net_at_exit_date_not_mark_to_market',
                proposal_status_counts=summary['proposal_status_counts'],
                guard_diagnostics={k: {a: b for a, b in v.items() if a != 'observed_post_activation_transfer'}
                                   for k, v in summary['guard_diagnostics'].items()},
                post_activation_transfer={k: [{a: b for a, b in row.items() if a != 'probability_ev'}
                                             for row in v['observed_post_activation_transfer']]
                                          for k, v in summary['guard_diagnostics'].items()},
                selection=None, promotion_approved=False)
    (OUTPUT / 'report_data.json').write_text(json.dumps(data, indent=2) + '\n', encoding='utf-8')

    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    import numpy as np
    from matplotlib.colors import TwoSlopeNorm
    from matplotlib.dates import DateFormatter, MonthLocator

    plt.rcParams.update({'font.family': 'DejaVu Sans', 'font.size': 10})
    fig, (ax, heat) = plt.subplots(2, 1, figsize=(14, 9), gridspec_kw={'height_ratios': [1.1, 1]})
    colors = ['#586574', '#a66214', '#167f6b', '#844b9e', '#ce5353']
    for policy, label, color in zip(POLICIES, LABELS, colors):
        daily = defaultdict(float)
        for row in ledgers[policy]:
            if row['event'] == 'EXIT':
                daily[row['date']] += row['net_usd']
        days = ['20260102', *sorted(daily)]
        values = [0, *np.cumsum([daily[d] for d in sorted(daily)])]
        ax.step([datetime.strptime(d, '%Y%m%d') for d in days], values, where='post',
                label=label, color=color, linewidth=1.8)
    ax.axhline(0, color='#303030', linewidth=0.8)
    ax.set_ylabel('PnL cerrado acumulado (USD)')
    ax.xaxis.set_major_locator(MonthLocator())
    ax.xaxis.set_major_formatter(DateFormatter('%m/2026'))
    ax.grid(alpha=0.18)
    ax.legend(ncol=3, loc='upper left', fontsize=9)
    ax.set_title('Ninguna variante cumple 8 de 8 meses completos positivos', loc='left', fontsize=16, pad=15)
    matrix = np.array([[results[p]['monthly'][m] for m in MONTHS] for p in POLICIES])
    limit = float(np.abs(matrix).max())
    heat.imshow(matrix, cmap='RdYlGn', norm=TwoSlopeNorm(vmin=-limit, vcenter=0, vmax=limit), aspect='auto')
    heat.set_yticks(range(5), LABELS)
    heat.set_xticks(range(9), ['Ene', 'Feb', 'Mar', 'Abr', 'May', 'Jun', 'Jul', 'Ago', 'Sep*'])
    for i in range(5):
        for j in range(9):
            value = matrix[i, j]
            heat.text(j, i, money(value), ha='center', va='center', fontsize=9,
                      color='white' if abs(value) > limit * 0.7 else '#17222a')
    heat.axvline(7.5, color='#222', linewidth=1.5, linestyle='--')
    heat.set_title('Resultado mensual neto adverso (USD), atribuido a la fecha de salida', loc='left', pad=12)
    heat.tick_params(length=0)
    fig.text(0.02, 0.02, '* Septiembre hasta el día 17, parcial. Capital inicial 100.000 USD por variante, sin reinicios.\n'
             'Operaciones en opciones weekly, salida H2. Curva de operaciones cerradas; no incluye valoración diaria de posiciones abiertas. Datos de desarrollo ya vistos.',
             fontsize=9, color='#444')
    fig.subplots_adjust(left=0.16, right=0.98, top=0.93, bottom=0.12, hspace=0.32)
    fig.savefig(OUTPUT / 'monthly_adaptation.png', dpi=150)
    plt.close(fig)

    text = ['# Reentrenamiento mensual y semanal: resultado cerrado', '',
            '**Ninguna de las cinco políticas cumple ocho meses completos positivos.** '
            'El reentrenamiento semanal inmediato acaba con +2.693,80 USD adversos, pero sólo gana en tres de ocho meses completos; '
            'su drawdown realizado es 46.860,80 USD. El beneficio agregado no satisface el criterio del usuario. '
            'No se selecciona ningún modelo.', '',
            'Periodo: 2 de enero a 17 de septiembre de 2026; septiembre es parcial. Opciones weekly de SPY/QQQ/SPXW, '
            'entrada 10:35 y salida después de dos sesiones (H2). Capital inicial 100.000 USD una sola vez por política. '
            'Los meses atribuyen el neto completo de cada operación a su salida; no representan valoración diaria a mercado.', '',
            '| Política | Neto base USD | Neto adverso USD | Meses positivos ene–ago | PF adverso | DD realizado USD | Trades |',
            '|---|---:|---:|---:|---:|---:|---:|']
    for p in POLICIES:
        r = results[p]; e = r['economics']['adverse']
        text.append(f"| {r['label']} | {money(r['economics']['base']['net_usd'])} | {money(e['net_usd'])} | {r['full_months_positive']}/8 | {e['profit_factor']:.4f} | {money(e['realized_max_drawdown_usd'])} | {e['trades']} |")
    text += ['', '![Resultado mensual y curva de operaciones cerradas](adaptation_result_01/monthly_adaptation.png)', '',
             '## Todos los meses, sin exclusiones', '',
             '| Mes | Congelado | Mensual inmediato | Semanal inmediato | Mensual con filtro | Semanal con filtro |',
             '|---|---:|---:|---:|---:|---:|']
    for m in MONTHS:
        text.append('| ' + m[:4] + '-' + m[4:] + (' (parcial)' if m == '202609' else '') + ' | ' + ' | '.join(money(results[p]['monthly'][m]) for p in POLICIES) + ' |')
    text += ['', 'Febrero mensual inmediato es cero y cuenta como mes no rentable. Se permiten días sin operar, '
             'pero no se eliminan meses sin beneficio del denominador.', '',
             '## Qué mejoró y qué no', '',
             'La actualización semanal inmediata reduce la pérdida de julio–septiembre parcial a −33.458,40 USD, '
             'frente a −62.075,20 USD del congelado en este libro continuo. Sigue perdiendo en los tres meses. '
             'Sin abril, su neto total sería −34.382,20 USD; al restar únicamente su mayor operación ganadora '
             '(+12.232,80 USD), sería −9.539,00 USD. Son restas descriptivas, no estrategias alternativas.', '',
             'El Q3 congelado anterior de −58.128,60 USD era un experimento separado. El libro continuo añade '
             'una operación del puente de junio cerrada en julio, por −3.946,60 USD: −62.075,20 USD. '
             'No se suman dos cuentas reiniciadas para construir este resultado.', '',
             '## Filtro de actualizaciones y regresión', '',
             'Cada propuesta se compara con una copia del modelo vigente durante 21 sesiones posteriores. '
             'Sólo se admite si no empeora logloss ni neto adverso. Aprobación retrospectiva con datos ya maduros '
             'no asegura mejoras después de activarla. Las propuestas contra una versión ya sustituida se rechazan como obsoletas.', '',
             '| Frecuencia | Aprobadas | Rechazadas por comparación | Obsoletas | Pendientes | Último modelo activo | Sesiones desde aceptación |',
             '|---|---:|---:|---:|---:|---|---:|']
    for freq, g in data['guard_diagnostics'].items():
        text.append(f"| {freq} | {g['promotions']} | {g['rejections']} | {g['stale']} | {g['pending']} | {g['final_active_model']} | {g['sessions_since_last_acceptance']} |")
    text += ['', 'El filtro mensual termina 24.417,40 USD por debajo de actualizar inmediatamente; '
             'el semanal, 33.295,00 USD por debajo. No evitó la regresión económica. '
             'El modelo mensual aceptado el 4 de junio permaneció activo hasta el corte y sus entradas '
             'posteriores acumularon −73.076,20 USD. Son resultados del modelo activo, no un efecto causal '
             'aislado de la frecuencia o del retraso.', '',
             '| Frecuencia | Activación | Modelo | Sesiones activas | Trades de esa cohorte | Neto posterior USD |',
             '|---|---|---|---:|---:|---:|']
    for freq, transfers in data['post_activation_transfer'].items():
        for t in transfers:
            text.append(f"| {freq} | {t['effective_at']} | {t['model_id']} | {t['sessions']} | {t['trades']} | {money(t['main_book_adverse_exit_net'])} |")
    text += ['', '## Probabilidades y valor esperado', '',
             'Las 612 oportunidades evaluadas son comunes a las cinco políticas. Los seleccionados incluyen '
             'intentos rechazados por ejecución/riesgo, además de fills. El sesgo EV es predicción menos neto '
             'observado por contrato: positivo significa sobreestimación media. Logloss/Brier menores son mejores.', '',
             '| Política | Logloss todas | Brier todas | Sesgo EV seleccionadas USD/contrato | MAE EV seleccionadas USD/contrato | N seleccionadas |',
             '|---|---:|---:|---:|---:|---:|']
    for p in POLICIES:
        r = results[p]; all_ = r['probability_ev']['all']; selected = r['probability_ev']['selected']
        ev = selected['ev']['adverse']
        text.append(f"| {r['label']} | {all_['logloss']:.6f} | {all_['brier']:.6f} | {money(ev['bias'])} | {money(ev['mae'])} | {selected['n']} |")
    text += ['', 'Las actualizaciones no mejoran logloss/Brier agregados frente al congelado en este periodo. '
             'El semanal inmediato mantiene sobreestimación media de EV seleccionada de +148,59 USD/contrato '
             'y MAE 1.024,58 USD/contrato. El calendario de reentrenamiento por sí solo no resuelve la selección '
             'de oportunidades con EV realizable. El archivo JSON conserva métricas con y sin cotas por datos ausentes; '
             'no se excluyen esas cotas del resultado principal.', '',
             '## Método, alcance y límites', '',
             '- 42 fits independientes de regresión logística multiclase CONTEXT182, 9 fechas mensuales y 38 semanales con 5 coincidencias. '
             'Imputación y escalado sólo con TRAIN; calibración con 63 sesiones anteriores maduras; TRAIN expansivo desde 2023. '
             'No se modificaron arquitectura, umbrales, features ni reglas tras ver resultados.',
             '- Cada ajuste empieza de cero conservando el histórico de TRAIN. No hay entrenamiento neuronal incremental '
             'que sobrescriba pesos de tareas anteriores. Esto evita ese mecanismo concreto de olvido, pero no demuestra '
             'que preservar historia o el filtro impidan regresión futura. Las 63 sesiones de calibración quedan fuera del ajuste de coeficientes.',
             '- Riesgo máximo 5.000 USD por entrada, un máximo de una posición por ticker y tres simultáneas. '
             'Comisión 1,30 USD por contrato/lado; deslizamiento 0,01 base y 0,02 adverso. '
             'Se supone fill completo al quote guardado, sin simulación de profundidad/volumen ni fills parciales.',
             '- El DD es realizado, no mark-to-market; no acredita el riesgo intratrade ni una curva de valoración diaria. '
             'El ajuste disponible antes de 10:30 es un supuesto operativo no verificado en vivo.',
             '- Todos los periodos son SEEN_DEVELOPMENT. Ningún resultado constituye un holdout nuevo ni garantiza '
             'meses futuros positivos. technical_ready=false, promotion_approved=false, selección null.', '',
             '## Integridad y aclaración del reloj', '',
             'Productor d03494bf completó 42 fits una sola vez, exit0 a18:14:13.873980UTC. '
             'Auditores01/02/03 fallidos se conservan: campo EV de replay, evento inicial sin caja y divergencia '
             'de interpretación del reloj, respectivamente. Ninguno se presenta como PASS parcial.', '',
             'El reloj conservador gate_end+3 ya estaba publicado en código/tests antes del run. '
             'La aclaración textual se decidió después del run: el auditor anterior exigía la primera fecha posible '
             'según etiquetas efectivas, requisito no explícito en el contrato. La regla conservada retrasa nueve '
             'resoluciones una o dos sesiones. No se ejecutó ni se eligió una variante más temprana para mejorar PnL. '
             'Durante el diagnóstico se imprimió incidentalmente la comparación de la primera propuesta; '
             'el resumen agregado no se interpretó hasta el cierre auditado. '
             '[Aclaración y revisión](ADAPTATION_CLOCK_CLARIFICATION_AND_AUDIT_V4_SCOPE_20261101.md).', '',
             'Auditor04 0723696a terminó exit0 el1nov2026 a18:54:51.566895UTC. '
             'Reconstruyó 42 estados, 3.060 scores (612×5), 10 libros, 47 propuestas y 890 filas de calendario. '
             'PASS_INDEPENDENT_NUMERIC_RECONSTRUCTION_GIVEN_SAVED_WEIGHTS_NOT_REFIT: '
             'reconstrucción con coeficientes guardados, sin refit independiente ni nueva lectura raw. '
             'Revisión independiente comprobó21inputs,18outputs,19pins y4recibos de archivos del cierre.', '',
             'Audit SHA9a487fba18504ae4faff2c1dba17d1c000eb237436a09a7fe22747e328cb307a; '
             'exit5d59d1a3978d8d9aa31c7c3fab567d1ae7e901494aa8efb12377ca65f91de420. '
             'Sin acceso API/bróker ni cambios productivos.', '',
             'La comparación queda cerrada con fallo del criterio mensual. La siguiente hipótesis debe centrarse '
             'en la calibración y ordenación del EV de oportunidades seleccionadas, incluyendo abstención y '
             'evaluación temporal predefinida; estos resultados no justifican otra búsqueda de frecuencia '
             'ni rescatar tickers/meses. No se ha entrenado ni autorizado para producción una variante nueva.', '']
    report = WEEK / 'ADAPTATION_MONTHLY_WEEKLY_RESULT_20261101.md'
    assert not report.exists()
    report.write_text('\n'.join(text), encoding='utf-8')
    for path, expected in pins.items():
        assert sha(path) == expected
    manifest = dict(status='DESCRIPTIVE_REPORT_COMPLETE', utc=datetime.now(timezone.utc).isoformat(),
                    resources=resources, cpu_affinity=psutil.Process().cpu_affinity(),
                    thread_variables={k: os.environ[k] for k in variables},
                    source_sha256=sha(Path(__file__)), inputs={str(k): v for k, v in pins.items()},
                    outputs={str(p): dict(bytes=p.stat().st_size, sha256=sha(p))
                             for p in [report, OUTPUT / 'report_data.json', OUTPUT / 'monthly_adaptation.png']})
    (OUTPUT / 'manifest.json').write_text(json.dumps(manifest, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(dict(status=manifest['status'], policies=5, monthly_groups=45, all_fail=True)))


if __name__ == '__main__':
    main()
