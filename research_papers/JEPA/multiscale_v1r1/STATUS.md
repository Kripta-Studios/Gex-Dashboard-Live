# Piloto de fuente y backend real en curso


### Checkpoint 2026-09-18 — API revisada y piloto de fuente predeclarado

Autoridades: multiscale_v1r1/18_THETADATA_API_REVIEW.md y 19_THETA_SOURCE_PILOT_SPEC.md.
El usuario confirma D:/ThetaData como única evidencia y remite a options_bulk.py
/script4_underlying_from_options.py para continuar con ThetaData. Terminal remoto
CONNECTED, diez GET de metadatos completados sin precios: 29 expiraciones ausentes
de 2022 no listadas; seis ticker-fechas de abril 2026 sí tienen fecha quote 0DTE.
Eso no admite sus archivos ni modifica el intento cerrado.

Capturador limitado a seis respuestas, parser y auditor independiente implementados;
11 tests focales/Ruff/compile PASS. Primero publicar código; luego piloto 20220801,
primer minuto Greeks 1s y OI, sin PnL ni reparación. Los 72 regresores reales del
fold sintético siguen ejecutándose; no declarar PASS antes del refit independiente.
Economía NOT_EVALUATED; promoción false; producción y raw anteriores intactos.
