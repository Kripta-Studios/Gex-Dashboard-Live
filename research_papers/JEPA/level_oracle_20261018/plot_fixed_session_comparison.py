"""Fixed first validation session illustration; no tuning or model fitting."""
import hashlib
import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle
import numpy as np
import pandas as pd

ROOT = Path("D:/GexResearchArtifacts/level_oracle_20261018")
DAY = "20250102"  # First validation session, fixed before loading its ledger.
TICKER = "SPY"


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    out = ROOT / "fixed_session_comparison_v1"
    out.mkdir(exist_ok=False)
    engine = ROOT / "engine_v1" / TICKER / DAY
    raw_path = ROOT / "cache_v1" / TICKER / (DAY + ".npz")
    learner_path = ROOT / "episode_learners_v1/validation/gbt_net__0_ledger.parquet"
    paths = [raw_path, engine / "levels.parquet", engine / "oracle_ledger.parquet", learner_path]
    before = {str(p): sha(p) for p in paths}
    with np.load(raw_path, allow_pickle=False) as raw:
        spot = raw["spot"].copy()
        valid = raw["spot_valid"].copy() & np.isfinite(spot) & (spot > 0)
    spot[~valid] = np.nan
    ib = spot[:60][np.isfinite(spot[:60])]
    low, high = float(ib.min()), float(ib.max())
    width = high - low
    levels = pd.read_parquet(engine / "levels.parquet")
    oracle = pd.read_parquet(engine / "oracle_ledger.parquet")
    model = pd.read_parquet(learner_path)
    model = model[(model.ticker == TICKER) & (model.date.astype(str) == DAY)].copy()
    model = model.sort_values("entry_i")
    oracle = oracle.sort_values("entry_i")
    fig, axes = plt.subplots(2, 1, figsize=(18, 12), sharex=True, sharey=True)
    lower, upper = np.nanmin(spot) - width * .12, np.nanmax(spot) + width * .12
    for ax, ledger, title in zip(axes, (oracle, model), ("Oracle: selecciona con el futuro", "GBT net, umbral 0: decisiones causales"), strict=True):
        ax.set_facecolor("#fafafa")
        ax.axvspan(0, 60, color="#d4dce5", alpha=.3)
        for minute in range(0, 390, 5):
            values = spot[minute:minute+5]
            values = values[np.isfinite(values)]
            if not len(values):
                continue
            open_, close = values[0], values[-1]
            color = "#287f6b" if close >= open_ else "#bd535b"
            ax.plot([minute + 2] * 2, [values.min(), values.max()], color=color, lw=.8)
            ax.add_patch(Rectangle((minute + .4, min(open_, close)), 3.2, max(abs(close-open_), .006), facecolor=color, alpha=.65, linewidth=0))
        for ratio in (-1, -.618, -.272, 0, .236, .382, .5, .618, .786, 1, 1.272, 1.618, 2):
            price = low + ratio * width
            if lower <= price <= upper:
                ax.hlines(price, 60, 390, color="#8b96a5", lw=.7, alpha=.65)
                ax.text(392, price, f"IB {ratio:g}", va="center", fontsize=8, color="#596475")
        for bit, color, label in ((2, "#b66e13", "Zona call OI"), (4, "#386ba6", "Zona put OI")):
            rows = levels[(levels.source_mask.astype(int) & bit) != 0]
            ax.scatter(rows.state_i, rows.center, s=3, c=color, alpha=.4, label=label)
        for row in ledger.itertuples(index=False):
            entry, exit_ = int(row.entry_i), int(row.exit_i)
            color = "#047857" if int(row.right) == 0 else "#9333a7"
            ax.plot([entry, exit_], [spot[entry], spot[exit_]], color=color, lw=1.7, alpha=.85)
            ax.scatter(entry, spot[entry], c=color, s=55, marker="^" if int(row.right) == 0 else "v", zorder=6)
            ax.scatter(exit_, spot[exit_], c=color, s=40, marker="x", zorder=6)
            ax.hlines(row.target_center, entry, exit_, color=color, lw=.9, linestyle="--", alpha=.7)
            ax.hlines(row.stop_center, entry, exit_, color=color, lw=.7, linestyle=":", alpha=.5)
        pnl = float(ledger.net_base.sum()) if len(ledger) else 0.
        ax.set_title(f"{title} | {len(ledger)} operaciones | neto {pnl:+,.2f} USD", loc="left", fontsize=13, pad=12)
        ax.set_ylabel("SPY — precio muestreado")
        ax.set_ylim(lower, upper)
        ax.set_xlim(0, 412)
        ax.grid(axis="x", color="#e4e7ec", lw=.6)
        ax.legend(loc="lower left", fontsize=8, framealpha=.9)
    ticks = np.arange(0, 391, 30)
    axes[-1].set_xticks(ticks, [f"{(570+int(t))//60:02d}:{(570+int(t))%60:02d}" for t in ticks])
    axes[-1].set_xlabel("Hora de Nueva York | triángulo: compra CALL/PUT; ×: venta; -- objetivo; ··· stop")
    fig.suptitle("SPY · 2 enero 2025 · primera sesión de validación", fontsize=18, x=.07, ha="left")
    fig.text(.07, .035, "Velas de 5 minutos construidas con snapshots de 1 minuto; no son OHLC tick. IB disponible desde 10:30.\nUn contrato por operación; costes base incluidos. Líneas de trades proyectadas sobre el subyacente, no sobre el precio de la opción.\nSesión fijada por calendario: ilustración, no estimación de rentabilidad ni selección de una estrategia.", fontsize=9, color="#475569")
    fig.subplots_adjust(left=.07, right=.95, bottom=.13, top=.92, hspace=.18)
    fig.savefig(out / "comparison.png", dpi=140)
    fig.savefig(out / "comparison.pdf")
    plt.close(fig)
    assert all(sha(p) == digest for p, digest in before.items())
    summary = dict(status="COMPLETE_FIXED_SESSION_ILLUSTRATION", ticker=TICKER, date=DAY,
                   selection="First validation session; SPY fixed before reading ledger", sources=before,
                   oracle_trades=len(oracle), oracle_net=float(oracle.net_base.sum()),
                   model_trades=len(model), model_net=float(model.net_base.sum()),
                   code_sha256=sha(__file__))
    (out / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps(summary), flush=True)


if __name__ == "__main__":
    main()
