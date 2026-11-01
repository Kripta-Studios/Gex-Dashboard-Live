# Auditor independiente de modelos contextuales: revisión y ejecución vinculada

El productor único ya cerró exit0. Sus artefactos y resultado descriptivo fueron
publicados en ccd0df6c4b2c7ded2df3584bea57eb60ed20bcf8. Este binding permite
una auditoría de sus parámetros guardados; no permite repetir fits, cambiar
features, calibración, cantidades, decisiones o costes.

## Implementación revisada

audit_weekly_context_models.py:
3eb6b9795ad260971435259858f86d3c00111bcc141973faf986411d4a68ad99.
test_audit_weekly_context_models.py:
440bb092743511873d278caf8bed0e6a1f23509fb24352436a524a107a124679.
Contrato 8a535acd67ae36e6854ccf3aa02ab0f4f699c08be91bbeae5e17f7925e670ca4
y productor bdc6534f059ade7acc58f23952a88ed2068c7a712518b04f438945a583a07a2f
intactos. El auditor no importa productor ni sklearn, no hace fit ni abre raw.

Reconstruye matrices CATEGORY30 y CONTEXT182, splits y elegibilidad, mediana,
indicadores, media y escala TRAIN. Restaura coeficientes dados para inferencia,
reconstruye calibración CAL, probabilidades y EV con las medias congeladas,
seis libros de riesgo, métricas y bootstrap con candidatos elegibles. BASE18
reutiliza scores auditados y debe reproducir sus dos libros congelados. No se
reajustan coeficientes para comprobar el optimizador ni se reconstruye raw.

Review_economic_runtime dio FIX_FIRST a la escala basada sólo en std==0.
La corrección reproduce el límite float64 de StandardScaler:
var <= n*eps*var + (n*mean*eps)^2. El focal verifica 1.752 filas constantes
0,1, casi constantes 1e12±0,1 y distinguibles 1e12±2. Root leyó el auditor,
sus guardas de admisión/cierre, el replay y el delta final.
Revisión final CLEAR_IMPLEMENTATION_ONLY con pins y evidencia física verificados;
no se declara una segunda suite independiente.

Evidencia autor final retry06: 9 PASS en 6,91 s según pytest, Ruff exit0,
stderr vacíos, CPU0 heredado y threads1; gate RAM6.833.545.216 y commit libre
4.529.496.064 bytes. Receipt4f89ce1d1adb4cbd30122b4cc88024dc84d92491a68e0ceb58bdbe1b5ec04c46;
pretest_pins2c87c2fc7e7fd4b1f68d8824fabbbb8cad25a2679a10fd2123ea479650658b55.

Intentos anteriores conservados: attempt01 falló el harness de quoting;
retry02/03 no arrancaron pytest al fallar el gate; retry04 tuvo 9 PASS en una
versión anterior; retry05 conserva 8 PASS y una aserción incorrecta del focal
(esperaba escala menor que1 para ±1). Se corrigió la aserción y se usó ±2
para distinguir inequívocamente el caso no constante; retry06 es la evidencia
final, sin sumar suites de versiones diferentes. No auditor real previo.
Root archivó y rehasheó 53 copias, 521.233 bytes, en
context_model_auditor_implementation_evidence_01, receipt
cac99d62aa787ea0396aa10d06f960ecb590a3ef3046aff9dffc9451c2fe0d44.

## Runtime concreto

Raíz de comparación:
D:/GexResearchArtifacts/weekly_multiday_20261101/h2_context_model_comparison_01.
Manifest externo:
662ac63eaa2895beff4363b9e94a97cd7adc91aac3558139bdd919d8fbf2861a.
El auditor exige además cuatro authorities congeladas: datasetbfc7370f,
evaluación54dc2d6c, contexto77aaf00d y riesgo50fa6b7a; 14 payloads consumidos,
14 outputs y productor se rehashean al admitir y al cierre/post-write.

Después de publicar estos bytes y verificar HEAD remoto, único comando:

```text
python -X utf8 -u audit_weekly_context_models.py --execute-reviewed-audit
  --comparison-root D:/GexResearchArtifacts/weekly_multiday_20261101/h2_context_model_comparison_01
  --comparison-manifest-sha256 662ac63eaa2895beff4363b9e94a97cd7adc91aac3558139bdd919d8fbf2861a
  --auditor-sha256 3eb6b9795ad260971435259858f86d3c00111bcc141973faf986411d4a68ad99
  --output-dir D:/GexResearchArtifacts/weekly_multiday_20261101/h2_context_model_comparison_audit_01
```

Observer nuevo h2_context_model_audit_observer_01, mismo BASE local. Verificar
ausencia de ambas raíces, código publicado y helper operativo SHA3cfe55a6,
CPU0/hilo1 y gate RAM/commit libre >=2GB inmediatamente antes del hijo oculto.
Guardar stdout/stderr directos, identidad de proceso y exit por handle retenido.
Si falla, preservar intento completo y no relanzar automáticamente ni cambiar
resultados. No Q3, API, producción, bróker o VPS. Goal activo; promociónfalse.
