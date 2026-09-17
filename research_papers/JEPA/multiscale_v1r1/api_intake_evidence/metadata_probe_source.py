"""Ten predeclared read-only metadata GETs. Never calls a price/history endpoint."""
import csv
import hashlib
import io
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, build_opener, HTTPRedirectHandler

ROOT = Path('D:/GexResearchArtifacts/multiscale_v1r1/theta_metadata_20260918_01')
BASE = 'http://91.99.90.39:25503/v3'
SPEC = Path('research_papers/JEPA/multiscale_v1r1/18_THETADATA_API_REVIEW.md')


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def run():
    ROOT.mkdir(parents=True, exist_ok=False)
    shutil.copyfile(__file__, ROOT / 'probe_source.py')
    requests = [('/terminal/mdds/status', {})]
    requests += [('/option/list/expirations', {'symbol': t, 'format': 'csv'}) for t in ('SPXW', 'SPY', 'QQQ')]
    requests += [('/option/list/dates/quote', {'symbol': t, 'expiration': d, 'format': 'csv'})
                 for t in ('SPY', 'QQQ') for d in ('20260401', '20260409', '20260415')]
    opener = build_opener(NoRedirect)
    report = dict(specification_sha256=hashlib.sha256(SPEC.read_bytes()).hexdigest(), requests=[],
                  source_values_opened=False, historical_economics='NOT_EVALUATED', promotion_approved=False)
    for i, (endpoint, params) in enumerate(requests):
        url = BASE + endpoint + ('?' + urlencode(params) if params else '')
        record = dict(endpoint=endpoint, params=params, url=url, started_at=datetime.now(timezone.utc).isoformat())
        try:
            try:
                response = opener.open(Request(url, method='GET'), timeout=20)
            except HTTPError as exc:
                response = exc
            with response:
                body = response.read(4 * 1024**2 + 1)
                record['http_status'] = response.status
                record['headers'] = {k: response.headers.get(k) for k in ('Content-Type', 'Date', 'Content-Length')}
            path = ROOT / f'{i:02d}_response.bin'
            path.write_bytes(body)
            record.update(received_at=datetime.now(timezone.utc).isoformat(), body_path=path.name,
                          body_size=len(body), body_sha256=hashlib.sha256(body).hexdigest(),
                          complete=len(body) <= 4 * 1024**2)
            if i == 0:
                status = body.decode('utf-8', errors='replace').strip().strip('"')
                record['connection_status'] = status if status in ('CONNECTED', 'DISCONNECTED', 'UNVERIFIED', 'ERROR') else 'UNRECOGNIZED'
            elif record['http_status'] == 200 and record['complete']:
                rows = list(csv.DictReader(io.StringIO(body.decode('utf-8-sig'))))
                field = 'expiration' if endpoint.endswith('expirations') else 'date'
                if rows and field not in rows[0]:
                    record['schema_status'] = 'UNRECOGNIZED'
                else:
                    record['schema_status'] = 'METADATA_ONLY'
                    dates = sorted({r[field].replace('-', '')[:8] for r in rows})
                    record['date_count'] = len(dates)
                    record['evaluation_period_dates'] = [d for d in dates if '20220801' <= d <= '20260630']
            print(json.dumps({k: record[k] for k in ('endpoint', 'http_status', 'connection_status', 'date_count') if k in record}), flush=True)
        except (URLError, TimeoutError, OSError, UnicodeError, csv.Error) as error:
            record.update(error_type=type(error).__name__, completed=False)
            print('metadata request failed: ' + type(error).__name__, flush=True)
        report['requests'].append(record)
        (ROOT / f'{i:02d}_request.json').write_text(json.dumps(record, indent=2), encoding='utf-8')
        if i == 0 and record.get('connection_status') != 'CONNECTED':
            break
    report['status'] = 'METADATA_PROBE_COMPLETED' if len(report['requests']) == 10 else 'BLOCKED_TERMINAL'
    (ROOT / 'summary.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
    print(report['status'], flush=True)


if __name__ == '__main__':
    run()
