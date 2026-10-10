# Actualización de fórmulas KING NODE — 10 octubre 2026

La web usa las fórmulas de los cuatro archivos recibidos en
`/home/kripta/gex-dashboard-transfer-20261010-115356`. Market Structure consume
el mismo snapshot `/api/king-node` que la pestaña KING NODE. Desaparece su matriz
JavaScript independiente y la clasificación de IV basada en una EMA de VIX.

## Autoridad y diferencias

| Archivo recibido | SHA-256 |
|---|---|
| `MASTER_KING_NODE_RECORD_V5.xlsx` | `ef8c5a0ddf5a93d9ca763c34146674ff5b6e775e1ee0f95320443deab30bdabb` |
| `MASTER_KING_NODE_RECORD_V5_REPLAY.xlsx` | `e25431c9529cfe0b01f795c8e89aa020515c9244cb4f3118fde451c55f92f5e7` |
| `live_king_node.py` | `29a3264ebe7d6592aac63fb68a614cfef3fa328a5c92266f6113ef4b841d521e` |
| `replay_king_node.py` | `f09d948c0816a2531c854dc66e9cc07112e65839978621bf136c5966c8cee116` |

Los dos libros tienen **18.302 fórmulas idénticas**, incluidas las fórmulas
compartidas expandidas. El libro anterior tenía 7.959. Se conservan 78 estados
Matrix y 54 entradas IV Regime Map. El catálogo antiguo sigue como referencia
explicativa; no sustituye las fórmulas actuales. El inventario reproducible está
en [king_node_formula_coverage.md](king_node_formula_coverage.md).

| Área | Comportamiento nuevo |
|---|---|
| Exposiciones | Black-Scholes de `live`, r=4,3%, q=1,2%, IV CALL para ambas patas, multiplicador 100 y SCALE=0,001. GEX usa OI CALL−PUT; gamma bruto, vega y vomma usan OI CALL+PUT. |
| Escalera | 47 strikes contiguos de 5 puntos, suavizado de tres observaciones y redondeo por strike. Los signos Matrix proceden de los netos sin suavizar. |
| IV | `King Node Model!L5` prioriza el mapa; `J5` queda como indicador bruto y fallback. Es correcto mostrar HIGH → Low en determinados estados. Sin override manual guardado. |
| Matrix | Textos actualizados, especialmente filas 13, 24, 34 y 35: compresión y deriva condicionada por posiciones. Charm usa el texto de la columna correspondiente a su signo. |
| Niveles | Fórmulas de selección, puntuación, confluencia, geometría, UNSAFE, vanna de llegada, zomma, toma de beneficio y riesgo de ruptura. Locks, quick reclaim, fragile gamma, IV fast/top, dEdge, PROX, drenaje y estados SAND/VEX persisten por sesión. |
| Monitores | GEX slope/tape, skew con baseline intradía del script, vol tension, spot/vol y squeeze proceden de las funciones suministradas. |
| Arranque | El servicio reconoce el argumento `normalized_input`. El cierre previo es opcional para la variación diaria; su ausencia no bloquea el cálculo de estructura. |
| Ruta pública | Excepciones exactas Caddy para `/api/king-node` y `/api/king-node/health`, antes del catch-all que enviaba esas peticiones a Inventario y devolvía 404. |

GEX por strike equivale a `gamma × (OIcall−OIput) × 0,1 × spot² × 0,01`.
VEX equivale a `vanna × (OIcall−OIput) × 0,1 × spot`. Los Greeks observados
del proveedor conservan su procedencia en la entrada, pero no reemplazan estas
ecuaciones. La procedencia publicada declara el modelo y sus parámetros.

## Adaptación al VPS

`export_king_node_runtime.py` exporta fórmulas y configuraciones explícitas.
Excluye los resultados cacheados, precios, overrides manuales y marcas guardadas.
El evaluador usa un parser de expresiones Excel y funciones permitidas de
`formulas==1.3.4`; no ejecuta macros, vínculos externos ni código de las celdas.
`sync_king_node_live_kernel.py` extrae funciones Python concretas mediante AST;
el servidor nunca importa los programas desktop, que arrancarían IBKR/Excel.

Hay una discrepancia entre los scripts recibidos: `replay` actualiza
`GK` (gamma-rank), `GO/GP` (shelf holds), mientras el `live` recibido no contiene
esos escritores. La adaptación usa los dos escritores de `replay`, con estado
propio, para no perpetuar marcas estáticas del archivo. `FN` queda desactivado,
como especifica el replay. Esta reconciliación es explícita y está probada;
no se afirma equivalencia con las marcas cacheadas de una sesión desktop.

El estado cambia a versión 3. Una sesión nueva o un estado antiguo reinicia
las confirmaciones. Un snapshot idéntico no avanza contadores; las observaciones
cambiadas o fuera de orden con la misma fecha/hora se rechazan. Los errores
de salida y de las funciones de estado impiden publicar un snapshot válido.
Los errores internos atrapados por IFERROR se distinguen en el diagnóstico.

## Límites de los datos y de la validación

- ThetaData sigue suministrando la cadena y las reconstrucciones VIX/VIX1D/VVIX.
  Usar las mismas fórmulas no convierte esos índices en observaciones IBKR
  idénticas ni prueba paridad de mercado entre proveedores.
- ES, TPO, VWAP y flujo de volumen no tienen entrada equivalente en este
  productor. Se muestran como no disponibles; no se inventan sus señales.
- Se conserva, y publica como metadato, el vencimiento fijo **20:00 UTC** del
  script recibido. No equivale al cierre de invierno ni a una sesión abreviada.
  Cuando ese reloj vence, el cálculo deja de ser válido. Cambiar esta convención
  requeriría reconciliar el desktop y la web explícitamente.
- Las fórmulas de presentación con el identificador indefinido `chr` se
  conservan. El parser lo representa como error Excel; no lo confunde con CHAR.
- El inventario de 18.302 fórmulas no es una prueba de ejecución de todas las
  ramas. Las pruebas cubren ecuaciones independientes, AST de funciones copiadas,
  semántica escalar/array, regímenes, estado persistido, integración real del
  servicio y renderizado. No se ejecutó Excel ni un backtest económico.

La comprobación de navegador usa una página local con datos sintéticos,
separada de producción. Ambos paneles coinciden y limpian la estructura anterior
si la API falla. El día del despliegue es sábado: la comprobación operativa
esperada es `CALENDAR_CLOSED/WEEKEND`, no un snapshot vivo fabricado.

## Evidencia de validación

- Suite focal de contratos, fórmulas, servicio, web y volatilidad: **46 passed**.
- Ruff en los nuevos módulos escritos para esta adaptación: PASS.
- Compilación Python, sintaxis de ambos JavaScript y script de despliegue: PASS.
- Generación del kernel reproducible; los cuatro archivos recibidos se conservan
  byte por byte.
- Prueba del runtime instalado en `/opt/king-node-venv`: 47 filas, cero errores
  de cálculo/estado en el fixture positivo; pico de memoria 214.744 KiB,
  por debajo de `MemoryMax=512M`. Tiempo de proceso en esa comprobación: 16,91 s.
- Navegador local: 47 filas, mismo régimen en ambos paneles, sin desbordamiento
  horizontal y vaciado de detalles tras una respuesta no disponible.

## Reproducción

```bash
python scripts/sync_king_node_live_kernel.py
python scripts/export_king_node_workbook_reference.py \
  --workbook MASTER_KING_NODE_RECORD_V5.xlsx \
  --catalogue MASTER_KING_NODE_RECORD_V5_CATALOGO_COMPLETO_DE_FORMULAS.md \
  --output config/king_node_reference.json
python -m pytest -q tests/test_king_node_*.py tests/test_volatility_indices.py
```

Instalación y reversión: [KING_NODE_VPS_DEPLOYMENT.md](KING_NODE_VPS_DEPLOYMENT.md).
