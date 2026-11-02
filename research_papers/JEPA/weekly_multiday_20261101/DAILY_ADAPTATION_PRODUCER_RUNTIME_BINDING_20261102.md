# Binding del productor de adaptación diaria

Este binding fija la única ejecución científica del productor DAILY. Compara
`FROZEN_CONTEXT182`, `MONTHLY_RAW`, `WEEKLY_RAW` y `DAILY_RAW` sin cambiar la
receta, los costes, el riesgo, los candidatos ni el criterio mensual. Reutiliza
42 estados sellados y ajusta exactamente 136 estados nuevos. Todo 2026 sigue
siendo `SEEN_DEVELOPMENT`; no se selecciona ni promociona ninguna política.

## Bytes ejecutables y evidencia previa

- `evaluate_weekly_daily_adaptation.py`, 38.763 bytes, SHA256
  `536a581d8295362b3374dd8c5db2224095f8afe66c5b0e9ae895cf08b18d4f2e`.
- `test_evaluate_weekly_daily_adaptation.py`, 14.142 bytes, SHA256
  `fa199a2a6339cf73911cc6f818c73f655cce1931e222733c041bff82b23e661e`.
- `DAILY_ADAPTATION_CONTRACT_20261101.md`, SHA256
  `5d388e484435c8fe23d40476c02928887c6ab5487af62197e5e74f08c1fe0047`.
- `DAILY_ADAPTATION_CONTRACT_REVIEW_20261101.md`, SHA256
  `bd0f514610c6d93167924aef651a2edf66e2d31c281e4be1fe0325ccd87eb841`.
- `DAILY_ADAPTATION_PRODUCER_FINAL_REVIEW_20261102.md`, SHA256
  `776ff783139386cee75fa6aa3bb4e0f75d74743c605fefb9d2aa373d5b720326`.
- `daily_adaptation_preparation_archive_02/archive_receipt.json`, SHA256
  `9eea35e9a13ad47653d714fd67059473341b5de2a656a71fd0415012b979f6e8`.
- Recibo de fixtures dentro del archivo, SHA256
  `0dbd6c8600037fb2f9b1054f19c2ec67a1eb65ec1f8f2ce3134c768b72d9bbfd`:
  compile, Ruff y 18 pruebas exit0; no runtime científico.

Dependencias científicas exactas:

- `evaluate_weekly_context_adaptation.py`:
  `d03494bf68e281bc7c9e68f385aa111567eac4206cf5b44133e17bb480ed5df8`.
- `evaluate_weekly_context_models.py`:
  `bdc6534f059ade7acc58f23952a88ed2068c7a712518b04f438945a583a07a2f`.
- `evaluate_weekly_h2_ev_v2.py`:
  `8a9e75855d542a12662e5c812583f2ef86042f5c3ae1bbbad73c16042e063476`.
- `replay_equal_risk_frozen.py`:
  `e4f42a9fa65120939cf5e131911c8f2990a9cd33d21ae036fa98d9eb816d5b9d`.
- Helper oficial de recursos:
  `3cfe55a6a2926007d91d44215c8a7c0a28801efaca189fcf306c275e352ed046`.

Autoridades externas cerradas:

- Adaptación upstream manifest
  `e8cf5cd4a001cd98cdf29e54cf47bbdf3c34d6652abf34ef7c71fffa0bd97f23`,
  audit04 `9a487fba18504ae4faff2c1dba17d1c000eb237436a09a7fe22747e328cb307a`
  y exit0 `5d59d1a3978d8d9aa31c7c3fab567d1ae7e901494aa8efb12377ca65f91de420`.
- Puente junio/julio manifest
  `9d1455c601ac38224c4f56365f20c3fb31978e997f8652454dbc69807e0abb86`
  y auditoría
  `83c9ade0b6b7205484dd275df8593107238f94468d8564f7351e9481a475033c`.
- Criterio mensual
  `806f7728a2ad434bc08929d3715f307455bd37862ae4c19a2cd2cc1d64a5ee5b`.

## Comando y raíces exclusivas

El launcher ejecuta con lista de argumentos:

```text
python -X utf8 -u evaluate_weekly_daily_adaptation.py
  --execute-reviewed-daily-adaptation
  --output D:/GexResearchArtifacts/weekly_multiday_20261101/h2_daily_adaptation_01
  --contract-sha256 5d388e484435c8fe23d40476c02928887c6ab5487af62197e5e74f08c1fe0047
  --implementation-sha256 536a581d8295362b3374dd8c5db2224095f8afe66c5b0e9ae895cf08b18d4f2e
  --tests-sha256 fa199a2a6339cf73911cc6f818c73f655cce1931e222733c041bff82b23e661e
  --review-sha256 bd0f514610c6d93167924aef651a2edf66e2d31c281e4be1fe0325ccd87eb841
```

Las únicas raíces nuevas son `h2_daily_adaptation_01` y
`h2_daily_adaptation_observer_01` bajo
`D:/GexResearchArtifacts/weekly_multiday_20261101`. Ambas deben estar ausentes.
No se permite resume, adopción de parciales ni retry automático.

## Admisión y cierre

Antes de crear el hijo, el launcher exige que HEAD local sea igual al remoto de
`research/multiscale-v1r1-net-usd`; cada miembro del paquete debe ser byte a byte
igual a `git show HEAD`; y todos los hashes internos y externos deben coincidir.
También exige exit0 upstream, CPU[0], ocho variables de threads a1 y observación
oficial contemporánea con RAM disponible y free commit mayores o iguales a2GB.
La observación se persiste antes del gate, incluso si rechaza.

El productor vuelve a aplicar el gate antes de cada uno de los136fits, guarda
FIT_START/FIT_COMPLETE y cada estado completo. Una interrupción preserva
evidencia pero no autoriza continuar. El launcher usa Popen oculto con argumentos
en lista, persiste PID/creation/comando antes de esperar, conserva el handle y
siempre ejecuta `wait()` después de crear el hijo, incluso si falla la lectura de
metadata. Registra stdout/stderr y exit final.

Un cierre candidato requiere exit0 retenido, manifest,178planes/agenda,
42reutilizados,136estados nuevos y272eventos de journal,2448scores y ocho libros,
además del rehash final de inputs. No se abrirán ni interpretarán resultados
económicos antes de preparar y publicar un binding auditor concreto. PASS del
productor no equivale a auditoría independiente ni a rentabilidad.

Este binding y su launcher sólo pueden usarse después de revisión independiente,
commit y verificación remota exacta. No toca API, bróker, VPS o producción.
`technical_ready=false`, `promotion_approved=false`, selección nula.
