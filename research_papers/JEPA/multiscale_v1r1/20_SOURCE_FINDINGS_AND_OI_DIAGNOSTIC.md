# Hallazgos del piloto y diagnóstico offline de OI

El piloto 19 terminó: seis respuestas HTTP preservadas; auditor independiente
PASS_INDEPENDENT_SOURCE_PILOT_AUDIT. Esto reproduce los diagnósticos, no da admisión
histórica. Los tres Greeks del primer minuto pasan schema/identidad/reloj. SPXW
tiene 326 observaciones iniciales cero/invalidas y primer precio positivo a
09:30:01. SPY/QQQ no presentan esos ceros. No hay duplicados ni dependencias del
subyacente posteriores a la quote en esas tres respuestas.

OI contiene timestamps posteriores a 09:30: SPXW 16/324, SPY 24/306 y QQQ 12/236.
Los últimos timestamps llegan a 17:30:29, 16:40:26.666 y 16:40:22 respectivamente.
Las tres respuestas FALLAN el chequeo de que todo su OI esté disponible antes de
la apertura. No se cambia este resultado ni se vuelve a consultar otra fecha.
No se han calculado walls, features, labels o PnL sobre estas respuestas.

El script4 usa el close de la propia barra al reparar parcialmente OHLC, cuando
ese close es válido. Por eso el primer precio positivo a 09:30:01 **no** demuestra
que ese sea el valor usado en una reparación original. Para una reproducción
se necesitaría el origen del close de la barra y su disponibilidad al terminar
el minuto, además de saber qué transformación produjo cada archivo antiguo.

## Siguiente lectura offline fijada antes de ejecutarla

Solo las seis respuestas ya selladas, verificando hashes antes de parsear. Sin
red ni captura adicional. Se hará un join exacto por símbolo/expiración/strike/
derecho para contar: OI temprano/tardío, OI cero/positivo, contratos presentes en
Greeks del minuto y contratos con al menos una quote válida bajo el predicado
**ya existente** de levels.py (IV en (0,2), bid>=0, ask>0, ask>=bid, finitos).
No calcular exposiciones, niveles, scores, payoffs ni elegir acciones o fechas.

El informe distinguirá registros tardíos de contratos que podrían participar en
una wall. El builder sintético ya exige OI positivo y disponible antes de abrir;
se contrasta ese requisito, sin introducir una exclusión nueva ni convertir el
piloto fallido en PASS. Una segunda implementación con csv/Decimal reconstruirá
los mismos conteos. No imputar OI cero ni mover timestamps a 06:30.

Root de diagnóstico nuevo:
D:/GexResearchArtifacts/multiscale_v1r1/theta_oi_diagnostic_20260918_01.
Economía NOT_EVALUATED. Recibir hoy un archivo histórico no demuestra recepción
original ni ausencia de revisiones del proveedor; no se concede promoción.
