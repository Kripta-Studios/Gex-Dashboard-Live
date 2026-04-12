import os
import pandas as pd
import kagglehub

def extraer_columnas_a_txt(ruta_dataset, archivo_salida="columnas_dataset.txt"):
    """
    Recorre un directorio, lee los encabezados de todos los archivos CSV 
    y los guarda de forma ordenada en un archivo de texto.
    """
    archivos_csv = []
    
    # 1. Buscamos todos los archivos CSV en la ruta y sus subcarpetas
    for raiz, directorios, archivos in os.walk(ruta_dataset):
        for archivo in archivos:
            if archivo.endswith('.csv'):
                archivos_csv.append(os.path.join(raiz, archivo))
    
    if not archivos_csv:
        print(f"No se encontraron archivos CSV en la ruta: {ruta_dataset}")
        return

    # 2. Creamos y escribimos en el archivo de texto
    with open(archivo_salida, 'w', encoding='utf-8') as f:
        f.write(f"--- ESQUEMA DEL DATASET: {ruta_dataset} ---\n\n")
        f.write("NOTA: Las unidades no vienen incluidas en los archivos CSV.\n")
        f.write("Deben revisarse en la documentación oficial (ej. README.md).\n\n")
        
        for ruta_csv in archivos_csv:
            nombre_archivo = os.path.basename(ruta_csv)
            carpeta_origen = os.path.basename(os.path.dirname(ruta_csv))
            
            try:
                # Leemos solo la fila de encabezados (nrows=0) para hacerlo instantáneo
                columnas = pd.read_csv(ruta_csv, nrows=0).columns.tolist()
                
                f.write(f"📁 Subcarpeta: {carpeta_origen} | 📄 Archivo: {nombre_archivo}\n")
                f.write("-" * 65 + "\n")
                
                for col in columnas:
                    # Dejamos un espacio estructurado para que anotes la unidad
                    f.write(f"  • {col:<30} [Unidad: ]\n")
                f.write("\n\n")
                
            except Exception as e:
                f.write(f"⚠️ Error al leer el archivo {nombre_archivo}: {e}\n\n")
    
    print(f"✅ Proceso completado con éxito. Revisa el archivo: {archivo_salida}")

# ==========================================
# 1. EJECUCIÓN PARA EL DATASET DE FITBIT
# ==========================================
print("Descargando dataset de Fitbit...")
ruta_fitbit = kagglehub.dataset_download("arashnic/fitbit")
print(f"Ruta descargada: {ruta_fitbit}")

# Generamos el txt para Fitbit
extraer_columnas_a_txt(ruta_fitbit, "columnas_fitbit.txt")


# ==========================================
# 2. EJECUCIÓN PARA EL DATASET GLOBEM (MULTI-YEAR)
# ==========================================
# Según el README que compartiste, estos datos suelen guardarse en la carpeta 'data_raw'.
# Solo necesitas descomentar estas líneas y asegurarte de poner la ruta correcta a tu carpeta descargada.

# ruta_globem = "./data_raw" # Cambia esto por la ruta donde guardaste el dataset GLOBEM
# extraer_columnas_a_txt(ruta_globem, "columnas_globem.txt")pip