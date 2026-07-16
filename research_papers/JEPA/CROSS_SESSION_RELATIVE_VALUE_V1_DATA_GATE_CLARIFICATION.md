# CROSS_SESSION_RELATIVE_VALUE_V1 — aclaración de data gate

**Estado:** `FROZEN_PRE_OUTCOME`

**Fecha:** 2026-07-17 Europe/Madrid

La predeclaración excluye `2023-06-05` como día de trade porque las tres barras
SPY 09:54–09:56 con envelope inválido caen dentro de la ventana que termina a
10:34. El mismo día contiene un close RTH 16:00 válido y es la sesión de mercado
inmediatamente anterior a `2023-06-06`.

Esta aclaración fija antes de ejecutar el ledger real:

- `2023-06-05` nunca produce señal, acción, fill ni PnL;
- el loader exige que las únicas filas con envelope inválido de todo el scope
  sean exactamente SPY 09:54, 09:55 y 09:56 de esa fecha;
- esas tres filas no se imputan, corrigen ni consumen;
- el close SPY/QQQ/SPXW 16:00 de `2023-06-05` sí puede actuar como `prior_close`
  de `2023-06-06`, preservando la sesión inmediatamente anterior;
- cualquier fila inválida adicional, falta de grid o valor no finito aborta;
- universo, señal, reloj, coste, payoff, fases y gates no cambian.

Esto resuelve una ambigüedad de procedencia conocida sin consultar el retorno
10:36→13:36 de ningún día.
