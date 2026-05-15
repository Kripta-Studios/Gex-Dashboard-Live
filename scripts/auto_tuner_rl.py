import subprocess
import time
import re
import os
import json
import sys
import optuna
from pathlib import Path

# --- CONFIGURACIÓN DEL BUSCADOR (Refinada según Logs) ---
# Hemos eliminado 1e-4 por colapso instantáneo y priorizado el rango 1e-5 a 5e-5
LR_RANGE = [1e-5, 1.5e-5, 2e-5] 
ENTROPY_RANGE = [0.015, 0.02, 0.025]
GAMMA_RANGE = [0.995, 0.998]
BATCH_RANGE = [256, 512] # Aumentado para mayor estabilidad de gradiente
CLIP_RANGE = [0.1, 0.15]
VALUE_COEFF_RANGE = [0.2, 0.3, 0.4] # 0.5 causaba demasiado ruido en el backbone
EPOCHS_RANGE = [2, 3, 4]

PROJECT_ROOT = Path(__file__).parent.parent.absolute()
CONFIG_PATH = PROJECT_ROOT / "neural" / "rl" / "config.py"
LOG_DIR = PROJECT_ROOT / "logs" / "tuning"
LOG_DIR.mkdir(parents=True, exist_ok=True)
MASTER_LOG = LOG_DIR / "tuner_master.log"
DB_PATH = f"sqlite:///{LOG_DIR / 'optuna_study.db'}"

def log_master(message):
    """Escribe en consola y en el archivo de log maestro (unbuffered)."""
    timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
    msg = f"[{timestamp}] {message}"
    print(msg)
    with open(MASTER_LOG, "a", encoding="utf-8") as f:
        f.write(msg + "\n")
        f.flush()

def modify_config(lr, entropy, gamma, batch_size, clip, v_coeff, epochs):
    """Modifica dinámicamente el archivo config.py."""
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        content = f.read()
    
    # Reemplazos usando regex
    content = re.sub(r'"learning_rate":\s*[\d\.e-]+', f'"learning_rate": {lr}', content)
    content = re.sub(r'"entropy_coeff":\s*[\d\.e-]+', f'"entropy_coeff": {entropy}', content)
    content = re.sub(r'"gamma":\s*[\d\.e-]+', f'"gamma": {gamma}', content)
    content = re.sub(r'"batch_size":\s*\d+', f'"batch_size": {batch_size}', content)
    content = re.sub(r'"clip_epsilon":\s*[\d\.e-]+', f'"clip_epsilon": {clip}', content)
    content = re.sub(r'"value_loss_coeff":\s*[\d\.e-]+', f'"value_loss_coeff": {v_coeff}', content)
    content = re.sub(r'"ppo_epochs":\s*\d+', f'"ppo_epochs": {epochs}', content)
    
    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        f.write(content)

def run_attempt(iteration, lr, entropy, gamma, batch_size, clip, v_coeff, epochs):
    """Ejecuta una sesión de entrenamiento y vigila el colapso."""
    log_file = LOG_DIR / f"run_{iteration}_lr{lr}_ent{entropy}.log"
    
    cmd = [
        "python", "-u", "-m", "rl.training",
        "--episode-index", "../rl_data/episode_index.parquet",
        "--options-cache", "../rl_data/rl_options_cache_chunks",
        "--save-dir", f"../rl_models_tune/run_{iteration}",
        "--total-updates", "500",
        "--workers", "10" 
    ]
    
    log_master(f"[TRIAL {iteration}] LR={lr}, ENT={entropy}, GAM={gamma}, BATCH={batch_size}, CLIP={clip}, V={v_coeff}, EP={epochs}")
    
    neural_dir = PROJECT_ROOT / "neural"
    
    process = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
        cwd=str(neural_dir)
    )

    completed = False
    consecutive_dead_steps = 0
    max_dead_steps = 14
    steps_total = 0
    rewards = []
    
    with open(log_file, "w", encoding="utf-8") as f:
        for line in process.stdout:
            f.write(line)
            f.flush()
            
            # Captura de progreso real (Update X/500)
            update_match = re.search(r"Update\s+(\d+)/", line)
            if update_match:
                steps_total = int(update_match.group(1))
            
            # Captura de Calidad (usamos el 'Score' de evaluación del RL)
            score_match = re.search(r"Score:\s+([\d\.]+)", line)
            if score_match:
                try:
                    rewards.append(float(score_match.group(1)))
                except ValueError:
                    pass

            if "nan" in line.lower():
                log_master(f"  [!] EXPLOSIÓN (NaN) en step {steps_total}.")
                process.terminate()
                break

            entropy_match = re.search(r"Entropy:\s+([\d\.]+)", line)
            if entropy_match:
                ent_val = float(entropy_match.group(1))
                if ent_val < 0.005:
                    log_master(f"  [!] COLAPSO ENTROPÍA ({ent_val}) en step {steps_total}.")
                    process.terminate()
                    break
                if steps_total > 60 and ent_val > 1.5:
                    log_master(f"  [!] RUIDO EXCESIVO ({ent_val}) en step {steps_total}.")
                    process.terminate()
                    break
            
            # Detección de éxito total
            if "TRAINING COMPLETE" in line or "TRAINING COMPLETADO" in line:
                completed = True

            if "Approx KL:  0.0000" in line:
                consecutive_dead_steps += 1
            elif "Approx KL:" in line:
                consecutive_dead_steps = 0
            
            if consecutive_dead_steps >= max_dead_steps:
                log_master(f"  [!] KL CONGELADO en step {steps_total}.")
                process.terminate()
                break

    process.wait()
    # Retornamos si se completó el entrenamiento
    return completed, steps_total, rewards

def objective(trial):
    # Sugerencias de Optuna
    lr = trial.suggest_categorical("lr", LR_RANGE)
    ent = trial.suggest_categorical("entropy", ENTROPY_RANGE)
    gam = trial.suggest_categorical("gamma", GAMMA_RANGE)
    batch = trial.suggest_categorical("batch_size", BATCH_RANGE)
    clip = trial.suggest_categorical("clip_epsilon", CLIP_RANGE)
    v_coeff = trial.suggest_categorical("value_coeff", VALUE_COEFF_RANGE)
    epochs = trial.suggest_categorical("ppo_epochs", EPOCHS_RANGE)
    
    modify_config(lr, ent, gam, batch, clip, v_coeff, epochs)
    
    success, steps, rewards = run_attempt(trial.number, lr, ent, gam, batch, clip, v_coeff, epochs)
    
    # Cálculo de Score Final para Optuna (Refinado: Supervivencia * Calidad)
    if steps < 300:
        # PENALIZACIÓN: No llegó al mínimo de estabilidad requerido
        log_master(f"  [!] TRIAL INSUFICIENTE ({steps} steps). Penalizando score a 0.0")
        return 0.0

    # Prioridad: Calidad del modelo (Mejor 'Score' de evaluación encontrado)
    best_rl_score = max(rewards) if len(rewards) > 0 else 0.0
    
    # El Score total es el producto de la supervivencia por la calidad real
    survival_ratio = steps / 500.0
    total_optuna_score = survival_ratio * best_rl_score
    
    log_master(f"  [Trial Finish] Steps: {steps}, Best RL Score: {best_rl_score:.4f}, Total Score: {total_optuna_score:.4f}")
    time.sleep(5)
    return total_optuna_score

if __name__ == "__main__":
    log_master("=== RL BAYESIAN AUTO-TUNER (Optuna + Log Knowledge) ===")
    log_master(f"DB: {DB_PATH}")
    
    study = optuna.create_study(
        study_name="rl_stability_tuning_v2", # Nueva versión para separar de pruebas anteriores
        storage=DB_PATH,
        direction="maximize",
        load_if_exists=True
    )
    
    # --- ENQUEUING: Priming con lo que mejor funcionó en los logs ---
    # Caso 1: El que más aguantó (run_1_lr2e-05) pero con clip más bajo para evitar explosión
    # Trial 0: El ganador absoluto (Run 3)
    study.enqueue_trial({
        "lr": 1e-05, "entropy": 0.02, "gamma": 0.998, 
        "batch_size": 256, "clip_epsilon": 0.1, "value_coeff": 0.4, "ppo_epochs": 3
    })
    
    # Trial 1: Variante conservadora (Más entropía para mayor exploración estable)
    study.enqueue_trial({
        "lr": 1e-05, "entropy": 0.025, "gamma": 0.998, 
        "batch_size": 256, "clip_epsilon": 0.1, "value_coeff": 0.4, "ppo_epochs": 3
    })

    # Trial 2: Promesa - El ganador (Trial 0) bajando value_coeff de 0.4 a 0.3
    study.enqueue_trial({
        "lr": 1e-05, "entropy": 0.02, "gamma": 0.998, 
        "batch_size": 256, "clip_epsilon": 0.1, "value_coeff": 0.3, "ppo_epochs": 3
    })
    
    try:
        study.optimize(objective, n_trials=None)
    except KeyboardInterrupt:
        log_master("Deteniendo el tuner por el usuario...")
        
    log_master("Resumen de mejores parámetros:")
    if study.best_trial:
        log_master(json.dumps(study.best_params, indent=4))
