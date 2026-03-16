#!/bin/bash
#SBATCH -J RL-Bot-TFG
#SBATCH -o RL-Bot-TFG_%j.log
#SBATCH -e RL-Bot-TFG_%j.err
#SBATCH -c 64
#SBATCH --mem-per-cpu=1G
#SBATCH -t 3:00:00

set -eo pipefail

# ── Carga de Módulos y Variables de Entorno ──────────────────────────────────
module load cesga/system
module load miniconda3/22.11.1-1

# Activar el entorno donde tienes PyTorch (versión CPU), SB3, etc.
source activate rl_trading

# ── Rutas y Directorios (Scratch para Rendimiento) ──────────────────────────
# Lustre Scratch es mucho más rápido para leer miles de shards .pkl
USER_SCRATCH="/mnt/lustre/scratch/nlsas/home/usc/cursos/$(whoami)"
WORKDIR="$USER_SCRATCH/rl_trading_run"
SCRIPT_DIR="$HOME/Gex-Dashboard-Live"

mkdir -p "$WORKDIR"
cd "$WORKDIR"

# ── Preparación de Datos ───────────────────────────────────────────────────
echo "Vinculando datos al scratch..."
# Aseguramos que el directorio del WORKDIR existe antes de enlazar
mkdir -p "$WORKDIR"

# Enlazamos las carpetas del Scratch al directorio de trabajo
ln -sf "$USER_SCRATCH/training_data" "$WORKDIR/training_data"
ln -sf "$USER_SCRATCH/rl_data" "$WORKDIR/rl_data"

# Enlazamos modelos y backtest desde el HOME
ln -sf "$SCRIPT_DIR/neural/models" "$WORKDIR/models"
ln -sf "$SCRIPT_DIR/backtest" "$WORKDIR/backtest"
mkdir -p "$WORKDIR/rl_models"

# ── Ejecución de Pipeline ──────────────────────────────────────────────────
cd "$SCRIPT_DIR/neural"

# PASO 1 — Entrenamiento GBT
echo -e "\n=== [GBT] ENTRENAMIENTO ==="
python train_walkforward.py \
  --data "$WORKDIR/training_data/training_data_spx_qqq.parquet" \
  --model-size small \
  --train-months 4 \
  --test-months 1 \
  --ensemble 5 \
  --top-n-windows 10 \
  --min-window 20 \
  --model_path "$WORKDIR/models/trading_hybrid_wf.joblib" \
  --norm_path "$WORKDIR/models/hybrid_normalizer_wf.npz"

# PASO 2 — Generación de Índice de Episodios
echo -e "\n=== [RL] GENERANDO INDICE ==="
python generate_episode_index.py \
  --data "$WORKDIR/training_data/training_data_spx_qqq.parquet" \
  --output "$WORKDIR/rl_data/episode_index.parquet"

# PASO 3 — RL Training (PPO) con CPU
echo -e "\n=== [RL] TRAINING (CPU) ==="
python -m rl.training \
  --episode-index "$WORKDIR/rl_data/episode_index.parquet" \
  --options-cache "$WORKDIR/rl_data/rl_options_cache_chunks" \
  --save-dir "$WORKDIR/rl_models" \
  --total-updates 600 \
  --workers 64

echo -e "\n=== PIPELINE FINALIZADO CON EXITO ==="

# ── Backup de Resultados a HOME ─────────────────────────────────────────────
BACKUP_DIR="$SCRIPT_DIR/resultados_entrenamiento_$(date +%Y%m%d_%H%M)"
mkdir -p "$BACKUP_DIR"
cp "$WORKDIR/rl_models"/*.pt "$BACKUP_DIR/" 2>/dev/null || true
cp "$WORKDIR/models"/*.joblib "$BACKUP_DIR/" 2>/dev/null || true
cp "$WORKDIR/models"/*.npz "$BACKUP_DIR/" 2>/dev/null || true

echo "Resultados copiados a: $BACKUP_DIR"
echo "FIN: $(date)"