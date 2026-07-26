# KING NODE SOFR hotfix

Corrige dos problemas:

1. El endpoint `/v3/interest_rate/history/eod` devuelve la fecha en `created`; el parser buscaba `timestamp`/`date` y descartaba todas las filas.
2. La ausencia de SOFR no debe impedir derivar VIX desde `underlying_price` de opciones VIX. Solo VIX1D y VVIX requieren el tipo de interés.

Archivos:

- `services/king_node_service.py`
- `scripts/check_king_node_health.py`
- `tests/test_volatility_indices.py`
