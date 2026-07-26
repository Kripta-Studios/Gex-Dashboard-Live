# KING NODE — volatilidad con ThetaData Options STANDARD

Esta implementación elimina la dependencia de endpoints de índices de ThetaData.

## Fuentes utilizadas

- `option/list/expirations`: selección de vencimientos SPXW y VIX.
- `option/snapshot/quote`: NBBO completo para reconstruir VIX1D y VVIX.
- `option/snapshot/greeks/first_order`: `underlying_price` robusto de SPX y VIX.
- `interest_rate/history/eod`: SOFR para el factor `exp(RT)`.
- `calendar/year_holidays`: reloj hábil de VIX1D.

No se consulta ningún endpoint directo de índices.

## Valores publicados

- **VIX**: mediana robusta del `underlying_price` observado en varias opciones VIX cercanas al ATM.
- **VIX1D**: réplica de la metodología de varianza de Cboe con dos cadenas SPXW, forward implícito, `K0`, alas OTM, corte tras dos strikes consecutivos con bid o ask cero e interpolación a 405 minutos hábiles.
- **VVIX**: misma familia de cálculo aplicada a dos cadenas VIX que rodean 30 días naturales.

Los valores VIX1D y VVIX se identifican como `reconstructed`, no como valores oficiales observados de Cboe.

## Estado fuera de mercado

Los snapshots de ThetaData pueden estar vacíos fuera de sesión. El servicio falla cerrado y publica `unavailable`; no reutiliza cadenas antiguas como si fuesen live. La única persistencia de fórmula es la varianza near-term de VIX1D durante la última hora permitida antes del vencimiento.

## Comprobación live

```bash
python3 scripts/check_thetadata_options_standard.py \
  --base-url http://127.0.0.1:25503/v3 \
  --json

python3 services/king_node_service.py --once

python3 scripts/check_king_node_health.py \
  --snapshot /var/lib/king-node/latest.json \
  --json
```

## Limitaciones

La reconstrucción usa el NBBO que entrega ThetaData y SOFR. Puede diferir del índice oficial Cboe por la fuente exacta de quotes, reglas operativas intradía, calendario y curva de tipos. El snapshot conserva diagnósticos suficientes para auditar forward, `K0`, strikes incluidos, varianzas, vencimientos y tipo aplicado.
