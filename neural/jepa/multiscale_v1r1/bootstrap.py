"""BOOT-001: paired within-month circular day blocks; no economic selection."""
import numpy as np

from .contract import SEED, TICKERS, ContractError


def paired_bootstrap(primary, ablation, calendar, *, draws=10000, block=5, seed=SEED):
    """Daily sufficient stats are [net USD, gross gains, gross losses, wins, trades]."""
    if draws != 10000 or block != 5 or seed != SEED:
        raise ContractError('BOOT-001: fixed bootstrap specification')
    months = sorted(calendar)
    rng = np.random.default_rng(seed)
    sums = {name: np.zeros((draws, len(TICKERS), 5)) for name in ('primary', 'ablation')}
    for month in months:
        days = calendar[month]
        if not days or len(set(days)) != len(days):
            raise ContractError('BOOT-001: empty or duplicate admitted calendar')
        n = len(days)
        starts = rng.integers(0, n, size=(draws, (n + block - 1) // block))
        indices = ((starts[:, :, None] + np.arange(block)) % n).reshape(draws, -1)[:, :n]
        for name, rows in (('primary', primary), ('ablation', ablation)):
            matrix = np.asarray([[rows.get((ticker, day), [0.] * 5) for ticker in TICKERS] for day in days], dtype=float)
            if matrix.shape != (n, len(TICKERS), 5) or not np.isfinite(matrix).all():
                raise ContractError('BOOT-001: invalid daily statistics')
            sums[name] += matrix[indices].sum(axis=1)

    def quantities(values):
        with np.errstate(divide='ignore', invalid='ignore'):
            return dict(pnl=values[:, :, 0], pf=values[:, :, 1] / values[:, :, 2],
                        wr=values[:, :, 3] / values[:, :, 4])

    metrics = {name: quantities(value) for name, value in sums.items()}
    with np.errstate(invalid='ignore'):
        metrics['paired_difference'] = {key: metrics['primary'][key] - metrics['ablation'][key] for key in ('pnl', 'pf', 'wr')}
    result = {'draws': draws, 'block_days': block, 'seed': seed, 'admitted_days': sum(map(len, calendar.values())),
              'shared_indices_across_tickers_and_policies': True, 'diagnostic_only': True, 'metrics': {}}
    for name, group in metrics.items():
        result['metrics'][name] = {}
        for metric, values in group.items():
            result['metrics'][name][metric] = {}
            for i, ticker in enumerate(TICKERS):
                finite = values[:, i][np.isfinite(values[:, i])]
                result['metrics'][name][metric][ticker] = dict(
                    finite_draws=len(finite), undefined_draws=int(np.isnan(values[:, i]).sum()),
                    positive_infinite_draws=int(np.isposinf(values[:, i]).sum()),
                    negative_infinite_draws=int(np.isneginf(values[:, i]).sum()),
                    finite_only_interval=np.quantile(finite, [.025, .975]).tolist() if len(finite) else None)
    return result
