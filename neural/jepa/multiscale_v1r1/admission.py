"""Explicit positive admission for synthetic sources, never a historical bypass."""
import pandas as pd

from .contract import ContractError


def inspect_lineage(record, feature_endpoint):
    required = {'source_id', 'input_hashes', 'transformation_sha256', 'parameters',
                'event_timestamp', 'available_at', 'received_at', 'materialized_at',
                'repair', 'evidence', 'environment'}
    if not required <= set(record):
        raise ContractError('ADMISSION: incomplete lineage record')
    if record['environment'] != 'SYNTHETIC_FIXTURE':
        raise ContractError('ADMISSION: positive historical admission is not granted by synthetic API')
    if not record['input_hashes'] or not record['transformation_sha256'] or not record['evidence']:
        return 'UNVERIFIABLE_FOR_CAUSAL_REPLAY'
    if record['available_at'] is None:
        return 'UNVERIFIABLE_FOR_CAUSAL_REPLAY'
    available = pd.Timestamp(record['available_at'])
    event = pd.Timestamp(record['event_timestamp'])
    endpoint = pd.Timestamp(feature_endpoint)
    if any(t.tzinfo is None for t in (available, event, endpoint)):
        raise ContractError('ADMISSION: explicit timezone required')
    if available < event or available > endpoint:
        return 'REJECTED_CAUSALITY'
    if record['repair'] is not None:
        repair = record['repair']
        if not repair.get('dependency_available_at') or not repair.get('evidence'):
            return 'UNVERIFIABLE_FOR_CAUSAL_REPLAY'
        if pd.Timestamp(repair['dependency_available_at']) > available:
            return 'REJECTED_CAUSALITY'
    # Materialization/download is deliberately not the historical market clock.
    return 'PROVENANCE_SUPPORTED'
