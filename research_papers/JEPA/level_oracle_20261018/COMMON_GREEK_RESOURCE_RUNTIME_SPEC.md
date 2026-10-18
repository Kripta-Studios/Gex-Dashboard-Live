# Umbral operativo solicitado por el usuario

El usuario ordenó exigir solamente2GB libres. Este ejecutor usa **2.000.000.000
bytes de RAM disponible y2.000.000.000 bytes de margen commit**, GB decimales,
comprobados antes de iniciar preparación y nuevamente inmediatamente antes del fit.
No aplica8/10GiB ni12/16GiB. El presupuesto conservador anterior queda como consejo
no adoptado; el umbral solicitado no garantiza ausencia de OOM. Monitor de memoria
cada1s y la misma publicación durable de modelo/predicciones/checkpoints.

La espera anterior, PID49024, quedó CANCELLED_RESOURCE_WAIT_PRE_FIT tras confirmar
sin hijos, runtime de hijo ni fit_started. Sus logs se conservan. Nueva salida:
`common_greek_control_resource_v1`, logs hermanos con sufijo `_logs`.

Sin monkeypatch: se reutilizan directamente `TrainingInputs` y
`fit_once(source,evidence,resource_gate=wait_resources)` del trainer SHA
`bba356f55467048c5f115d8fd7c580afcaa4a5c6cb2c532220df511319f3ce44`.
La revisión científica base SHA
`79fc3d9ef28268083f014274b2371622b0003004c66b434daef1b439b515e61d`
y sus14 dependencias/5 autoridades permanecen intactas. Sólo se duplica la
orquestación de contrato/snapshots para vincular explícitamente el ejecutor y
su revisión operativa. CONFIG, filas, etiquetas, escalas, IPW, LightGBM4hilos,
readback y política de continuación del export son idénticos. Sin VAL/TEST.

La revisión operativa fija código/spec, SHA de revisión base y gate_bytes.
El contrato final vincula ambas revisiones y sus snapshots, con `resource_runtime`
explícito. Un fit interrumpido sin export completo no se reintenta automáticamente.
