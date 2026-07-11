# SUMMARY-articles.md — Literatura JEPA/World Models y pruebas

**Inicio:** 10 de julio de 2026
**Estado:** los 29 trabajos aportados han sido auditados; experimentos causales en curso.

## 1. Contrato experimental

Una idea académica solo contará para live si se prueba con:

- opciones 0DTE y labels executable_quote: entrada ask, mark/salida bid;
- features observables hasta el minuto de decisión;
- rejilla 10:30–14:30 ET cada cinco minutos;
- una posición por ticker y cooldown/cupo idénticos a runtime;
- train y selección anteriores al mes externo;
- enero–mayo de 2026 como zona exploratoria nested;
- junio de 2026 intacto hasta congelar un único protocolo.

Gates por ticker y mes: hold realizado `>=30m`, PnL > 0 en todos los meses walk-forward, WR `>=50%`, PF `>=1,3` y al menos 18 trades por mes.

El histórico local disponible para train/inner-validation causal cubre 2022–2026 en:

```text
D:/ThetaData/data_options
D:/ThetaData/data_underlying_derived
```

La disponibilidad de más historia no autoriza a abrir junio de 2026 ni a usar meses externos para seleccionar arquitectura, policy o thresholds.

## 2. Baseline causal a superar

| Scope | Trades | WR | PF | PnL (R) | Min trades/mes | Meses positivos |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Overall | 324 | 43,827% | 0,909 | -9,287 | 48 | 40% |
| QQQ | 94 | 44,681% | 0,984 | -0,492 | 15 | 40% |
| SPXW | 107 | 42,991% | 0,832 | -5,816 | 10 | 40% |
| SPY | 123 | 43,902% | 0,919 | -2,979 | 19 | 40% |

Artefacto: research_papers/JEPA/results/_diagnostics/event_option_execquote_causal1030_nested_exploratory_202601_202605_v1/

Dictamen: baseline causal y auditable, pero no rentable. Junio no se utilizó.

## 3. Ideas ya presentes en el repo

| Idea | Evidencia local | Estado real |
| --- | --- | --- |
| JEPA temporal multihorizonte | neural/jepa/model.py, train_xinput_jepa.py | Investigación legacy; no certificada ask→bid |
| Encoder de secuencia y latentes futuros | neural/jepa/walkforward_event_phys_td_jepa_oof.py | Exportación OOF causal por mes |
| Modalidades semánticas de features | classify_feature_modality(), ModalSequenceEncoder | Implementado; no probado sobre el parquet ejecutable actual |
| Horizontes 1,2,3,6 | flag horizons de Phys-TD-JEPA | Implementado |
| Teacher EMA | make_ema_teacher(), update_ema_teacher() | Implementado, no promovido |
| Prototipos tipo DINO | PrototypeDistillationLoss, lambda-proto | Implementado, no promovido |
| SIGReg/VISReg/VICReg | neural/jepa/sigreg.py y flags del trainer | Implementado y comparado en legacy |
| Straightening latente | lambda-straightening | Implementado, no promovido |
| Teacher-to-student de trades | neural/jepa/distill_event_option_teacher.py | Probado en legacy; no live-ready |
| Routers de acción/retorno/expertos | walkforward_event_action_return_router.py y routers | Varias pruebas; ninguna certificada con labels actuales |
| Diagnóstico de colapso | effective rank, PC variance y std latente | Implementado |

## 4. Evidencia previa invalidada para PnL live

Las comparativas en `research_papers/JEPA/results/_diagnostics/visreg_gate_*` usaron un dataset legacy desde 10:00, salida fixed y sin `option_price_mode=executable_quote`. Sirven para estudiar representación, no para estimar rentabilidad live. Además, la comparación VISReg cambió a la vez straightening y otros regularizadores, por lo que no es una ablación de un solo factor.

| Variante legacy, filtrada a enero–mayo | Trades | WR | PF | PnL (R) |
| --- | ---: | ---: | ---: | ---: |
| Phys-TD baseline | 300 | — | 0,852 | -8,781 |
| Phys-TD + VISReg | 300 | — | 0,878 | -7,181 |
| XInput baseline | 300 | 33,33% | 0,827 | -10,381 |
| XInput + VISReg | 300 | 33,33% | 0,827 | -10,381 |

VISReg elevó el rango efectivo del embedding y alguna estabilidad mensual, pero no creó edge en esa prueba.

## 5. Registro por artículo auditado

| Fuente | Idea transferible | Evidencia y resultado local | Estado real |
| --- | --- | --- | --- |
| [I-JEPA 2301.08243](https://arxiv.org/abs/2301.08243) | Contexto distribuido, grandes bloques objetivo y predicción en embedding | Hay JEPA temporal multihorizonte y OOF, pero no masking tiempo×modalidad. XInput Gate A quedó en PF 1,094 frente a 1,300 del baseline. | Parcial; familia no promovida |
| [LeWorldModel 2603.19312](https://arxiv.org/abs/2603.19312) | Transformer causal action-conditioned, MSE+SIGReg, surprise y CEM/MPC | `le_jepa_model.py` y `train_leworldmodel.py` implementan una aproximación tabular actionless. No hay action transformer ni planner. Mantener el mercado actionless es correcto: la orden no causa el mercado. | Parcial; planning ausente |
| [Hierarchical Planning 2604.03208](https://arxiv.org/abs/2604.03208) | World model lento/alto, rápido/bajo, subgoals y macroacciones | Los heads multihorizonte son solo un precursor; no existen dos world models ni subgoal conditioning. | Núcleo no probado |
| [Intuitive Physics from V-JEPA 2502.11831](https://arxiv.org/abs/2502.11831) | Surprise como discrepancia entre estado predicho y observado | XInput y Phys-TD exportan errores/surprise. En XInput la predicción fue peor que persistencia a 5–60m y mejor a 120/180m; AUC OOS de surprise 0,440/0,449/0,498. | Parcial; señal débil |
| [LeJEPA 2511.08544](https://arxiv.org/abs/2511.08544) | Alignment MSE + SIGReg Epps–Pulley sin stop-gradient, teacher ni prototipos | `le_jepa_model.py`, `train_leworldmodel.py` y `sigreg.py` lo implementan en research; no existe paquete live promovido. | Implementado; no promovido |
| [DINOv3 2508.10104](https://arxiv.org/abs/2508.10104) | Gram anchoring para preservar geometría densa durante entrenamiento largo | No hay pérdida Gram ni teacher de referencia congelado en el repo. | Ausente |
| [V-JEPA 2.1 2603.14482](https://arxiv.org/abs/2603.14482) | Objetivo denso en tokens masked/visibles y supervisión profunda intermedia | Encoder modal y predicción multihorizonte existen; faltan masks, loss en visibles y heads intermedios. El downstream TDVP dio 711 trades, PF 0,948 y -4,45R. | Parcial; downstream rechazado |
| [Spectral SSL 2205.11508](https://arxiv.org/abs/2205.11508) | La relación positiva define el grafo y el espectro aprendido | Existen SIGReg/VICReg/VISReg, pero no un grafo causal de positivos semánticos ni pérdida Laplaciana. | Parcial; regularizadores no promovidos |
| [DINOv2 2304.07193](https://arxiv.org/abs/2304.07193) | EMA teacher, distillation global, masked-patch, prototipos y datos curados | Hay teacher EMA y `PrototypeDistillationLoss`; no iBOT/masking, KoLeo, deduplicación ni teacher grande. El downstream TDVP fue negativo. | Parcial; rechazado |
| [PatchCore 2106.08265](https://arxiv.org/abs/2106.08265) | Banco nominal multiescala, coreset y anomalía kNN | Hay kNN/robust-z OOD y drift, sin coreset facility-location jerárquico. Un gate QQQ previo obtuvo PF 1,144 y mínimo mensual 7. | Parcial; rechazado |
| [When Does LeJEPA Learn a World Model? 2605.26379](https://arxiv.org/abs/2605.26379) | Identificabilidad lineal bajo latentes gaussianos, independientes, estacionarios y ruido aditivo | Hay SIGReg/rank diagnostics, pero no test de recuperación con latente conocido u OU. Las hipótesis no describen bien un mercado no estacionario. | Aportación central no probada |
| [V-JEPA 2 2506.09985](https://arxiv.org/abs/2506.09985) | Pretraining action-free y predictor de interacción condicionado por acción con CEM/MPC | XInput usa inputs exógenos, no acciones. Gate A falló; un proxy fixed-hold 180m fue prometedor, pero no live-equivalente ni promovido. | Parcial; no promovido |
| [VL-JEPA 2512.10942](https://arxiv.org/abs/2512.10942) | Targets semánticos continuos y decoding selectivo solo ante cambio semántico | `ModalSequenceEncoder` ya agrupa `price_level`, `option_surface`, `physics`, `cross_asset` y `other`, pero todas las corridas auditadas usaron modo `flat`. | Implementado pero nunca probado en modal |
| [EB-JEPA 2602.03604](https://arxiv.org/abs/2602.03604) | Stack modular de percepción→world model→acción, inverse dynamics y MPPI | El repo tiene módulos y regularizadores; faltan inverse-dynamics y planificación energética/MPPI. | Parcial |
| [JEPA-DNA 2602.17162](https://arxiv.org/abs/2602.17162) | Objetivo generativo + predicción latente de spans contiguos + agregado global | El anclaje físico es una analogía parcial; no hay span masking, agregador global ni objetivo generativo+JEPA. | Núcleo no probado |
| [Var-JEPA 2603.20111](https://arxiv.org/abs/2603.20111) | ELBO conjunto, posterior latente y uncertainty principiada; incluye variante tabular | No existen `mean/logvar`, KL ni likelihood. `xjepa_entropy` solo mide entropía clasificatoria. | Ausente; alta relevancia |
| [FF-JEPA 2606.09311](https://arxiv.org/abs/2606.09311) | Planner action-free de subgoals + forward model corto condicionado por acción | Los heads paralelos actuales no son subgoals ni condicionan un modelo inferior. | Ausente |
| [A Path Towards Autonomous Machine Intelligence](https://openreview.net/forum?id=BZ5a1r-kVsf) | H-JEPA, actor, coste, critic, memoria y planificación por energía | Hay piezas conceptuales y risk guards, pero no H-JEPA real. Los action routers previos fueron rechazados; QQQ cayó a PF 0,990. | Parcial conceptual |
| [MIRA / Multiplayer Interactive World Models](https://arxiv.org/abs/2607.05352) | Autoencoder de representación + latent diffusion condicionada por acciones multiagente | No es JEPA y no hay equivalente local. Transferible: preservar tokens semánticos antes de comprimir. | Ausente; prioridad baja |
| [VISReg 2606.02572](https://arxiv.org/abs/2606.02572) | Regularización separada de centro, escala y forma mediante Sliced Wasserstein | `sigreg.py` reproduce el algoritmo. La prueba previa fue confounded: Phys-TD mejoró PF 0,852→0,878, XInput no cambió, ambos siguieron negativos. | Implementado; no promovido |
| [Fast LeWorldModel 2606.26217](https://arxiv.org/abs/2606.26217) | Predicción paralela para prefijos de acciones/horizontes y consistencia directa frente a composición temporal | Phys-TD predice varios horizontes desde un ancla, pero no codifica prefijos de acciones, planning paralelo ni self-consistency. | Parcial |
| [On Training in Imagination 2605.06732](https://arxiv.org/abs/2605.06732) | Separar sesgo de dinámica y reward, controlar suavidad/Lipschitz y distinguir ruido de sesgo sistemático | Straightening solo mejora geometría latente; no hay reward model imaginado, calibración Lipschitz ni asignación de rollouts. | Parcial; sin señal downstream útil |
| [MJEPA 2606.25225](https://arxiv.org/abs/2606.25225) | Pérdidas intra-modal y cross-modal bidireccionales | `ModalSequenceEncoder` proyecta y concatena modalidades, pero carece de objetivos cross-modal explícitos. La aproximación `mtv20` obtuvo PF 0,993 y -0,615R. | Parcial; aproximación ingenua fallida |
| [AdaJEPA 2606.32026](https://arxiv.org/abs/2606.32026) | Adaptación causal online del predictor con buffer reciente/difícil y reset por episodio | No hay test-time gradient adaptation; los routers online son reglas. Contradice el contrato de base mensual congelada salvo experimento shadow aislado. | Ausente; solo shadow mode |
| [Phys-JEPA 2606.16076](https://arxiv.org/abs/2606.16076) | Latente físico + residual y consistencia de estado/transición | Split físico/residual, projector y losses ya existen. PTDJ standalone dio PF 0,95; variantes por ticker mejoraron parcialmente, pero ninguna cumplió simultáneamente todos los gates. | Aplicado; no certificado |
| [SkyJEPA 2606.23444](https://arxiv.org/abs/2606.23444) | Rollout multihorizonte y prober físico congelado/estructurado | Hay rollout y prober, no integrador físico diferenciable ni planner. El prober tuvo R² negativo y accuracy direccional 0,486. | Parcial; rechazado |
| [Neuro-JEPA 2606.14957](https://arxiv.org/abs/2606.14957) | MoE disperso multimodal y tolerancia a modalidades ausentes | Hay routers de policy, no sparse latent MoE. La evidencia de router mejoró 2026 pero falló 2025. | Núcleo ausente |
| [WorldDP 2606.08775](https://arxiv.org/abs/2606.08775) | World model alto de subobjetivos y ejecutor bajo | No hay object slots, subgoal model ni diffusion policy. Sustitutos supervisados de acción/salida dieron PF 0,942 y 0,811 con pérdidas grandes. | Núcleo ausente; análogo rechazado |
| [TDV 2606.15956](https://arxiv.org/abs/2606.15956) | Movimiento latente aditivo, EMA teacher y prototype loss sin masking complejo | Delta encoder, additive motion, EMA y prototipos existen. `tdv20` logró PF 1,220 y +16,414R, pero mínimo mensual cero; otros gates fueron inestables/negativos. | Aplicado; no válido como señal independiente |

Los 29 trabajos quedan clasificados. Ningún resultado histórico de esta tabla sustituye una prueba nueva con labels `executable_quote`, continuidad temporal, nested selection y replay live.

## 6. Cola experimental predeclarada

1. **Phys-TD/MJEPA modal ejecutable.** Activar primero el encoder modal ya escrito sobre enero–mayo, con tokens observables de precio/niveles, superficie/Greeks/liquidez, física y cross-asset. Comparar `flat`, concatenación modal y pérdidas intra/cross-modal con el mismo presupuesto, seed y nested selector. Mejorar el grounding físico solo con restricciones defendibles y observables: bounds, monotonía/convexidad por strike, parity cuando proceda y residuos delta-gamma-theta. **(ESTADO: Parte 1 completada. La concatenación `modal` superó a `flat` en PF global 0,91 vs 0,86 y mejoró SPY/SPXW, pero destruyó QQQ. Ninguno pasó el gate de producción. Quedan pendientes las pérdidas intra/cross-modal explícitas).**
2. **Semantic-Masked Market JEPA.** Enmascarar modalidades completas y spans temporales solo dentro del prefijo observado. Predecir latentes futuros en horizontes rápidos y lentos; hacer ablations limpias de SIGReg, EMA/prototipos, VISReg y Gram anchoring cambiando un factor cada vez. **(ESTADO 2026-07-10 21:39 CEST: baseline SMM y `sigreg_off` completadas y rechazadas; `visreg` está entrenando y después siguen `proto`/`gram`. Recomputado sobre la ventana comparable `202601..202605`, SMM baseline obtuvo 341 trades, WR 41,35%, PF 0,778 y -24,177R; `sigreg_off`, 422 trades, WR 40,52%, PF 0,851 y -20,951R. La cifra SMM previa de 908 trades/PF 0,739 cubría `202505..202605`, no enero–mayo. La comparación modal→SMM tampoco aísla un factor porque activó dos máscaras y cambió CPU→CUDA; antes de concluir sobre masking se exige control CUDA sin máscara y arms modal-only/temporal-only. Los selectores extendidos quedan `provenance passed=false` por ausencia de policy en 202511, aunque los 15 folds de enero–mayo sí tienen hashes; se regenerará el selector en la ventana correcta.)**
2. **Semantic-Masked Market JEPA.** Enmascarar modalidades completas y spans temporales solo dentro del prefijo observado. Predecir latentes futuros en horizontes rápidos y lentos; hacer ablations limpias de SIGReg, EMA/prototipos, VISReg y Gram anchoring cambiando un factor cada vez. **(ESTADO 2026-07-10 21:55 CEST: los arms SMM v1 quedan invalidados para atribución porque el mismo encoder en modo train también enmascaraba los targets futuros, no solo el prefijo. Se detuvieron las colas heredadas antes de `proto/gram`; `visreg` conserva extracción completa y selector parcial 8/39, solo diagnóstico. Se corrigió el target con `apply_mask=False` y la suite focalizada pasa 58/58. El siguiente arm v2 predeclarado cambia únicamente máscara modal `0→0,15` sobre el control modal CPU, mantiene máscara temporal en cero y evalúa solo `202601..202605` en directorios nuevos.)**

   Nota de implementación reproducida: el arm `proto` actual activa `lambda_proto=1.0` sin `use_ema_teacher`, por lo que no prueba EMA; el arm `gram` compara Gram de predicción y target del mismo modelo, no ancla contra un teacher de referencia congelado. Se mantendrán esos nombres operativos para terminar la cola heredada, pero se reportarán como prototype self-distillation y Gram relational consistency. La baseline modal ya tenía el objetivo JEPA multihorizonte; SMM añadió masking (y cambió backend), no el predictor latente.
3. **H-Market-JEPA/Fast-LeWM.** Modelo lento de subgoals 60/120/180m y modelo rápido 5/15/30m condicionado por el subgoal. El mercado permanece actionless. Para cartera, enumerar prefijos discretos y exigir consistencia de predicción directa frente a compuesta, con ejecutor determinista antes de considerar diffusion.
4. **Portfolio Var-JEPA condicionado por acción.** Separar `market_latent(t+1)=f(estado, contexto exógeno)` de `portfolio/payoff=g(trayectoria, acción, contrato exacto)`. Solo el segundo recibe `HOLD/CALL/PUT` y contrato. Usar ELBO e incertidumbre para abstención, no retorno futuro como feature.
5. **Surprise + PatchCore de abstención.** Congelar el encoder por fold, construir un coreset nominal solo con train y elegir el umbral en inner validation. La distancia regula abstención/riesgo, nunca dirección.
6. **AdaJEPA en shadow mode, no live.** Solo después de disponer de una base congelada: adaptar un bloque pequeño con transiciones observadas, sin PnL futuro, reset diario y límites de norma/rollback. No puede modificar la policy productiva durante esta investigación.

Los tres huecos previos del trainer ya están cerrados: el OOF exige que el cutoff físico coincida con su mes final, rechaza features que no puede reproducir live y solo construye ventanas sobre tramos realmente contiguos de cinco minutos. La primera ablación usará horizontes 5/15/30/60m para aislar `flat` frente a `modal`; 120/180m se reservan para la variante jerárquica. Ninguna variante llegará a junio hasta superar claramente el baseline exploratorio y quedar congelada.

## 7. Corrección del downstream flat/modal al contrato runtime

La extracción OOF de `flat` y `modal` sí está completa y cambia únicamente `encoder_input_mode`, con CPU, seed `20260618`, 8 épocas, 277 features live, secuencias contiguas y cutoff `202605`. La evaluación downstream publicada no fijó correctamente el contrato live: aplicó cooldown de 30 minutos a todos los tickers y dejó variar los cupos diarios.

Se predeclara una única corrección común, sin reentrenar los encoders ni cambiar la arquitectura:

- SPXW: máximo 4 trades/día, cooldown 0m;
- QQQ: máximo 2 trades/día, cooldown 30m;
- SPY: máximo 1 trade/día, cooldown 0m;
- selector nested `202601..202605`, CPU y seed `20260618`;
- datasets derivados físicamente truncados en `20260529`;
- mismo espacio de perfiles, thresholds y presupuesto para ambos arms.

El selector flat runtime-equivalente se lanzó en `...flat..._walkforward_runtime_contract_v2/`; modal se predeclaró idéntico salvo por los embeddings OOF ya congelados. La evidencia de representación ya calculada es desfavorable a `modal`; por tanto, no se avanzará a pérdidas intra/cross-modal si el informe final no demuestra una mejora reproducible tanto representacional como downstream.

Actualización: flat terminó 15/15 folds con provenance PASS y contrato validado (hold mínimo observado 30m). Produjo 481 trades, WR 43,87%, PF 0,900 y -15,094R. QQQ quedó en PF 1,000, SPXW 0,813 y SPY 0,969; el mínimo mensual fue 28/17/17 respectivamente. Flat queda rechazado. Modal runtime-equivalente está ejecutándose con configuración idéntica y salida nueva; no se tomarán decisiones hasta completar la comparación pareada.

### Dictamen final de la cola modal/MJEPA

Modal terminó con 491 trades, WR 42,97%, PF 0,858, -21,989R y 0/15 celdas ticker×mes superando simultáneamente PnL/WR/PF/volumen. Flat obtuvo 481 trades, PF 0,900, -15,094R y 1/15 celdas. Modal además produjo abstain en `SPY/202601`.

La mejora de loss in-sample de modal (12/13 folds) no se reproduce en representación OOF: solo gana 2/15 celdas en error/persistencia y 0/15 en tasa de batir persistencia. Tampoco mejora downstream de forma pareada: gana PF y PnL en 7/15, con medianas negativas y p-values 0,835/0,640. Bootstrap diario modal-flat: -6,895R, IC95% [-31,537,+17,109].

**La condición de avance de la sección 6 no se cumple.** No se ejecutarán pérdidas intra/cross-modal de MJEPA, semantic masking, VISReg/prototipos/Gram ni la cola jerárquica a partir de este encoder modal. Las corridas SMM v1/v2 parciales quedan solo como diagnóstico inválido/incompleto.

Siguiente hipótesis de un solo factor, todavía no lanzada: ampliar el histórico del baseline flat desde 2025 a 2022 usando los datos ThetaData disponibles, tras reconstruir y hashear labels executable_quote homogéneos. Mantener arquitectura, seeds, presupuesto, selector nested y evaluación 202601–202605; junio continúa sellado.

### Ablación de historia predeclarada

El manifest sellado `202201..202605` contiene 3.116 sesiones 0DTE completas: QQQ/SPY tienen 170 en 2022 y 250/252/250 en 2023/2024/2025; SPXW tiene 220 y luego 250/252/250. Todas las 6.425 filas del manifest disponen de Greeks, IV, OHLC, OI y spot. Hash: `88BE8A2FF44C18FB57FCA360D31DEF574DDBB0419A792FC88349942711D2974A`.

Se comparará exclusivamente `train_start=202201` frente a `train_start=202501` sobre dos vistas del mismo dataset causal sellado. Arquitectura flat, features, folds, seed, epochs, batch, horizontes, selector y runtime serán idénticos. El build usará hasta 24 procesos CPU; el entrenamiento usará la RTX 5070 Ti 12 GB solo si un preflight confirma que ambos arms caben con el mismo batch, sin fallback asimétrico.

Actualización 2026-07-11 03:15 CEST: el dataset quedó construido y auditado (108.156 filas, hash physics `11E26AADDD91FD441222D552E0362C1D4C2C4489A08D7A6DE66479D6EB454FB1`); la vista 2025 común al downstream tiene hash `AB144DBAD1F6F103C771AE119A1172AC728BC11B6AA79DB5FB0648561673F720`. El preflight CUDA a batch 1024 reservó ~818 MiB y pasó en modo determinista. Se congelaron 13 folds OOF `202505..202605`, seeds por fold y evaluación nested runtime-equivalente `202601..202605`. En ese hito el runner estaba predeclarado pero aún no lanzado; la cola modal/MJEPA continuaba cerrada.

Actualización 2026-07-11 03:26 CEST: la ablación está activa. `history_2025` terminó 13/13 folds OOF y el join completo; su selector nested lleva 3/15 folds. El runner persistente PID `25112` continuará después con `history_2022`. La cola modal/MJEPA no se reabrió y junio sigue sellado.

Actualización 2026-07-11 03:39 CEST: `history_2025` terminó también 15/15 folds nested con provenance PASS, pero queda rechazado (495 trades, WR 45,05%, PF 0,863, -20,174R; QQQ/SPXW/SPY PF 0,893/0,711/1,336). `history_2022` está entrenando en el mismo runner y con seeds pareadas; no se tomará una decisión de historia hasta completar representación y downstream.

Actualización 2026-07-11 03:51 CEST: `history_2022` completó 13/13 folds OOF y join idéntico; su selector nested está activo. El analizador pareado ya está versionado (`507af59`) y exige mejora simultánea de error/persistencia, tasa de batir persistencia, PF/PnL por celda y bootstrap diario antes de recomendar cualquier continuación.

Actualización final 2026-07-11 04:14 CEST: ambos arms terminaron 13/13 folds OOF y 15/15 nested con provenance PASS. `history_2025` obtuvo 495 trades, PF `0,863` y `-20,174R`; `history_2022`, 440 trades, PF `0,764` y `-31,476R`. La historia larga mejora significativamente la representación OOF (13/15 wins en error/persistencia, `p=0,000580`; 11/15 en tasa de batir persistencia, `p=0,003357`), pero no PF ni PnL downstream (6/15 y 7/15 wins; `p=0,9527/0,7729`). Bootstrap diario: `-11,302R`, IC95% `[-44,087,+20,825]`. Se fija `continue_from_history_2022=false`: la extensión queda rechazada y no reabre MJEPA/modal/SMM ni la cola jerárquica. Junio permaneció sellado.

El primer punto verdaderamente pendiente de la cola es ahora el 4, `Portfolio Var-JEPA condicionado por acción`. Antes de ejecutar nada debe predeclararse una comparación de un solo factor que congele el encoder flat/control y separe estrictamente `market_latent` actionless del head de payoff/portfolio condicionado por `HOLD/CALL/PUT` y contrato exacto. La primera prueba debe aislar incertidumbre/abstención frente a un head determinista con el mismo presupuesto y nested folds; no se autoriza barrido masivo, selección por PnL agregado ni uso de junio.

Actualización 2026-07-11 04:40 CEST: Portfolio Var-JEPA v1 quedó implementado y predeclarado, todavía sin lanzar la corrida completa. El control y la variante comparten encoder flat OOF congelado, datos, MLP backbone/decoder, 40 épocas, batch 512, optimizador, cinco folds `202601..202605` y seeds `20260618+YYYYMM`; la variante añade únicamente prior/posterior Gaussianos, reparametrización y KL annealed. `HOLD` se implementa como abstención por threshold seleccionado en los tres meses internos, evitando fabricar una etiqueta HOLD futura. La incertidumbre no puede intervenir en v1. El avance exige mejora pareada OOS de MAE/RMSE y correlación incertidumbre-error reproducible; PF/WR/volumen/meses positivos se auditan aparte y nunca se decide por PnL agregado. Predeclaración y hashes: `research_papers/JEPA/PORTFOLIO_VAR_JEPA_PREDECLARATION_V1.md`; tests `9 passed`.

Actualización final 2026-07-11 04:47 CEST: Portfolio Var-JEPA v1 queda rechazado. Var ganó MAE/RMSE en 9/15 celdas, sin significación (`p=0,489/0,381`), perdió effective rank en 15/15 y su incertidumbre correlacionó positivamente con error en solo 1/15 (mediana Spearman `-0,180`). Ningún threshold de validación cumplió simultáneamente las cuatro gates en ninguno de los arms; ambos congelaron abstain y realizaron 0 trades OOS. No se relajarán gates ni se probará incertidumbre como filtro. `advance_to_uncertainty_abstention_ablation=false`; el siguiente punto admisible de la cola es Surprise + PatchCore, predeclarado como un factor nuevo y con coreset solo de train.

Actualización 2026-07-11 05:05 CEST: PatchCore abstention v1 quedó predeclarado. No se reutiliza el selector flat-history porque su espacio incluía buckets distintos del live exacto; el control es el payoff head d25/d35. Un único modelo mensual alimenta ambos arms y PatchCore solo añade un cap de distancia seleccionado en inner validation. Coreset k-center determinista de 128 latentes actionless por ticker, train-only; siete quantiles fijos, sin sweep. Continuar exige simultáneamente gates downstream completas por ticker y distancia-error positiva reproducible en 10/15 celdas.

Actualización final 2026-07-11 05:15 CEST: PatchCore queda rechazado como filtro de trading. La distancia sí correlaciona con error en 10/15 celdas (mediana Spearman `0,099`), pero 0/1.470 combinaciones cumplieron simultáneamente las gates y las 15 policies se abstuvieron. No se explorarán tamaños/quantiles adicionales. La señal se conserva solo como diagnóstico de drift; `continue_from_patchcore=false`. El último punto de la cola es AdaJEPA solo en shadow, nunca adaptación de la policy productiva.

Actualización 2026-07-11 05:25 CEST: el paper primario confirma adaptación self-supervised después de observar la transición y antes de replantear, con uno o pocos pasos de gradiente. El OOF local no es aún un sustrato válido: cada mes usa un encoder distinto y no exporta `pred_z`. La precondición de AdaJEPA será crear cinco espacios latentes congelados por fold y re-encodear en cada uno todo train/inner/test con el mismo checkpoint. Adaptar directamente el parquet OOF mezclaría coordenadas y queda prohibido.

Actualización 2026-07-11 05:45 CEST: la precondición técnica ya está implementada. Un exportador separado produce pares causalmente auditables `z_t/pred_z/target_z` desde un checkpoint congelado, impide cruzar gaps/sesiones y marca el target como observable solo en el timestamp siguiente. Falta construir los cinco checkpoints/espacios coherentes antes de probar un único paso de adaptación shadow.

El build de esos cinco espacios quedó predeclarado con train_end anterior a tres meses internos, arquitectura flat y presupuesto idéntico. Todavía no contiene adaptación ni downstream; solo habilita una comparación AdaJEPA fiel y causal.

Informe, hashes y tablas de la ablación de historia quedaron publicados en `8da7a7a`.
