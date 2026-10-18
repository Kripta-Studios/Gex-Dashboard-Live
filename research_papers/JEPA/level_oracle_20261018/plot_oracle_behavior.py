"""Plot all nine descriptive oracle groups; no data/model selection."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import shutil

import matplotlib

matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=Path('D:/GexResearchArtifacts/level_oracle_20261018/oracle_behavior_v2'))
    args = parser.parse_args()
    source = args.root / 'summary.json'
    summary = json.loads(source.read_text(encoding='utf-8'))
    if summary['status'] != 'COMPLETE_DESCRIPTIVE_HINDSIGHT':
        raise ValueError('Complete descriptive output required')
    groups = {(g['ticker'], g['split']): g['statistics'] for g in summary['groups']}
    tickers, splits = ('SPXW', 'SPY', 'QQQ'), ('train', 'validation', 'test')
    if set(groups) != {(ticker, split) for ticker in tickers for split in splits}:
        raise ValueError('Expected all nine fixed groups')
    target = args.root / 'oracle_behavior_profile.png'
    if target.exists():
        raise FileExistsError(target)
    colors = ('#235ea8', '#bc6542', '#138578')
    fig, axes = plt.subplots(1, 3, figsize=(16, 6), facecolor='#f7f8fc')
    fig.suptitle('ORACLE RETROSPECTIVO · USA FUTURO · NO OPERABLE',
                 fontsize=20, color='#a32337', fontweight='bold', y=.97)
    fig.text(.5, .89, 'Perfil completo: SPXW, SPY y QQQ · 2.595 ticker-días · 36.019 operaciones · sin selección de sesiones',
             ha='center', fontsize=11, color='#445068')
    x = np.arange(3)
    for i, (ticker, color) in enumerate(zip(tickers, colors)):
        values = [groups[ticker, split] for split in splits]
        axes[0].plot(x, [100 * v['farther_than_nearest_offered'] / v['trades'] for v in values],
                     marker='o', color=color, linewidth=2, label=ticker)
        axes[1].plot(x, [100 * v['not_best_standalone'] / v['trades'] for v in values],
                     marker='o', color=color, linewidth=2)
        medians = np.array([v['holding']['median'] for v in values])
        low = np.array([v['holding']['p10'] for v in values])
        high = np.array([v['holding']['p90'] for v in values])
        axes[2].errorbar(x + (i - 1) * .13, medians, yerr=[medians - low, high - medians],
                        fmt='o', color=color, capsize=5, linewidth=1.6)
    titles = ('Objetivo más lejano que el primero ofrecido',
              'No maximiza el beneficio aislado del trade',
              'Duración: punto = mediana; rango = p10–p90')
    for index, (axis, title) in enumerate(zip(axes, titles)):
        axis.set_title(title, fontsize=10.5, pad=14)
        axis.set_xticks(x, ['2023–24', '2025', '2026 H1'], fontsize=10)
        axis.set_xlim(-.35, 2.35)
        axis.set_facecolor('white')
        axis.spines[['top', 'right']].set_visible(False)
        axis.grid(axis='y', alpha=.16)
        axis.set_ylim(0, 100 if index < 2 else 45)
        axis.set_ylabel('% de operaciones' if index < 2 else 'Minutos')
    handles, names = axes[0].get_legend_handles_labels()
    fig.legend(handles, names, ncol=3, loc='upper center', bbox_to_anchor=(.5, .858), frameon=False)
    fig.text(.055, .085, 'El DP puede preferir un trade de menor beneficio individual para liberar la posición y aprovechar otra oportunidad de la jornada.',
             fontsize=10, color='#45546c')
    fig.text(.055, .047, 'Las proporciones describen elecciones con futuro; no son probabilidades de acierto causal. 2026 sigue siendo desarrollo ya visto.',
             fontsize=10, color='#45546c')
    fig.subplots_adjust(left=.055, right=.98, top=.71, bottom=.2, wspace=.29)
    fig.savefig(target, dpi=160, facecolor=fig.get_facecolor())
    plt.close(fig)
    shutil.copy2(__file__, args.root / 'plot_oracle_behavior.executed.py')
    manifest = dict(summary_sha256=sha(source), plotter_sha256=sha(__file__), image_sha256=sha(target),
                    plotted_groups=9, oracle_uses_future=True, selection_performed=False,
                    output=str(target), columns=['farther_than_nearest_offered', 'not_best_standalone', 'holding'])
    (args.root / 'oracle_behavior_profile_manifest.json').write_text(json.dumps(manifest, indent=2), encoding='utf-8')
    print(json.dumps(manifest))


if __name__ == '__main__':
    main()
