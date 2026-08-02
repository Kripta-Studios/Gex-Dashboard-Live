import base64
from dataclasses import dataclass
from datetime import UTC, datetime
import hashlib
import hmac
import json
import logging
import os
from pathlib import Path
import glob
import http.server
import re
import socketserver
import threading
import time
import urllib.parse
import uuid
from qiskit import QuantumCircuit
from qiskit_aer import AerSimulator
# --- CONFIGURATION ---
PORT = int(os.environ.get("FINANCIAL_SERVER_PORT", "8609"))
SERVER_BIND = os.environ.get("FINANCIAL_SERVER_BIND", "127.0.0.1")
IP = "91.99.90.39"
# Get the project root directory (parent of services/)
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(SCRIPT_DIR)

DATA_FOLDER = os.path.join(PROJECT_ROOT, "json_data")
TEMPLATE_FOLDER = os.path.join(PROJECT_ROOT, "web", "templates")
DOCS_PDF_FOLDER = os.path.join(PROJECT_ROOT, "docs", "pdfs")
VIS_FOLDER = os.path.join(PROJECT_ROOT, "visualizar")
KING_NODE_SNAPSHOT = os.environ.get(
    "KING_NODE_SNAPSHOT",
    os.path.join(PROJECT_ROOT, "runtime", "king_node", "latest.json"),
)
KING_NODE_LIVE_SNAPSHOT = os.environ.get("KING_NODE_LIVE_SNAPSHOT", KING_NODE_SNAPSHOT)
KING_NODE_LAST_COMPLETED_SNAPSHOT = os.environ.get(
    "KING_NODE_LAST_COMPLETED_SNAPSHOT",
    os.path.join(os.path.dirname(KING_NODE_SNAPSHOT), "last_completed.json"),
)
KING_NODE_HEALTH_STATE = os.environ.get(
    "KING_NODE_HEALTH_STATE",
    os.path.join(os.path.dirname(KING_NODE_SNAPSHOT), "health.json"),
)
KING_NODE_MAX_AGE_SECONDS = int(
    os.environ.get("KING_NODE_WEB_MAX_AGE_SECONDS", "900")
)
KING_NODE_V2_SCHEMA = "king-node.v2"
KING_NODE_FRONTEND_SCHEMA = os.environ.get("KING_NODE_FRONTEND_SCHEMA", KING_NODE_V2_SCHEMA)

os.makedirs(DOCS_PDF_FOLDER, exist_ok=True)
os.makedirs(VIS_FOLDER, exist_ok=True)

# Cambio solicitado: nombre del archivo de logs
LOG_FILE = os.path.join(PROJECT_ROOT, "servidor_logs.txt")
MOVIE_DIRECTORY = "/home/kripta/Movies"
MOVIE_FILENAME = "oppenheimer.mp4"

# MEMORIA RAM GLOBAL
LATEST_DATA_CACHE = {}
CACHE_LOCK = threading.Lock()
QUANTUM_SIMULATOR = AerSimulator()

AUTH_SCHEMA_VERSION = "dashboard-auth.v1"
DASHBOARD_AUTH_FILE = Path(
    os.environ.get("DASHBOARD_AUTH_FILE", "/etc/kripta/dashboard-auth.json")
)
DASHBOARD_AUTH_REQUIRED = os.environ.get("DASHBOARD_AUTH_REQUIRED", "0") == "1"


class DashboardAuthError(ValueError):
    """A configuration error intentionally safe for API callers."""


@dataclass(frozen=True)
class PasswordRecord:
    email: str
    role: str
    salt: bytes
    digest: bytes
    iterations: int


@dataclass(frozen=True)
class ApiKeyRecord:
    key_id: str
    role: str
    owner: str
    salt: bytes
    digest: bytes
    iterations: int


def _decode_b64(value: object, field: str) -> bytes:
    if not isinstance(value, str) or not value:
        raise DashboardAuthError(f"invalid auth {field}")
    try:
        decoded = base64.b64decode(value.encode("ascii"), validate=True)
    except (ValueError, UnicodeEncodeError) as exc:
        raise DashboardAuthError(f"invalid auth {field}") from exc
    if not decoded:
        raise DashboardAuthError(f"invalid auth {field}")
    return decoded


def _parse_hash_record(raw: object) -> tuple[bytes, bytes, int]:
    if not isinstance(raw, dict) or raw.get("algorithm") != "pbkdf2_sha256":
        raise DashboardAuthError("unsupported auth hash")
    iterations = raw.get("iterations")
    if not isinstance(iterations, int) or not 100_000 <= iterations <= 2_000_000:
        raise DashboardAuthError("invalid auth iterations")
    return (
        _decode_b64(raw.get("salt"), "salt"),
        _decode_b64(raw.get("digest"), "digest"),
        iterations,
    )


def _verify_secret(secret: str, *, salt: bytes, digest: bytes, iterations: int) -> bool:
    if not isinstance(secret, str) or not secret:
        return False
    candidate = hashlib.pbkdf2_hmac(
        "sha256", secret.encode("utf-8"), salt, iterations
    )
    return hmac.compare_digest(candidate, digest)


class DashboardAuthStore:
    """Root-owned credential artifact reader; no credential is retained in source."""

    def __init__(
        self,
        users: dict[str, PasswordRecord] | None = None,
        api_keys: tuple[ApiKeyRecord, ...] = (),
    ) -> None:
        self._users = users or {}
        self._api_keys = api_keys

    @classmethod
    def from_file(cls, path: Path, *, required: bool) -> "DashboardAuthStore":
        if not path.is_file():
            if required:
                raise DashboardAuthError("dashboard auth artifact is required")
            return cls()
        try:
            mode = path.stat().st_mode & 0o777
            if mode & 0o077:
                raise DashboardAuthError("dashboard auth artifact permissions are unsafe")
            raw = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError) as exc:
            raise DashboardAuthError("dashboard auth artifact is unreadable") from exc
        if not isinstance(raw, dict) or raw.get("schema_version") != AUTH_SCHEMA_VERSION:
            raise DashboardAuthError("dashboard auth schema is invalid")
        users: dict[str, PasswordRecord] = {}
        for item in raw.get("users", []):
            if not isinstance(item, dict):
                raise DashboardAuthError("dashboard user record is invalid")
            email, role = item.get("email"), item.get("role")
            if not isinstance(email, str) or not isinstance(role, str) or role not in {"ADMIN", "USER"}:
                raise DashboardAuthError("dashboard user record is invalid")
            salt, digest, iterations = _parse_hash_record(item.get("password_hash"))
            if email in users:
                raise DashboardAuthError("duplicate dashboard user")
            users[email] = PasswordRecord(email, role, salt, digest, iterations)
        keys: list[ApiKeyRecord] = []
        seen_ids: set[str] = set()
        for item in raw.get("api_keys", []):
            if not isinstance(item, dict):
                raise DashboardAuthError("dashboard api key record is invalid")
            key_id, role, owner = item.get("id"), item.get("role"), item.get("owner")
            if (
                not isinstance(key_id, str)
                or not isinstance(role, str)
                or not isinstance(owner, str)
                or key_id in seen_ids
            ):
                raise DashboardAuthError("dashboard api key record is invalid")
            seen_ids.add(key_id)
            salt, digest, iterations = _parse_hash_record(item.get("key_hash"))
            keys.append(ApiKeyRecord(key_id, role, owner, salt, digest, iterations))
        if required and not users:
            raise DashboardAuthError("dashboard auth artifact has no users")
        return cls(users, tuple(keys))

    @property
    def configured(self) -> bool:
        return bool(self._users)

    def verify_password(self, email: object, password: object) -> dict[str, str] | None:
        if not isinstance(email, str) or not isinstance(password, str):
            return None
        record = self._users.get(email)
        if record is None or not _verify_secret(
            password,
            salt=record.salt,
            digest=record.digest,
            iterations=record.iterations,
        ):
            return None
        return {"email": record.email, "role": record.role}

    def verify_api_key(self, key: object) -> dict[str, str] | None:
        if not isinstance(key, str) or not key:
            return None
        for record in self._api_keys:
            if _verify_secret(
                key,
                salt=record.salt,
                digest=record.digest,
                iterations=record.iterations,
            ):
                return {"email": f"apikey:{record.owner}", "role": record.role, "_api_key": record.key_id}
        return None


try:
    AUTH_STORE = DashboardAuthStore.from_file(
        DASHBOARD_AUTH_FILE, required=DASHBOARD_AUTH_REQUIRED
    )
except DashboardAuthError:
    # Startup enforces this in production.  Importing without a secret artifact is
    # intentionally possible for fixture-only tests and non-serving tooling.
    if DASHBOARD_AUTH_REQUIRED:
        raise
    AUTH_STORE = DashboardAuthStore()

SESSIONS: dict[str, dict[str, str]] = {}
EMAIL_TO_TOKEN: dict[str, str] = {}
API_KEY_LOCKS: dict[str, threading.Lock] = {}

# Configure Logging
logging.basicConfig(
    filename=LOG_FILE,
    level=logging.INFO,
    format="%(asctime)s | %(message)s",  # La fecha y hora se ponen automáticas aquí
    datefmt="%Y-%m-%d %H:%M:%S",
)


class ThreadedReusableServer(socketserver.ThreadingMixIn, socketserver.TCPServer):
    allow_reuse_address = True
    daemon_threads = True


class KingNodeSnapshotError(ValueError):
    def __init__(self, code: str, *, retryable: bool) -> None:
        self.code = code
        self.retryable = retryable
        super().__init__(code)


_UNSAFE_RESPONSE_KEYS = {
    "path",
    "snapshot_path",
    "source_path",
    "exception",
    "traceback",
    "stack",
}
_UNSAFE_PATH_MARKERS = ("file://", "/home/", "/etc/", "/var/", "\\\\")


def _parse_utc_timestamp(value: object) -> datetime | None:
    if not isinstance(value, str) or not value.strip():
        return None
    text = value.strip()
    if text.endswith("Z"):
        text = f"{text[:-1]}+00:00"
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return None
    return parsed.astimezone(UTC)


def _public_value(value):
    """Defence in depth: snapshots must not reveal host paths or exceptions."""
    if isinstance(value, dict):
        return {
            str(key): _public_value(item)
            for key, item in value.items()
            if str(key).lower() not in _UNSAFE_RESPONSE_KEYS
        }
    if isinstance(value, list):
        return [_public_value(item) for item in value]
    if isinstance(value, str) and any(marker in value.lower() for marker in _UNSAFE_PATH_MARKERS):
        return "[redacted]"
    return value


def _safe_king_node_error(code: str, *, component: str, retryable: bool) -> dict:
    return {
        "schema_version": KING_NODE_V2_SCHEMA,
        "status": "unavailable",
        "error": {
            "code": code,
            "component": component,
            "retryable": retryable,
        },
    }


class ExposureDataHandler(http.server.SimpleHTTPRequestHandler):

    # --- AUTH MIDDLEWARE ---
    def _check_auth(self):
        """Verify a session token or a hashed API key without logging either."""
        auth = self.headers.get("Authorization", "")
        if auth.startswith("Bearer "):
            token = auth[7:]
            with CACHE_LOCK:
                session = SESSIONS.get(token)
            return dict(session) if session else None

        api_key = self.headers.get("X-API-Key", "")
        record = AUTH_STORE.verify_api_key(api_key)
        if record:
            key_id = record["_api_key"]
            with CACHE_LOCK:
                lock = API_KEY_LOCKS.setdefault(key_id, threading.Lock())
            if lock and not lock.acquire(blocking=False):
                return "RATE_LIMITED"
            return record

        return None

    def _release_api_key(self, auth_info):
        """Release API key lock after response is sent."""
        if auth_info and isinstance(auth_info, dict) and "_api_key" in auth_info:
            lock = API_KEY_LOCKS.get(auth_info["_api_key"])
            if lock:
                try:
                    lock.release()
                except RuntimeError:
                    pass  # Already released

    def _send_json(self, code, data):
        """Helper to send JSON response."""
        body = json.dumps(data, allow_nan=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-type", "application/json")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    @staticmethod
    def _read_snapshot_file(path: str) -> dict:
        """Read one private artifact without returning its location to callers."""
        try:
            candidate = Path(path)
            if not candidate.is_file():
                raise KingNodeSnapshotError("SNAPSHOT_UNAVAILABLE", retryable=True)
            if candidate.stat().st_size > 5 * 1024 * 1024:
                raise KingNodeSnapshotError("SNAPSHOT_INVALID", retryable=False)
            with candidate.open("r", encoding="utf-8") as handle:
                payload = json.load(handle)
        except KingNodeSnapshotError:
            raise
        except (OSError, UnicodeError, json.JSONDecodeError) as exc:
            raise KingNodeSnapshotError("SNAPSHOT_INVALID", retryable=True) from exc
        if not isinstance(payload, dict):
            raise KingNodeSnapshotError("SNAPSHOT_INVALID", retryable=False)
        return payload

    def _read_king_node_snapshot(self, session: str = "live"):
        """Read a v2 artifact and fail closed on stale/invalid delivery.

        The legacy v1 branch remains only for the old direct helper contract.  It
        is never eligible for the v2 HTTP route, which requires an explicit v2
        status/freshness/quality contract.
        """
        if session not in {"live", "last_completed"}:
            raise KingNodeSnapshotError("INVALID_SESSION", retryable=False)
        path = (
            KING_NODE_LIVE_SNAPSHOT
            if session == "live"
            else KING_NODE_LAST_COMPLETED_SNAPSHOT
        )
        payload = self._read_snapshot_file(path)
        if payload.get("schema_version") == "king-node.v1":
            if session != "live":
                raise KingNodeSnapshotError("SNAPSHOT_SCHEMA_UNSUPPORTED", retryable=False)
            # Compatibility only for legacy server tests / direct consumers.  No
            # local path is included in the returned delivery metadata.
            generated = _parse_utc_timestamp(payload.get("generated_at"))
            age_seconds = (
                max(0.0, (datetime.now(UTC) - generated).total_seconds())
                if generated is not None
                else None
            )
            response = _public_value(dict(payload))
            response["delivery"] = {
                "age_seconds": age_seconds,
                "max_age_seconds": KING_NODE_MAX_AGE_SECONDS,
                "stale": age_seconds is None or age_seconds > KING_NODE_MAX_AGE_SECONDS,
            }
            return response
        if payload.get("schema_version") != KING_NODE_V2_SCHEMA:
            raise KingNodeSnapshotError("SNAPSHOT_SCHEMA_UNSUPPORTED", retryable=False)
        expected_status = "live" if session == "live" else "last_completed_session"
        if payload.get("status") != expected_status:
            raise KingNodeSnapshotError("SNAPSHOT_STATUS_INVALID", retryable=True)
        freshness = payload.get("freshness")
        quality = payload.get("quality")
        generated = _parse_utc_timestamp(payload.get("generated_at"))
        if not isinstance(freshness, dict) or not isinstance(quality, dict) or generated is None:
            raise KingNodeSnapshotError("SNAPSHOT_INVALID", retryable=False)
        max_age = freshness.get("max_age_seconds", KING_NODE_MAX_AGE_SECONDS)
        if not isinstance(max_age, (int, float)) or max_age <= 0:
            raise KingNodeSnapshotError("SNAPSHOT_INVALID", retryable=False)
        age_seconds = max(0.0, (datetime.now(UTC) - generated).total_seconds())
        invalid_quality = quality.get("valid") is not True or bool(quality.get("errors"))
        stale_live = (
            session == "live"
            and (freshness.get("stale") is True or age_seconds > float(max_age))
        )
        invalid_completed = (
            session == "last_completed"
            and freshness.get("kind") != "sealed_completed_session"
        )
        if invalid_quality or stale_live or invalid_completed:
            raise KingNodeSnapshotError("SNAPSHOT_STALE_OR_INVALID", retryable=True)
        response = _public_value(dict(payload))
        response["delivery"] = {
            "age_seconds": age_seconds,
            "max_age_seconds": float(max_age),
            "stale": False,
        }
        return response

    def _king_node_health(self) -> dict:
        """Return a path-free health view for privileged operational callers."""
        try:
            payload = self._read_snapshot_file(KING_NODE_HEALTH_STATE)
        except KingNodeSnapshotError:
            payload = {}
        snapshot: dict[str, object]
        try:
            live = self._read_king_node_snapshot("live")
            snapshot = {
                "status": "ready",
                "schema_version": live.get("schema_version"),
                "session": live.get("session"),
                "freshness": live.get("freshness"),
            }
        except KingNodeSnapshotError as exc:
            snapshot = {"status": "unavailable", "code": exc.code}
        return _public_value(
            {
                "schema_version": KING_NODE_V2_SCHEMA,
                "status": "ok" if snapshot.get("status") == "ready" else "degraded",
                "process": payload.get("process", {"status": "unknown"}),
                "provider": payload.get("provider", {"status": "unknown"}),
                "entitlement": payload.get("entitlement", {"status": "unknown"}),
                "refresh": payload.get("refresh", {"status": "unknown"}),
                "snapshot": snapshot,
                "api": {"schema_version": KING_NODE_V2_SCHEMA, "frontend_schema": KING_NODE_FRONTEND_SCHEMA},
                "session": payload.get("session", snapshot.get("session")),
            }
        )

    def _require_auth(self):
        """Check auth and send error if unauthorized. Returns auth_info or None."""
        auth_info = self._check_auth()
        if auth_info is None:
            self._send_json(401, {"status": "error", "message": "Unauthorized"})
            return None
        if auth_info == "RATE_LIMITED":
            self._send_json(429, {"status": "error", "message": "Too many requests for this API key"})
            return None
        return auth_info

    def _require_admin(self):
        auth_info = self._require_auth()
        if not auth_info:
            return None
        if auth_info.get("role") != "ADMIN":
            self._send_json(403, {"status": "error", "message": "Admin access required"})
            self._release_api_key(auth_info)
            return None
        return auth_info

    def _king_node_session_query(self) -> str:
        parsed = urllib.parse.urlparse(self.path)
        values = urllib.parse.parse_qs(parsed.query, keep_blank_values=True)
        unknown = set(values).difference({"session", "_"})
        if unknown or len(values.get("session", [])) > 1:
            raise KingNodeSnapshotError("INVALID_QUERY", retryable=False)
        requested = values.get("session", ["live"])[0]
        if requested not in {"live", "last_completed"}:
            raise KingNodeSnapshotError("INVALID_SESSION", retryable=False)
        return requested

    def list_directory(self, path):
        """Sobrescribe el método por defecto para deshabilitar el listado de directorios"""
        self.send_error(403, "Directory listing is disabled for security reasons.")
        return None

    # --- MODIFICACIÓN CLAVE: Sistema de Logs ---
    def log_message(self, format, *args):
        """
        Sobrescribe el método por defecto para guardar logs.
        Detecta la IP real si se usa un Proxy Inverso (Nginx/Apache).
        """
        # 1. Intentar obtener la IP desde cabeceras (Proxy Inverso)
        headers = getattr(self, 'headers', None)
        x_forwarded = headers.get("X-Forwarded-For") if headers else None
        x_real = headers.get("X-Real-IP") if headers else None
        
        if x_forwarded:
            client_ip = x_forwarded.split(',')[0].strip()
        elif x_real:
            client_ip = x_real
        else:
            client_ip = self.client_address[0]

        status_message = format % args
        req_line = getattr(self, 'requestline', 'N/A')

        log_entry = (
            f"IP: {client_ip: <15} | REQ: {req_line} | RES: {status_message}"
        )

        # Escribir en el archivo y mostrar en consola
        logging.info(log_entry)
        # print(f"{datetime.now()} | {log_entry

    # --- NUEVA FUNCIÓN: BÚSQUEDA INTELIGENTE ---
    def smart_glob(self, ticker, exp, date_str=None):
        ticker_vars = list(set([ticker.upper(), ticker.lower(), ticker]))
        exp_vars = list(set([exp.lower(), exp.upper(), exp]))

        found_files = []

        for t in ticker_vars:
            for e in exp_vars:
                if date_str:
                    pattern = os.path.join(
                        DATA_FOLDER, f"*{t}*{e}*ExposureData*{date_str}*.json"
                    )
                else:
                    pattern = os.path.join(DATA_FOLDER, f"*{t}*{e}*ExposureData*.json")

                matches = glob.glob(pattern)
                if matches:
                    found_files.extend(matches)

        return sorted(list(set(found_files)))

    def serve_video(self, full_path):
        """Streams video with Range support"""
        try:
            file_size = os.path.getsize(full_path)
            range_header = self.headers.get("Range", "").strip()
            start, end = 0, file_size - 1

            if range_header:
                m = re.search(r"bytes=(\d+)-(\d*)", range_header)
                if m:
                    start = int(m.group(1))
                    if m.group(2):
                        end = int(m.group(2))

            length = end - start + 1
            self.send_response(206)
            self.send_header("Content-Type", "video/x-matroska")
            self.send_header("Accept-Ranges", "bytes")
            self.send_header("Content-Range", f"bytes {start}-{end}/{file_size}")
            self.send_header("Content-Length", str(length))
            self.end_headers()

            with open(full_path, "rb") as f:
                f.seek(start)
                remaining = length
                while remaining > 0:
                    chunk_size = min(65536, remaining)
                    data = f.read(chunk_size)
                    if not data:
                        break
                    try:
                        self.wfile.write(data)
                        remaining -= len(data)
                    except (BrokenPipeError, ConnectionResetError):
                        break
        except Exception as e:
            logging.error(f"Video Error: {e}")

    def do_POST(self):
        # --- LOGIN ENDPOINT (no auth required) ---
        if self.path == "/login":
            content_len = int(self.headers.get("Content-Length", 0))
            post_body = self.rfile.read(content_len)

            try:
                creds = json.loads(post_body)
                email = creds.get("email")
                password = creds.get("password")

                user = AUTH_STORE.verify_password(email, password)

                if user:
                    token = str(uuid.uuid4())
                    role = user["role"]
                    assert isinstance(email, str)

                    with CACHE_LOCK:
                        # Single-session: kill old session (except ADMIN)
                        if role != "ADMIN" and email in EMAIL_TO_TOKEN:
                            old_token = EMAIL_TO_TOKEN[email]
                            SESSIONS.pop(old_token, None)
                            logging.info(f"Session kicked for {email} (new login)")

                        SESSIONS[token] = {"email": email, "role": role}
                        EMAIL_TO_TOKEN[email] = token

                    response = {"status": "ok", "token": token, "role": role}
                    self._send_json(200, response)
                    logging.info(f"Login OK: {email} ({role})")
                else:
                    response = {"status": "error", "message": "Invalid credentials"}
                    self._send_json(401, response)
                    logging.info(f"Login FAILED: {email}")

            except Exception as e:
                self.send_error(500, str(e))
            return

        # --- BATCH ENDPOINT (auth required) ---
        if self.path == "/get_batch":
            auth_info = self._require_auth()
            if not auth_info:
                return

            content_len = int(self.headers.get("Content-Length", 0))
            post_body = self.rfile.read(content_len)

            try:
                request_data = json.loads(post_body)
                response_data = {}

                with CACHE_LOCK:
                    for item in request_data:
                        t = item.get("ticker").upper()
                        e = item.get("exp").lower()
                        key = f"{t}_{e}"

                        if key in LATEST_DATA_CACHE:
                            response_data[key] = json.loads(
                                LATEST_DATA_CACHE[key]["content"]
                            )
                        else:
                            response_data[key] = None

                self._send_json(200, response_data)

            except Exception as e:
                self.send_error(500, str(e))
            finally:
                self._release_api_key(auth_info)
            return

    def do_GET(self):
        parsed_url = urllib.parse.urlparse(self.path)
        path_only = parsed_url.path

        # Endpoint especial para que Impacthon pueda leer su propio .env
        # Mantenemos este handler ANTES de los bloqueos de seguridad de ".env"
        if path_only == "/api/impacthon/env":
            env_file = os.path.join(PROJECT_ROOT, "Impacthon", ".env")
            if os.path.exists(env_file):
                self.send_response(200)
                self.send_header("Access-Control-Allow-Origin", "*") # Allow cross-origin if needed
                self.send_header("Content-type", "text/plain")
                self.end_headers()
                with open(env_file, "rb") as f:
                    self.wfile.write(f.read())
            else:
                self.send_error(404, "Impacthon .env not found")
            return

        # SEGURIDAD PREVENTIVA: Bloquea Path Traversal y archivos sensibles inmediatamente
        if any(x in self.path for x in [".git", "servidor.py", ".."]):
            logging.warning(
                f"Intento de acceso bloqueado desde {self.client_address[0]}: {self.path}"
            )
            self.send_error(403, "Forbidden: Access Denied")
            return
            
        # Bloquear cualquier acceso a archivos .env por rutas directas
        if ".env" in self.path:
            logging.warning(f"Intento de acceso a .env bloqueado desde {self.client_address[0]}: {self.path}")
            self.send_error(403, "Forbidden: Access Denied")
            return


        # 0. VERIFY TOKEN (no auth required — it IS the auth check)
        if path_only == "/verify_token":
            auth_info = self._check_auth()
            if auth_info and isinstance(auth_info, dict):
                self._send_json(200, {"status": "ok", "role": auth_info["role"], "email": auth_info["email"]})
            else:
                self._send_json(401, {"status": "error", "message": "Invalid or expired token"})
            return

        # 0.5 DOCS HTML (no auth required for HTML, but auth is done in JS)
        if path_only in ["/docs", "/docs/"]:
            docs_path = os.path.join(TEMPLATE_FOLDER, "docs.html")
            if os.path.exists(docs_path):
                self.send_response(200)
                self.send_header("Content-type", "text/html")
                self.end_headers()
                with open(docs_path, "rb") as f:
                    self.wfile.write(f.read())
            else:
                self.send_error(404, f"Falta {docs_path}")
            return

        # --- INICIO: Subproyectos Impacthon (rutas directas) ---
        if path_only.startswith("/gem/"):
            rel_path = path_only.replace("/gem/", "", 1)
            if not rel_path: rel_path = "index.html"
            file_path = os.path.join(PROJECT_ROOT, "Impacthon", "gem", rel_path)
            if os.path.exists(file_path) and os.path.isfile(file_path):
                self.send_response(200)
                if file_path.endswith(".css"): self.send_header("Content-type", "text/css")
                elif file_path.endswith(".js"): self.send_header("Content-type", "application/javascript")
                elif file_path.endswith(".html"): self.send_header("Content-type", "text/html")
                elif file_path.endswith(".json"): self.send_header("Content-type", "application/json")
                elif file_path.endswith(".png"): self.send_header("Content-type", "image/png")
                self.end_headers()
                with open(file_path, "rb") as f: self.wfile.write(f.read())
            else:
                self.send_error(404, "File not found in gem")
            return

        if path_only.startswith("/gem-phone/"):
            rel_path = path_only.replace("/gem-phone/", "", 1)
            if not rel_path: rel_path = "mobile.html"
            file_path = os.path.join(PROJECT_ROOT, "Impacthon", "gem - phone", rel_path)
            if os.path.exists(file_path) and os.path.isfile(file_path):
                self.send_response(200)
                if file_path.endswith(".css"): self.send_header("Content-type", "text/css")
                elif file_path.endswith(".js"): self.send_header("Content-type", "application/javascript")
                elif file_path.endswith(".html"): self.send_header("Content-type", "text/html")
                elif file_path.endswith(".json"): self.send_header("Content-type", "application/json")
                elif file_path.endswith(".png"): self.send_header("Content-type", "image/png")
                self.end_headers()
                with open(file_path, "rb") as f: self.wfile.write(f.read())
            else:
                self.send_error(404, "File not found in gem-phone")
            return
        # --- FIN: Subproyectos Impacthon ---

        # 1. SERVIR HTML/CSS/JS (no auth required)
        if path_only == "/" or path_only == "/index.html":
            index_path = os.path.join(TEMPLATE_FOLDER, "index.html")
            if os.path.exists(index_path):
                self.send_response(200)
                self.send_header("Content-type", "text/html")
                self.end_headers()
                with open(index_path, "rb") as f:
                    self.wfile.write(f.read())
            else:
                self.send_error(404, f"Falta {index_path}")
            return

        if path_only.endswith(".css") or path_only.endswith(".js"):
            filename = path_only.lstrip("/")
            file_path = os.path.join(TEMPLATE_FOLDER, filename)

            # Enforce ADMIN role for sensitive dashboard modules
            if filename in [
                "js/ib.js",
                "js/market_structure.js",
                "js/charts.js",
                "js/fourier.js",
                "js/bot_status.js",
                "js/king_node.js",
            ]:
                auth_info = self._check_auth()
                if not auth_info or auth_info.get("role") != "ADMIN":
                    logging.warning(f"Unauthorized JS access attempt: {filename} from {self.client_address[0]}")
                    self._send_json(403, {"status": "error", "message": "Admin script access denied"})
                    return

            if os.path.exists(file_path):
                self.send_response(200)
                ctype = (
                    "text/css"
                    if filename.endswith(".css")
                    else "application/javascript"
                )
                self.send_header("Content-type", ctype)
                self.end_headers()
                with open(file_path, "rb") as f:
                    self.wfile.write(f.read())
                return
            else:
                self.send_error(404)
                return

        # 2. API: LISTAR ARCHIVOS (auth required)
        if self.path.startswith("/list_files"):
            auth_info = self._require_auth()
            if not auth_info:
                return
            try:
                query = urllib.parse.urlparse(self.path).query
                params = urllib.parse.parse_qs(query)
                ticker = params.get("ticker", ["SPX"])[0]
                exp = params.get("exp", ["0dte"])[0]
                requested_date = params.get("date", [None])[0]

                if requested_date:
                    today_str = requested_date
                else:
                    today_str = datetime.now().strftime("%Y%m%d")

                files = self.smart_glob(ticker, exp, date_str=today_str)
                filenames = [os.path.basename(f) for f in files]

                self.send_response(200)
                self.send_header("Content-type", "application/json")
                self.end_headers()
                import json

                self.wfile.write(json.dumps(filenames).encode("utf-8"))
                return
            except Exception as e:
                self.send_error(500, str(e))
                return
            finally:
                self._release_api_key(auth_info)

        # API: LISTAR PDFs (auth required, ADMIN only)
        if path_only == "/api/pdfs/list":
            auth_info = self._require_auth()
            if not auth_info or auth_info.get("role") != "ADMIN":
                if auth_info: # if authenticated but not admin
                    self._send_json(403, {"status": "error", "message": "Admin access required"})
                return
            
            try:
                found_pdfs = []
                for base_dir in [DOCS_PDF_FOLDER, VIS_FOLDER]:
                    if os.path.exists(base_dir):
                        for root, _, files in os.walk(base_dir):
                            for file in files:
                                if file.lower().endswith(".pdf"):
                                    full_path = os.path.join(root, file)
                                    rel_path = os.path.relpath(full_path, PROJECT_ROOT).replace("\\", "/")
                                    found_pdfs.append(rel_path)
                
                self._send_json(200, sorted(found_pdfs))
            except Exception as e:
                self.send_error(500, str(e))
            finally:
                self._release_api_key(auth_info)
            return

        # API: SERVIR PDF (auth checked via query token)
        if path_only == "/api/pdfs/serve":
            query = urllib.parse.urlparse(self.path).query
            params = urllib.parse.parse_qs(query)
            token = params.get("token", [""])[0]
            rel_file = params.get("file", [""])[0]

            auth_info = None
            with CACHE_LOCK:
                if token in SESSIONS:
                    auth_info = SESSIONS[token]
            
            if not auth_info or auth_info.get("role") != "ADMIN":
                self.send_error(403, "Admin access required")
                return

            if not rel_file or ".." in rel_file:
                self.send_error(400, "Invalid file path")
                return

            full_path = os.path.abspath(os.path.join(PROJECT_ROOT, rel_file))
            if not (full_path.startswith(os.path.abspath(DOCS_PDF_FOLDER)) or full_path.startswith(os.path.abspath(VIS_FOLDER))):
                self.send_error(403, "Path traversal restricted")
                return

            if not os.path.exists(full_path) or not full_path.lower().endswith(".pdf"):
                self.send_error(404, "PDF not found")
                return

            try:
                self.send_response(200)
                self.send_header("Content-type", "application/pdf")
                self.send_header("Content-Disposition", f'inline; filename="{os.path.basename(full_path)}"')
                self.end_headers()
                with open(full_path, "rb") as f:
                    self.wfile.write(f.read())
            except Exception as e:
                self.send_error(500, str(e))
            return

        # 2.5 API: KING NODE v2 snapshot and operational health (ADMIN only).
        # The cache-buster query key is intentionally ignored; it must not change
        # endpoint selection or artifact identity.
        if path_only in {"/api/king-node", "/api/king-node/health"}:
            auth_info = self._require_admin()
            if not auth_info:
                return
            try:
                if path_only == "/api/king-node/health":
                    self._send_json(200, self._king_node_health())
                    return
                try:
                    requested_session = self._king_node_session_query()
                except KingNodeSnapshotError as exc:
                    self._send_json(
                        400,
                        _safe_king_node_error(
                            exc.code, component="request", retryable=False
                        ),
                    )
                    return
                try:
                    snapshot = self._read_king_node_snapshot(requested_session)
                except KingNodeSnapshotError as exc:
                    self._send_json(
                        503,
                        _safe_king_node_error(
                            exc.code, component="snapshot", retryable=exc.retryable
                        ),
                    )
                    return
                if snapshot.get("schema_version") != KING_NODE_V2_SCHEMA:
                    self._send_json(
                        503,
                        _safe_king_node_error(
                            "SNAPSHOT_SCHEMA_UNSUPPORTED",
                            component="snapshot",
                            retryable=False,
                        ),
                    )
                    return
                self._send_json(200, snapshot)
            finally:
                self._release_api_key(auth_info)
            return

        # 3. API: GET LATEST (auth required)
        if self.path.startswith("/get_latest"):
            auth_info = self._require_auth()
            if not auth_info:
                return
            try:
                query = urllib.parse.urlparse(self.path).query
                params = urllib.parse.parse_qs(query)
                ticker = params.get("ticker", ["SPX"])[0].upper()
                exp = params.get("exp", ["0dte"])[0].lower()

                key = f"{ticker}_{exp}"
                content = None

                with CACHE_LOCK:
                    if key in LATEST_DATA_CACHE:
                        content = LATEST_DATA_CACHE[key]["content"]

                if content:
                    self.send_response(200)
                    self.send_header("Content-type", "application/json")
                    self.end_headers()
                    self.wfile.write(content)
                else:
                    files = self.smart_glob(ticker, exp)

                    if not files:
                        print(
                            f"[ERROR LATEST] No se encontraron archivos para {ticker} {exp} en {DATA_FOLDER}"
                        )
                        self.send_error(404, "No data")
                        return

                    latest_file = max(files, key=os.path.getctime)

                    with open(latest_file, "rb") as f:
                        content = f.read()

                    self.send_response(200)
                    self.send_header("Content-type", "application/json")
                    self.end_headers()
                    self.wfile.write(content)

                return
            except Exception as e:
                print(f"Server Error: {e}")
                self.send_error(500, str(e))
                return
            finally:
                self._release_api_key(auth_info)

        # 4. API: GET HISTORY (auth required)
        if self.path.startswith("/get_history"):
            auth_info = self._require_auth()
            if not auth_info:
                return
            try:
                query = urllib.parse.urlparse(self.path).query
                params = urllib.parse.parse_qs(query)
                ticker = params.get("ticker", ["SPX"])[0]
                exp = params.get("exp", ["0dte"])[0]
                req_time_str = params.get("time", ["0930"])[0]

                try:
                    req_h = int(req_time_str[:2])
                    req_m = int(req_time_str[2:])
                except:
                    self.send_error(400, "Formato de hora inválido. Use HHMM")
                    return

                cet_h = req_h + 6
                target_cet_int = (cet_h * 100) + req_m
                today_str = datetime.now().strftime("%Y%m%d")

                files = self.smart_glob(ticker, exp, date_str=today_str)

                if not files:
                    self.send_error(404, f"No hay historial para hoy ({today_str})")
                    return

                files.sort()
                best_file = None

                for f_path in files:
                    filename = os.path.basename(f_path)
                    match = re.search(r"_(\d{8})_(\d{6})\.json$", filename)
                    if match:
                        file_time_str = match.group(2)
                        file_hhmm = int(file_time_str[:4])

                        if file_hhmm <= target_cet_int:
                            best_file = f_path
                        else:
                            break

                if best_file:
                    with open(best_file, "rb") as f:
                        content = f.read()
                    self.send_response(200)
                    self.send_header("Content-type", "application/json")
                    self.end_headers()
                    self.wfile.write(content)
                else:
                    if files:
                        with open(files[0], "rb") as f:
                            content = f.read()
                        self.send_response(200)
                        self.send_header("Content-type", "application/json")
                        self.end_headers()
                        self.wfile.write(content)
                    else:
                        self.send_error(404, "No hay archivos disponibles.")
                return

            except Exception as e:
                print(f"History Error: {e}")
                self.send_error(500, str(e))
                return
            finally:
                self._release_api_key(auth_info)

        # 4.5 API: BOT STATUS (auth required, ADMIN only)
        if self.path == "/api/bot_status":
            auth_info = self._require_auth()
            if not auth_info or auth_info.get("role") != "ADMIN":
                if auth_info:
                    self._send_json(403, {"status": "error", "message": "Admin Role Required"})
                return
                
            try:
                trades_dir = os.path.join(PROJECT_ROOT, "trades_rl")
                today_str = datetime.now().strftime("%Y%m%d")
                
                def safe_load_json(filepath, default_val):
                    if os.path.exists(filepath):
                        try:
                            with open(filepath, "r") as f:
                                return json.load(f)
                        except json.JSONDecodeError as e:
                            logging.warning(f"Error parseando {filepath}: {e}")
                            return default_val
                    return default_val

                open_rl = safe_load_json(os.path.join(trades_dir, "open_positions_rl.json"), {})
                open_gbm = safe_load_json(os.path.join(trades_dir, "open_gbm_trackers.json"), {})
                
                hist_rl = safe_load_json(os.path.join(trades_dir, f"trades_rl_{today_str}.json"), [])
                hist_gbm = safe_load_json(os.path.join(trades_dir, f"trades_gbm_{today_str}.json"), [])
                
                if not hist_rl:
                    hist_rl = safe_load_json(os.path.join(trades_dir, f"trades_{today_str}.json"), [])

                response_data = {
                    "open_positions": {"rl": open_rl, "gbm": open_gbm},
                    "history": {"rl": hist_rl, "gbm": hist_gbm}
                }
                
                self._send_json(200, response_data)
                return
            except Exception as e:
                logging.error(f"Bot Status Error: {e}")
                self.send_error(500, str(e))
                return
            finally:
                self._release_api_key(auth_info)

        # 5. API: QUANTUM GENERATOR (Para Unity)
        if self.path == "/generate_bit":
            try:
                import json
                
                # 1. Crear circuito cuántico (1 Qubit, 1 Bit clásico)
                circuit = QuantumCircuit(1, 1)
                
                # 2. Puerta Hadamard (Superposición 50/50)
                circuit.h(0)
                
                # 3. Medir el colapso
                circuit.measure(0, 0)
                
                # 4. Ejecutar simulación
                result = QUANTUM_SIMULATOR.run(circuit, shots=1, memory=True).result()
                memory = result.get_memory(circuit)
                quantum_bit = int(memory[0]) # Resultado: 0 o 1
                
                # 5. Preparar respuesta JSON
                response = {
                    "success": True,
                    "value": quantum_bit,
                    "source": "vps_quantum_server",
                    "timestamp": datetime.now().strftime("%H:%M:%S")
                }
                
                # 6. Enviar cabeceras
                self.send_response(200)
                self.send_header("Content-type", "application/json")
                # Vital para que Unity (WebGL/Editor) no tenga problemas de CORS
                self.send_header("Access-Control-Allow-Origin", "*")
                self.end_headers()
                
                # 7. Enviar cuerpo
                self.wfile.write(json.dumps(response).encode("utf-8"))
                
                # Log extra para ver que Unity está conectando
                logging.info(f"⚛️ Quantum Request from {self.client_address[0]} | Result: {quantum_bit}")
                return

            except Exception as e:
                logging.error(f"Quantum Error: {e}")
                self.send_error(500, str(e))
                return
        # OTROS (Video, Seguridad)
        if self.path == "/Oppenheimer":
            full_movie_path = os.path.join(MOVIE_DIRECTORY, MOVIE_FILENAME)
            if os.path.exists(full_movie_path):
                self.serve_video(full_movie_path)
            else:
                self.send_error(404, "Movie not found")
            return

        allowed_dirs = ["/json_data/", "/fourier/", "/ib_charts/"]
        requested_dir = None
        for directory in allowed_dirs:
            if self.path.startswith(directory):
                requested_dir = directory
                break

        if requested_dir:
            # Enforce authentication for ANY direct access
            auth_info = self._require_auth()
            if not auth_info:
                return
                
            # Enforce ADMIN role for sensitive analytics data
            if requested_dir in ["/fourier/", "/ib_charts/"]:
                if auth_info.get("role") != "ADMIN":
                    self._send_json(403, {"status": "error", "message": "Access Denied: Admin Role Required"})
                    return

            return http.server.SimpleHTTPRequestHandler.do_GET(self)
        else:
            self.send_error(404, "File not found or Access Denied")
            return


def cache_updater_loop():
    """Escanea la carpeta cada 1 segundo y carga los JSON en RAM"""
    while True:
        try:
            # Obtenemos todos los archivos JSON de hoy
            today_str = datetime.now().strftime("%Y%m%d")
            pattern = os.path.join(DATA_FOLDER, f"*{today_str}*.json")
            files = glob.glob(pattern)

            new_cache = {}

            # Procesamos archivos para encontrar el más reciente por Ticker/Exp
            # Esto es una simplificación, adáptalo a tu estructura de nombres exacta
            # Asumo formato: Ticker_Exp_ExposureData_Fecha_Hora.json
            for f_path in files:
                filename = os.path.basename(f_path)
                parts = filename.split("_")
                if len(parts) >= 2:
                    ticker = parts[0].upper()
                    exp = parts[1].lower()
                    key = f"{ticker}_{exp}"

                    # Si ya tenemos uno, comparamos fechas/horas para quedarnos con el último
                    if (
                        key not in new_cache
                        or os.path.getctime(f_path) > new_cache[key]["time"]
                    ):
                        try:
                            with open(f_path, "rb") as f:
                                content = f.read()
                                new_cache[key] = {
                                    "content": content,
                                    "time": os.path.getctime(f_path),
                                }
                        except:
                            pass  # Error leyendo archivo (quizás se está escribiendo)

            # Actualizamos la variable global de forma segura
            with CACHE_LOCK:
                global LATEST_DATA_CACHE
                LATEST_DATA_CACHE = new_cache

        except Exception as e:
            logging.error(f"Cache Update Error: {e}")

        time.sleep(1)  # Esperar 1 segundo antes de volver a escanear


def start_static_server(directory, port):
    import functools
    def run():
        Handler = functools.partial(http.server.SimpleHTTPRequestHandler, directory=directory)
        try:
            with ThreadedReusableServer((SERVER_BIND, port), Handler) as httpd:
                print(f"Subproyecto servidor corriendo en puerto {port} -> {directory}")
                logging.info(f"Subproyecto servidor corriendo en puerto {port} -> {directory}")
                httpd.serve_forever()
        except Exception as e:
            msg = f"Error iniciando servidor en puerto {port}: {e}"
            print(msg)
            logging.error(msg)
            
    t = threading.Thread(target=run, daemon=True)
    t.start()

if __name__ == "__main__":
    if not os.path.exists(DATA_FOLDER):
        os.makedirs(DATA_FOLDER)
        
    # --- INICIO: Agregar servidores estáticos de Impacthon ---
    impacthon_dir = os.path.join(PROJECT_ROOT, "Impacthon")
    gem_dir = os.path.join(impacthon_dir, "gem")
    gem_phone_dir = os.path.join(impacthon_dir, "gem - phone")
    
    if os.path.exists(gem_dir):
        start_static_server(gem_dir, 8096)
    if os.path.exists(gem_phone_dir):
        start_static_server(gem_phone_dir, 8097)
    # --- FIN: Agregar servidores estáticos de Impacthon ---

    t = threading.Thread(target=cache_updater_loop, daemon=True)
    t.start()
    print("Background Cache Updater Started")
    print(f"Server running on port {PORT}. Logs in {LOG_FILE}")
    if DASHBOARD_AUTH_REQUIRED and not AUTH_STORE.configured:
        raise SystemExit("dashboard auth artifact is required")
    with ThreadedReusableServer((SERVER_BIND, PORT), ExposureDataHandler) as httpd:
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            pass
