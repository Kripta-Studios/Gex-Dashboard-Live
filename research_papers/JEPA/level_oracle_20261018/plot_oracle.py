"""Read-only visual report of three fixed pilot days, after oracle completion.

No engine imports, source rebuilding, model training, or economic selection.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import matplotlib

matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
from matplotlib.patches import Rectangle
import numpy as np
import pandas as pd

DATE = '20230103'
TICKERS = ('SPXW', 'SPY', 'QQQ')
DEFAULT_CACHE = Path('D:/GexResearchArtifacts/level_oracle_20261018/cache_v1')
DEFAULT_OUTPUT = Path('D:/GexResearchArtifacts/level_oracle_20261018/oracle_charts')
FIB_RATIOS = (-1., -.618, -.272, 0., .236, .382, .5, .618, .786, 1., 1.272, 1.618, 2.)
WALL_COLORS = {2: '#d89513', 4: '#4677c8', 8: '#a03ca0', 16: '#198c91'}
WALL_NAMES = {2: 'CALL OI', 4: 'PUT OI', 8: 'CALL gamma proxy', 16: 'PUT gamma proxy'}


def sha256(path):
    digest = hashlib.sha256()
    with Path(path).open('rb') as handle:
        for block in iter(lambda: handle.read(8 * 1024 * 1024), b''):
            digest.update(block)
    return digest.hexdigest()


def clock(minute):
    value = 570 + int(minute)
    return f'{value // 60:02d}:{value % 60:02d}'


def sampled_candles(spot, valid):
    """Five-minute OHLC of observed one-minute snapshots; never fill gaps."""
    rows = []
    spot = np.asarray(spot, dtype=float)
    valid = np.asarray(valid, dtype=bool) & np.isfinite(spot) & (spot > 0)
    for start in range(0, 390, 5):
        values = spot[start:start + 5][valid[start:start + 5]]
        if len(values):
            rows.append((start, values[0], values.max(), values.min(), values[-1], len(values)))
    return pd.DataFrame(rows, columns=['minute', 'open', 'high', 'low', 'close', 'observed'])


def extract_walls(levels):
    """Recover causal raw wall components; merged centers are not wall strikes."""
    rows = []
    for row in levels.itertuples(index=False):
        for component in json.loads(row.components_json):
            source = int(component['source_mask'])
            if source in WALL_COLORS:
                rows.append((int(row.state_i), float(component['center']), source,
                             float(component['weight'])))
    return pd.DataFrame(rows, columns=['minute', 'center', 'source', 'weight']).drop_duplicates()


def inspect_ledger(ledger, states, levels, spot, valid):
    """Geometry/accounting consistency for reporting; not an oracle audit."""
    state_index = states.set_index('state_i', verify_integrity=True)
    level_index = levels.set_index(['state_i', 'level_id'], verify_integrity=True)
    rows = []
    next_state = 60
    for number, row in enumerate(ledger.itertuples(index=False), 1):
        decision, entry, exit_i = int(row.state_i), int(row.entry_i), int(row.exit_i)
        if not (decision >= next_state and entry == decision + 1 and entry < exit_i <= 385):
            raise ValueError('Ledger chronology/overlap mismatch')
        if row.status != 'FILLED' or int(row.hold_minutes) != exit_i - entry:
            raise ValueError('Ledger status/holding mismatch')
        state = state_index.loc[decision]
        center = float(level_index.loc[(decision, int(row.entry_level_id)), 'center'])
        decision_distance = abs(float(state.spot) - center) / float(row.band)
        if decision_distance > 1 + 1e-10:
            raise ValueError('Decision was outside its entry zone')
        fill_distance = abs(float(spot[entry]) - center) / float(row.band) if valid[entry] else None
        rows.append({'trade': number, 'action_id': int(row.action_id), 'decision_i': decision,
                     'entry_i': entry, 'exit_i': exit_i, 'side': 'CALL' if int(row.right) == 0 else 'PUT',
                     'strike': float(row.strike), 'target': float(row.target_center),
                     'stop': float(row.stop_center), 'band': float(row.band),
                     'entry_zone_center': center, 'decision_distance_bands': decision_distance,
                     'fill_distance_bands': fill_distance, 'hold_minutes': exit_i - entry,
                     'reason': str(row.reason), 'net_base': float(row.net_base),
                     'net_adverse': float(row.net_adverse)})
        next_state = exit_i + 1
    return rows


def load_day(engine_dir, cache_path, ticker):
    summary = json.loads((engine_dir / 'summary.json').read_text(encoding='utf-8'))
    identity = json.loads((engine_dir / 'identity.json').read_text(encoding='utf-8'))
    metadata = json.loads(cache_path.with_suffix('.json').read_text(encoding='utf-8'))
    if summary['status'] != 'COMPLETED_HINDSIGHT_ORACLE_DAY':
        raise ValueError('Engine pilot has not completed')
    if not summary['oracle']['oracle_uses_future']:
        raise ValueError('Expected explicitly retrospective oracle')
    if metadata['ticker'] != ticker or str(metadata['date']) != DATE:
        raise ValueError('Fixed pilot cache identity mismatch')
    if identity['metadata']['sha256'] != metadata['sha256'] or sha256(cache_path) != metadata['sha256']:
        raise ValueError('Engine/cache identity mismatch')
    hashes = {}
    frames = {}
    for name in ('states', 'levels', 'oracle_ledger'):
        path = engine_dir / f'{name}.parquet'
        hashes[path.name] = sha256(path)
        if hashes[path.name] != summary['artifact_hashes'][path.name]:
            raise ValueError('Engine artifact hash mismatch: ' + path.name)
        frames[name] = pd.read_parquet(path)
    with np.load(cache_path, allow_pickle=False) as source:
        spot = source['spot'].copy()
        valid = source['spot_valid'].copy() & np.isfinite(spot) & (spot > 0)
        times = source['time_ns'].copy()
    if len(spot) != 391 or not np.all(np.diff(times) == 60_000_000_000):
        raise ValueError('Invalid minute grid')
    expected = pd.Timestamp(DATE) + pd.Timedelta(hours=9, minutes=30)
    if pd.Timestamp(int(times[0])) != expected:
        raise ValueError('Pilot clock mismatch')
    rows = inspect_ledger(frames['oracle_ledger'], frames['states'], frames['levels'], spot, valid)
    if not np.isclose(sum(row['net_base'] for row in rows), summary['oracle']['net_base'], atol=1e-8):
        raise ValueError('Summary/ledger total mismatch')
    hashes['cache_npz'] = metadata['sha256']
    hashes['summary.json'] = sha256(engine_dir / 'summary.json')
    return frames, rows, spot, valid, metadata, hashes


def draw_candles(ax, candles):
    for row in candles.itertuples(index=False):
        color = '#16836d' if row.close >= row.open else '#c74a50'
        x = row.minute + 2
        ax.vlines(x, row.low, row.high, color=color, linewidth=.8, zorder=4)
        if row.open == row.close:
            ax.hlines(row.open, x - 1.65, x + 1.65, color=color, linewidth=1.1, zorder=4)
        else:
            ax.add_patch(Rectangle((x - 1.65, min(row.open, row.close)), 3.3,
                                   abs(row.close - row.open), facecolor=color,
                                   edgecolor=color, alpha=.9, zorder=4))


def render_day(engine_dir, cache_path, ticker, output):
    frames, rows, spot, valid, metadata, hashes = load_day(engine_dir, cache_path, ticker)
    candles = sampled_candles(spot, valid)
    walls = extract_walls(frames['levels'])
    height = 11.6 + max(0, len(rows) - 10) * .19
    fig = plt.figure(figsize=(17, height), facecolor='#f7f8fc')
    grid = fig.add_gridspec(3, 2, height_ratios=[4.7, 2.2, max(2.2, len(rows) * .19)],
                           width_ratios=[4, 1], hspace=.31, wspace=.16)
    ax = fig.add_subplot(grid[0, :])
    context = fig.add_subplot(grid[1, :], sharex=ax, sharey=ax)
    table_ax = fig.add_subplot(grid[2, 0])
    hist = fig.add_subplot(grid[2, 1])
    fig.suptitle('ORACLE RETROSPECTIVO · USA FUTURO', fontsize=22, fontweight='bold', color='#a32337', y=.977)
    fig.text(.5, .946, f'{ticker} · 03 enero 2023 · sesión fija, no seleccionada por beneficio · NO ES UN MODELO OPERABLE',
             ha='center', fontsize=11, color='#3c4556')
    draw_candles(ax, candles)
    state_valid = frames['states'].loc[frames['states'].state_valid]
    ib_low = ib_high = None
    if len(state_valid):
        ib_low, ib_high = float(state_valid.iloc[0].ib_low), float(state_valid.iloc[0].ib_high)
    limits = spot[valid].tolist()
    for row in rows:
        limits.extend((row['target'], row['stop']))
    low, high = min(limits), max(limits)
    margin = max((high - low) * .09, .01)
    ax.set_ylim(low - margin, high + margin)
    if ib_low is not None:
        for ratio in FIB_RATIOS:
            level = ib_low + ratio * (ib_high - ib_low)
            if low - margin <= level <= high + margin:
                color = '#435578' if ratio in (0., 1.) else '#9aa8bc'
                ax.hlines(level, 60, 390, color=color, linewidth=1.05 if ratio in (0., 1.) else .65,
                          linestyles='--', alpha=.8, zorder=1)
                ax.text(392, level, f'{ratio:g}', va='center', fontsize=8, color=color)
    palette = plt.get_cmap('tab10')
    for idx, row in enumerate(rows):
        color = palette(idx % 10)
        entry, exit_i = row['entry_i'], row['exit_i']
        for name, style in (('target', '-'), ('stop', ':')):
            ax.hlines(row[name], entry, exit_i, color=color, linestyles=style, linewidth=2, zorder=6)
            ax.fill_between([entry, exit_i], row[name] - row['band'], row[name] + row['band'],
                            color=color, alpha=.06, zorder=0)
        for minute, marker in ((entry, '^' if row['side'] == 'CALL' else 'v'), (exit_i, 'X')):
            if valid[minute]:
                ax.scatter(minute, spot[minute], marker=marker, s=70, color=color,
                           edgecolor='white', linewidth=.6, zorder=8)
                if minute == entry:
                    ax.annotate(str(row['trade']), (minute, spot[minute]), xytext=(0, 10),
                                textcoords='offset points', ha='center', fontsize=8, color=color)
            else:
                ax.text(minute, high + margin * .65, f"{row['trade']} sin spot", fontsize=7, rotation=90)
    ax.set_title('Velas de snapshots 5m · IB/Fibonacci solo desde 10:30 · objetivo y stop congelados durante cada operación',
                 fontsize=11, loc='left', pad=12)
    ax.legend(handles=[Line2D([0], [0], color='#474f60', lw=2, label='Objetivo'),
                       Line2D([0], [0], color='#474f60', lw=2, ls=':', label='Stop'),
                       Line2D([0], [0], color='#474f60', marker='^', ls='', label='Entrada CALL / ▾ PUT'),
                       Line2D([0], [0], color='#474f60', marker='X', ls='', label='Salida')],
              ncol=4, fontsize=8, loc='upper left', framealpha=.9)
    context.plot(np.arange(391), np.where(valid, spot, np.nan), color='#334155', linewidth=1.1, label='Spot muestreado')
    for source, color in WALL_COLORS.items():
        subset = walls.loc[walls.source == source]
        context.scatter(subset.minute, subset.center, color=color, s=5, alpha=.45, label=WALL_NAMES[source])
    context.set_title('Contexto causal móvil: top 3 strikes por lado y familia · puntos, sin interpolar walls · gamma = proxy BS × OI',
                      fontsize=10, loc='left')
    context.legend(ncol=5, fontsize=8, loc='upper left')
    for axis in (ax, context):
        axis.axvspan(0, 60, color='#a7b3cb', alpha=.12)
        axis.axvline(60, color='#718096', linewidth=.8)
        axis.axvline(385, color='#718096', linewidth=.8, linestyle=':')
        axis.set_xlim(-3, 400)
        ticks = list(range(0, 391, 30))
        axis.set_xticks(ticks, [clock(value) for value in ticks], fontsize=8)
        axis.set_ylabel('Spot', fontsize=9)
        axis.grid(axis='y', alpha=.13)
        axis.spines[['top', 'right']].set_visible(False)
        axis.set_facecolor('white')
    context.set_xlabel('Hora de Nueva York · área sombreada = formación del IB', fontsize=9)
    table_ax.axis('off')
    table_rows = [[r['trade'], r['side'], f"{r['strike']:g}", clock(r['entry_i']), clock(r['exit_i']),
                   r['hold_minutes'], r['reason'], f"{r['target']:.2f}", f"{r['stop']:.2f}",
                   f"{r['net_base']:+.2f}"] for r in rows]
    headers = ['#', 'Lado', 'Strike', 'Entrada', 'Salida', 'Min', 'Motivo', 'Objetivo', 'Stop', 'Neto $']
    if table_rows:
        table = table_ax.table(cellText=table_rows, colLabels=headers, cellLoc='center',
                              bbox=[0, 0, 1, .94])
        table.auto_set_font_size(False)
        table.set_fontsize(8)
        table.scale(1, 1.25)
        for (r, _), cell in table.get_celld().items():
            cell.set_edgecolor('#dde3ee')
            cell.set_facecolor('#e5eaf3' if r == 0 else ('white' if r % 2 else '#f2f5fa'))
    else:
        table_ax.text(.5, .5, 'Oracle sin operaciones', ha='center')
    total = sum(row['net_base'] for row in rows)
    table_ax.set_title(f'{len(rows)} operaciones · neto base {total:+,.2f} USD · un contrato por operación, no rentabilidad de cuenta',
                       fontsize=10, loc='left', pad=8)
    holds = [row['hold_minutes'] for row in rows]
    if holds:
        bins = np.unique([0, 5, 15, 30, 60, 120, 330])
        hist.hist(holds, bins=bins, color='#5477a5', edgecolor='white')
        hist.set_title(f'Duración variable\nmin {min(holds)} · med {np.median(holds):g} · max {max(holds)}', fontsize=9)
        hist.set_xlabel('Minutos', fontsize=8)
        hist.set_ylabel('Operaciones', fontsize=8)
        hist.tick_params(labelsize=8)
    else:
        hist.axis('off')
    fig.text(.06, .047, 'OHLC de muestras 1m: no incluye extremos intraminuto. IB usa 09:30–10:29. Figuras de niveles fuera del eje se omiten visualmente.',
             fontsize=8, color='#4c596c')
    fig.text(.06, .031, 'Entrada ask/salida bid del mismo contrato + costes; marcadores situados en spot, no en prima. El oracle conoce el futuro y elige la trayectoria.',
             fontsize=8, color='#4c596c')
    fig.subplots_adjust(top=.9, bottom=.1, left=.06, right=.95)
    output.mkdir(parents=True, exist_ok=True)
    png = output / f'{ticker}_{DATE}_oracle.png'
    if png.exists():
        raise FileExistsError(png)
    fig.savefig(png, dpi=150, facecolor=fig.get_facecolor())
    plt.close(fig)
    pd.DataFrame(rows).to_csv(output / f'{ticker}_{DATE}_trades.csv', index=False)
    counts = pd.Series(holds, dtype=int).value_counts().sort_index()
    fill_observed = [r for r in rows if r['fill_distance_bands'] is not None]
    report = {'ticker': ticker, 'date': DATE, 'fixed_session_not_selected_for_pnl': True,
              'oracle_uses_future': True, 'operable_model': False, 'trades': len(rows),
              'net_base': total, 'holding_minutes_counts': {str(k): int(v) for k, v in counts.items()},
              'decisions_near_entry_zone': sum(r['decision_distance_bands'] <= 1 + 1e-10 for r in rows),
              'observed_fill_spots': len(fill_observed),
              'fills_still_near_frozen_entry_zone': sum(r['fill_distance_bands'] <= 1 for r in fill_observed),
              'five_minute_candles': len(candles), 'partial_candles': int((candles.observed < 5).sum()),
              'clock_basis': metadata['clock_basis'], 'input_hashes': hashes, 'png': str(png),
              'plotter_sha256': sha256(__file__), 'scope': 'visual reconstruction, not independent oracle audit'}
    (output / f'{ticker}_{DATE}_chart_manifest.json').write_text(
        json.dumps(report, indent=2, allow_nan=False), encoding='utf-8')
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--engine-root', type=Path, required=True)
    parser.add_argument('--cache-root', type=Path, default=DEFAULT_CACHE)
    parser.add_argument('--output', type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    for ticker in TICKERS:
        engine_dir = args.engine_root / ticker / DATE
        report = render_day(engine_dir, args.cache_root / ticker / f'{DATE}.npz', ticker, args.output)
        print(json.dumps(report, allow_nan=False))


if __name__ == '__main__':
    main()
