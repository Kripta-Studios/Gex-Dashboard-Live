# CROSS_VENUE_CALENDAR_RR_LEADER_V1 — auditoría de paridad live

**Estado:** `NOT_LIVE_READY`

**Fecha:** 2026-07-17 Europe/Madrid

Auditoría solo de lectura de `services/realtime_feed.py`,
`bots/tradingbot_wrapper_jepa.py` y sus servicios systemd. No se modificó
producción. Este documento no autoriza implementación antes de superar la
secuencia económica 2024→2025→2026.

## Capacidades actuales reutilizables

- `realtime_feed` consulta cada 60 segundos SPXW, QQQ y SPY y conserva spot
  derivado de los tres subyacentes.
- Descarga cadenas 0DTE con first-order Greeks y quotes; el bot ya selecciona
  contratos por delta, compra al ask y marca/cierra al bid.
- `ai_bot.service` usa `--paper-order-intents`; no existe envío al broker.
- Ambos servicios cargan policy/registry con gate `production_live_ready` y el
  bot ya normaliza SPX→SPXW.

Estas piezas reducen el trabajo de integración, pero no prueban equivalencia
con calendar-RR.

## Mismatches bloqueantes

1. **Expiración back incorrecta.** `_compute_target_expirations` busca el
   vencimiento semanal de viernes. La feature congelada usa exactamente el
   menor `expiration > trade_date`, que puede ser la sesión siguiente. Weekly y
   next-expiry no son intercambiables.
2. **IV no equivalente.** `ENDPOINTS_0DTE/ENDPOINTS_WEEKLY` omite el endpoint
   `greeks/implied_volatility` porque first-order contiene un IV puntual. El
   research usa midpoint de `bid_implied_vol`/`ask_implied_vol`; no se puede
   sustituir por `implied_volatility` sin una nueva validación.
3. **No existe el estado t0→t1.** Los parquets `*_latest` se sobrescriben cada
   poll. V1 debe seleccionar CALL/PUT25 en 10:30, congelar esos cuatro contratos
   front/back y comprobar los mismos contratos a 10:35.
4. **Scheduler distinto.** El bot actual evalúa candidatos durante una ventana
   amplia y puede abrir según caps/cooldowns de otra policy. V1 requiere una
   única decisión diaria después de 10:35, entrada alrededor de 10:36 y mapping
   sincronizado QQQ←QQQ, SPY←SPY, SPX/SPXW←SPY.
5. **Payoff todavía no demostrado.** El runner predeclarado valida dirección
   sobre cash 10:36→13:36 con coste proxy. Eso no demuestra PF de una opción
   comprada al ask y vendida al bid. Antes de `production_live_ready` debe
   congelarse y pasar una traducción ejecutable a opción 0DTE, sin elegir delta,
   stop o salida mirando 2026.
6. **Persistencia/restart.** El estado de contratos 10:30 debe sobrevivir un
   restart 10:30–10:35 y quedar auditable junto con timestamps, expiraciones y
   keys. El estado genérico actual no contiene este contrato calendar-RR.

## Integración permitida solo después de PASS

Si la investigación supera 2024, 2025, 2026 y el payoff ejecutable:

- añadir `next_expiration=min(exp>today)` sin alterar el weekly usado por otras
  policies;
- consultar first-order y bid/ask-IV para front y next-expiry;
- implementar un builder compartido offline/live que congele t0 y emita a t1
  `signal_pressure`, sensor, action, source hashes y parity audit;
- añadir una policy/registry nuevos, no sobrescribir el paquete actual;
- hacer que el bot consuma una sola señal diaria exact-date y mantenga
  `paper_order_intents=true`;
- ampliar el validador para exigir paridad de feature, scheduler, selector y
  salida ask→bid;
- probar `py_compile`, suite focal, validador `--require-live-ready` y smoke de
  arranque de ambos servicios antes del restart VPS.

Hasta entonces no se modifican `realtime_feed.py`, `tradingbot_wrapper_jepa.py`,
systemd ni el paquete productivo.
