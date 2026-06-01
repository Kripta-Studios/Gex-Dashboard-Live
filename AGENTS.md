# 🤖 AI Agent Hand-off: GBT + RL Options Pipeline

Este documento está diseñado específicamente para que un **Agente de IA** (como tú o tu sucesor) pueda entender rápidamente la arquitectura, el flujo de ejecución y el propósito de cada script dentro de este proyecto.

El objetivo supremo del sistema es lograr **rentabilidad consistente y alto volumen de operaciones** (Target: >2000 trades, PnL >250k) operando opciones 0DTE del SPX. El éxito definitivo se mide en la salida de `backtest/backtest_rl.py`.

---

## 🚀 El Pipeline Principal: `neural/run_pipeline.ps1`

El script `run_pipeline.ps1` es el orquestador absoluto de todo el entrenamiento. Automatiza el flujo desde la ingesta de datos brutos hasta la visualización final del backtest. Está dividido en "Pasos" ejecutables mediante flags (ej. `-tr` salta directo al entrenamiento RL).

1. **Paso 0 (Data Collection):** Ejecuta `collect_training_data_spx_qqq.py`. Recolecta y empaqueta los datos de opciones, underlying y features de mercado.
2. **Paso 1 (GBT Training):** Ejecuta `train_walkforward.py`. Entrena un ensemble de modelos LightGBM (Gradient Boosting Trees) que actúan como "Oráculo Base". El GBT decide *cuándo* hay una oportunidad en el mercado.
3. **Paso 2 (Episode Index):** Ejecuta `generate_episode_index.py`. Escanea la historia del mercado y filtra los minutos exactos donde el GBT tiene una confianza superior al umbral (`min_confidence`, ej. 0.450). Estos instantes se convierten en los puntos de inicio de los "Episodios" de RL.
4. **Paso 3 (Preprocess RL Cache):** Ejecuta `run_preprocess.py`. Dado el índice de episodios, pre-calcula y guarda en disco (en formato *chunks*) todos los features y datos de las cadenas de opciones de esos episodios. Esto evita que el RL tenga que recalcular todo en cada paso, acelerando el entrenamiento x100.
5. **Paso 4 (RL Training):** Ejecuta `rl/training.py`. Lanza el algoritmo PPO. El agente RL aprende a elegir qué *Strike* operar y *cuándo salir* (Exit) para maximizar la rentabilidad sobre las señales del GBT.
6. **Paso 6 y 7 (Backtesting):** Ejecuta `backtest_gbt_parquet.py` (solo GBT como baseline) y `backtest_rl.py` (GBT + RL).
7. **Paso 8 (Visualización):** Genera gráficos y métricas de feature drift.

---

## 📁 Archivos Core en `neural/`

- **`train_walkforward.py`**: El corazón predictivo. Usa *Walk-Forward Validation* para entrenar el modelo LightGBM que da el disparo inicial (entry signal).
- **`hybrid_model.py` / `gbt_model.py`**: Definiciones de las clases wrapper para manejar la inferencia de los árboles.
- **`diagnose_pipeline.py` / `diagnose_gbm.py`**: Scripts útiles para aislar bugs de convergencia y chequear overfitting antes de pasar al RL.

---

## 🧠 El Agente RL: Directorio `neural/rl/`

El directorio RL contiene un agente **Proximal Policy Optimization (PPO)**. La arquitectura usa un *Pure MLP Backbone* (~172k parámetros) que alimenta dos cabezas políticas (Strike Head y Exit Head) y un Value Head (Critic).

- **`config.py`**: El mapa del tesoro. Define los hiperparámetros de entrenamiento, el tamaño de la red, los `entropy_coeffs`, el `kl_target` y las fases del **Curriculum Learning**.
- **`agent.py`**: La red neuronal PyTorch. Aquí se define el backbone y las cabezas. Históricamente tenía un *Mixture of Experts (MoE)*, pero fue bypasseado para usar un MLP monolítico directo.
- **`environment.py`**: El gimnasio del agente. Simula el mercado de opciones minuto a minuto. Recibe la acción del agente y devuelve el estado modificado y el reward latente. Importante: impone frenos mecánicos como el `min_hold_minutes`.
- **`rewards.py`**: Define la función de recompensa. El agente está programado para buscar "Home-runs" (beneficios del 300%+).
  - *Ojo:* El `compute_terminal_reward` fue re-escalado multiplicando por `0.1` para acotar sus valores a `[-0.6, 2.0]` y evitar destruir la Varianza del Value Head frente a los *step rewards* (~0.05).
- **`training.py`**: El bucle de entrenamiento PPO.
  - Usa *multiprocessing* en `worker_collect` para recopilar experiencia en paralelo.
  - Implementa *Adaptive KL Penalty* y *Early Stopping* intra-batch (si `KL > kl_target * 2.0`).
  - **Crítico:** Contiene lógica para ignorar las transiciones del buffer donde el `environment` fuerza un HOLD, impidiendo así que el Exit Head colapse a entropía cero por aprender falsos positivos.

---

## 🎯 Directrices para tu Optimización Continua

Si estás leyendo esto porque el Humano te ha pedido seguir mejorando el PnL, enfócate en esto:

1. **Vigila el Colapso del Exit Head:** El agente RL tiende a buscar atajos. Asegúrate de que `H[Exit]` (Entropía) no caiga bruscamente a 0 en los primeros 100 updates. El filtro de `episode_forced_actions` en el buffer y el ruido logit (`logit_noise_exit_override=0.30`) son tus salvavidas actuales.
2. **Convergencia del Critic:** El pre-entrenamiento del critic debe acabar con un `V_loss` muy bajo (idealmente < 1.0). Si sube de 5.0, los *Advantages* del PPO serán puro ruido. Juega con el escalado en `rewards.py` y el `pretrain_critic_samples` de ser necesario.
3. **El Backtest Manda:** No te fíes ciegamente del PnL del entorno de entrenamiento. El verdadero juez es `backtest_rl.py`. Asegúrate de que el agente RL logre aumentar el *Profit Factor* (PF) del GBT base mientras mantiene un volumen suficiente de operaciones (*Win Rate* no necesita ser >50% debido a la asimetría de opciones, pero los winners deben ser masivos).
