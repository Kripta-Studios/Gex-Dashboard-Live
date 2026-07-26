import uuid
import json
import threading
import time
import http.server
import socketserver
import os
import glob
import urllib.parse
import re
import logging
from datetime import datetime
from qiskit import QuantumCircuit
from qiskit_aer import AerSimulator
# --- CONFIGURATION ---
PORT = 8609
IP = "91.99.90.39"
# Get the project root directory (parent of services/)
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(SCRIPT_DIR)

DATA_FOLDER = os.path.join(PROJECT_ROOT, "json_data")
TEMPLATE_FOLDER = os.path.join(PROJECT_ROOT, "web", "templates")
DOCS_PDF_FOLDER = os.path.join(PROJECT_ROOT, "docs", "pdfs")
VIS_FOLDER = os.path.join(PROJECT_ROOT, "visualizar")

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

# --- AUTHENTICATION ---
USERS = {
    "admin@flowgreeks.com": {"pass": "admin123", "role": "ADMIN"},
    "user1@flowgreeks.com": {"pass": "FlowGreeksPlottingUser1", "role": "USER"},
    "user2@flowgreeks.com": {"pass": "FlowGreeksPlottingUser2", "role": "USER"},
    "user3@flowgreeks.com": {"pass": "FlowGreeksPlottingUser3", "role": "USER"},
}
SESSIONS = {}        # { token_uuid: {"email": str, "role": str} }
EMAIL_TO_TOKEN = {}  # { email: token } — single-session enforcement

# Static API keys for scripts/bots (add more as needed)
API_KEYS = {
    "gex_bot_2026_xyz": {"role": "BOT", "owner": "trading_bot"},
}
API_KEY_LOCKS = {k: threading.Lock() for k in API_KEYS}  # 1 req/key

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


class ExposureDataHandler(http.server.SimpleHTTPRequestHandler):

    # --- AUTH MIDDLEWARE ---
    def _check_auth(self):
        """Verify Bearer token or API key. Returns auth dict or None."""
        # Option A: Bearer token (web users)
        auth = self.headers.get("Authorization", "")
        if auth.startswith("Bearer "):
            token = auth[7:]
            with CACHE_LOCK:
                session = SESSIONS.get(token)
            return session  # {"email": ..., "role": ...} or None

        # Option B: API key (scripts)
        api_key = self.headers.get("X-API-Key", "")
        if api_key and api_key in API_KEYS:
            # Try to acquire lock (non-blocking)
            lock = API_KEY_LOCKS.get(api_key)
            if lock and not lock.acquire(blocking=False):
                return "RATE_LIMITED"  # Another request is active
            return {"role": API_KEYS[api_key]["role"], "email": f"apikey:{API_KEYS[api_key]['owner']}", "_api_key": api_key}

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
        body = json.dumps(data).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-type", "application/json")
        self.end_headers()
        self.wfile.write(body)

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

                user = USERS.get(email)

                if user and user["pass"] == password:
                    token = str(uuid.uuid4())
                    role = user["role"]

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
            with ThreadedReusableServer(("0.0.0.0", port), Handler) as httpd:
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
    with ThreadedReusableServer(("0.0.0.0", PORT), ExposureDataHandler) as httpd:
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            pass
