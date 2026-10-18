# Ejecución del diagnóstico modelo–oracle

La ejecución empezó el18-oct-2026 a19:16:55 UTC, PID16112. Código y plan se
congelaron después de8fixtures PASS y Ruff. Root:
`D:/GexResearchArtifacts/level_oracle_20261018/oracle_model_diagnostic_v1`.
Runtime: `oracle_model_diagnostic_v1_runtime`.

Orden fijo:741ticker-días VAL2025 con scores existentes; después96ticker-días
TRAIN seleccionados por hash, cuatro por ticker×trimestre2023–2024. La lista
se publica antes de leer outcomes/inferir. No hay fits, GPU, test nuevo,
umbrales nuevos ni modificación del experimento de episodios. Autoridad de
entrada: freeze y validación sellados, modelos y predicciones verificadas.

Cada día genera dos tablas de estados, tabla temporal, scores TRAIN si procede
y marker `ticker_fecha.complete.json`. El marker vincula fuentes, outputs,
código/plan/modelos y clave del día. Se publican archivos atómicamente. Una
interrupción antes del marker conserva parciales y permite repetir sólo ese día;
un día completo con hash alterado falla cerrado. El lock del sistema operativo
impide dos escritores. Después de comprobar que el proceso anterior terminó:

```powershell
python -u research_papers/JEPA/level_oracle_20261018/diagnose_oracle_model.py `
  --root D:/GexResearchArtifacts/level_oracle_20261018 `
  --output D:/GexResearchArtifacts/level_oracle_20261018/oracle_model_diagnostic_v1 `
  --resume
```

Conservar los logs del intento anterior en su runtime. Los agregados de un
periodo interrumpido se reconstruyen desde checkpoints completos; no se cambia
la muestra ni el análisis según resultados. Una identidad distinta o corrupción
no autoriza recomputar silenciosamente un día completo.

La redirección PowerShell puede retener stdout en un buffer. El avance real se
mide por markers diarios y por `progress.json/resources.jsonl`, escritos cada30s
por `observe_oracle_diagnostic.py`, observador externo de sólo lectura que
comprueba PID, creación y comando. Sus picos son desde que empezó la observación,
no una medición retrospectiva exacta del máximo durante el arranque.

TRADE en las categorías significa elección/intento; `_filled` distingue ejecución
y NO_FILL. Estados libres del modelo y del oracle se mantienen separados; los
resultados de todos los estados no constituyen una cartera simultáneamente
ejecutable. La suma de regret en la trayectoria del modelo se comprueba contra
el gap de PnL realizado, pero el oracle conoce el futuro: no representa expectativa
causal alcanzable. Timing±1/2/5 compara sólo contrato, centros y band idénticos,
separando estados de fill; es hindsight descriptivo y no una política operable.

El primer proceso cerró con error después de publicar los741checkpoints VAL,
al escribir únicamente el parquet agregado de timing: los flags `original_fill`
y `shifted_fill` mezclaban booleanos,0/1float y NaN entre días. El traceback y
outputs parciales se preservan. No se alteró el productor congelado.

La continuación técnica `resume_oracle_diagnostic_dtype.py`, revisada por root
y con2fixturesPASS/RuffPASS, reemplaza exactamente una llamada de serialización
agregada. Valida que esos dos campos sólo contienen bool/0/1/null y los escribe
como booleanos nullable sobre una copia; no cambia orden, otras columnas,
cálculos, scores o selección. Reutiliza los741días sellados y después ejecuta
las inferencias96TRAIN previstas, sin fits. El runtimev2 empezó a19:50:05,644UTC,
PID6228; guarda autoridad de revisión, código, proceso, logs y monitor externo.

```powershell
python -u research_papers/JEPA/level_oracle_20261018/resume_oracle_diagnostic_dtype.py `
  --root D:/GexResearchArtifacts/level_oracle_20261018 `
  --output D:/GexResearchArtifacts/level_oracle_20261018/oracle_model_diagnostic_v1 `
  --previous-runtime D:/GexResearchArtifacts/level_oracle_20261018/oracle_model_diagnostic_v1_runtime
```

El informeVAL separado se construyó desde los741checkpoints diarios completos,
reverificando hashes; no necesitó inventar un marcador de cierre del productor.
`ORACLE_MODEL_VALIDATION_DIAGNOSTIC.md` y sus CSV incluyen calibración de scores
sólo en trades realmente ejecutados y comparación de barreras/hold con la
trayectoria oracle. El informeTRAIN+VAL se publica aparte al completar ambos.

La continuación terminó exit0 con741VAL+96TRAIN y5509fuentes rehasheadas;
`COMPLETE_DESCRIPTIVE_ORACLE_MODEL_DIAGNOSTIC`, cero fits. Tiempo interno del
wrapper123,876s. SummarySHA74f955f535e9a26cb85f281a8bc78c1405767e85219a1fc51262c0630372b6ad.
El informe completo es `ORACLE_MODEL_DIAGNOSTIC_RESULT.md`, conCSV de cohortes,
calibración, señales y timing. Los agregados originales permanecen en sus roots;
el informe no selecciona una corrección o política nueva.
