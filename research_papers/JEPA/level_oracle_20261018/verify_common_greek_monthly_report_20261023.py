"""Independent descriptive reconciliation; consumes sealed ledgers, never market quotes."""
from collections import defaultdict
import ctypes
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path
import re

BASE = Path('D:/GexResearchArtifacts/level_oracle_20261018')
ROOT = BASE / 'common_greek_comparison_v1'
CODE = Path(__file__).resolve().parent
AUDIT = BASE / 'common_greek_comparison_v1_economic_audit_02/audit.json'
SUMMARY = BASE / 'common_greek_comparison_v1_monthly_report_20261023_01/summary.json'
AUDIT_SHA = '45caae6c11cdce9306284367e7742d9dbe17e03a8afeb52eff447b3408758a0d'
SUMMARY_SHA = '6086af9fba7d5a7423a36eda120c9873415a9c3f3f5b61d9fea0bfa3ab47183c'
POLICIES = ('cue_net__0', 'common_greek_net__0')
TICKERS = ('QQQ', 'SPXW', 'SPY')
MISSING = {(t, d) for t in ('QQQ', 'SPY') for d in ('20260401', '20260409', '20260415')}


def digest(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def main():
    output = CODE / 'COMMON_GREEK_MONTHLY_REPORT_VERIFICATION_20261023.json'
    assert not output.exists(), 'Immutable new verification required'

    class Memory(ctypes.Structure):
        _fields_ = [('length', ctypes.c_ulong), ('load', ctypes.c_ulong)] + [
            (name, ctypes.c_ulonglong) for name in
            ('total', 'ram', 'total_commit', 'commit', 'virtual', 'free_virtual', 'extended')]

    memory = Memory()
    memory.length = ctypes.sizeof(memory)
    assert ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(memory))
    resources = {'available_ram_bytes': memory.ram, 'free_commit_bytes': memory.commit}
    assert min(resources.values()) >= 2_000_000_000
    print(json.dumps({'gate': resources}), flush=True)
    import pyarrow.parquet as pq

    sources = {}

    def consume(path, expected):
        path = Path(path).resolve()
        assert digest(path) == expected, str(path)
        sources[str(path)] = expected
        return path

    def read(path):
        return json.loads(Path(path).read_text(encoding='utf-8'))

    audit = read(consume(AUDIT, AUDIT_SHA))
    summary = read(consume(SUMMARY, SUMMARY_SHA))
    assert audit['status'] == 'PASS_INDEPENDENT_COMMON_GREEK_COMPARISON_ECONOMIC_AUDIT'
    assert Path(audit['binding']['comparison_root']).resolve() == ROOT.resolve()
    assert audit['policies'] == list(POLICIES)
    assert summary['status'] == 'COMPLETE_DESCRIPTIVE_MONTHLY_REPORT'
    assert summary['policy_selection'] is False and summary['new_fits'] == summary['new_predictions'] == 0
    assert summary['development_seen'] is True and summary['promotion_approved'] is False
    for path, expected in summary['sources'].items():
        consume(path, expected)
    marker = read(consume(ROOT / 'comparison.complete.json', audit['binding']['comparison_complete_sha256']))
    assert marker['status'] == 'COMPLETE' and marker['binding'] == audit['binding']['freeze_sha256']
    members = {}
    for key, value in marker['files'].items():
        path = (ROOT / key).resolve()
        assert path.is_relative_to(ROOT.resolve()) and path not in members
        members[path] = value
    checked = 0
    max_error = 0.0

    def same(actual, expected, label):
        nonlocal checked, max_error
        checked += 1
        if isinstance(expected, bool) or expected is None or isinstance(expected, (str, list, int)):
            assert actual == expected, (label, actual, expected)
        else:
            assert math.isfinite(actual) and math.isfinite(expected), label
            error = abs(actual - expected)
            max_error = max(max_error, error)
            assert error <= 1e-8 + 1e-12 * abs(expected), (label, actual, expected)

    def economics(values):
        assert all(math.isfinite(v) for v in values)
        gains = math.fsum(v for v in values if v > 0)
        losses = -math.fsum(v for v in values if v < 0)
        return dict(trades=len(values), net_usd=math.fsum(values), gross_gains_usd=gains,
                    gross_losses_usd=losses, profit_factor=gains / losses if losses else None,
                    profit_factor_infinite=gains > 0 and losses == 0,
                    win_rate=sum(v > 0 for v in values) / len(values) if values else None)

    groups = defaultdict(list)
    annual = defaultdict(list)
    calendars = defaultdict(set)
    parquet_count = 0
    for path, expected in sorted(members.items()):
        match = re.fullmatch(r'days/(QQQ|SPXW|SPY)/(202[56][0-9]{4})\.json', path.relative_to(ROOT).as_posix())
        if not match:
            continue
        ticker, date = match.groups()
        calendars[ticker, date[:4]].add(date)
        daily = read(consume(path, expected))
        assert set(daily) == set(POLICIES)
        for policy in POLICIES:
            row = daily[policy]
            assert (row['ticker'], row['date']) == (ticker, date)
            assert (row['source_status'] == 'MISSING_SOURCE') == ((ticker, date) in MISSING)
            assert row['source_status'] in ('COMPLETE', 'MISSING_SOURCE')
            ledger_path = ROOT / 'days' / ticker / (date + '.' + policy + '.parquet')
            consume(ledger_path, members[ledger_path])
            attempts = pq.read_table(ledger_path, columns=['status', 'net_base', 'net_adverse'], use_threads=False).to_pylist()
            parquet_count += 1
            assert all(a['status'] in ('FILLED', 'NO_FILL') for a in attempts)
            assert all(math.isfinite(a[c]) for a in attempts for c in ('net_base', 'net_adverse'))
            assert all(a['net_base'] == a['net_adverse'] == 0 for a in attempts if a['status'] == 'NO_FILL')
            fills = [a for a in attempts if a['status'] == 'FILLED']
            same(len(attempts), row['attempts'], 'daily attempts')
            same(len(fills), row['trades'], 'daily fills')
            for c in ('net_base', 'net_adverse'):
                same(math.fsum(a[c] for a in fills), row[c], 'daily ' + c)
            if row['source_status'] == 'MISSING_SOURCE':
                assert not attempts and row['net_base'] == row['net_adverse'] == 0
            record = {'row': row, 'fills': fills}
            groups[policy, ticker, date[:6]].append(record)
            annual[policy, ticker, date[:4]].append(record)
            annual[policy, 'ALL', date[:4]].append(record)
    months = [f'2025{m:02}' for m in range(1, 13)] + [f'2026{m:02}' for m in range(1, 7)]
    assert set(groups) == {(p, t, m) for p in POLICIES for t in TICKERS for m in months}
    for year, count in [('2025', 250), ('2026', 123)]:
        assert all(len(calendars[t, year]) == count for t in TICKERS)
        assert calendars['QQQ', year] == calendars['SPY', year] == calendars['SPXW', year]
    reported = {(r['policy'], r['ticker'], r['month']): r for r in summary['months']}
    assert len(summary['months']) == len(reported) == 108 and set(reported) == set(groups)

    def coverage(records):
        days = [r['row'] for r in records]
        available = [d for d in days if d['source_status'] == 'COMPLETE']
        missing = [d for d in days if d['source_status'] == 'MISSING_SOURCE']
        failures = [d for d in available if d['trades'] == 0]
        return days, available, missing, failures

    for key, records in groups.items():
        row = reported[key]
        days, available, missing, failures = coverage(records)
        expected = dict(expected_days=len(days), available_days=len(available), missing_days=len(missing),
                        observed_days_without_fill=len(failures), no_fill_dates=[d['date'] for d in failures],
                        missing_dates=[d['date'] for d in missing], observable_daily_pass=bool(available) and not failures,
                        universal_daily_status='NO_EVALUABLE' if missing else ('FAIL' if failures else 'PASS'))
        for name, value in expected.items():
            same(row[name], value, str(key) + name)
        for kind, column in [('base', 'net_base'), ('adverse', 'net_adverse')]:
            values = [a[column] for r in records for a in r['fills']]
            for name, value in economics(values).items():
                same(row[kind][name], value, str(key) + kind + name)
        daily_values = [d['net_base'] for d in sorted(available, key=lambda d: d['date'])]
        balance = high = drawdown = 0.0
        for value in daily_values:
            balance += value
            high = max(high, balance)
            drawdown = max(drawdown, high - balance)
        for name, value in dict(available_daily_close_drawdown_usd=drawdown,
                               best_available_day_usd=max(daily_values) if daily_values else None,
                               worst_available_day_usd=min(daily_values) if daily_values else None,
                               observed_positive_days=sum(v > 0 for v in daily_values)).items():
            same(row[name], value, str(key) + name)
        assert row['drawdown_scope'] == 'AVAILABLE_SESSION_CLOSE_CASH_PNL_NOT_ACCOUNT_RETURN_OR_INTRADAY_DRAWDOWN'

    annual_result = []
    periods = {year: read(consume(ROOT / f'period{year}.json', audit['binding'][f'period{year}_sha256'])) for year in ('2025', '2026')}
    for (policy, ticker, year), records in sorted(annual.items()):
        target = periods[year]['policies'][policy][ticker]
        days, available, missing, failures = coverage(records)
        expected_coverage = dict(expected_days=len(days), available_days=len(available), missing_days=len(missing),
                                 available_days_without_fill=len(failures), observable_daily_pass=bool(available) and not failures,
                                 universal_daily_pass=not missing and not failures,
                                 universal_daily_status='NO_EVALUABLE' if missing else ('FAIL' if failures else 'PASS'),
                                 missing_keys=sorted(d['ticker'] + '/' + d['date'] for d in missing),
                                 unfilled_available_keys=sorted(d['ticker'] + '/' + d['date'] for d in failures))
        for name, value in expected_coverage.items():
            actual = target['coverage'][name]
            same(sorted(actual) if isinstance(actual, list) else actual, value, year + policy + ticker + name)
        out = dict(year=year, policy=policy, ticker=ticker, coverage=expected_coverage)
        for kind, column in [('base', 'net_base'), ('adverse', 'net_adverse')]:
            calc = economics([a[column] for r in records for a in r['fills']])
            out[kind] = calc
            for source, destination in [('trades', 'trades'), ('net_usd', column), ('profit_factor', column + '_profit_factor'),
                                        ('profit_factor_infinite', column + '_pf_infinite'), ('win_rate', column + '_win_rate')]:
                same(target['available_economics'][destination], calc[source], year + policy + ticker + destination)
        annual_result.append(out)
    for path, expected in sources.items():
        assert digest(path) == expected, 'Source changed during review: ' + path
    result = dict(status='PASS_INDEPENDENT_COMMON_GREEK_MONTHLY_REPORT_RECONCILIATION',
                  scope='DESCRIPTIVE_RECONCILIATION_GIVEN_AUDITED_SEALED_ATTEMPTS', reviewer='/root/tcn_completion',
                  finished_at_utc=datetime.now(timezone.utc).isoformat(), resources=resources,
                  audit_sha256=AUDIT_SHA, summary_sha256=SUMMARY_SHA, verifier_sha256=digest(__file__),
                  groups_verified=108, annual_groups_verified=16, daily_policy_records=2238, ledger_parquets=parquet_count,
                  files_rehashed_before_after=len(sources), comparisons=checked, max_absolute_numeric_difference=max_error,
                  reconciliation_tolerance=dict(atol=1e-8, rtol=1e-12), source_hash_mismatches=0,
                  missing_ticker_days=sorted(t + '/' + d for t, d in MISSING), annual=annual_result,
                  scheduler_or_inference_rerun=False, new_fit=False, promotion_approved=False,
                  sources=sources)
    with output.open('x', encoding='utf-8') as stream:
        json.dump(result, stream, indent=2, allow_nan=False)
        stream.write('\n')
    print(json.dumps({k: result[k] for k in ('status', 'groups_verified', 'annual_groups_verified', 'ledger_parquets',
                                           'files_rehashed_before_after', 'comparisons', 'max_absolute_numeric_difference')}), flush=True)


if __name__ == '__main__':
    main()
