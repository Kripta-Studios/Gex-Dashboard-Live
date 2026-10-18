"""Plot every fixed representation and ticker; no selection or model fitting."""
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import pandas as pd


ROOT = Path("D:/GexResearchArtifacts/restart_20261018")
EXPERIMENTS = (
    ("zone_benchmark_parallel_v3", "Octubre–diciembre 2023"),
    ("wide_zone_benchmark", "Enero–junio 2026"),
)
COLORS = {"price": "#5d7185", "authentic": "#087e8b", "placebo": "#c97a35"}
LABELS = {
    "price": "Precio + contexto",
    "authentic": "Zonas auténticas",
    "placebo": "Zonas desplazadas",
}


def main():
    plt.rcParams.update({"font.size": 10, "axes.spines.top": False,
                         "axes.spines.right": False})
    fig, axes = plt.subplots(2, 3, figsize=(16, 8.5), layout="constrained")
    for row, (directory, title) in enumerate(EXPERIMENTS):
        source = ROOT / directory
        if not (source / "completion.json").exists():
            raise RuntimeError(f"Experiment not complete: {source}")
        ledger = pd.read_parquet(source / "ledger.parquet")
        ledger = ledger.loc[ledger.period == "test"].copy()
        daily = pd.read_csv(source / "test_daily_net.csv", dtype={"date": str})
        dates = pd.DatetimeIndex(pd.to_datetime(daily.iloc[:, 0].astype(str)))
        ledger["plot_date"] = pd.to_datetime(ledger.date.astype(str))
        for column, ticker in enumerate(("SPXW", "SPY", "QQQ")):
            ax = axes[row, column]
            ax.axhline(0, color="#343b43", linewidth=0.7)
            for name in COLORS:
                chosen = ledger.loc[(ledger.representation == name)
                                    & (ledger.ticker_name == ticker)]
                pnl = chosen.groupby("plot_date").net.sum().reindex(dates, fill_value=0)
                ax.plot(dates, pnl.cumsum(), color=COLORS[name], label=LABELS[name],
                        linewidth=1.8 if name == "authentic" else 1.3)
            ax.set_title(f"{ticker} · {title}", fontsize=11, loc="left")
            ax.set_ylabel("Resultado neto acumulado (USD)")
            ax.grid(axis="y", alpha=0.18)
            ax.xaxis.set_major_locator(mdates.MonthLocator())
            ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y-%m"))
            ax.tick_params(axis="x", rotation=25)
    handles, labels = axes[0, 0].get_legend_handles_labels()
    fig.legend(handles, labels, loc="outside lower center", ncol=3, frameon=False)
    fig.suptitle("Pruebas retrospectivas: un contrato por operación, ask → bid y costes\n"
                 "Todas las representaciones y tickers · desarrollo visto, sin evidencia live",
                 fontsize=15, fontweight="bold")
    target = ROOT / "benchmark_comparison.png"
    fig.savefig(target, dpi=170, facecolor="white")
    plt.close(fig)
    print(target)


if __name__ == "__main__":
    main()
