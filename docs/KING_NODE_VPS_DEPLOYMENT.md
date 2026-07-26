# Despliegue de KING NODE en el VPS

Esta guía instala el motor portable sin Excel. El flujo de producción es:

```text
Tastytrade -> gex_daemon.service -> json_data/SPX_0dte_ExposureData_*.json
Theta Terminal -> VIX/VVIX/VIX1D observados
ambas fuentes -> king-node.service -> /var/lib/king-node/latest.json
snapshot -> financial-server.service -> GET /api/king-node -> pestaña web
```

## 1. Requisitos

- checkout del repositorio en
  `/home/Option-Greeks-Plotting-Discord-Bot`;
- Python 3 con `requirements.txt` instalado;
- Java y `services/ThetaTerminalv3.jar`;
- Theta Terminal autenticado con una suscripción que permita los snapshots de
  índices VIX, VVIX y VIX1D;
- credenciales OAuth de Tastytrade ya configuradas para `gex_daemon.py`;
- servicios `thetadata_feed.service`, `gex_daemon.service` y
  `financial-server.service` existentes.

El archivo KING NODE no contiene credenciales. Tastytrade continúa leyendo del
`.env` privado existente del proyecto:

```text
TASTYTRADE_CLIENT_SECRET=...
TASTYTRADE_REFRESH_TOKEN=...
```

No se deben copiar estos secretos al repositorio ni a
`.env.king-node.example`.

## 2. Actualizar el checkout

Desde el VPS:

```bash
cd /home/Option-Greeks-Plotting-Discord-Bot
git status --short
git fetch origin
git pull --ff-only origin main
```

Si `git status` muestra cambios locales, detenerse y preservarlos antes del
pull. El instalador no ejecuta Git ni modifica el checkout.

Instalar dependencias solo si el entorno aún no las contiene:

```bash
sudo /usr/bin/python3 -m pip install -r requirements.txt
```

## 3. Configuración

El instalador crea una sola vez `/etc/kripta/king-node.env` a partir del
ejemplo y conserva el archivo en despliegues posteriores:

```bash
sudo APP_DIR=/home/Option-Greeks-Plotting-Discord-Bot \
  bash scripts/deploy_king_node_vps.sh
sudo nano /etc/kripta/king-node.env
sudo chmod 600 /etc/kripta/king-node.env
```

Valores esperados:

```text
KING_NODE_TASTY_DATA_DIR=/home/Option-Greeks-Plotting-Discord-Bot/json_data
KING_NODE_OUTPUT=/var/lib/king-node/latest.json
KING_NODE_STATE_FILE=/var/lib/king-node/state.json
KING_NODE_REFERENCE=/home/Option-Greeks-Plotting-Discord-Bot/config/king_node_reference.json
KING_NODE_INTERVAL_SECONDS=30
KING_NODE_TASTY_MAX_AGE_SECONDS=900
KING_NODE_INDEX_MAX_AGE_SECONDS=180
KING_NODE_SNAPSHOT=/var/lib/king-node/latest.json
KING_NODE_WEB_MAX_AGE_SECONDS=900
THETADATA_URL=http://127.0.0.1:25503/v3
```

Tras editar la configuración:

```bash
sudo systemctl restart king-node.service financial-server.service
```

## 4. Preflight de proveedores

Comprobar que Tastytrade está produciendo SPX 0DTE reciente:

```bash
find json_data -maxdepth 1 -type f \
  -name 'SPX_0dte_ExposureData_*.json' -mmin -15 -print | tail
sudo systemctl status gex_daemon.service --no-pager --full
sudo journalctl -u gex_daemon.service -n 100 --no-pager
```

Comprobar Theta Terminal de forma directa:

```bash
curl -fsS 'http://127.0.0.1:25503/v3/index/snapshot/price?symbol=VIX'
curl -fsS 'http://127.0.0.1:25503/v3/index/snapshot/price?symbol=VVIX'
curl -fsS 'http://127.0.0.1:25503/v3/index/snapshot/price?symbol=VIX1D'
```

No avanzar si una respuesta es de autenticación, licencia o no contiene un
precio observado. KING NODE no sustituye índices faltantes por proxies.

## 5. One-shot antes del servicio continuo

```bash
cd /home/Option-Greeks-Plotting-Discord-Bot
set -a
. /etc/kripta/king-node.env
set +a
/usr/bin/python3 services/king_node_service.py --once
/usr/bin/python3 scripts/check_king_node_health.py --json
```

El verificador de producción exige:

- schema `king-node.v1`;
- snapshot y JSON Tastytrade dentro de la edad máxima;
- exactamente 47 strikes;
- VIX, VVIX y VIX1D observados por ThetaData;
- ausencia de errores del productor.

La advertencia `semantic_fallback` es esperable mientras
`config/king_node_reference.json` no contenga una exportación auditada de las
tablas estáticas `Matrix` e `IV Regime Map`. Para convertirla en fallo:

```bash
/usr/bin/python3 scripts/check_king_node_health.py \
  --require-reference-export
```

## 6. Instalación y orden de arranque

El script es idempotente: preserva el environment privado, recompila los
módulos, instala las dos unidades y reinicia en este orden:

```text
thetadata_feed.service
gex_daemon.service
king-node.service
financial-server.service
```

Ejecutar:

```bash
sudo APP_DIR=/home/Option-Greeks-Plotting-Discord-Bot \
  bash scripts/deploy_king_node_vps.sh
```

## 7. Health checks y logs

```bash
systemctl is-active thetadata_feed.service gex_daemon.service \
  king-node.service financial-server.service
sudo /usr/bin/python3 scripts/check_king_node_health.py
sudo journalctl -u king-node.service -f
sudo journalctl -u financial-server.service -n 100 --no-pager
sudo ls -l /var/lib/king-node/latest.json /var/lib/king-node/state.json
```

La API es ADMIN-only. Tras autenticarse en el dashboard:

```bash
curl -sS -H "Authorization: Bearer $GEX_ADMIN_TOKEN" \
  http://127.0.0.1:8609/api/king-node
```

No pegar tokens reales en shell history compartido. También se puede validar
abriendo la pestaña **KING NODE** en el navegador: debe mostrar edad, fuentes,
47 strikes y los tres índices.

## 8. Diagnóstico

`KING NODE UNHEALTHY` por Tastytrade:

- comprobar fecha/hora y mercado;
- revisar `gex_daemon.service`;
- confirmar que el fichero más reciente terminó de escribirse;
- confirmar `KING_NODE_TASTY_DATA_DIR`.

Índices no observados:

- comprobar `thetadata_feed.service`;
- repetir los tres `curl`;
- revisar autenticación/suscripción de Theta Terminal;
- confirmar que `THETADATA_URL` termina en `/v3`.

API `503`:

- ejecutar el health checker sobre `/var/lib/king-node/latest.json`;
- revisar edad máxima del productor y del servidor;
- confirmar que ambas unidades leen la misma ruta.

Pestaña sin aparecer:

- KING NODE solo se carga para rol `ADMIN`;
- revisar la consola del navegador y el `journalctl` del servidor;
- confirmar que `/js/king_node.js` y `/api/king-node` responden autenticados.

## 9. Rollback

No borrar el estado para volver atrás. Revertir en Git los commits KING NODE
que se quieran deshacer, publicar el revert y ejecutar otra vez el instalador.
Como medida inmediata:

```bash
sudo systemctl disable --now king-node.service
sudo systemctl restart financial-server.service
```

El snapshot y estado quedan en `/var/lib/king-node` para diagnóstico. Se pueden
reactivar después con:

```bash
sudo systemctl enable --now king-node.service
```
