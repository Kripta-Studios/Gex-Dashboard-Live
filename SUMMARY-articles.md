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

Gates por ticker y mes: PnL > 0, WR > 50%, PF > 1,3 y más de 18 trades.

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

El selector flat runtime-equivalente está activo en `...flat..._walkforward_runtime_contract_v2/` y no debe duplicarse. Modal se ejecutará solo cuando flat termine y será idéntico salvo por los embeddings OOF ya congelados. La evidencia de representación ya calculada es desfavorable a `modal`; por tanto, no se avanzará a pérdidas intra/cross-modal si el informe final no demuestra una mejora reproducible tanto representacional como downstream.
