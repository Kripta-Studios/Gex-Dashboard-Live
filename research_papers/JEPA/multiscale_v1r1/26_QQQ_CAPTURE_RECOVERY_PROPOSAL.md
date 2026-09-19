# Recuperación QQQ: una solicitud autorizada

Fecha: 2026-09-19. Estado: AUTHORIZED_SINGLE_REQUEST_NOT_EXECUTED.
Referencia: USER_QQQ_SINGLE_GET_20260919. El usuario respondió a la pregunta que
reproducía los límites de esta propuesta: «Autorizar esa única solicitud QQQ».
La autorización cubre una GET nueva y su auditoría, con los límites siguientes.

El piloto23 consumió el intento QQQ y quedó sin manifest. Prohíbe retries.
No se puede añadirle un sello retrospectivo a un cuerpo de completitud desconocida.
El usuario autoriza esta excepción y exige conservar el intento anterior intacto.

## Petición única autorizada

```text
method: GET
endpoint: /v3/option/history/greeks/first_order
symbol: QQQ
date: 20220801
expiration: 20220801
strike: *
right: both
interval: 1s
start_time: 09:30:00
end_time: 10:30:00
version: 1
format: csv
```

Usar únicamente el Terminal ThetaData ya configurado. No status request adicional,
no retry automático, redirect, fallback, segunda fecha, otro ticker o modificación
de servicio/licencia. Tope512MiB, deadline1200s, timeout inactivo120s, reserva20GiB
adicional a la respuesta. Root nuevo separado:
`D:/GexResearchArtifacts/multiscale_v1r1/qqq_ib_recovery_20260919_01`.

Publicar código/contrato antes de capturar y registrar la referencia a la
autorización del usuario. Conservar bytes, params, SHA, tamaños, tiempos y errores.
Cada byte recibido se escribe en streaming. Un fallo queda terminal para este
intento y no habilita otra solicitud.

## Verificación posterior

Reconstruir las60 barras y sus niveles IB con productor y auditor separados ya
publicados, usando esta respuesta nueva. Comparación exacta. Conservar la
reconstrucción por proveedor recibida ahora como tal, sin afirmar vintage2022.
Si pasa: PASS_RECONSTRUCTED_QQQ_IB_COMPONENT. No combinarlo con el intento23 como
si fuese su ejecución original completa ni borrar su cierre INCOMPLETE.

SPXW/SPY se referencian por los hashes que valide24; no se descargan de nuevo.
Esta recuperación no admite D1–D5, prior-close, todo el prefijo, walls ni payoffs.
Economía NOT_EVALUATED, original_vintage_verified=false,
historical_economic_admission=false, promoción false. No modelos de mercado,
órdenes, servicios, bots, systemd, web o VPS.

## Consumo y cierre de la autorización

Publicar este documento y el capturador antes de la GET. Pasar la referencia
`USER_QQQ_SINGLE_GET_20260919` al CLI y conservarla en el run manifest.
La primera llamada de transporte consume esta autorización, aunque termine en
error o interrupción. No relanzar, cambiar el root ni ampliar el presupuesto.
El cierre registra resultado, bytes, SHA, tiempos y auditoría en otro informe;
este documento conserva la especificación previa a ejecución.
