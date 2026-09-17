"""Independent full-tensor checks at all 18 contractual decision clocks."""
import json
import tempfile
from pathlib import Path

import numpy as np
import pandas as pd

from neural.jepa.multiscale_v1r1.contract import DECISIONS
from neural.jepa.multiscale_v1r1.interactions import build_event
from neural.jepa.multiscale_v1r1.synthetic_fixtures import source_fixture
from neural.jepa.multiscale_v1r1_audit.tensor import audit_tensor_fixture
from neural.jepa.multiscale_v1r1.artifacts import write_json

results = []
frame, greek, oi, prior = source_fixture()
with tempfile.TemporaryDirectory(prefix='gex_all_clocks_') as temporary:
    root = Path(temporary)
    frame.to_parquet(root / 'bars.parquet', index=False)
    greek.to_parquet(root / 'greeks.parquet', index=False)
    oi.to_parquet(root / 'oi.parquet', index=False)
    for day, source in prior.items():
        source.to_parquet(root / f'ib_{day}.parquet')
    for clock in DECISIONS:
        decision = pd.Timestamp('2025-01-10 ' + clock, tz='America/New_York')
        event = build_event(frame, prior, greek, oi, 'SPXW', '2025-01-10', decision, 99.8)
        for name in ('x5', 'm5', 'x15', 'm15', 'static'):
            np.save(root / f'{name}.npy', event[name])
        (root / 'identity.json').write_text(json.dumps(dict(day='2025-01-10', ticker='SPXW', decision=decision.isoformat(), prior_close=99.8)))
        audit = audit_tensor_fixture(root)
        results.append(dict(clock=clock, **audit))
        print('clock', clock, audit['status'], flush=True)
write_json(Path('D:/GexResearchArtifacts/multiscale_v1r1/continuation_20260917_01/all_clock_audit.json'),
           dict(status='PASS_ALL_18_SYNTHETIC_CLOCKS', results=results, synthetic_only=True, historical_economics='NOT_EVALUATED'))
