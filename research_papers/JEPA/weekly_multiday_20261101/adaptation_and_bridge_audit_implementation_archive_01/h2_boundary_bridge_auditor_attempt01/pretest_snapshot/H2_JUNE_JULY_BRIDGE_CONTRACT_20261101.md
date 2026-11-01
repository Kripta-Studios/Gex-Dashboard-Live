# Puente H2 entre junio y julio para evaluación continua

La autorización de reentrenamiento mensual/semanal exige un universo continuo.
La división histórica H1/Q3 dejó seis filasjunio29/30×SPY/QQQ/SPXW fuera del
horizonte. Este contrato reconstruye sólo esas filas, antes de nueva economía.
No cambia reglas, fuentes originales, modelos o resultados cerrados.

Raíces D:/GexResearchArtifacts/weekly_multiday_20261101:
h2_dataset_v2_01 manifest bfc7370f38e32e1209bc41fe72f01563dcdaa17ddf86fe7b625814beedcbe1d8;
h2_dataset_v2_extension_2026q3_partial_01 manifest b45b017c63fea42036ab73418cc07faa8e377047fec1f8d60c908e98eea5400b.
Verificar sus payloads coverage/candidates antes y al cierre. Sus calendarios
se unen por ticker/date, sin colisiones:2790filas/930sesiones20230103–20260917.
Autoridad H1 index7124d98155eae8ee5ae06457377570278d4059defe2cf02340e34c288fcb60b4;
Q3calendarJSONac9bd2569d91e9bd9b0475d6f5e2d5400b2816cc1d1d0d9ec98c69e4dbe2e72b,
parquete16ef041efadc0f6914585540e19e9c04fcb05f1597952137e4f5bcf06de8c78,
manifest5a530747f2c97704869d87c04d09bba3cc00125f38a8a78454c2d459a2ea502c.

Nuevo wrapper build_weekly_h2_boundary_bridge.py importa sólo funciones puras
del builderV2 ec19e2c9066f0bb6103526ccf30a5b156c69a25a96349220d9fd680a92822945
y sourcepilot ad5b3ffba4e125ca7fcb4d5b0789eec601ace55be3740813d46374827766c878.
Contratos245a6df1530fbabf29e6a2e5e86662972ebdc680e011987253f35eb61257d5d5
yclockamendment9210c6e50094e5745f80c5e03f577f6bd673263f84d3c3ef764ad76b22ca56eb
permanecen intactos. WrapperQ3 a29a72cbd6afeb5d87a05ef5b9908bd0c40514bd6eee0a17c736e5da103b97df
es referencia estructural, no dependencia científica necesaria ni permiso para
abrir sus modelos/outcomes auxiliares. No mutar globals ni ejecutar mains.

Planner usa calendario mínimo[20260629,20260630,20260701,20260702] idéntico
al segmento completo para cada ticker. Retener sólo entradasjunio29/30;
exigir que las seis filas originales eran HORIZON_OUTSIDE_CALENDAR sin IDs.
Junio29→julio1; junio30→julio2. Selección original de serie1–8DTE con
exit_date<expiration y menor vencimiento elegible. Metadata ya observada:
junio29 elige expiry20260702, tresPLANNED; junio30 tresNO_SERIES porque el
único expiry1–8DTE coincide con su salida. No eliminar junio30 del universo.

Fuentes nominales acotadas a seis rutas:
D:/ThetaData/data_options/{SPY,QQQ,SPXW}/greeks/2026/06/{T}_20260702_20260629_greeks.parquet
y ./greeks/2026/07/{T}_20260702_20260701_greeks.parquet.
Cuatro presentes (tresentradas+salidaSPXW), salidasSPY/QQQ ausentes. No abrir
archivosjulio2 ni entryjunio30: no hay serie elegible. Cambios deexistencia,
selección, calendario o universo respecto al inventario externo hacen fallar.

Fase1 metadata: verificar autoridades, rutasplain/sinlinks/aliases, rehash,
schema/rows/reloj de las cuatrofuentes presentes y nulos explícitos para las
dos ausentes. No leer valores de columnas. Guardar calendario unido/segmento,
seis planes, inventario path/bytes/SHA/identidad física ymetadata. Publicar
manifest real e inventarioSHA después del cierre/revisión antes deextraer.
Output nuevo h2_boundary_bridge_01; inicial sólo inventario yrecibo. Noresume.

Fase2 una extracción: admitir inventarioexterno, importar ec19/ad5 verificados
antes/después, build_candidates sobre los seis planes sin cambios. Misma
políticadelta0,50/ask válido<=49,95, decisión10:30 yquotes10:35, relojV2,
escenarios5/costes0,01/0,02+1,30porlado. Salida faltante sólo se vuelve cota
conservadora si se obtiene un candidato real; no inventar su existencia.
El SHA de calendario guardado ensource_pins liga el calendario unido sellado.

Guardar coverage_overlay.json con seis filas finales, candidates.jsonl nuevos,
metadata declocks, inventario ymanifest. IDs únicos, sin colisión con3234previos;
se conservan los seis planes, incluidos NO_SERIES. Rehash fuentes/códigos/
autoridades/copies al cerrar. Flags fit/economic_evaluation/promotion false.
No sobrescribir ni reetiquetar datasetH1/Q3.

Auditor separado, sin importar wrapper: verifica universo/cadena/slots/source
pins, reproduce construcción desde mismas funciones congeladas ec19/ad5 y
compara campos exactos deoverlay/candidatos/clocks; no representa un segundo
parser raw independiente. Verificar también que aplicaroverlay cambia sólo
seis coverage IDs y añade sólo IDs nuevos, preservando3234candidatos originales
y2790coverage IDs. No declarar economía o modelo auditados con este PASS.
Root fijará manifest concreto delpuente ysu audit enbinding walk-forward.

Fixtures antes del real: segmentoH2, regla pre-expiry/NO_SERIES, seisplanes,
missing exit realvsnocandidato, colisiones ysuperposición, clocksV2, alteración
fuente/inventario/código,symlink/alias,destino ocupado yoriginales inmutables.
Código/tests/revisión ybinding publicados antes de cada fase real. CPU0/seis
variableshilos1,gateRAM/commit2GB contemporáneo,logs/handle retenido; fallos
preservados sinretryautomático. SóloD:/ThetaData local, sinmarketAPI/producción.
SEEN_DEVELOPMENT,goalactivo,promociónfalse.
