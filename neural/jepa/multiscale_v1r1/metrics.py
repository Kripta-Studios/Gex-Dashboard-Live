"""GATE-001: scenario-specific dollar accounting, never account return."""
from decimal import Decimal


def summarize_pnl(pnls, months, expected_months):
    values = [Decimal(str(p)) for p in pnls]
    if len(values) != len(months) or any(m not in expected_months for m in months):
        raise ValueError('GATE-001: invalid monthly alignment')
    if any(not v.is_finite() for v in values):
        raise ValueError('GATE-001: nonfinite PnL')
    gains = sum((p for p in values if p > 0), Decimal(0))
    losses = -sum((p for p in values if p < 0), Decimal(0))
    pf = float(gains / losses) if losses else ('Infinity' if gains > 0 else None)
    monthly = {m: sum((p for p, k in zip(values, months, strict=True) if k == m), Decimal(0))
               for m in expected_months}
    positive = [p for p in monthly.values() if p > 0]
    return {'trades': len(values), 'wr': sum(p > 0 for p in values) / len(values) if values else None,
            'pf': pf, 'net_dollar_pnl': str(sum(values, Decimal(0))),
            'gross_gains': str(gains), 'gross_losses': str(losses),
            'monthly_pnl': {m: str(p) for m, p in monthly.items()},
            'monthly_counts': {m: months.count(m) for m in expected_months},
            'positive_months': len(positive),
            'concentration': float(max(positive) / sum(positive)) if positive else None}


def pf_value(summary):
    pf = summary['pf']
    return float('-inf') if pf is None else float(pf)


def terminal_gate(base, adverse, ablation):
    frequency = len(base['monthly_counts']) == 18 and min(base['monthly_counts'].values()) >= 13
    if not frequency:
        return 'FAILED_FREQUENCY'
    economic = (pf_value(base) > 1.2 and base['wr'] is not None and base['wr'] > .45
                and Decimal(base['net_dollar_pnl']) > 0 and base['positive_months'] >= 13
                and base['concentration'] is not None and base['concentration'] <= .4
                and pf_value(adverse) > 1.2 and Decimal(adverse['net_dollar_pnl']) > 0
                and adverse['positive_months'] >= 13)
    if not economic:
        return 'FAILED_ECONOMIC'
    if (Decimal(base['net_dollar_pnl']) <= Decimal(ablation['net_dollar_pnl'])
            or pf_value(base) < pf_value(ablation)):
        return 'FAILED_INCREMENTAL'
    return 'DEVELOPMENT_PASS_REQUIRES_SHADOW'
