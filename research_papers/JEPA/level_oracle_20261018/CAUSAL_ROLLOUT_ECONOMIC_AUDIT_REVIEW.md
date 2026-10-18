# Auditoría económica del rollout causal — revisión y ejecución

## Cierre real: PASS dado scores sellados

La ejecución única terminó con exit 0 el 18-oct-2026 a las 20:58:32,851 UTC.
Estado exacto: `PASS_INDEPENDENT_CAUSAL_ROLLOUT_ECONOMIC_AUDIT_GIVEN_SEALED_SCORES`.
Artefacto: [audit.json](D:/GexResearchArtifacts/level_oracle_20261018/causal_rollout_v1_economic_audit/audit.json),
SHA256 `6dd69574ed50a5d3d26587b488b347874c40908d55ff8d8b19d2a95d9c581cd3`.

Se reconstruyeron muestreo/IPW, escalas H1, Gπ/Aπ y firmas de entrenamiento:
teacher 372 días, 47.430×1.954; aprendices finales 1.119 días, 285.286×1.955.
Las seis políticas, intentos, fills, ledgers y resúmenes coinciden en 741 días
de validación y 363 días test disponibles. La selección `causal_residual__5`
y su freeze previo al test se reprodujeron; λ no entra en el PnL económico.
Los 33.786 artefactos retenidos pasaron el rehash terminal sin discrepancias.

Los umbrales residuales 0 y 5 cumplen participación en 741/741 días disponibles
de validación; los tres residuales cumplen 363/363 test disponibles. Siguen seis
ticker-días test NO_EVALUABLE, separados de cero fills observados. El calendario
es de sesiones completas, por lo que tampoco acredita las medias sesiones
excluidas. PASS técnico no significa rentabilidad: la política seleccionada
mantiene pérdidas y fallan sus tres gates económicos por ticker.

Alcance exacto: cero refits independientes, sin regeneración de predicciones y
sin recomputar features desde raw. Se verifica la matriz contra chunks sellados
y las firmas/procedencia, además de reconstruir targets y economía. No prueba
recepción observada ni paridad live. Tiempo interno 2.340,481 s; supervisor
2.346,600 s. Pico privado muestreado 593.711.104 bytes; RSS 2.702.786.560 bytes
incluye páginas de matriz memmap. Código y spec originales permanecieron intactos.

## Revisión previa preservada

Revisión previa a la auditoría real,18-oct-2026. Auditor original:
`audit_causal_rollout_economics.py`, SHA256
`3286a1bae8d2525129a608c0924b6124ad19af4d92974bd4b44f1d8c186ffd33`.
SpecSHA`01db9f7ddc5e7069f2e30af69abe035020292475cf13034977b9685fb074ddcd`.
23fixtures repetidas independientemente PASS en1,05s; RuffPASS. No se modificó
el auditor ni se inició su ejecución económica durante el productor vivo.

Autoridad del productor: runcontractSHA
`66ef48eca5aadca70726b1c66997c93dd513ebf7a32283e07e26fc7e3c129a9d`;
`CAUSAL_ROLLOUT_IMPLEMENTATION_REVIEW.json`, SHA
`0ca688d835814ac22ff9700b2b89861e0b52994e869dbfb5d269d7e7c89cfe9f`.
El launcher alternativo de recuperación de recursos fue contingencia no activada.

Comprobaciones leídas:

- h=0 al inicio; WAIT/NO_FILL avanzan un minuto conservando h, sin sustituir
  la acción fallida por otra del mismo estado. FILLED incluso negativo/cero
  cambia h a1 y bloquea hasta exit_i+1.
- Choices se reconstruyen exclusivamente por score/ID, umbral estricto y empate
  por menor action_id; ambos flags del teacher coinciden. Sus checkpoints
  preceden a los targets; el teacher completo precede a todos los choices.
- Gπ independiente evalúa la política fija por recurrencia memoizada, sin
  maximizar labels futuros. Aπ usa neto+continuación−WAIT; NO_FILL exactamente0.
  La penalización terminal−λ sólo pertenece al target, nunca al PnL económico.
- Muestreo top32 por franja e identidades completas, pesos IPW/día, duplicación
  h/mitad de peso, escalas premium H1, matrices frente a chunks y firmas de
  los tres fits. No refits ni reconstrucción independiente de features raw.
- Seis políticas, calendario completo y disponible, seis ausencias exactas de
  SPY/QQQ abril2026; NO_EVALUABLE separado de día observado sin fill. Selección
 2025 exige fill diario, puede ser nula, y freeze precede a cada score test.
- Neto/costes, PF, WR, drawdown, meses, TARGET/STOP/EOD y duración se reconstruyen
  dados scores sellados. El orden h0≥h1 es diagnóstico, sin corregir scores.

La ejecución real espera `validation_freeze.complete.json`, `test/summary.complete.json`,
`test/score_h_diagnostic.complete.json` y salida exit0 del productor. Root nuevo
previsto: `D:/GexResearchArtifacts/level_oracle_20261018/causal_rollout_v1_economic_audit`.
Un fallo se preservará; no habrá reemplazo silencioso del resultado.

Alcance: auditoría independiente de targets/muestreo/integridad y economía dados
scores. No prueba recepción histórica, paridad live, cotizaciones ejecutables en
tamaño real, expectativas futuras o rentabilidad. El universo conserva sólo
sesiones completas; un PASS técnico no acredita operar todos los días NYSE.
