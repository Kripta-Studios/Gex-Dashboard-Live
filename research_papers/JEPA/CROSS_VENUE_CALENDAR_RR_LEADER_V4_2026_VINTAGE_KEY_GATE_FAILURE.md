# CROSS_VENUE_CALENDAR_RR_LEADER_V4 — fallo cerrado del gate vintage 2026

**Congelado:** 2026-07-22 Europe/Madrid, después del PASS development V4
auditado y antes de cualquier captura nativa, feature u outcome 2026.

## Resultado

`FAILED_V4_2026_VINTAGE_KEY_PARITY_CLOSED`.

El censo outcome-free enumeró solo los sensores congelados QQQ y SPY. Ambos
tienen 127 sesiones con front0DTE y siguiente expiry comunes Greek/IV entre
2026-01-02 y 2026-07-15: 254 sesiones sensor y 508 parejas front/back. Cada mes
completado conserva capacidad (enero20, febrero19, marzo22, abril18, mayo20,
junio21 por sensor); julio MTD contiene7.

Se leyeron exclusivamente las claves vintage a los relojes 10:30/10:35 mediante
el normalizador ya versionado `read_vintage_targets`. No se leyó ningún valor
underlying 2026, open10:36/13:36, retorno, label, outcome o dato live. No hubo
consulta de red ni captura native-clock.

Resultado de las 508 comparaciones:

| Capture | Greek-only | IV-only |
| --- | ---: | ---: |
| QQQ 20260624 front 20260624 | 80 | 0 |
| QQQ 20260626 front 20260626 | 0 | 28 |
| SPY 20260624 front 20260624 | 12 | 0 |
| SPY 20260625 front 20260625 | 0 | 484 |
| SPY 20260626 front 20260626 | 0 | 4 |
| **Total** | **92** | **516** |

Las otras 503 capturas tienen igualdad de claves. Shared rows totales391.556;
digest lógico de counts por captura
`d7c9b4707f5d094f4b570e0bceeb6bdbe80af30503e6d0e70d4fd43e1e28f68e`.

## Decisión obligatoria

La predeclaración V4 conserva `Greek∩IV` exclusivamente para los cuatro repair
IDs V1R1 de 2024–2025 y ordena fallo cerrado ante cualquier quinta discrepancia.
Los cinco captures anteriores son IDs nuevos 2026; por tanto no se permite:

- usar su intersección para producir features;
- añadirlos a la whitelist V1R1;
- hacer fill, nearest, as-of, exclusión de fechas o recaptura current-provider;
- sustituir SPY por SPXW ni alterar QQQ←QQQ/SPY←SPY/SPXW←SPY;
- abrir outcomes 2026 para decidir una reparación.

V4 queda cerrada antes del data gate 2026. El buen development 2025 permanece
guardado, pero no autoriza 2026 ni producción. `services/`, `bots/`, `systemd/`
y paquetes live continúan intactos.
