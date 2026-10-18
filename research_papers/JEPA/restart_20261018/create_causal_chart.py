"""Predetermined, cutoff-filtered sampled-candle/OI-zone illustrations; no outcomes."""
from pathlib import Path
import hashlib
import json

import matplotlib
matplotlib.use('Agg')
import matplotlib.dates as mdates
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle
import numpy as np
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq

ROOT = Path('D:/ThetaData/data_options')
OUT = Path('D:/GexResearchArtifacts/restart_20261018/causal_charts')
DATES = ['20230103', '20260102']
TICKERS = ['SPXW', 'SPY', 'QQQ']
RATIOS = [-.618, -.272, 0., 1., 1.272, 1.618]


def source(ticker, day, kind):
    return ROOT / ticker / kind / day[:4] / day[4:6] / f'{ticker}_{day}_{day}_{kind}.parquet'


def parse_time(series):
    if pd.api.types.is_datetime64_any_dtype(series.dtype):
        return pd.to_datetime(series)
    return pd.to_datetime(series, format='ISO8601')


def filter_value(field, value):
    if pa.types.is_timestamp(field.type):
        return pd.Timestamp(value).to_pydatetime()
    return value


def prepare(ticker, day):
    greek_path = source(ticker, day, 'greeks')
    oi_path = source(ticker, day, 'oi')
    if not greek_path.exists() or not oi_path.exists():
        return None, {'ticker': ticker, 'day': day, 'status': 'missing_source'}
    schema = pq.ParquetFile(greek_path).schema_arrow
    field = 'timestamp' if 'timestamp' in schema.names else 'underlying_timestamp'
    date = f'{day[:4]}-{day[4:6]}-{day[6:]}'
    start, end = f'{date}T09:30:00', f'{date}T12:30:00'
    cols = list(dict.fromkeys([field, 'underlying_timestamp', 'underlying_price', 'symbol', 'trade_date']))
    greek = pq.read_table(greek_path, columns=cols,
                          filters=[(field, '>=', filter_value(schema.field(field), start)),
                                   (field, '<', filter_value(schema.field(field), end))]).to_pandas()
    greek['_time'] = parse_time(greek[field])
    grouped = greek.groupby('_time').underlying_price
    samples = grouped.first()
    invalid = (grouped.nunique(dropna=False) != 1) | ~np.isfinite(samples) | (samples <= 0)
    samples[invalid] = np.nan
    # Reindex adds missingness, never a price. Both plots use the same observed series.
    sample_index = pd.date_range(f'{date} 09:30', f'{date} 12:29', freq='min')
    samples = samples.reindex(sample_index)
    ib_samples = samples.loc[f'{date} 09:30':f'{date} 10:29']
    ib_low, ib_high = float(ib_samples.min()), float(ib_samples.max())
    oi_schema = pq.ParquetFile(oi_path).schema_arrow
    oi_cols = ['strike', 'right', 'open_interest']
    if 'timestamp' in oi_schema.names:
        oi_cols.append('timestamp')
        oi = pq.read_table(oi_path, columns=oi_cols,
                           filters=[('timestamp', '<=', filter_value(oi_schema.field('timestamp'), f'{date}T12:34:00'))]).to_pandas()
        oi_basis = 'timestamp OI nativo <= 12:34'
    else:
        oi = pq.read_table(oi_path, columns=oi_cols).to_pandas()
        oi_basis = 'OI disponible 09:30: supuesto'
    oi['right'] = oi.right.replace({'C': 'CALL', 'P': 'PUT'})
    oi = oi.loc[np.isfinite(oi.strike) & np.isfinite(oi.open_interest) & (oi.open_interest > 0)]
    if oi.duplicated(['strike', 'right']).any():
        raise ValueError(f'Duplicate OI identity: {oi_path}')
    walls = []
    for side in ['CALL', 'PUT']:
        ranked = oi.loc[oi.right == side].sort_values(['open_interest', 'strike'], ascending=[False, True])
        if not ranked.empty:
            row = ranked.iloc[0]
            walls.append({'right': side, 'strike': float(row.strike), 'open_interest': int(row.open_interest)})
    manifest = {'ticker': ticker, 'day': day, 'status': 'rendered',
                'timezone_convention': 'America/New_York, naive source fields',
                'feature_cutoff': f'{date}T12:34:00', 'decision_time': f'{date}T12:35:00',
                'displayed_samples_start_inclusive': start, 'displayed_samples_end_exclusive': end,
                'latest_displayed_sample': str(samples.dropna().index.max()),
                'clock_basis': 'native_timestamp' if field == 'timestamp' else 'assumed_underlying_snapshot_clock',
                'projected_source_rows': len(greek), 'valid_displayed_samples': int(samples.notna().sum()),
                'missing_displayed_samples': int(samples.isna().sum()), 'ib_valid_samples': int(ib_samples.notna().sum()),
                'ib_low': ib_low, 'ib_high': ib_high, 'ib_is_sampled': True,
                'oi_basis': oi_basis, 'walls': walls, 'band_halfwidth_ib_fraction': .1,
                'source_hashes': {str(path): hashlib.sha256(path.read_bytes()).hexdigest()
                                  for path in [greek_path, oi_path]},
                'outcomes_read': False, 'selection_basis': 'fixed dates and tickers, not profitability'}
    return (samples, ib_low, ib_high, walls, oi_basis), manifest


def draw(ticker, day, prepared, manifest):
    samples, ib_low, ib_high, walls, oi_basis = prepared
    width = ib_high - ib_low
    date = f'{day[:4]}-{day[4:6]}-{day[6:]}'
    start = pd.Timestamp(f'{date} 09:30')
    ib_end = pd.Timestamp(f'{date} 10:30')
    plot_end = pd.Timestamp(f'{date} 12:50')
    decision = pd.Timestamp(f'{date} 12:35')
    fig, axes = plt.subplots(2, 1, figsize=(15, 9.2), sharex=True)
    fig.set_facecolor('#f4f6f8')
    fig.subplots_adjust(left=.065, right=.83, top=.87, bottom=.13, hspace=.14)
    visible_low = min(float(samples.min()), ib_low - .75 * width)
    visible_high = max(float(samples.max()), ib_high + .75 * width)
    margin = (visible_high - visible_low) * .06
    low, high = visible_low - margin, visible_high + margin
    for ax, minutes in zip(axes, [5, 15]):
        ax.set_facecolor('white')
        bars = samples.resample(f'{minutes}min', origin=start).agg(['first', 'max', 'min', 'last', 'count'])
        bars = bars.loc[(bars.index + pd.Timedelta(minutes=minutes)) <= pd.Timestamp(f'{date} 12:30')]
        candle_width = minutes / 1440 * .62
        for stamp, bar in bars.iterrows():
            if bar['count'] == 0:
                continue
            center = mdates.date2num(stamp + pd.Timedelta(minutes=minutes / 2))
            color = '#128879' if bar['last'] >= bar['first'] else '#d85454'
            ax.plot([center, center], [bar['min'], bar['max']], color=color, linewidth=1.3, zorder=4)
            height = max(abs(bar['last'] - bar['first']), (high - low) * .001)
            ax.add_patch(Rectangle((center - candle_width / 2, min(bar['first'], bar['last'])),
                                   candle_width, height, facecolor=color, edgecolor=color, zorder=5,
                                   hatch='///' if bar['count'] < minutes else None))
        ax.axvspan(start, ib_end, color='#cbd5e1', alpha=.22, zorder=0)
        # Final IB values are drawn only after IB is complete: no visual lookahead.
        for ratio in RATIOS:
            value = ib_low + ratio * width
            if not low <= value <= high:
                continue
            core = ratio in [0., 1.]
            color = '#334155' if core else '#718096'
            ax.plot([ib_end, plot_end], [value, value], color=color,
                    linewidth=1.3 if core else .9, linestyle='-' if core else '--', zorder=2)
            text = ('IB low · 0' if ratio == 0 else 'IB high · 1' if ratio == 1 else f'Fib {ratio:g}')
            ax.text(1.01, value, text, transform=ax.get_yaxis_transform(), va='center',
                    fontsize=8.5, color=color, clip_on=False)
        for wall in walls:
            strike = wall['strike']
            if not low <= strike <= high:
                continue
            color = '#7757b4' if wall['right'] == 'CALL' else '#c68125'
            ax.axhspan(strike - .1 * width, strike + .1 * width, color=color, alpha=.12, zorder=1)
            ax.axhline(strike, color=color, linewidth=1, zorder=2)
        ax.axvspan(pd.Timestamp(f'{date} 12:30'), plot_end, color='#e2e8f0', alpha=.65)
        ax.axvline(decision, color='#1e293b', linestyle=':', linewidth=1.2)
        ax.text(.012, .92, f'{minutes} minutos · velas muestreadas', transform=ax.transAxes,
                fontsize=10, weight='bold', color='#334155', zorder=10,
                bbox={'facecolor': 'white', 'edgecolor': 'none', 'alpha': .85, 'pad': 2})
        ax.text(mdates.date2num(pd.Timestamp(f'{date} 12:40')), high - .12 * (high - low),
                'Futuro\nno mostrado', ha='center', va='center', fontsize=8.5, color='#64748b')
        ax.set_ylim(low, high)
        ax.grid(axis='y', color='#e2e8f0', linewidth=.7)
        ax.spines[['top', 'right']].set_visible(False)
        ax.set_ylabel('Spot muestreado', fontsize=9, color='#334155')
        ax.tick_params(labelsize=9, colors='#475569')
    axes[-1].set_xlim(start, plot_end)
    axes[-1].xaxis.set_major_locator(mdates.MinuteLocator(byminute=[0, 30]))
    axes[-1].xaxis.set_major_formatter(mdates.DateFormatter('%H:%M'))
    axes[-1].set_xlabel('Hora de Nueva York · decisión 12:35 · corte de features 12:34', fontsize=9)
    fig.suptitle(f'{ticker}  |  {date}   ·   Geometría visible antes de decidir', x=.065, ha='left',
                 fontsize=19, color='#152538', weight='bold')
    wall_parts = [f"{w['right']} OI máximo: strike {w['strike']:g} · OI {w['open_interest']:,}" for w in walls]
    wall_text = '     |     '.join(wall_parts)
    fig.text(.065, .905, wall_text + '     |     Banda: ±0,10 × IB', fontsize=10, color='#475569')
    fig.text(.065, .063, f'Sampled OHLC / IB · IB {ib_low:.2f}–{ib_high:.2f} · {manifest["ib_valid_samples"]}/60 muestras válidas. '
             'Las líneas IB/Fib empiezan a las 10:30.', fontsize=9, color='#475569')
    clock_text = 'timestamp nativo' if manifest['clock_basis'] == 'native_timestamp' else 'underlying_timestamp como reloj de snapshot asumido'
    fig.text(.065, .038, f'{clock_text} · {oi_basis}. OI = concentración por strike, no posición ni signo de dealers.',
             fontsize=9, color='#475569')
    filename = OUT / f'{ticker}_{day}_causal_1235.png'
    fig.savefig(filename, dpi=150, facecolor=fig.get_facecolor())
    plt.close(fig)
    manifest['png'] = str(filename)
    manifest['png_sha256'] = hashlib.sha256(filename.read_bytes()).hexdigest()


def main():
    OUT.mkdir(parents=True, exist_ok=False)
    records = []
    for day in DATES:
        for ticker in TICKERS:
            prepared, manifest = prepare(ticker, day)
            if prepared is not None:
                draw(ticker, day, prepared, manifest)
            records.append(manifest)
    (OUT / 'manifest.json').write_text(json.dumps(records, indent=2), encoding='utf-8')
    print(json.dumps({'directory': str(OUT), 'charts': len([r for r in records if r['status'] == 'rendered'])}))


if __name__ == '__main__':
    main()
