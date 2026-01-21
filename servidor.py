import uuid  # <--- AÑADIR ESTO
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

# --- CONFIGURATION ---
PORT = 8609
DATA_FOLDER = "json_data"
TEMPLATE_FOLDER = "templates"
# Cambio solicitado: nombre del archivo de logs
LOG_FILE = "servidor_logs.txt"
MOVIE_DIRECTORY = "/home/kripta/Movies"
MOVIE_FILENAME = "oppenheimer.mp4"

# MEMORIA RAM GLOBAL
LATEST_DATA_CACHE = {}
CACHE_LOCK = threading.Lock()

USERS = {
    "admin@flowgreeks.com": {"pass": "admin123", "role": "ADMIN"},
    "flowgreeks@email.com": {"pass": "FlowGreeksPlotting", "role": "USER"},
}
SESSIONS = {}  # Almacena tokens activos: { "token_uuid": "role" }

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

    # --- MODIFICACIÓN CLAVE: Sistema de Logs ---
    def log_message(self, format, *args):
        """
        Sobrescribe el método por defecto para guardar logs.
        Detecta la IP real si se usa un Proxy Inverso (Nginx/Apache).
        """
        # 1. Intentar obtener la IP desde la cabecera X-Forwarded-For (Estándar)
        x_forwarded = self.headers.get("X-Forwarded-For")

        # 2. Intentar obtener la IP desde X-Real-IP (Común en Nginx)
        x_real = self.headers.get("X-Real-IP")

        if x_forwarded:
            # X-Forwarded-For puede ser una lista: "client, proxy1, proxy2"
            # Nos quedamos con la primera, que es la del cliente real.
            client_ip = x_forwarded.split(',')[0].strip()
        elif x_real:
            client_ip = x_real
        else:
            # Si no hay proxy, usar la IP directa de la conexión
            client_ip = self.client_address[0]

        status_message = format % args

        log_entry = (
            f"IP: {client_ip: <15} | REQ: {self.requestline} | RES: {status_message}"
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
        # --- LOGIN ENDPOINT ---
        if self.path == "/login":
            content_len = int(self.headers.get("Content-Length", 0))
            post_body = self.rfile.read(content_len)

            try:
                import json

                creds = json.loads(post_body)
                email = creds.get("email")
                password = creds.get("password")

                user = USERS.get(email)

                if user and user["pass"] == password:
                    # Login Exitoso
                    token = str(uuid.uuid4())
                    role = user["role"]

                    with CACHE_LOCK:
                        SESSIONS[token] = role

                    response = {"status": "ok", "token": token, "role": role}
                    self.send_response(200)
                else:
                    # Login Fallido
                    response = {"status": "error", "message": "Invalid credentials"}
                    self.send_response(401)

                self.send_header("Content-type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps(response).encode("utf-8"))

            except Exception as e:
                self.send_error(500, str(e))
            return

        # --- EXISTING BATCH ENDPOINT ---
        if self.path == "/get_batch":
            content_len = int(self.headers.get("Content-Length", 0))
            post_body = self.rfile.read(content_len)

            import json

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

                self.send_response(200)
                self.send_header("Content-type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps(response_data).encode("utf-8"))

            except Exception as e:
                self.send_error(500, str(e))
            return

    def do_GET(self):
        parsed_url = urllib.parse.urlparse(self.path)
        path_only = parsed_url.path

        # 1. SERVIR HTML/CSS/JS
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

        # 2. API: LISTAR ARCHIVOS
        if self.path.startswith("/list_files"):
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

        # 3. API: GET LATEST
        if self.path.startswith("/get_latest"):
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

        # 4. API: GET HISTORY
        if self.path.startswith("/get_history"):
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

        # OTROS (Video, Seguridad)
        if self.path == "/Oppenheimer":
            full_movie_path = os.path.join(MOVIE_DIRECTORY, MOVIE_FILENAME)
            if os.path.exists(full_movie_path):
                self.serve_video(full_movie_path)
            else:
                self.send_error(404, "Movie not found")
            return

        # SEGURIDAD Y FALLBACK
        if any(x in self.path for x in [".git", ".env", "servidor.py", ".."]):
            logging.warning(
                f"Intento de acceso bloqueado desde {self.client_address[0]}: {self.path}"
            )
            self.send_error(403, "Forbidden: Access Denied")
            return

        allowed_dirs = ["/json_data/", "/fourier/", "/ib_charts/"]

        is_allowed = False
        for directory in allowed_dirs:
            if self.path.startswith(directory):
                is_allowed = True
                break

        if is_allowed:
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


if __name__ == "__main__":
    if not os.path.exists(DATA_FOLDER):
        os.makedirs(DATA_FOLDER)
    t = threading.Thread(target=cache_updater_loop, daemon=True)
    t.start()
    print("Background Cache Updater Started")
    print(f"Server running on port {PORT}. Logs in {LOG_FILE}")
    with ThreadedReusableServer(("0.0.0.0", PORT), ExposureDataHandler) as httpd:
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            pass
