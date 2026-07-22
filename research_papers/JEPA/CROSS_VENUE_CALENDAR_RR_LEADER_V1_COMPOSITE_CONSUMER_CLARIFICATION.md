# CROSS_VENUE_CALENDAR_RR_LEADER_V1 — composite consumer clarification

Status: `FROZEN_PRE_OUTCOME`

Fecha: 2026-07-22 Europe/Madrid. Esta aclaración se congela después del seal
outcome-free V1R1 y antes de leer retornos 2024, 2025 o 2026. No cambia señal,
mapping, clocks, expiraciones, selección 25-delta, frecuencia, horizonte,
costes ni gates económicas.

## Autoridad de fuente

El único sidecar admisible pasa a ser el composite inmutable:

```text
D:/ThetaData/cross_venue_calendar_rr_native_clock_2024_2025_v1r1_composite
```

Identidad exacta:

- commit de sellado: `963f91c9fde298a8820e7dafa55c625f1220f88f`;
- `seal.json` SHA-256:
  `5b97ebc5fc867e06ef51d0fcd2956a48a4c06d2291828f5e3ca0e8ae1c9cf84f`;
- composite contract:
  `68714d77ec693028f61b3cf08396ff896ff2415c24f7c21f169872916fd8c046`;
- capture index:
  `e5a669b7bf5fc17ac1dff62284b9d5c63751554812c0085cf23fc089f1943a0e`;
- ticker-year summary:
  `41deb0149075908052bfaf8f6069b10ae55760e8cf21639251a5e9fe6cf6df65`;
- universe:
  `98d416ea810c5bde657b6c23a9d7c599885d5eedfef3e332cd1885f6ddee45f4`.

El seal cubre 3.012 captures/1.506 ticker-sessions: 3.008 `V1` y cuatro
`V1R1_REPAIR`, con 2.415.402 keys compartidas, ocho unilaterales audit-only y
cero shared faltantes. Los blobs compactos committed deben coincidir byte a
byte con el root local antes de consumir una captura.

## Resolución multi-root

Auditor y builder deben resolver cada captura exclusivamente mediante las
columnas selladas `storage_generation` y `storage_root` del capture index. No
pueden reconstruir una ruta suponiendo un root único, copiar los cuatro repairs
dentro de V1 ni modificar ninguno de los dos roots.

- `V1`: revalidar con contrato/runtime/code hashes originales.
- `V1R1_REPAIR`: revalidar con contrato/runtime/code hashes, endpoint, request
  params y source provenance del overlay.
- Cualquier generación, root, capture ID o hash adicional falla cerrado.

El inventario económico continúa leyendo Greek/IV vintage y underlying exacto
10:30/10:35. El sidecar solo certifica option timestamp/key. Raw, parquet y
manifest nativos se rehashean, pero sus valores no sustituyen delta/IV/bid/ask.

## Semántica Greek/IV

Para las 3.008 capturas V1 se conserva igualdad exacta de key-set Greek=IV; una
sola diferencia nueva invalida el gate. Solo los cuatro IDs predeclarados pueden
usar `Greek ∩ IV`:

| Capture ID | Greek-only rows | IV-only rows | Shared rows |
| --- | ---: | ---: | ---: |
| `4b5b53cd7bce4944364d631d` | 0 | 2 | 406 |
| `839ad0588cc9ee1309cd8c6f` | 2 | 0 | 706 |
| `207459dd60dbfe7dd06da8cf` | 0 | 2 | 858 |
| `8993033a23f2068d7a25d3c2` | 0 | 2 | 858 |

Los conteos incluyen ambos clocks. Las ocho rows unilaterales no certifican
features, no seleccionan contratos y deben aparecer en auditoría. La respuesta
nativa debe certificar todas las shared keys; sus extras siguen audit-only.

## Outputs y secuencia

El full auditor debe versionar el contract/seal/index composite y resumir por
generación, incluida la exclusión unilateral. El data gate debe persistir en su
capture revalidation las columnas multi-root y los conteos shared/unilaterales,
además de hashear todas las fuentes físicas.

Secuencia única:

1. commit/push de esta aclaración;
2. implementar y testear auditor/builder composite-aware;
3. commit/push del código antes de ejecutar;
4. full audit offline → commit/push de compactos;
5. data gate outcome-free → auditoría independiente → commit/push;
6. frozen runner committed → único outer 2024.

No abrir outcomes, no excluir los cuatro días y no tocar live/systemd durante
esta compatibilidad de fuente.
