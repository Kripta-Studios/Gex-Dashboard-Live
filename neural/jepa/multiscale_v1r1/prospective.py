"""Offline append-only reception recorder. No sockets, credentials or broker API."""
import json
from pathlib import Path

import pandas as pd

from .artifacts import append_access, content_digest
from .contract import ContractError


def record_reception(path, event):
    required = {'event_id', 'market_timestamp', 'received_at', 'feature_started_at',
                'feature_completed_at', 'decision_at', 'intent_at', 'quote_age_ms',
                'processing_latency_ms', 'policy_sha256', 'feature_sha256', 'decision_reason'}
    if not required <= set(event) or event.get('broker_submission', False) is not False:
        raise ContractError('SHADOW-001: invalid offline record')
    clocks = [pd.Timestamp(event[k]) for k in ('market_timestamp', 'received_at', 'feature_started_at',
                                             'feature_completed_at', 'decision_at', 'intent_at')]
    if any(t.tzinfo is None for t in clocks) or clocks != sorted(clocks):
        raise ContractError('SHADOW-001: invalid receipt/processing chronology')
    if (event['quote_age_ms'] != (clocks[4] - clocks[0]).total_seconds() * 1000 or
            event['processing_latency_ms'] != (clocks[3] - clocks[2]).total_seconds() * 1000):
        raise ContractError('SHADOW-001: inconsistent latency')
    path = Path(path)
    prior = []
    if path.exists():
        prior = [json.loads(line) for line in path.read_text(encoding='utf-8').splitlines()]
    revisions = [r for r in prior if r['event_id'] == event['event_id']]
    record = dict(event, revision=len(revisions), supersedes_sha256=revisions[-1]['record_sha256'] if revisions else None,
                  broker_submission=False, capture_mode='OFFLINE_FIXTURE', prospective_validation_state='NOT_STARTED')
    append_access(path, **record)
    return content_digest(record)
