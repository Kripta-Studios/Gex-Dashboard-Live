"""
Visualize Feature Importance from Trained Hybrid Model
"""
import torch
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
import argparse
from hybrid_model import load_hybrid_model, FEATURE_COLUMNS, get_device

# Configuración
MODEL_PATH = "models/trading_hybrid.pt"
NORMALIZER_PATH = "models/hybrid_normalizer.npz"
DATA_PATH = "training_data/training_data.csv" # Tu CSV
MODEL_SIZE = "medium" # Must match what was used during training

def explain_attention(feature_name, weight, feature_idx):
    """Prints a detailed explanation of how the attention weight is calculated."""
    print(f"\n" + "="*60)
    print(f"  🧠 EXPLICACIÓN DE ATENCIÓN: {feature_name}")
    print(f"="*60)
    print(f"  Este feature tiene un peso de atención de: {weight:.4f}")
    print(f"  (Promedio sobre 100 muestras aleatorias)")
    
    print("\n  ¿Cómo se calcula este número?")
    print(f"  1. Feature Embedding: El valor crudo de {feature_name} se proyecta a un vector de 64 dimensiones.")
    print(f"  2. Type Embedding: Se suma un vector aprendido único para el índice {feature_idx}.")
    print(f"  3. Contexto: El mecanismo de Self-Attention mira a TODOS los demás features para ver relaciones.")
    print(f"  4. Query de Importancia: El modelo tiene una 'pregunta' aprendida (Query) que compara contra el estado final del feature.")
    print(f"  5. Score: El producto punto entre la Query y el Feature determina este peso.")
    
    if weight > 0.05:
        print(f"\n  [!] Este feature es MUY IMPORTANTE (>0.05). El modelo depende mucho de él.")
        print(f"      Pequeños cambios en {feature_name} pueden cambiar drásticamente la predicción.")
    elif weight > 0.02:
        print(f"\n  [i] Este feature es RELEVANTE (>0.02). Contribuye significativamente al resultado.")
    else:
        print(f"\n  [.] Este feature es SECUNDARIO (<0.02). El modelo lo usa como contexto, pero no guía la decisión principal.")

def visualize(target_feature=None, no_plot=False):
    device = get_device()
    
    # 1. Cargar modelo
    print(f"Cargando modelo {MODEL_SIZE}...")
    try:
        model, normalizer = load_hybrid_model(MODEL_PATH, NORMALIZER_PATH, MODEL_SIZE, device)
    except FileNotFoundError:
        print("Error: No se encuentra el modelo. Entrena primero con train_hybrid.py")
        return

    # 2. Cargar una muestra de datos reales
    df = pd.read_csv(DATA_PATH)
    
    # Tomar 100 muestras aleatorias para promediar la atención
    sample_df = df.sample(100)
    features = sample_df[FEATURE_COLUMNS].values.astype(np.float32)
    features = np.nan_to_num(features, nan=0.0)
    
    # Normalizar
    features_norm = normalizer.transform(features)
    tensor_x = torch.FloatTensor(features_norm).to(device)
    
    # 3. Obtener Atención
    model.eval()
    with torch.no_grad():
        # Model returns (logits, time_pred, attention_weights) with return_attention=True
        logits, time_pred, attention = model(tensor_x, return_attention=True)
    
    # Promediar la importancia de cada feature en las 100 muestras
    # attention shape: (100, num_features)
    avg_attention = attention.mean(dim=0).cpu().numpy()
    
    # Crear DataFrame de importancia
    importance_df = pd.DataFrame({
        'Feature': FEATURE_COLUMNS,
        'Importance': avg_attention
    })
    
    # Ordenar por importancia
    importance_df = importance_df.sort_values('Importance', ascending=False)
    
    # --- VISUALIZACIÓN DE FEATURE ESPECÍFICO ---
    if target_feature:
        if target_feature in FEATURE_COLUMNS:
            idx = FEATURE_COLUMNS.index(target_feature)
            weight = avg_attention[idx]
            rank = importance_df[importance_df['Feature'] == target_feature].index[0]
            rank_pos = importance_df.index.get_loc(rank) + 1
            
            explain_attention(target_feature, weight, idx)
            print(f"\n  Ranking: #{rank_pos} de {len(FEATURE_COLUMNS)}")
            
            # Mostrar contexto (vecinos en ranking)
            print("\n  Contexto (Vecinos en importancia):")
            start = max(0, rank_pos - 3)
            end = min(len(importance_df), rank_pos + 2)
            subset = importance_df.iloc[start:end]
            
            for i, (f, w) in enumerate(zip(subset['Feature'], subset['Importance'])):
                prefix = ">>" if f == target_feature else "  "
                print(f"  {prefix} #{start+i+1:2d} {f:25s}: {w:.4f}")
                
        else:
            print(f"Error: El feature '{target_feature}' no existe.")
            print(f"Features disponibles: {', '.join(FEATURE_COLUMNS[:5])}...")
    
    # 4. Crear Gráfico (si no se deshabilita)
    if not no_plot:
        plt.figure(figsize=(12, 8))
        
        # Plot
        sns.barplot(x='Importance', y='Feature', hue='Feature', data=importance_df, palette='viridis', legend=False)
        plt.title(f'Qué está mirando tu IA ({MODEL_SIZE.upper()})', fontsize=16)
        plt.xlabel('Peso de Atención (Importancia)', fontsize=12)
        plt.grid(axis='x', alpha=0.3)
        plt.tight_layout()
        
        if not target_feature:
            print("\nTop 5 Indicadores más importantes para el modelo:")
            print(importance_df.head(5))
        
        plt.show()

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Visualizar atención del modelo híbrido")
    parser.add_argument("--feature", type=str, help="Nombre del feature para inspeccionar en detalle")
    parser.add_argument("--no-plot", action="store_true", help="No mostrar el gráfico")
    
    args = parser.parse_args()
    
    visualize(target_feature=args.feature, no_plot=args.no_plot)