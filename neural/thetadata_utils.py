"""
thetadata_utils.py
──────────────────
Módulo compartido por script1, script2 y script3.

NOTA IMPORTANTE — formato de la API v3:
  Todas las respuestas vienen envueltas en {"response": [...]}
  NO devuelven listas directamente. Usar siempre parse_response()
  para extraer el contenido antes de procesarlo.

Funcionalidades:
  - parse_response()        : extrae lista/valor de {"response": ...}
  - get_logger()            : logger con 3 destinos (consola, log completo, errores)
  - RetryAuditLog           : CSV de auditoría de reintentos
  - RequestStats            : métricas de latencia por endpoint
  - timed_get()             : petición HTTP con timing y reintentos
  - fetch_with_interval_fallback() : fallback 1m → 30s → 5m
  - align_greeks_with_underlying() : join correcto por underlying_timestamp
"""

import asyncio
import csv
import logging
import time
from datetime import datetime
from pathlib import Path
from typing import Any

import httpx

# ─────────────────────────────────────────────────────────────────────────────
# CONFIGURACIÓN GLOBAL
# ─────────────────────────────────────────────────────────────────────────────

SLOW_THRESHOLD_SECONDS = 15.0
INTERVAL_FALLBACKS     = ["1m", "30s", "5m"]

# ─────────────────────────────────────────────────────────────────────────────
# PARSER CENTRAL — extrae datos del wrapper {"response": ...}
# ─────────────────────────────────────────────────────────────────────────────

def parse_response(raw: Any) -> Any:
    """
    La API v3 de ThetaData SIEMPRE envuelve las respuestas así:
        {"response": [...]}   o   {"response": {...}}

    Esta función extrae el contenido interior.
    Si ya es una lista (respuesta directa sin wrapper), la devuelve tal cual.
    Si es None o vacío, devuelve lista vacía.

    Uso:
        raw   = resp.json()
        items = parse_response(raw)   # siempre una lista o dict limpio
    """
    if isinstance(raw, list):
        return raw                          # ya es lista directa
    if isinstance(raw, dict):
        return raw.get("response", [])      # extrae de {"response": ...}
    return []


def parse_expiration(item: Any) -> "date | None":
    """
    Parsea un item de /option/list/expirations al tipo date.

    Formatos posibles observados en la API v3:
      - dict:   {"symbol": "SPXW", "expiration": "2026-02-17"}
      - string: "2026-02-17"  o  "20260217"
    """
    from datetime import date as date_type
    try:
        if isinstance(item, dict):
            s = item.get("expiration", "")
        else:
            s = str(item)
        s = s.replace("-", "").strip()
        if len(s) == 8:
            return date_type(int(s[:4]), int(s[4:6]), int(s[6:8]))
    except Exception:
        pass
    return None


# ─────────────────────────────────────────────────────────────────────────────
# LOGGER
# ─────────────────────────────────────────────────────────────────────────────

def get_logger(output_dir: Path, name: str = "thetadata", symbol: str = "") -> logging.Logger:
    output_dir.mkdir(parents=True, exist_ok=True)
    logger = logging.getLogger(name)
    logger.setLevel(logging.DEBUG)

    suffix = f"_{symbol}" if symbol else ""
    fmt = logging.Formatter(
        "%(asctime)s.%(msecs)03d [%(levelname)-8s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    if not logger.handlers:
        ch = logging.StreamHandler()
        ch.setLevel(logging.INFO)
        ch.setFormatter(fmt)
        logger.addHandler(ch)

        fh_all = logging.FileHandler(output_dir / f"descarga{suffix}.log", encoding="utf-8")
        fh_all.setLevel(logging.DEBUG)
        fh_all.setFormatter(fmt)
        logger.addHandler(fh_all)

        fh_err = logging.FileHandler(output_dir / f"errores{suffix}.log", encoding="utf-8")
        fh_err.setLevel(logging.WARNING)
        fh_err.setFormatter(fmt)
        logger.addHandler(fh_err)

    return logger


# ─────────────────────────────────────────────────────────────────────────────
# RETRY AUDIT LOG
# ─────────────────────────────────────────────────────────────────────────────

class RetryAuditLog:
    def __init__(self, output_dir: Path, suffix: str = ""):
        self.path = output_dir / f"retry_audit{suffix}.csv"
        self._lock = asyncio.Lock()
        if not self.path.exists():
            with open(self.path, "w", newline="", encoding="utf-8") as f:
                csv.writer(f).writerow([
                    "timestamp", "url", "params_summary",
                    "attempt", "error_type", "error_msg", "elapsed_s"
                ])

    async def record(self, url, params, attempt, error, elapsed):
        row = [
            datetime.utcnow().isoformat(timespec="milliseconds"),
            url, _short_params(params), attempt,
            type(error).__name__, str(error)[:200], f"{elapsed:.3f}",
        ]
        async with self._lock:
            with open(self.path, "a", newline="", encoding="utf-8") as f:
                csv.writer(f).writerow(row)


def _short_params(params: dict) -> str:
    keep = ["symbol", "expiration", "date", "interval", "strike", "right", "year"]
    return " ".join(f"{k}={params[k]}" for k in keep if k in params)


# ─────────────────────────────────────────────────────────────────────────────
# REQUEST STATS
# ─────────────────────────────────────────────────────────────────────────────

class RequestStats:
    def __init__(self):
        self._data: dict[str, dict[str, Any]] = {}

    def record(self, key: str, elapsed: float, success: bool, slow: bool):
        if key not in self._data:
            self._data[key] = {"ok": 0, "err": 0, "slow": 0, "times": []}
        e = self._data[key]
        e["times"].append(elapsed)
        if success: e["ok"]   += 1
        else:       e["err"]  += 1
        if slow:    e["slow"] += 1

    def summary(self) -> str:
        hdr = f"{'KEY':<40} {'OK':>5} {'ERR':>5} {'SLOW':>5} {'AVG_s':>7} {'MAX_s':>7}"
        lines = [hdr]
        for key, d in sorted(self._data.items()):
            t = d["times"]
            avg = sum(t) / len(t) if t else 0
            lines.append(
                f"{key:<40} {d['ok']:>5} {d['err']:>5} {d['slow']:>5} "
                f"{avg:>7.2f} {max(t, default=0):>7.2f}"
            )
        return "\n".join(lines)

    def save_csv(self, output_dir: Path, suffix: str = ""):
        path = output_dir / f"request_stats{suffix}.csv"
        with open(path, "w", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            w.writerow(["key", "ok", "err", "slow", "avg_s", "max_s", "min_s", "n"])
            for key, d in sorted(self._data.items()):
                t = d["times"]
                n = len(t)
                avg = sum(t) / n if n else 0
                w.writerow([key, d["ok"], d["err"], d["slow"],
                            f"{avg:.3f}", f"{max(t,default=0):.3f}",
                            f"{min(t,default=0):.3f}", n])


# ─────────────────────────────────────────────────────────────────────────────
# HTTP CON TIMING Y REINTENTOS
# ─────────────────────────────────────────────────────────────────────────────

async def timed_get(
    client: httpx.AsyncClient,
    url: str,
    params: dict,
    logger: logging.Logger,
    audit: RetryAuditLog,
    stats: RequestStats,
    stat_key: str,
    timeout: float = 200.0,
    max_attempts: int = 5,
) -> "httpx.Response | None":
    attempt = 0
    last_exc = None

    while attempt < max_attempts:
        attempt += 1
        t0 = time.monotonic()
        try:
            resp = await client.get(url, params=params, timeout=timeout)
            elapsed = time.monotonic() - t0
            slow = elapsed > SLOW_THRESHOLD_SECONDS

            logger.log(
                logging.WARNING if slow else logging.DEBUG,
                f"{'🐢 LENTA' if slow else 'GET'} [intento {attempt}] "
                f"{_short_params(params)} → HTTP {resp.status_code} en {elapsed:.2f}s",
            )
            stats.record(stat_key, elapsed, success=(resp.status_code < 400), slow=slow)
            if slow:
                await audit.record(url, params, attempt,
                                   Exception(f"Lenta ({elapsed:.1f}s)"), elapsed)
            return resp

        except (httpx.TimeoutException, httpx.NetworkError, httpx.ConnectError) as exc:
            elapsed = time.monotonic() - t0
            last_exc = exc
            wait = min(2 ** attempt, 30)
            logger.warning(
                f"⚠ Reintento {attempt}/{max_attempts} {_short_params(params)} "
                f"— {type(exc).__name__} — esperando {wait}s"
            )
            await audit.record(url, params, attempt, exc, elapsed)
            stats.record(stat_key, elapsed, success=False,
                         slow=elapsed > SLOW_THRESHOLD_SECONDS)
            await asyncio.sleep(wait)

    logger.error(f"✗ Todos los intentos fallaron {_short_params(params)}: {last_exc}")
    return None


# ─────────────────────────────────────────────────────────────────────────────
# FALLBACK DE INTERVALO
# ─────────────────────────────────────────────────────────────────────────────

async def fetch_with_interval_fallback(
    client: httpx.AsyncClient,
    url: str,
    base_params: dict,
    logger: logging.Logger,
    audit: RetryAuditLog,
    stats: RequestStats,
    stat_key: str,
    intervals: list = None,
    timeout: float = 200.0,
) -> "tuple[httpx.Response | None, str | None]":
    """
    Intenta la petición con cada intervalo de INTERVAL_FALLBACKS.
    Usa parse_response() para detectar si la respuesta tiene datos reales.
    Devuelve (response, intervalo_usado) o (None, None).
    """
    if intervals is None:
        intervals = INTERVAL_FALLBACKS

    # Endpoints sin intervalo (calendar, expirations, open_interest)
    needs_interval = "interval" in base_params or all(
        k not in stat_key for k in ("calendar", "expirations", "oi")
    )

    if not needs_interval or "oi" in stat_key:
        resp = await timed_get(client, url, base_params, logger, audit, stats,
                               stat_key, timeout)
        return resp, None

    for interval in intervals:
        params = {**base_params, "interval": interval}
        resp = await timed_get(client, url, params, logger, audit, stats,
                               stat_key, timeout)

        if resp is None:
            logger.warning(f"Intervalo {interval} → sin respuesta. Siguiente…")
            continue
        if resp.status_code == 404:
            return resp, interval
        if resp.status_code >= 400:
            logger.warning(f"Intervalo {interval} → HTTP {resp.status_code}. Siguiente…")
            continue

        try:
            items = parse_response(resp.json())
        except Exception:
            logger.warning(f"Intervalo {interval} → respuesta no parseable. Siguiente…")
            continue

        if not isinstance(items, list) or len(items) == 0:
            logger.debug(f"Intervalo {interval} → sin datos.")
            return resp, interval  # vacío es definitivo para este día

        logger.info(f"✓ Intervalo {interval} OK ({len(items)} items)")
        return resp, interval

    logger.error(f"✗ Todos los intervalos fallaron para {_short_params(base_params)}")
    return None, None


# ─────────────────────────────────────────────────────────────────────────────
# FEATURE ALIGNMENT: Greeks ↔ Underlying
# ─────────────────────────────────────────────────────────────────────────────

def align_greeks_with_underlying(greeks_df, underlying_df, tolerance_seconds: int = 60):
    """
    Join Greeks con subyacente usando underlying_timestamp como clave.
    Ver README sección 13 para la explicación completa.
    """
    import pandas as pd
    import warnings

    if "underlying_timestamp" not in greeks_df.columns:
        raise ValueError("'underlying_timestamp' no encontrado en greeks_df.")
    if "timestamp" not in underlying_df.columns:
        raise ValueError("'timestamp' no encontrado en underlying_df.")

    greeks = greeks_df.copy()
    und    = underlying_df.copy()

    greeks["_uts"] = pd.to_datetime(greeks["underlying_timestamp"], utc=False)
    und["_uts"]    = pd.to_datetime(und["timestamp"],               utc=False)
    greeks = greeks.sort_values("_uts").reset_index(drop=True)
    und    = und.sort_values("_uts").reset_index(drop=True)

    rename_map = {"timestamp": "und_timestamp", "open": "und_open",
                  "high": "und_high", "low": "und_low",
                  "close": "und_close", "volume": "und_volume"}
    und_slim = und.rename(columns={k: v for k, v in rename_map.items() if k in und.columns})
    keep = [v for v in rename_map.values() if v in und_slim.columns] + ["_uts"]
    und_slim = und_slim[[c for c in keep if c in und_slim.columns]]

    merged = pd.merge_asof(
        greeks, und_slim, on="_uts", direction="backward",
        tolerance=pd.Timedelta(seconds=tolerance_seconds) if tolerance_seconds > 0 else None,
    )

    if "und_timestamp" in merged.columns:
        merged["und_lag_seconds"] = (
            merged["_uts"] - pd.to_datetime(merged["und_timestamp"], utc=False)
        ).dt.total_seconds()
    else:
        merged["und_lag_seconds"] = float("nan")

    merged = merged.drop(columns=["_uts"])

    unmatched = merged["und_lag_seconds"].isna().sum()
    if unmatched > 0:
        warnings.warn(
            f"align_greeks_with_underlying: {unmatched}/{len(merged)} filas sin match "
            f"(tolerance={tolerance_seconds}s). Sus columnas und_* serán NaN.",
            stacklevel=2,
        )
    return merged