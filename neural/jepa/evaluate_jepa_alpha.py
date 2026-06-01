from __future__ import annotations

import argparse
import json
from pathlib import Path


def load_payload(path: str | Path) -> dict:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def metric(payload: dict, name: str, default: float = 0.0) -> float:
    return float(payload.get("metrics", {}).get(name, default))


def fmt_money(v: float) -> str:
    return f"{v:+,.2f}"


def row(label: str, payload: dict) -> str:
    return (
        f"| {label} | {metric(payload, 'total_trades'):.0f} | "
        f"{metric(payload, 'win_rate'):.1f}% | {metric(payload, 'profit_factor'):.3f} | "
        f"{fmt_money(metric(payload, 'total_pnl'))} | {fmt_money(metric(payload, 'max_drawdown'))} |"
    )


def deltas(base: dict, cand: dict) -> dict:
    return {
        "trades_delta": metric(cand, "total_trades") - metric(base, "total_trades"),
        "trades_ratio": metric(cand, "total_trades") / max(1.0, metric(base, "total_trades")),
        "pf_delta": metric(cand, "profit_factor") - metric(base, "profit_factor"),
        "pnl_delta": metric(cand, "total_pnl") - metric(base, "total_pnl"),
        "pnl_ratio": metric(cand, "total_pnl") / max(1.0, abs(metric(base, "total_pnl"))),
        "drawdown_worsening_ratio": (
            abs(metric(cand, "max_drawdown")) / max(1.0, abs(metric(base, "max_drawdown")))
        ),
    }


def gate_a(base: dict, cand: dict) -> tuple[bool, list[str]]:
    d = deltas(base, cand)
    reasons = []
    pf_pass = d["pf_delta"] >= 0.05
    pnl_pass = d["pnl_delta"] >= 0.10 * abs(metric(base, "total_pnl"))
    if pf_pass:
        reasons.append(f"PF improved by {d['pf_delta']:.3f} >= 0.050")
    if pnl_pass:
        reasons.append(f"PnL improved by {fmt_money(d['pnl_delta'])} >= 10% baseline")
    if not (pf_pass or pnl_pass):
        reasons.append("PF/PnL improvement threshold not met")

    if d["trades_ratio"] < 0.90 and d["pf_delta"] < 0.10:
        reasons.append(f"trade count ratio too low: {d['trades_ratio']:.3f}")
        volume_pass = False
    else:
        volume_pass = True

    if d["drawdown_worsening_ratio"] > 1.10:
        reasons.append(f"drawdown worsened too much: {d['drawdown_worsening_ratio']:.3f}x")
        dd_pass = False
    else:
        dd_pass = True

    return bool((pf_pass or pnl_pass) and volume_pass and dd_pass), reasons


def ticker_table(payloads: dict[str, dict]) -> str:
    tickers = sorted({t for p in payloads.values() for t in p.get("per_ticker", {}).keys()})
    lines = ["| Ticker | Run | Trades | WR | PF | PnL | Max DD |", "| --- | --- | ---: | ---: | ---: | ---: | ---: |"]
    for ticker in tickers:
        for label, payload in payloads.items():
            p = {"metrics": payload.get("per_ticker", {}).get(ticker, {})}
            lines.append(row(f"{ticker} {label}", p).replace(f"| {ticker} {label} |", f"| {ticker} | {label} |"))
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="Evaluate whether JEPA added GBT alpha.")
    parser.add_argument("--baseline", required=True)
    parser.add_argument("--jepa", required=True)
    parser.add_argument("--jepa-only", required=True)
    parser.add_argument("--jepa-permuted", default=None)
    parser.add_argument("--output-md", required=True)
    parser.add_argument("--output-json", required=True)
    args = parser.parse_args()

    base = load_payload(args.baseline)
    jepa = load_payload(args.jepa)
    jepa_only = load_payload(args.jepa_only)
    perm = load_payload(args.jepa_permuted) if args.jepa_permuted else None

    passed, reasons = gate_a(base, jepa)
    payloads = {"baseline": base, "gbt_jepa": jepa, "jepa_only": jepa_only}
    if perm:
        payloads["jepa_permuted"] = perm

    lines = [
        "# JEPA Alpha Report",
        "",
        f"Gate A: {'PASS' if passed else 'FAIL'}",
        "",
        "## Overall Metrics",
        "",
        "| Run | Trades | WR | PF | PnL | Max DD |",
        "| --- | ---: | ---: | ---: | ---: | ---: |",
        row("baseline", base),
        row("gbt_jepa", jepa),
        row("jepa_only", jepa_only),
    ]
    if perm:
        lines.append(row("jepa_permuted", perm))

    d = deltas(base, jepa)
    lines += [
        "",
        "## Delta: GBT + JEPA vs Baseline",
        "",
        f"- Trades delta: {d['trades_delta']:+.0f} ({d['trades_ratio']:.3f}x baseline)",
        f"- PF delta: {d['pf_delta']:+.3f}",
        f"- PnL delta: {fmt_money(d['pnl_delta'])}",
        f"- Drawdown ratio: {d['drawdown_worsening_ratio']:.3f}x baseline",
        "",
        "## Gate Reasons",
        "",
    ]
    lines += [f"- {r}" for r in reasons]

    if perm:
        pd = deltas(perm, jepa)
        lines += [
            "",
            "## Permutation Check",
            "",
            "- This compares the candidate model against the same model/data after OOS JEPA feature permutation.",
            f"- PF candidate minus permuted: {pd['pf_delta']:+.3f}",
            f"- PnL candidate minus permuted: {fmt_money(pd['pnl_delta'])}",
        ]

    lines += [
        "",
        "## Per Ticker",
        "",
        ticker_table(payloads),
        "",
    ]

    report = "\n".join(lines)
    Path(args.output_md).parent.mkdir(parents=True, exist_ok=True)
    Path(args.output_md).write_text(report, encoding="utf-8")
    result = {
        "gate_a_pass": passed,
        "reasons": reasons,
        "baseline": base,
        "gbt_jepa": jepa,
        "jepa_only": jepa_only,
        "jepa_permuted": perm,
        "delta_gbt_jepa_vs_baseline": d,
    }
    Path(args.output_json).write_text(json.dumps(result, indent=2, default=float), encoding="utf-8")
    print(report)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

