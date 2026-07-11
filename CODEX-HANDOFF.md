# CODEX-HANDOFF.md — Estado para continuación por otro agente

## Actualización 2026-07-11 04:14 CEST — ablación de historia cerrada y rechazada

- El runner predeclarado `run_flat_history_ablation_v1.ps1` terminó ambos arms y salió normalmente con el mensaje `Flat history ablation completed for both arms.`; stdout SHA-256 `A254625E41F90B73321F291C625CA91A7611E0EF3D5DB425C2B7EDADC62CE917`, stderr vacío. Ya no quedan trainer, selector, pytest ni proceso Python de esta ablación.
- Ambos arms completaron 13/13 folds OOF `202505..202605`, join 29.046/29.046, 15/15 folds nested `202601..202605` y provenance PASS. Usaron arquitectura flat, CUDA determinista, 8 épocas, batch 1024, 277 features live, seed base `20260618` y seed de fold `base+YYYYMM`.
- Factor único confirmado por el analizador: inicio de historia `202501` frente a `202201`; solo difieren `data` y `output_dir`. Dataset largo SHA-256 `11E26AADDD91FD441222D552E0362C1D4C2C4489A08D7A6DE66479D6EB454FB1`; control reciente `AB144DBAD1F6F103C771AE119A1172AC728BC11B6AA79DB5FB0648561673F720`.
- Control `history_2025`: 495 trades, WR `45,051%`, PF `0,863`, `-20,174R`, DD `-27,180R`; QQQ/SPXW/SPY PF `0,893/0,711/1,336`, PnL `-4,819/-22,935/+7,580R`; 4/15 celdas ticker×mes pasan todos los gates.
- Arm `history_2022`: 440 trades, WR `42,273%`, PF `0,764`, `-31,476R`, DD `-34,403R`; QQQ/SPXW/SPY PF `0,764/0,696/0,874`, PnL `-10,638/-16,542/-4,296R`; 1/15 celdas pasa.
- Meses overall `history_2022`: enero PF `0,514`/`-18,133R`; febrero `0,981`/`-0,417R`; marzo `0,682`/`-8,107R`; abril `1,002`/`+0,048R`; mayo `0,808`/`-4,868R`. El CSV versionable contiene las 15 celdas ticker×mes de cada arm.
- La historia larga sí mejora representación OOF: 13/15 wins en ratio error/persistencia (mediana `-0,07913`, Wilcoxon `p=0,000580`) y 11/15 en tasa de batir persistencia (mediana `+0,07973`, `p=0,003357`). No mejora downstream: PF 6/15 wins (`p=0,9527`), PnL 7/15 (`p=0,7729`); bootstrap diario 2022−2025 `-11,302R`, IC95% `[-44,087,+20,825]`, `P(diff>0)=0,248`.
- Decisión congelada: `continue_from_history_2022=false`. La mejora representacional no se traduce en edge; se rechaza la extensión y no se reabre modal/MJEPA/SMM. Ningún arm cumple gates y ninguno es candidato de promoción.
- Contrato revalidado por código: solo `executable_quote`, ask→bid, 0DTE, rejilla 10:30–14:30 ET/5m, hold mínimo 30m, una posición por ticker, cero solapamientos, cupos `SPXW=4/QQQ=2/SPY=1`, cooldowns `0/30/0`. Junio no aparece en datos, OOF, selección ni trades; fecha máxima del dataset `20260529`.
- Informe autocontenido: `research_papers/JEPA/results/_diagnostics/ptdj_ablation_flat_history_2022_vs_2025_runtime_contract_analysis_202601_202605_v1/`. Hash `summary.json`: `A1AFC66158674F239DA027C614C83566817563F19DB32F1A6CAF57A13530BB1`; `REPORT.md`: `AFBA779FF33F9814A7147B7D9D43B0B787B1C0E9ED5CE36ADEA24621BA1BD99D`.
- Verificación final: `py_compile` PASS y `70 passed in 4.88s` en la suite focalizada, incluido el analizador de historia.
- Primer paso seguro siguiente: versionar este informe pequeño y los handoffs, hacer push, y después predeclarar —sin ejecutar una búsqueda masiva— el primer factor independiente del punto 4 de la cola (`Portfolio Var-JEPA`). Debe mantener congelado el market encoder flat/control y aislar la incertidumbre/abstención del payoff head; no usar PnL agregado como criterio ni abrir junio.

## Actualización 2026-07-11 03:23 CEST — ablación flat-history activa, no duplicar

- `fd712e2` y los tres commits técnicos anteriores están subidos a `origin/main`.
- El primer launch perdió su PowerShell padre por timeout, pero el trainer control PID `23084` siguió sano y terminó 13/13 folds. No se borró ni reinició la salida.
- Runner reanudado de forma persistente con `-EncodedCommand`: PID `25112`; stdout `tmp/flat_history_ablation_v1_resume2.stdout.log`, stderr homónimo. El intento de quoting fallido previo queda preservado en logs `...resume.*.log` y no tocó artefactos.
- Control `history_2025` completado: 13 folds OOF, 29.046 filas de features, join 29.046/29.046 y 15/15 folds nested con provenance PASS. Overall: 495 trades, WR `45,05%`, PF `0,863`, `-20,174R`; QQQ PF `0,893`, SPXW `0,711`, SPY `1,336`. Solo abril fue positivo overall; control rechazado.
- `history_2022` terminó 13/13 folds OOF con las mismas seeds mensuales, 29.046 filas y join 29.046/29.046. Su nested selector PID `37752` está activo en `...history_2022..._walkforward_runtime_contract_v1`, 2×12 hilos. No lanzar otro runner/selector mientras PID `25112` siga activo.
- Analizador pareado versionado y subido en `507af59`; test focalizado `3 passed`. Exige representación + downstream, no PnL agregado aislado.
- Junio sigue sellado; no se tocó systemd ni ninguna policy.

## Actualización 2026-07-11 03:15 CEST — dataset auditado y ablación lista para lanzar

- El runner de dataset terminó sin procesos huérfanos: 159/159 chunks, 108.156 filas base/physics, 371 columnas physics y fecha máxima `20260529`.
- SHA-256 base: `DED31E49D70EC2525194497994E26FD6A6DD4BF502F7775EA547826B0FB879BF`; physics completo: `11E26AADDD91FD441222D552E0362C1D4C2C4489A08D7A6DE66479D6EB454FB1`.
- Vista physics reciente común al downstream (`202501..202605`): 36.796 filas, SHA-256 `AB144DBAD1F6F103C771AE119A1172AC728BC11B6AA79DB5FB0648561673F720`.
- Auditoría: solo `zero_dte`/`executable_quote`, 0 duplicados, 0 infinitos, 0 filas off-grid, 277 features live en ambos arms, junio físicamente ausente. Dos filas SPXW del `20220222` marcan PUT no disponible; ThetaData confirma 162 strikes PUT pero bid/ask cero en esos timestamps. El selector las excluye por disponibilidad observable; no se imputaron ni borraron.
- Se fijaron 13 folds OOF idénticos `202505..202605`; evaluación nested `202601..202605`; flat, seed base `20260618`, seeds por fold `base+YYYYMM`, CUDA determinista, 8 épocas, batch 1024 y mismo contrato runtime.
- Commits nuevos: `6de6aa6` (masking/targets y CUDA determinista), `bf42cd9` (liberación de memoria del selector), `670b2e3` (seed independiente por fold/resume reproducible).
- Suite focalizada completa antes de predeclarar: `66 passed in 4.64s`; test Phys-TD posterior a fold seeds: `14 passed in 2.38s`.
- Predeclaración: `research_papers/JEPA/results/_diagnostics/flat_history_ablation_predeclared_202201_202605_v1/`. Runner: `run_flat_history_ablation_v1.ps1`, SHA-256 `A8DC76553B0573E8594939A60A81AB80C50C64B3DB42510834320EE8EDA1F63D`, parse PASS.
- Próximo paso exacto: commitear/pushear runner+predeclaración+handoffs; después comprobar de nuevo procesos/GPU y lanzar una sola vez el runner. No lanzar SMM/modal ni abrir junio.

## Actualización 2026-07-11 02:53 CEST — build histórico activo, no duplicar

- Se leyeron completos `SUMMARY-update.md`, `SUMMARY-articles.md`, `SUMMARY.md` y este handoff antes de ejecutar trabajo experimental.
- Git auditado: `HEAD=73f1080`, `main` alineado con `origin/main`; se preservan los diffs y artefactos heredados del usuario/agentes previos. Los commits `ce796d9` y `73f1080` ya contienen la predeclaración del dataset histórico y el join Phys-TD explícito.
- Los logs más recientes de `C:\CodexAutomation\logs` son las corridas del 10 de julio terminadas con error de capacidad del modelo; no contienen un entrenamiento posterior oculto.
- La comparación `flat` frente a `modal` está cerrada: ambos arms completaron 13 folds OOF y el downstream nested runtime-equivalente de enero–mayo de 2026. Flat obtuvo PF `0,8996`/PnL `-15,094R`; modal PF `0,8579`/PnL `-21,989R`. Modal perdió también en representación OOF y permanece `advance_to_cross_modal=false`.
- No se debe reanudar SMM/MJEPA modal, VISReg, proto o Gram. El primer paso pendiente real es la ablación de historia del encoder flat.
- Build causal histórico activo y verificado, iniciado por `run_flat_history_dataset_build_v1.ps1`: PowerShell PID `45348`, Python padre PID `6764`, hasta 24 workers. Comando sellado `20220101..20260531`, `option_price_mode=executable_quote`, ask→bid, trailing `50%/25%`, stop `60%`, TP `1000%`, hold mínimo `30m`, horizonte `180m`, rejilla `630..870`/5m y OI obligatorio.
- Hash del runner activo: `DE5E71AC6690BDDEEF497213E1657F4D3B15DCC9A3FC17CC86064CF941737F17`, coincidente con la predeclaración. A las 02:52 había 60 chunks parquet+JSON bajo `tmp/event_option_dataset_execquote_causal1030_202201_202605_v1/`; no lanzar otro build ni tocar esa salida.
- GPU sin entrenamiento CUDA: unos `2.363 MiB` libres; el build actual es CPU. Tras terminar, el runner creará el parquet consolidado y `..._v1_physics`; auditar ambos hashes, filas, meses/tickers, continuidad y ausencia física de junio antes de definir/lanzar los dos arms de training.
- No se tocó systemd, ninguna policy legacy ni ningún estado `production_live_ready`.

**Fecha:** 2026-07-10T21:55 CEST (actualización incremental; colas v1 detenidas)
**HEAD:** `cc5665f docs: record results of flat vs modal causal ablation` (`origin/main` en el mismo commit)
**Estado de esta continuación:** auditoría inicial completada sin duplicar ni interrumpir las corridas heredadas.

## Actualización 2026-07-11 02:04 CEST — selector flat runtime-equivalente activo

- Se repitió la auditoría completa de handoffs, Git, logs y procesos.
- No había Python/CUDA/pytest activo al comenzar. Se encontraron artefactos creados después del handoff: SMM v2r1 parcial (solo folds `202505..202507`) y colas v1 parciales/contaminadas. No se reanudaron.
- `flat` y `modal` originales están completos: 13 folds OOF y 15 folds nested OOS por arm, provenance `passed=true`.
- Hallazgo P0 nuevo: el selector downstream original usó cooldown 30m para SPXW/SPY/QQQ y cupos variables. No equivale al runtime `SPXW=4/0m`, `QQQ=2/30m`, `SPY=1/0m`.
- Las métricas históricas flat/modal no deben usarse como comparación live-equivalente hasta terminar los nuevos selectores.
- Se crearon dos parquets derivados bajo `tmp/`, físicamente sellados hasta `20260529`, con 41.883 filas, 538 columnas, ask→bid `executable_quote` y rejilla 10:30–14:30/5m.
- Hash flat sellado: `65CCD607A77AF65C71469A74EF76D71F40B56E6BCDD3DEE408E673A5FA59ECEB`.
- Hash modal sellado: `FC99717F6C8B801C09C9F1B4F39FA1E9860505FDA2E112A9706746298CF0DD64`.
- Proceso activo que no debe duplicarse: PID `8636`, selector flat sobre salida nueva `ptdj_ablation_flat_h1_3_6_12_causal_202501_202605_v1_walkforward_runtime_contract_v2`.
- Comando contractual: `--ticker-cooldown-minutes SPXW=0 QQQ=30 SPY=0 --ticker-max-day-grids SPXW=4 QQQ=2 SPY=1 --lgb-device-type cpu --seed 20260618 --no-resume`.
- Primer checkpoint observado: `SPXW/202601`.
- Próximo paso seguro: esperar a que PID `8636` termine; verificar 15 folds/hashes/provenance y solo entonces lanzar modal en otra ruta nueva con idénticos argumentos.
- Junio de 2026 sigue sellado. No se modificó systemd, no se promovió ningún paquete y no se tocó la policy legacy.

### Actualización incremental 2026-07-11 02:20 CEST

- Flat runtime-equivalente terminó 15/15 folds en `ptdj_ablation_flat_h1_3_6_12_causal_202501_202605_v1_walkforward_runtime_contract_v2`.
- Validación independiente: provenance PASS, 481 trades, `min(exit_minutes)=30`, mes máximo `202605`, sin off-grid, cupos excedidos ni solapamientos.
- Overall flat: WR `43,867%`, PF `0,8996`, PnL `-15,094R`, Max DD `-26,009R`.
- QQQ: 166 trades, PF `0,9998`, PnL `-0,010R`, mínimo mensual 28, 60% meses positivos.
- SPXW: 217 trades, PF `0,8127`, PnL `-14,249R`, mínimo mensual 17, 60% meses positivos.
- SPY: 98 trades, PF `0,9695`, PnL `-0,835R`, mínimo mensual 17, 40% meses positivos.
- Flat queda rechazado por PF/WR, volumen en SPXW/SPY y meses negativos.
- Modal runtime-equivalente está activo en PID `38064`, salida `ptdj_ablation_modal_h1_3_6_12_causal_202501_202605_v1_walkforward_runtime_contract_v2`, con los mismos argumentos, CPU/8 workers y seed `20260618`.
- No lanzar otro modal mientras PID `38064` esté activo. Tras terminar: validar contrato, ejecutar `analyze_event_phys_td_flat_modal.py`, persistir el informe/hashes y decidir si se detiene MJEPA.

## Actualización final 2026-07-11 02:35 CEST — flat/modal cerrado

- No quedan procesos Python, pytest ni entrenamientos de esta comparación.
- Flat runtime-equivalente: 481 trades, WR `43,867%`, PF `0,8996`, `-15,094R`, DD `-26,009R`, 1/15 celdas ticker×mes pasa todos los gates.
- Modal runtime-equivalente: 491 trades, WR `42,974%`, PF `0,8579`, `-21,989R`, DD `-31,039R`, 0/15 celdas pasa; `SPY/202601` fue abstain.
- Ambos provenance mensuales terminaron `passed=true`; contrato de ejecución validado, incluyendo hold mínimo observado 30m y ausencia de solapamientos.
- Representación OOF rechaza modal: 2/15 wins en ratio error/persistencia y 0/15 en tasa de batir persistencia.
- Downstream pareado rechaza modal: 7/15 wins en PF y 7/15 en PnL; bootstrap diario `-6,895R`, IC95% `[-31,537,+17,109]`.
- Decisión congelada: `advance_to_cross_modal=false`. No reanudar SMM v1, v2r1, proto, VISReg o Gram; no avanzar a H-Market-JEPA desde esta rama modal.
- Informe autocontenido: `research_papers/JEPA/results/_diagnostics/ptdj_ablation_flat_vs_modal_runtime_contract_analysis_202601_202605_v2/`.
- Hash `summary.json`: `EB1D233E3FD65FE3384ADAD736117CD48766E6A953E85489DACDAAB5017D1C5C`.
- Hash `REPORT.md`: `F7ACE4AA90594F6C7C06CEE7A216118B9303A1EB3157BA8A592FF97B106A4502`.
- Hash parquet flat sellado: `65CCD607A77AF65C71469A74EF76D71F40B56E6BCDD3DEE408E673A5FA59ECEB`.
- Hash parquet modal sellado: `FC99717F6C8B801C09C9F1B4F39FA1E9860505FDA2E112A9706746298CF0DD64`.
- Tests: `py_compile` PASS; suite focalizada completa `64 passed in 3.88s`; test del analizador posterior `6 passed in 0.94s`.
- Commits ya subidos durante la sesión: `d947b5b`, `f55550c`, `e863129`, `279e399`, `943fc40`.
- Commits finales también subidos: `13b9660` (manifests sellados en el analizador), `98311d3` (informe y handoffs) y `b5bb1c1` (ocho JSON/CSV pequeños con métricas, hashes y folds; añadidos explícitamente porque `_diagnostics` los ignora por defecto).
- No se tocó systemd, no se marcó ningún paquete live-ready, no se promovió/restauró legacy y junio de 2026 permaneció sellado.

### Primer paso seguro para la siguiente continuación

1. Confirmar Git/logs/procesos y leer este handoff completo.
2. No relanzar flat/modal ni ninguna cola SMM: la decisión ya está cerrada.
3. Auditar cobertura, consistencia y hashes de ThetaData 2022–2024 para opciones y spot, sin abrir junio.
4. Si los labels executable_quote son homogéneos, predeclarar una única ablación de historia para el encoder flat: train desde 2022 frente a train desde 2025, igual arquitectura/seed/presupuesto y selector nested runtime-equivalente.
5. No ejecutar hasta versionar el manifest, estimar coste y fijar folds. Usar CUDA/32 hilos solo de forma simétrica en ambos arms.

## Actualización 2026-07-11 02:43 CEST — historia 2022 predeclarada

- Objetivo activo: continuar hasta un candidato rentable, sin ampliar gates ni abrir junio.
- Hardware: RTX 5070 Ti Laptop 12.227 MiB, Ryzen 9/32 hilos, 32 GB RAM. La GPU mostraba ~2,2 GB libres al auditar; comprobar de nuevo antes de CUDA.
- Manifest nuevo sellado a mayo: `research_papers/JEPA/results/_diagnostics/thetadata_manifest_spxw_spy_qqq_202201_202605_sealed_v1/`.
- Manifest: 6.425/6.425 filas completas, 3.116 zero_dte, fechas `20220103..20260529`, cero claves 0DTE duplicadas.
- Hash manifest: `88BE8A2FF44C18FB57FCA360D31DEF574DDBB0419A792FC88349942711D2974A`; hash summary: `5075E530CC8BBDF5613028B42071EFBFF21DCB73F586735AC483640339A14B19`.
- Zero-dte por año QQQ: `170/250/252/250/99`; SPXW: `220/250/252/250/102`; SPY: `170/250/252/250/99` para 2022/2023/2024/2025/ene–may 2026.
- Runner creado: `run_flat_history_dataset_build_v1.ps1`; parse PowerShell PASS.
- Hash runner final: `DE5E71AC6690BDDEEF497213E1657F4D3B15DCC9A3FC17CC86064CF941737F17`; tests del builder: `9 passed in 0.42s`.
- Hash builder: `6E89AAFED8A2BB66AA8EE80DF70644ECA189D0CE1D8C56F3812895430DAC4307`.
- Hash enhancer: `3E420DB49315AFD9363C45B9F0FEFFA38732EFC116889D3D69B4417A94D2CB36`.
- Próximo paso: commitear/pushear manifest+runner+docs, ejecutar el build causal reanudable y auditar filas/hashes antes de entrenar.

### Objetivo cuantitativo obligatorio

Para cada ticker (`SPXW`, `QQQ`, `SPY`) y no solo en agregado, cualquier candidato debe cumplir en el walk-forward:

- hold por trade `>=30m`;
- PF `>=1,30`;
- WR `>=50%`;
- trades por mes `>=18`;
- PnL mensual positivo en todos los meses de evaluación.

Hay datos históricos de opciones y spot de 2022 a 2026 bajo `D:/ThetaData/data_options` y `D:/ThetaData/data_underlying_derived`. Deben usarse solo con ventanas causales y hashes/manifests reproducibles. Junio de 2026 permanece sellado hasta que exista un único protocolo congelado.

## Auditoría de reanudación de 2026-07-10 21:31 CEST

- Se leyeron completos `SUMMARY-update.md`, `SUMMARY-articles.md`, `SUMMARY.md` y este handoff.
- Se inspeccionaron `git status`, `git log`, todos los diffs tracked, los artefactos untracked relevantes y los logs recientes de `C:\CodexAutomation\logs`.
- `flat` y `modal` están realmente completos; el primer paso pendiente es la cola SMM predeclarada.
- La baseline SMM y su nested selector están completos. `sigreg_off` terminó 39/39 folds a las 21:38:51 y el wrapper avanzó a entrenamiento `visreg`.
- Proceso padre: PID `58028`, `powershell -Command "$env:PYTHONPATH=\".\"; .\run_smm_ablations.ps1"`, iniciado a las 20:29:13.
- Proceso activo: PID `18384`, trainer `...smm_visreg... --lambda-visreg 0.1 --device cuda --seed 20260618`, iniciado a las 21:38:51.
- No hay otro entrenamiento/evaluador JEPA activo. El PID `66384` corresponde al wrapper de esta ejecución programada de Codex, no a un experimento.
- Junio de 2026 continúa sellado: el trainer registra `effective_data_cutoff_month=202605`; el selector termina en `202605`.
- Hallazgo metodológico: `modal` histórico se ejecutó en CPU, mientras SMM baseline usa CUDA y activa simultáneamente `mask_modal_prob=0.15` y `mask_temporal_prob=0.15`. Por ello, la comparación directa modal→SMM es exploratoria y no una ablación limpia de un único factor. Las comparaciones SMM baseline→`sigreg_off`/`visreg`/`proto`/`gram` sí parten de la misma baseline CUDA y cambian un regularizador por arm.
- Hallazgo de ventana: `flat/modal` reportan únicamente `202601..202605`; los selectores SMM se lanzaron con `--start-month 202505`. La tabla SMM original mezclaba ventanas. Recomputación comparable: baseline SMM 341 trades, WR 41,35%, PF 0,778, -24,177R; `sigreg_off` 422 trades, WR 40,52%, PF 0,851, -20,951R. Ambos rechazados.
- Los provenance extendidos de baseline y `sigreg_off` tienen `passed=false`: faltan policies/hashes para los tres tickers en 202511. Los 15 folds enero–mayo sí tienen hashes completos. Pendiente ejecutar selectores separados con `--start-month 202601 --end-month 202605` sobre cada dataset ya enriquecido.
- Semántica auditada: `proto` no activa EMA (`use_ema_teacher=false`); `gram` es consistencia relacional Gram predicción–target, no anchoring contra teacher congelado; SMM baseline no añadió el predictor JEPA, que ya estaba en `modal`.
- Fallo P0 experimental: el encoder v1 enmascaraba también `target_z` futuro porque se llamaba en modo train. Baseline/`sigreg_off`/`visreg` SMM v1 no prueban masking solo en prefijo y quedan invalidados para atribución.
- Se detuvo PID `51972` (selector visreg) tras 8/39 folds y el wrapper `58028` salió. Automatizaciones paralelas del IDE relanzaron el selector `sigreg_off` sobre la misma ruta; se detuvieron PID `5268`/`28468` y `66588`/`30300` tras verificar comandos. El directorio `_walkforward` de `sigreg_off` quedó sobrescrito parcialmente con una fila.
- Corrección aplicada: `apply_mask=False` explícito para target con/sin teacher, masking preservado en contexto, validación de probabilidades. Suite focalizada: 58/58 PASS.
- No se ha tocado systemd, no se ha restaurado/promovido la policy legacy y no se ha abierto junio.

## Estado del experimento

### Ablación predeclarada: `flat` vs `modal` encoder (SUMMARY-articles.md §6, punto 1)

**Estado:** COMPLETADO. Ambos arms (`flat` y `modal`) completaron extracción OOF y evaluación OOS con nested walk-forward.

**Diseño experimental:**
- **Factor único cambiado:** `--encoder-input-mode flat` vs `--encoder-input-mode modal`
- **Dataset:** `tmp/event_option_dataset_execquote_causal1030_202501_202606_v3_physics/event_option_dataset.parquet` (44.169 filas, 371 cols)
- **SHA-256 dataset:** `E6A19EFBA1EDB055C733AAB4967843F7A4B5F1D2C8238A7A243FC5BBC2251903`
- **Seed:** `20260618` (default del trainer)
- **Horizons:** `1,3,6,12` (equivalentes a 5/15/30/60 minutos)
- **OOF range:** `--start-month 202501 --end-month 202605`
- **Data cutoff:** `202605` (junio excluido físicamente)
- **Features live-observable:** `--live-observable-features-only`
- **Contiguidad 5min:** `--expected-step-minutes 5`
- **Rejilla 10:30–14:30 ET:** `--entry-start-minute-et 630 --entry-end-minute-et 870`

**Arms:**
1. `flat`: `research_papers/JEPA/results/_diagnostics/ptdj_ablation_flat_h1_3_6_12_causal_202501_202605_v1/`
2. `modal`: `research_papers/JEPA/results/_diagnostics/ptdj_ablation_modal_h1_3_6_12_causal_202501_202605_v1/`

### Comandos ejecutados

#### 1. Tests focalizados (50 passed)

```powershell
python -m pytest -q tests/test_build_event_option_dataset.py tests/test_event_option_live_causality.py tests/test_event_option_non_overlap.py tests/test_event_option_production_validator.py tests/test_jepa_bot_execution.py tests/test_event_phys_td_jepa_causality.py --basetemp C:\tmp\pytest-jepa-causal-20260710b
```

### Arm 1: `flat` (COMPLETADO)

Comando ejecutado con `--encoder-input-mode flat`.
Output: `research_papers/JEPA/results/_diagnostics/ptdj_ablation_flat_h1_3_6_12_causal_202501_202605_v1/`
Folds generados: 13 folds OOF (mayo 2025 – mayo 2026).
Filas OOF: 33.380.

### Arm 2: `modal` (COMPLETADO)

Comando:

```powershell
python neural/jepa/walkforward_event_phys_td_jepa_oof.py \
  --data "tmp/event_option_dataset_execquote_causal1030_202501_202606_v3_physics/event_option_dataset.parquet" \
  --output-dir "research_papers/JEPA/results/_diagnostics/ptdj_ablation_modal_h1_3_6_12_causal_202501_202605_v1" \
  --tickers SPXW SPY QQQ --expiry-modes zero_dte \
  --start-month 202501 --end-month 202605 \
  --horizons 1,3,6,12 --encoder-input-mode modal \
  --live-observable-features-only \
  --entry-start-minute-et 630 --entry-end-minute-et 870 \
  --entry-grid-anchor-minute-et 600 --expected-step-minutes 5 \
  --seed 20260618 --device cpu --epochs 8 --batch-size 1024 \
  --context-len 6 --z-dim 32 --phys-dim 12 --delta-dim 16 \
  --hidden-dim 128 --num-layers 2
```

Output: `research_papers/JEPA/results/_diagnostics/ptdj_ablation_modal_h1_3_6_12_causal_202501_202605_v1/`

#### 2. Verificación de la continuación

```powershell
python -m py_compile neural/jepa/walkforward_event_phys_td_jepa_oof.py neural/jepa/append_xinput_oof_to_event_option_dataset.py
python -m pytest -q tests/test_build_event_option_dataset.py tests/test_event_option_live_causality.py tests/test_event_option_non_overlap.py tests/test_event_option_production_validator.py tests/test_jepa_bot_execution.py tests/test_event_phys_td_jepa_causality.py --basetemp C:\tmp\pytest-jepa-causal-20260710c
```

Resultado: `50 passed in 10.44s`.

#### 3. Recomputación de métricas SMM

Se leyó cada `event_option_profile_trades.csv` con `dtype={'date': str, 'month': str, 'ticker': str}` y se llamó a:

```python
from neural.jepa.walkforward_event_option_gate import metrics
metrics(frame, expected_months=['202601', '202602', '202603', '202604', '202605'])
```

Se recomputaron scopes overall/ticker/mes/ticker-mes para baseline SMM y `sigreg_off`, además de la vista extendida `202505..202605`. No se leyó ni se puntuó junio.

### Procesos activos

- Ningún proceso Python/entrenamiento/evaluador JEPA activo tras detener las colas v1 verificadas.

### Artefactos y checkpoints

- Dataset: `tmp/event_option_dataset_execquote_causal1030_202501_202606_v3_physics/event_option_dataset.parquet`
- Exploratory nested WF (rechazado): `research_papers/JEPA/results/_diagnostics/event_option_execquote_causal1030_nested_exploratory_202601_202605_v1/`
- SMM baseline encoder/features: `research_papers/JEPA/results/_diagnostics/ptdj_ablation_smm_baseline_h1_3_6_12_causal_202501_202605_v1/`
- SMM baseline selector extendido: mismo path con sufijo `_walkforward/`; 39 folds, 202511 sin policy en los tres tickers.
- SMM `sigreg_off` encoder/features: `research_papers/JEPA/results/_diagnostics/ptdj_ablation_smm_sigreg_off_h1_3_6_12_causal_202501_202605_v1/`
- SMM `sigreg_off` selector extendido: mismo path con sufijo `_walkforward/`; 39 folds, 202511 sin policy en los tres tickers.
- SMM `visreg` activo: `research_papers/JEPA/results/_diagnostics/ptdj_ablation_smm_visreg_h1_3_6_12_causal_202501_202605_v1/`.

### Hashes y seeds

| Artefacto | SHA-256 |
| --- | --- |
| Dataset base | `68AE45C89D521F71431261DEEA9BCC7E465FEB294D17BF122AFBDDBB30A4C8F8` |
| Dataset physics | `E6A19EFBA1EDB055C733AAB4967843F7A4B5F1D2C8238A7A243FC5BBC2251903` |
| Trainer cargado por la cola | `74DA6ECD9DEAB88719296A7DF37C1364B1CE4FDA041E3F7DFB4F3EE37FDFFCB7` |
| Appender cargado por la cola | `DAAB0C1D9F6E42067D090996EBBB6CB256195177398FB45EBB3E496A8D8F2914` |
| `run_smm_ablations.ps1` | `229F7F0333A4E47B49A468A164353485246040F44A0DAF12B7E39F1393FE9D1F` |
| SMM baseline metadata | `2E659A9712B29765B1C18F45651146DDAC53D3C9F627EAB20EAB345F61602A8F` |
| SMM baseline fold configs | `653A2B0880D48D94D9F375834E42AD67AEF3616ACC37B7FC91DFE96EEBC03C7E` |
| SMM baseline OOF features | `9B1AD00835CAB570EDEF1FF46B632AD51FB184F6749939303E3B1C88E1636E0A` |
| SMM baseline joined dataset | `A81D5F2F2CB010C1F729B6777B12EEDCA101B854A67286756903BE07F9DE7FA2` |
| SMM baseline extended trades | `C89FD11A2480E3DEEDE697968B9F4D9C3BC38F144B52FDE0B33F7398AAC2B82A` |
| SMM baseline extended metrics | `E829085A01720DFB7D895D5EB4EF5C57BC621BB47928B4FC83157CA0B8D06E10` |
| SMM baseline selected folds | `E6D7DDE5883E78E40524CED2266A5E12A8A5CF995AE952147E2FAAE842F5EA33` |
| SMM baseline provenance | `4B252477B3D767CC64281E17D58AB2C419DF33E69CC169673AD88EB0AF5CA1B9` |
| `sigreg_off` metadata | `424C21F3A8A299F8A7B1E841568B352EA636CAF2D88FADF3CD6465F6FF16E9F7` |
| `sigreg_off` fold configs | `873DC69F2356D2479B33BA2C607C634C07CE6E67587BE5B93AF61F6582961D23` |
| `sigreg_off` OOF features | `0F9B2EE2243B489A96A636C3850D43E7E68E054E3EF741BB0F56517C337BFA16` |
| `sigreg_off` joined dataset | `9A04B13D83B6ED1844B86F7E030F5D52FD06A1D2F5F6028E0A9BD85D728D2E30` |
| `sigreg_off` extended trades (snapshot previo; ruta sobrescrita después) | `267454B20F09F8E489D800DA96FA7BD1A1D9CF54A44005C9BE7611C17B313566` |
| `sigreg_off` extended metrics (snapshot previo; ruta sobrescrita después) | `6B3BD5439F125805B18A12BB659E1E9236AE6C1C12A24F4828D23AD5DC3A25D8` |
| `sigreg_off` selected folds (snapshot previo; ruta sobrescrita después) | `B82B1C5E061B92F1BBFCC6D89C3C1F46428947C9B19C63830299DA534D8A35EF` |
| `sigreg_off` provenance (snapshot previo; ruta sobrescrita después) | `3A1BF938CB07076EC33D62945CBFF2F80D28D48EE3542221EAF84EB15FADFD9B` |
| Seed | `20260618` |

Hashes v2 antes de lanzar:

| Artefacto | SHA-256 |
| --- | --- |
| Trainer prefix-only corregido | `8196D9391AE32CE157C5162C5901E99BF346C79AFB7FCBF0EBFCD591973F8F03` |
| Runner modal-mask-only v2r1 | `4236E47E52F7D203847EC74B46089E7D649AE7821D4E5D50C7C6D25D72157BEC` |
| Test Phys-TD/SMM | `DD2DE9A1576B33B0EAB1E2D600B4D0B6C250E2294845A0B72D7B65C4A6A78A29` |
| Test appender | `D779ED90FFE3F36F882ACE8D188CD4B3EC5BD181917EBC7A4E12BCB14FB7E1DD` |

### Tests ejecutados

```text
50 passed in 4.92s (2026-07-10T19:17 CEST)
50 passed in 10.44s (2026-07-10T21:39 CEST; py_compile previo PASS)
8 passed in 2.20s (tests Phys-TD/SMM, después de corregir un fixture que omitía `output_dim`)
53 passed in 3.79s (suite focalizada completa posterior, basetemp `C:\tmp\pytest-jepa-causal-20260710d`)
1 passed in 0.52s (`tests/test_append_xinput_oof_to_event_option_dataset.py`)
13 passed in 1.99s (target masking corregido + appender)
58 passed in 3.91s (suite focalizada completa tras corrección, basetemp `C:\tmp\pytest-jepa-causal-20260710e`)
```

Suite:
```text
tests/test_build_event_option_dataset.py
tests/test_event_option_live_causality.py
tests/test_event_option_non_overlap.py
tests/test_event_option_production_validator.py
tests/test_jepa_bot_execution.py
tests/test_event_phys_td_jepa_causality.py
```

### Métricas disponibles

- Baseline nested exploratorio Jan–May rechazado: Overall PF 0,909, WR 43,8%
- SMM baseline Jan–May: 341 trades, WR 41,35%, PF 0,778, `-24,177R`, Max DD `-27,33%`; rechazada.
- SMM `sigreg_off` Jan–May: 422 trades, WR 40,52%, PF 0,851, `-20,951R`, Max DD `-33,31%`; rechazada.
- Vista extendida baseline: 908 trades, PF 0,739, `-79,727R`, mínimo mensual 0; no comparable directamente con `flat/modal`.
- Vista extendida `sigreg_off`: 1.025 trades, PF 0,743, `-90,675R`, mínimo mensual 0.
- Legacy package: BLOCKED_FOR_PRODUCTION

### Fallos encontrados

- La comparación SMM publicada usó métricas `202505..202605` contra `flat/modal` `202601..202605`; corregido en los resúmenes.
- La comparación modal→SMM cambió dos máscaras y CPU→CUDA; no es atribución causal de un factor.
- `policy_selection_provenance.json` de baseline/`sigreg_off` extendidos marca `passed=false` por tres folds sin policy en 202511. Los folds enero–mayo están completos, pero requieren un selector de ventana correcta para provenance autocontenido.
- El primer intento de los tests SMM nuevos dio 2 fallos porque el fixture no pasaba `output_dim` a `ModalSequenceEncoder`; corregido en el test, sin cambiar código experimental. Resultado posterior 8/8 PASS.
- SMM v1 enmascaraba targets futuros; colas invalidadas y detenidas.
- `run_smm_ablations_202601.ps1` habría mezclado versiones de código y usa `--output` inválido en el appender de `proto/gram`.
- La automatización paralela sobrescribió parcialmente el selector `sigreg_off`; no asumir que sus hashes snapshot siguen presentes en disco.
- Primer launch v2 falló antes de cualquier fold porque el timeout corto cerró stdout (`OSError 22`); directorio `..._v2/` conserva solo metadata/nombres. Reintento debe usar `..._v2r1/`.

### Cambios sin commit

```text
M CODEX-HANDOFF.md
M SUMMARY-update.md
M SUMMARY-articles.md
M neural/jepa/append_xinput_oof_to_event_option_dataset.py
M neural/jepa/walkforward_event_phys_td_jepa_oof.py
M tests/test_event_phys_td_jepa_causality.py
?? tests/test_append_xinput_oof_to_event_option_dataset.py
M backtest/backtest_gbt_parquet.py  (solo line-ending)
M neural/models/jepa/.../event_option_policy.json  (entry_sample_minutes/anchor additions)
M neural/models/jepa/.../component_registry.json  (newline at end)
M neural/models/jepa/.../QQQ_static_union_balanced.json  (newline)
M neural/models/jepa/.../SPXW_static_union_balanced.json  (newline)
M neural/models/jepa/.../SPY_static_union_balanced.json  (newline)
M neural/models/jepa/.../runtime_policy_replay_summary.json  (newline)
?? run_smm_ablations.ps1
?? run_smm_ablations_202601.ps1
?? run_smm_modal_mask_only_v2.ps1
?? artefactos diagnósticos flat/modal/SMM y `tmp/` (grandes; no añadir sin selección explícita)
```

Estos diffs son del agente anterior y solo añaden `entry_sample_minutes`/`entry_sample_anchor_minute_et` al policy JSON. No afectan la ablación en curso.

### Último commit

```text
cc5665f docs: record results of flat vs modal causal ablation
```

### Junio de 2026

Completamente sellado. El `--data-cutoff-month 202605` / `--end-month 202605` excluye junio del dataset y del OOF.

### Primera acción del siguiente agente

1. Confirmar que ninguna automatización del IDE ha relanzado un proceso sobre directorios v1.
2. Lanzar el arm válido v2 predeclarado: CPU, `mask_modal_prob=0.15`, `mask_temporal_prob=0`, resto idéntico al control modal, salida nueva; junio excluido.
3. Enriquecer con prefijo `ptdj_` y ejecutar selector solo `202601..202605` en salida nueva.
4. Verificar 15 folds con hashes/provenance PASS y recomputar métricas por mes/ticker.
5. Solo después decidir el arm temporal; implementar spans contiguos antes de probarlo, porque el v1 usaba Bernoulli por timestep.
