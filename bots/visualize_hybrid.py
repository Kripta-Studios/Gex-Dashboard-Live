"""
Visualize Feature Importance from Trained Hybrid Model
"""
import torch
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
from hybrid_model import load_hybrid_model, FEATURE_COLUMNS, get_device

# Configuración
MODEL_PATH = "models/trading_hybrid.pt"
NORMALIZER_PATH = "models/hybrid_normalizer.npz"
DATA_PATH = "training_data/training_data.csv" # Tu CSV
MODEL_SIZE = "small" # Asegúrate que coincida con lo que entrenaste

def visualize():
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
        # El modelo devuelve (logits, attention_weights)
        _, attention = model(tensor_x, return_attention=True)
    
    # Promediar la importancia de cada feature en las 100 muestras
    # attention shape: (100, num_features)
    avg_attention = attention.mean(dim=0).cpu().numpy()
    
    # 4. Crear Gráfico
    plt.figure(figsize=(12, 8))
    
    # Crear DataFrame para el plot
    importance_df = pd.DataFrame({
        'Feature': FEATURE_COLUMNS,
        'Importance': avg_attention
    })
    
    # Ordenar por importancia
    importance_df = importance_df.sort_values('Importance', ascending=False)
    
    # Plot
    sns.barplot(x='Importance', y='Feature', data=importance_df, palette='viridis')
    plt.title(f'Qué está mirando tu IA ({MODEL_SIZE.upper()})', fontsize=16)
    plt.xlabel('Peso de Atención (Importancia)', fontsize=12)
    plt.grid(axis='x', alpha=0.3)
    plt.tight_layout()
    
    print("\nTop 5 Indicadores más importantes para el modelo:")
    print(importance_df.head(5))
    
    plt.show()

if __name__ == "__main__":
    visualize()