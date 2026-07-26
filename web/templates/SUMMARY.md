# KING NODE web — hand-off de implementación

Última actualización: 2026-07-26  
Repositorio: `C:\Users\Álvaro Schwiedop\Desktop\KriptaStudios\Gex-Dashboard-Live`  
Rama: `main`

## Objetivo autorizado

Portar a la pestaña web **KING NODE** el núcleo portable de
`MASTER_KING_NODE_RECORD_V5.xlsx`, usando como autoridad:

- `MASTER_KING_NODE_RECORD_V5_CATALOGO_COMPLETO_DE_FORMULAS.md`;
- `live_king_node.py`;
- los JSON en tiempo real que escribe `services/gex_daemon.py` desde Tastytrade;
- ThetaData Standard para precios observados de VIX, VVIX y VIX1D;
- un nivel adicional **RAW GAMMA LEVEL** definido, por strike, como:

```text
(call_gamma × call_open_interest) + (put_gamma × put_open_interest)
```

El resultado debe funcionar sin Excel en el VPS, conservar estado entre ciclos,
exponer un endpoint autenticado para la web, incluir pruebas y dejar preparado
el despliegue mediante systemd.

## Estado del repositorio y aislamiento

El trabajo partió de `c4204844` (`Predeclare executable contextual bandit
development`). El árbol contenía muchos archivos modificados/no rastreados de
investigación JEPA que pertenecen al usuario. No deben entrar en ningún commit
de KING NODE.

Usar siempre `git add` con rutas explícitas. En particular, no añadir los
`SUMMARY.md` de la raíz, `AGENTS.md`, los resultados de `research_papers/JEPA`,
artefactos `.parquet`, `.pt`, `.tar.gz`, scripts JEPA ni `tmp/`.

Los tres artefactos de referencia de KING NODE estaban sin rastrear al comenzar:

- `MASTER_KING_NODE_RECORD_V5.xlsx`;
- `MASTER_KING_NODE_RECORD_V5_CATALOGO_COMPLETO_DE_FORMULAS.md`;
- `live_king_node.py`.

## Trabajo ya realizado

### Pestaña web existente

El commit anterior `67fc4e16` ya había conectado una pestaña KING NODE solo para
ADMIN mediante:

- `web/templates/js/king_node.js`;
- `web/templates/css/king_node.css`;
- integración existente en `auth.js`, `tabs.js`, `dashboard.js`, `refresh.js`,
  `styles.css` y la lista protegida de `services/servidor.py`.

La primera versión consumía `/get_latest?ticker=SPX&exp=0dte`, seleccionaba las
23 strikes más cercanas a cada lado de spot (47 en total), agregaba duplicados
por strike y mostraba GEX/DEX/VEX/Zomma/Vomma/Vega/Speed.

### RAW GAMMA implementado en el checkpoint inicial

La primera versión calculó raw gamma en JavaScript para cerrar el contrato y
probar el orden correcto de operaciones:

```text
strike 6000:
  (1×10 + 2×20) + (3×5 + 4×7) = 93
```

Después, el cálculo se trasladó íntegramente al motor backend. La versión final
de `web/templates/js/king_node.js` **no** lee gamma/OI ni recalcula finanzas:
solo valida y representa el snapshot autenticado `/api/king-node`. La regresión
de 93 continúa en `tests/test_king_node_engine.py`.

La validación del checkpoint inicial dio:

- `node --check web/templates/js/king_node.js`: PASS;
- `python -m pytest tests/test_king_node_web.py -q`: `3 passed`;
- `git diff --check`: sin errores, solo avisos CRLF de Windows.

También se ejecutó el cálculo contra un JSON Tastytrade real:

`D:\TrainingDataBackUp\June\json_data\SPX_0dte_ExposureData_20260617_100003.json`

Resultado observado en la ventana de 47 strikes:

- calidad `COMPLETE`;
- raw gamma total `469.20084337229827`;
- raw gamma level `7495`;
- raw gamma en ese strike `57.12861240565436`;
- nodo GEX `7525`.

### Auditoría del libro y de `live_king_node.py`

El catálogo declara 11 hojas y 7.382 celdas con fórmula. Las áreas principales
son:

- King Node Model: 1.303 fórmulas;
- GEX Depth: 954;
- Level Engine: 4.042;
- Master Dashboard / Dashboard: 511 / 472.

Fórmulas relevantes identificadas:

- boost DTE:
  `1 + 0.6 × max(0, 1 - dte_hours/6.5)`;
- régimen IV raw:
  HIGH si `VIX1D/VIX >= 1.1`, `VVIX >= 110` o `VIX >= 22`;
  LOW si `VIX1D/VIX <= 0.9` o (`VVIX <= 90` y `VIX <= 15`);
  NEUTRAL en otro caso;
- intensidad IV:
  `clamp(0.6, 1.4, 0.6×VIX1D/VIX + 0.4×VVIX/100 + 0.4)`;
- matrix key:
  `IVclass|gammaSign|zommaSign|dexSign|vexSign|vegaSign|vommaSign|speedSign`;
- box key:
  `Positive/Negative|VIX direction|VVIX direction|VIX1D direction`;
- columna A:I de la tabla:
  strike, gamma gross, GEX, Zomma, DEX, VEX, Vomma, Vega y Speed;
- max/min GEX en `T22/T23`;
- gamma flip y zero gamma en `D26/D27`;
- call/put walls: los tres mayores gamma gross condicionados por GEX positivo
  o negativo;
- GEX Depth:
  `net_flow = flow_factor × (GEX×dSpot + dIV×VEX×spot
  + accel×0.5×Speed×dSpot² + cross×Zomma×dSpot×dIV)`.

De `live_king_node.py` se identificaron los contratos de runtime que se deben
portar:

- refresco 30 s;
- suavizado de tres lecturas;
- lock de niveles de tres ciclos;
- 47 strikes;
- dirección por media de dos mitades con ventana 50 y deadbands:
  VIX 0,10; VVIX 0,25; VIX1D 0,10; ATM IV 0,001;
- monitor de pendiente/sign flip de net GEX;
- monitor de pico/roll de Vomma cerca de spot;
- skew de puts/calls a ±25 puntos;
- vol tension;
- persistencia de niveles de soporte/resistencia.

### Auditoría de fuentes en local

Los JSON Tastytrade persistidos contienen las gammas, IV y OI por lado, además
de todas las exposiciones necesarias. Son suficientes para raw gamma y para el
perfil A:I.

El feed ThetaData existente guarda SPXW/QQQ/SPY 0DTE y weekly, spot y opciones
VIX, pero no persiste todavía precios directos de VVIX/VIX1D. La API v3 oficial
de ThetaData Standard expone:

```text
GET /v3/index/snapshot/price?symbol=VIX
GET /v3/index/snapshot/price?symbol=VVIX
GET /v3/index/snapshot/price?symbol=VIX1D
```

El port debe leer esos valores observados y fallar cerrado para cada índice que
Theta Terminal no entregue. No se deben fabricar proxies.

Los archivos ThetaData históricos locales actuales no incluyen todos los
vencimientos necesarios para reconstruir de forma oficial VVIX/VIX1D desde
opciones. Existen históricos diarios Cboe locales, pero no deben sustituir un
snapshot intradía real.

### Limitación de referencia que no debe ocultarse

Las hojas `Matrix` e `IV Regime Map` contienen tablas de valores estáticos. El
catálogo registra sus fórmulas consumidoras pero no reproduce todas las celdas
literales de esas tablas.

El runtime de spreadsheets requerido para inspeccionar el `.xlsx` no estuvo
disponible en esta sesión, por lo que no se debe afirmar paridad literal de esas
dos tablas. El motor portable debe:

- calcular y exponer las keys exactas;
- usar reglas semánticas explícitamente marcadas como fallback si no existe un
  JSON de referencia exportado;
- aceptar después un `config/king_node_reference.json` generado desde Excel,
  sin cambiar el contrato del endpoint.

## Arquitectura implementada

### 1. Motor puro

`modules/king_node_engine.py` no depende de Excel:

- validar el split JSON de Tastytrade;
- agregar por strike;
- seleccionar la ventana 47;
- producir el perfil A:I y raw gamma;
- calcular totales, flags, keys, régimen IV, skew, walls, gamma flip, zero
  gamma y niveles;
- actualizar direcciones, pendiente GEX, Vomma y vol tension;
- aplicar suavizado y lock/histéresis;
- devolver snapshot JSON y estado serializable;
- marcar origen, frescura, cobertura, warnings y degradaciones.

### 2. Servicio en tiempo real

`services/king_node_service.py`:

- localizar de forma segura el último `SPX_0dte_ExposureData_*.json`;
- consultar VIX/VVIX/VIX1D en Theta Terminal;
- no procesar archivos parciales;
- persistir estado entre reinicios;
- escribir atómicamente `runtime/king_node/latest.json`;
- archivar snapshots compactos opcionalmente;
- soportar `--once`, `--interval`, `--tasty-data-dir`, `--output-dir`,
  `--state-file` y `--thetadata-url`;
- configurar edad máxima por variables de entorno.

### 3. Endpoint y web final

`services/servidor.py` incluye el endpoint ADMIN:

```text
GET /api/king-node
```

El endpoint lee solo el snapshot precomputado, comprueba estructura/edad y
devuelve errores JSON controlados. JavaScript es un renderer del contrato
backend, con:

- status/edad/orígenes;
- spot, régimen y vol tension;
- VIX/VVIX/VIX1D con dirección y edad;
- raw gamma level;
- max/min GEX, flip y zero gamma;
- tres call walls y tres put walls;
- seis resistencias y seis soportes bloqueados;
- tabla de 47 strikes;
- warnings visibles de cualquier degradación.

### 4. Operación VPS — pendiente de este hand-off

Falta añadir:

- `systemd/king-node.service`;
- `.env.king-node.example` sin secretos;
- script de instalación/actualización idempotente;
- `docs/KING_NODE_VPS_DEPLOYMENT.md`;
- comandos de health check, logs, rollback y diagnóstico de Tastytrade /
  Theta Terminal.

Orden de servicios previsto:

```text
thetadata_feed.service
gex_daemon.service
king-node.service
financial-server.service
```

### 5. Verificación y commits

Añadir pruebas unitarias del motor, cliente ThetaData, selección/frescura,
estado e endpoint. Validar con el JSON real de junio, ejecutar suite focal,
Ruff/compile, `node --check`, `git diff --check` y revisar que no haya secretos.

Los commits deben ser parciales y con add selectivo:

1. raw gamma + este hand-off;
2. motor/servicio/API + pruebas;
3. renderer final + CSS + pruebas;
4. systemd/config/docs + validación final.

Después de cada commit se debe ejecutar `git push origin main` y registrar aquí
el hash y el resultado.

## Registro de commits KING NODE

- `67fc4e16` — `feat(web): add King Node exposure tab` (preexistente).
- `fc592de7` — `feat(king-node): add raw gamma level and handoff`.
- `85254f29` — `feat(king-node): add realtime engine service and API`.
- `3021fc66` — `feat(king-node): render precomputed realtime model`.

## Checkpoint backend implementado después de `fc592de7`

Se crearon, validaron y publicaron en `85254f29`:

- `modules/king_node_engine.py`: motor puro, ventana 47, perfil A:I, raw gamma,
  régimen, keys, skew de-trended, walls, gamma flip, zero gamma, top-6 por lado,
  suavizado, lock, pendiente GEX, Vomma, vol tension y estado de VIX1D;
- `services/king_node_service.py`: selector de JSON Tastytrade, cliente oficial
  `index/snapshot/price`, edades, estado, escritura atómica y CLI;
- `config/king_node_reference.json`: contrato vacío/auditable para las dos
  tablas estáticas, con fallback semántico explícito;
- `services/servidor.py`: endpoint ADMIN `GET /api/king-node`;
- `tests/test_king_node_engine.py`: seis regresiones de cálculo, estado,
  histéresis, ThetaData y publicación.

Validación de este checkpoint:

- `python -m pytest tests/test_king_node_engine.py -q`: `6 passed`;
- `python -m compileall`: PASS;
- `python -m ruff check`: PASS;
- `git diff --check`: PASS salvo aviso CRLF de Windows;
- one-shot contra la carpeta real de junio: 47 strikes, raw gamma level 7500,
  raw gamma 81,3700 y snapshot `DEGRADED` esperado al deshabilitar Theta.

## Checkpoint renderer final

La versión actual pendiente de commit convierte
`web/templates/js/king_node.js` en un renderer fail-closed de
`king-node.v1`. Muestra:

- calidad, frescura y procedencia de Tastytrade/ThetaData;
- spot, régimen, dealer action, vol tension y raw gamma;
- VIX, VVIX, VIX1D y ATM IV con dirección/edad;
- raw gamma level, king gamma, max/min GEX, flip y zero gamma;
- diez exposiciones agregadas;
- seis resistencias, seis soportes, tres call walls y tres put walls;
- 47 strikes con perfil A:I y raw gamma;
- matrix key, box key, monitores, coberturas, degradaciones y errores.

El renderer escapa todo texto originado en backend. La prueba de contrato
inyecta deliberadamente `<script>alert('no')</script>` como warning y verifica
que solo aparece escapado.

Validación actual:

- `node --check web/templates/js/king_node.js`: PASS;
- `python -m pytest tests/test_king_node_web.py
  tests/test_king_node_engine.py -q`: `9 passed`;
- `git diff --check`: PASS salvo avisos CRLF de Windows;
- inspección visual automatizada: no ejecutada porque el conector de navegador
  de esta sesión respondió `No browser is available`; la validación DOM
  determinista con Node sí pasó.

## Checkpoint operativo preparado después de `3021fc66`

Archivos creados, todavía pendientes del siguiente hash:

- `.env.king-node.example`: rutas, intervalos y edades sin secretos;
- `systemd/king-node.service`: estado en `/var/lib/king-node`, dependencias
  blandas sobre Theta/Tasty, restart y hardening;
- `systemd/financial-server.service`: ruta compartida del snapshot y orden
  posterior a KING NODE;
- `scripts/check_king_node_health.py`: contrato de health verificable y salida
  JSON;
- `scripts/deploy_king_node_vps.sh`: instalación idempotente y arranque
  ordenado;
- `docs/KING_NODE_VPS_DEPLOYMENT.md`: preflight, one-shot, instalación, logs,
  diagnóstico y rollback;
- `tests/test_king_node_deployment.py`: cuatro regresiones del contrato
  operativo.

El health de producción permite la advertencia explícita del fallback estático,
pero exige snapshot/Tasty frescos, 47 strikes y VIX/VVIX/VIX1D observados. La
opción `--require-reference-export` hace que la paridad estática pendiente sea
un gate estricto.

Validación actual:

- suite focal completa: `13 passed`;
- Ruff de los archivos nuevos: PASS;
- `compileall`: PASS;
- `node --check`: PASS;
- `bash -n scripts/deploy_king_node_vps.sh`: PASS;
- `git diff --check`: PASS salvo avisos CRLF de Windows.

Siguiente orden exacto:

1. commit/push del checkpoint operativo y este hand-off;
2. registrar su hash final en este documento;
3. decidir si versionar los tres artefactos fuente que siguen sin rastrear;
4. en el VPS, validar un one-shot con Tastytrade y Theta Terminal realmente
   disponibles.
