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

def visualize(model_path, normalizer_path, data_path, model_size, target_feature=None, no_plot=False):
    device = get_device()
    
    # 1. Cargar modelo
    print(f"Cargando modelo {model_size} desde {model_path}...")
    try:
        model, normalizer = load_hybrid_model(model_path, normalizer_path, model_size, device)
    except FileNotFoundError:
        print(f"Error: No se encuentra el modelo en {model_path}. Entrena primero con train_hybrid.py o train_walkforward.py")
        return

    # 2. Cargar una muestra de datos reales
    df = pd.read_csv(data_path)
    
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
    importance_df = importance_df.sort_values('Importance', ascending=False).reset_index(drop=True)
    
    # --- VISUALIZACIÓN DE FEATURE ESPECÍFICO ---
    if target_feature:
        if target_feature in FEATURE_COLUMNS:
            idx = FEATURE_COLUMNS.index(target_feature)
            # Find the actual rank in the sorted dataframe
            rank_df = importance_df[importance_df['Feature'] == target_feature]
            if not rank_df.empty:
                rank_pos = rank_df.index[0]
                weight = rank_df['Importance'].values[0]
                
                explain_attention(target_feature, weight, idx)
                print(f"\n  Ranking: #{rank_pos + 1} de {len(FEATURE_COLUMNS)}")
                
                # Mostrar contexto (vecinos en ranking)
                print("\n  Contexto (Vecinos en importancia):")
                start = max(0, rank_pos - 2)
                end = min(len(importance_df), rank_pos + 3)
                subset = importance_df.iloc[start:end]
                
                for i, row in subset.iterrows():
                    f = row['Feature']
                    w = row['Importance']
                    prefix = ">>" if f == target_feature else "  "
                    print(f"  {prefix} #{i+1:2d} {f:25s}: {w:.4f}")
        else:
            print(f"Error: El feature '{target_feature}' no existe.")
            print(f"Features disponibles: {', '.join(FEATURE_COLUMNS[:5])}...")
    
    # 4. Crear Gráfico (si no se deshabilita)
    if not no_plot:
        plt.figure(figsize=(12, 8))
        
        # Plot top 30 to avoid clutter
        top_df = importance_df.head(30)
        sns.barplot(x='Importance', y='Feature', hue='Feature', data=top_df, palette='viridis', legend=False)
        plt.title(f'Feature Importance Top 30 ({model_size.upper()})', fontsize=16)
        plt.xlabel('Weighting (Importance)', fontsize=12)
        plt.grid(axis='x', alpha=0.3)
        plt.tight_layout()
        
        if not target_feature:
            print("\nTop 5 Indicadores más importantes para el modelo:")
            print(importance_df.head(5))
        
        plt.show()

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Visualizar atención del modelo híbrido")
    
    # Argumentos de configuración del modelo y datos
    parser.add_argument("--model", type=str, default="models/trading_hybrid_wf.pt", help="Ruta al archivo del modelo (.pt)")
    parser.add_argument("--normalizer", type=str, default="models/hybrid_normalizer_wf.npz", help="Ruta al archivo del normalizador (.npz)")
    parser.add_argument("--data", type=str, default="training_data/training_data.csv", help="Ruta al archivo de datos CSV")
    parser.add_argument("--model-size", type=str, default="micro", choices=["micro", "small", "medium", "large"], help="Tamaño de la arquitectura")
    
    # Argumentos de visualización
    parser.add_argument("--feature", type=str, help="Nombre del feature para inspeccionar en detalle")
    parser.add_argument("--no-plot", action="store_true", help="No mostrar el gráfico")
    
    args = parser.parse_args()
    
    visualize(
        model_path=args.model,
        normalizer_path=args.normalizer,
        data_path=args.data,
        model_size=args.model_size,
        target_feature=args.feature, 
        no_plot=args.no_plot
    )