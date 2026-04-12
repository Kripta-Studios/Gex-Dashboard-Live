import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns

# Configuración de estilo
sns.set_theme(style="whitegrid")

def generar_visualizaciones(archivo_csv):
    # Cargar los datos generados previamente
    df = pd.read_csv(archivo_csv)
    
    # 1. Gráfico de Dispersión (Correlación)
    plt.figure(figsize=(10, 6))
    sns.scatterplot(data=df, x='Avg_Sedentary_Minutes', y='RMSSD_ms', hue='Estado_SNA', palette='viridis', s=100)
    plt.title('Correlación: RMSSD vs. Minutos Sedentarios', fontsize=14)
    plt.xlabel('Minutos Sedentarios Promedio', fontsize=12)
    plt.ylabel('RMSSD (ms) - Salud del SNA', fontsize=12)
    plt.savefig('1_correlacion_sna.png', bbox_inches='tight')
    plt.close()

    # 2. Ranking de RMSSD por Usuario
    df_sorted_rmssd = df.sort_values('RMSSD_ms', ascending=False)
    plt.figure(figsize=(12, 6))
    sns.barplot(data=df_sorted_rmssd, x='Id', y='RMSSD_ms', hue='Estado_SNA', palette='magma')
    plt.xticks(rotation=45)
    plt.title('Ranking de Salud del SNA (RMSSD) por Usuario', fontsize=14)
    plt.savefig('2_ranking_rmssd.png', bbox_inches='tight')
    plt.close()

    # 3. Distribución por Estado
    plt.figure(figsize=(8, 6))
    sns.boxplot(data=df, x='Estado_SNA', y='RMSSD_ms', palette='Set2')
    sns.stripplot(data=df, x='Estado_SNA', y='RMSSD_ms', color='black', alpha=0.5)
    plt.title('Distribución de RMSSD según Clasificación', fontsize=14)
    plt.savefig('3_distribucion_estado.png', bbox_inches='tight')
    plt.close()

    # 4. Comparativa Dual (Sedentarismo vs RMSSD)
    fig, ax1 = plt.subplots(figsize=(14, 7))
    ax1.set_xlabel('ID del Usuario')
    ax1.set_ylabel('RMSSD (ms)', color='tab:blue')
    sns.lineplot(data=df_sorted_rmssd, x='Id', y='RMSSD_ms', marker='o', color='tab:blue', ax=ax1, label='RMSSD')
    ax1.tick_params(axis='y', labelcolor='tab:blue')
    plt.xticks(rotation=45)

    ax2 = ax1.twinx()
    ax2.set_ylabel('Minutos Sedentarios', color='tab:red')
    sns.lineplot(data=df_sorted_rmssd, x='Id', y='Avg_Sedentary_Minutes', marker='s', color='tab:red', ax=ax2, label='Sedentarismo')
    ax2.tick_params(axis='y', labelcolor='tab:red')
    
    plt.title('Espejo de Salud: RMSSD vs. Sedentarismo', fontsize=14)
    plt.savefig('4_comparativa_dual.png', bbox_inches='tight')
    plt.close()

    print("✅ 4 Gráficos generados: correlacion_sna, ranking_rmssd, distribucion_estado y comparativa_dual.")

if __name__ == "__main__":
    generar_visualizaciones('reporte_final_sna.csv')