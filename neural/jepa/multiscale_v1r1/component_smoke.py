"""Full-width real LightGBM A/B smoke on artificial data, with measured resources."""
import gc
import json
import threading
import time
from pathlib import Path

import numpy as np
import psutil

from .artifacts import digest, write_json
from .contract import PRIMARY_DIM, PROCESS_LIMIT, SEED, TICKERS, ContractError
from .models import fit_action, parameters


def run(destination):
    from lightgbm import Booster
    root = Path(destination)
    root.mkdir(parents=True, exist_ok=False)
    process = psutil.Process()
    stats = {'peak_rss_bytes': process.memory_info().rss}
    stop = threading.Event()

    def sample():
        while not stop.wait(.05):
            stats['peak_rss_bytes'] = max(stats['peak_rss_bytes'], process.memory_info().rss)

    monitor = threading.Thread(target=sample, daemon=True)
    monitor.start()
    try:
        total_start = time.perf_counter()
        build_start = time.perf_counter()
        x = np.lib.format.open_memmap(root / 'synthetic_full_width.npy', mode='w+', dtype='float32', shape=(600, PRIMARY_DIM))
        # Dense representation and production width; low-entropy fixture deliberately
        # differs from historical data. This does not estimate the full historical fit.
        x[:] = 0
        signal = np.tile([-1., 1.], 300)
        rng = np.random.default_rng(SEED)
        x[:, :32] = signal[:, None]
        x[:, 32:48] = rng.normal(size=(600, 16)).astype('float32')
        x.flush()
        y = signal * 50 + np.tile([0., .2, -.2], 200)
        tickers = np.tile(TICKERS, 200)
        construction = time.perf_counter() - build_start
        results = []
        for config in ('A', 'B'):
            if process.memory_info().rss + 600 * PRIMARY_DIM * 8 > PROCESS_LIMIT:
                raise ContractError('BLOCKED_RESOURCE: insufficient process budget before fit')
            clock = time.perf_counter()
            model = fit_action(x, y, tickers, config)
            fit_seconds = time.perf_counter() - clock
            clock = time.perf_counter()
            prediction = model.predict(x)
            predict_seconds = time.perf_counter() - clock
            clock = time.perf_counter()
            path = root / f'model_{config}.txt'
            model.booster_.save_model(str(path))
            save_seconds = time.perf_counter() - clock
            clock = time.perf_counter()
            restored = Booster(model_file=str(path))
            restored_prediction = restored.predict(x, num_threads=1)
            load_predict_seconds = time.perf_counter() - clock
            if not np.array_equal(prediction, restored_prediction):
                raise ContractError('MODEL-001: save/load prediction mismatch')
            agreement = float(np.mean(np.sign(prediction) == np.sign(y)))
            if agreement != 1.:
                raise ContractError('SYNTHETIC: real component failed designed signal')
            np.save(root / f'prediction_{config}.npy', prediction)
            results.append(dict(config=config, parameters=parameters(config), fit_seconds=fit_seconds,
                                predict_seconds=predict_seconds, save_seconds=save_seconds,
                                load_predict_seconds=load_predict_seconds, sign_agreement=agreement,
                                model_sha256=digest(path), prediction_sha256=digest(root / f'prediction_{config}.npy')))
            del restored, model, prediction, restored_prediction
            gc.collect()
        result = dict(status='PASS_REAL_COMPONENT_SYNTHETIC_SMOKE', rows=600, columns=PRIMARY_DIM,
                      configs=results, construction_seconds=construction, elapsed_seconds=time.perf_counter() - total_start,
                      peak_rss_bytes=stats['peak_rss_bytes'], process_limit_bytes=PROCESS_LIMIT,
                      limitations='Two real regressors, artificial low-entropy features. Not 18x24 full historical fits or complete runtime estimate.',
                      historical_economics='NOT_EVALUATED', promotion_approved=False)
        write_json(root / 'summary.json', result)
        print(json.dumps(result), flush=True)
        return result
    finally:
        stop.set()
        monitor.join()
