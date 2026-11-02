# Preparación de trayectorias weekly para revisitas de zonas

El productor y módulo spot pasan95pruebas sintéticas en attempt03, con compile0
y Ruff0. No se han extraído todavía valores reales ni calculado eventos o PnL.
Esta fase prepara cotizaciones del mismo contrato weekly en D/D1/H2 y spot
observado, para estudiar después las revisitas IB/Fibonacci/walls propuestas por
el usuario. La rentabilidad de esa hipótesis sigue sin evaluar.

La receta causal conserva selección10:30,3240contratos previstos y9720segmentos;
no selecciona por10:35 ni por futuro. Spot previsto1086570filas/2790identidades,
2772disponibles+18missing, incluyendo24SHORT. Los inventarios históricos contienen
488996866filas de opciones: el código valida por batches y escribe por fuente,
sin acumular toda esa población en memoria.

Builder b6528622/tests ea5c7d0b; spot0953d344/tests80d91442. Reviews finales
b53b88a4/22100448. Suite: pytest PID47368 exit0 retenido12:22:30.119950UTC,
95PASS en1,35s; receiptfcc9aabf079747499d2aac231b6ceb6763a644e12525d741e58b4d41cef1c02a.
CPU0, diez variables1, CUDA=-1 y gates RAM/commit/disco superados en cada etapa.
Attempt01 F401 y attempt02 fixture09:30 frente aselector10:30 se conservan;
ambos cambios fueron sólo de tests y el código productor permanece intacto.

Archivo `weekly_zone_event_value_path_fixture_archive_01`:80copias exactas,
997692B;82archivos incluyendo manifestf4fae528 y recibo23d9473a. Root cotejó
fuentes y destinos completos, sin diferencias, con orden POSIX explícito.

Binding758c8afc/launcher93292a27 revisados para un run tras publicación exacta.
El auditor independiente está en pruebas: todavía no tiene PASS de suite ni
run de valores. Su compilefallido01 y Rufffallido02 están preservados; las
correcciones son sintaxis de ruta e imports/estilo, sin cambiar la ciencia.

Goal activo. Progreso operativo: extractor probado y paquete real revisado.
No hay selección, promoción, modelo rentable estable ni nuevo resultado económico.
