# Piloto de admisión ThetaData — seis capturas limitadas

Autoridad: el usuario pide continuar la investigación, confirma que D:/ThetaData
es toda la evidencia existente y permite revisar la API por si es necesario
descargar datos adicionales. La revisión 18 identificó la dependencia concreta.
Este piloto de fuente es el siguiente paso de esa continuación: no es una
evaluación económica, una reejecución V1R1 ni una reparación de sus artefactos.

Seis GET, sin retry, fallback, cambio de licencia o compra. Terminal remoto ya
configurado y comprobado CONNECTED. No se inicia ni reconfigura ningún servicio.
Fecha fija 2022-08-01, seleccionada como primera sesión del intervalo, no por PnL.
Tickers SPXW/SPY/QQQ, expiración 2022-08-01, strike=*, right=both, format=csv.

1. `/option/history/greeks/first_order`: interval=1s, start_time=09:30:00,
   end_time=09:31:00, version=1. Tres peticiones.
2. `/option/history/open_interest`: mismo ticker/fecha/expiración; sin intervalo
   ni relleno. Tres peticiones. Se examina el timestamp reportado, sin asumir que
   todos los registros llegaron a las 06:30.

`version=1` es una convención explícita solo de esta prueba técnica. No acredita
igualdad con los archivos antiguos ni se introduce en una política histórica.
Se preservan valores por defecto no especificados como parámetros del proveedor;
no se afirma conocimiento de su versión histórica. Ver documentación enlazada en 18.

Root nuevo: D:/GexResearchArtifacts/multiscale_v1r1/theta_source_pilot_20260918_01.
Conservar cuerpo íntegro, URL/parámetros, HTTP status, timestamps locales de request
y recepción, SHA256 del cuerpo/código/contrato y headers no sensibles. Máximo
128 MiB por respuesta. Una respuesta truncada/fallida nunca es una fuente admitida.
Los errores HTTP se preservan y no se reinterpretan como falta de contratos.
Hash y parser consumen los mismos bytes capturados; no sobrescribir evidencia.

Validación de admisión, sin labels/features del modelo: schema explícito, identidad
de símbolo/expiración/derecho, timestamps locales NY, duplicados nativos, tiempo
del subyacente no posterior a la quote, precios iniciales cero/invalidos y primer
instante válido. No eliminar filas, resamplear, hacer bfill/ffill ni reparar precios.
OI: claves contractuales únicas, conteos, timestamp mínimo/máximo y precedencia
respecto de 09:30. Su significado como posición al cierre previo procede de la
documentación; la recepción original del mensaje no se inventa.

Una segunda implementación audita identidad, reloj, ceros, duplicados y checksums
desde las copias. PASS del piloto solo certifica ese alcance técnico de seis
respuestas actuales. No demuestra igualdad con la fuente perdida, ausencia de
revisiones del proveedor, admisión de toda la sesión/IB/histórico o paridad live.
El único minuto inspeccionado antecede a todas las decisiones contractuales;
no se calculan acciones, scores, PnL, payoffs ni métricas de rentabilidad.

Implementación/tests y este alcance publicados antes de enviar las peticiones.
Si falta permiso de acceso o falla el schema/reloj, conservar el resultado preciso
y no ampliar descarga ni relajar validación. Economía NOT_EVALUATED, shadow
NOT_STARTED y promotion_approved=false.
