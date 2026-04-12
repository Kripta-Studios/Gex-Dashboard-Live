import os
import pandas as pd
import urllib.request
import zipfile
import shutil

def generar_esquema_desde_github(archivo_salida="columnas_globem_github.txt"):
    """
    Descarga el repo de GLOBEM, extrae la carpeta data_raw y genera el esquema.
    """
    url_zip = "https://github.com/UW-EXP/GLOBEM/archive/refs/heads/main.zip"
    archivo_zip = "globem_repo.zip"
    carpeta_destino = "globem_temp"
    
    # 1. Descargar y descomprimir el repositorio
    print("📥 Descargando datos de muestra desde GitHub...")
    urllib.request.urlretrieve(url_zip, archivo_zip)
    
    with zipfile.ZipFile(archivo_zip, 'r') as zip_ref:
        zip_ref.extractall(carpeta_destino)
        
    os.remove(archivo_zip) # Limpiamos el zip
    
    # La ruta donde están los CSVs
    ruta_data_raw = os.path.join(carpeta_destino, "GLOBEM-main", "data_raw")
    
    print(f"✅ Datos descargados. Leyendo CSVs en: {ruta_data_raw}")
    
    archivos_csv = []
    for raiz, directorios, archivos in os.walk(ruta_data_raw):
        for archivo in archivos:
            if archivo.endswith('.csv'):
                archivos_csv.append(os.path.join(raiz, archivo))

    # 2. Generar el archivo de texto
    with open(archivo_salida, 'w', encoding='utf-8') as f:
        f.write("=== ESQUEMA DEL DATASET GLOBEM (DATOS DE MUESTRA GITHUB) ===\n")
        f.write("Nota: Las unidades no vienen en el CSV. Deben inferirse.\n\n")
        
        carpetas = {}
        for ruta in archivos_csv:
            carpeta = os.path.basename(os.path.dirname(ruta))
            if carpeta not in carpetas:
                carpetas[carpeta] = []
            carpetas[carpeta].append(ruta)
            
        for carpeta, rutas in carpetas.items():
            f.write(f"\n📁 DIRECTORIO O CATEGORÍA: {carpeta}\n")
            f.write("=" * 60 + "\n")
            
            for ruta_csv in rutas:
                nombre_archivo = os.path.basename(ruta_csv)
                try:
                    # Leer solo la fila de encabezados
                    columnas = pd.read_csv(ruta_csv, nrows=0).columns.tolist()
                    
                    f.write(f"\n  📄 Archivo: {nombre_archivo}\n")
                    f.write("  " + "-" * 45 + "\n")
                    
                    for col in columnas:
                        f.write(f"    • {col:<35} [Unidad: ]\n")
                        
                except Exception as e:
                    f.write(f"  ⚠️ Error al leer {nombre_archivo}: {e}\n")

    # (Opcional) Puedes borrar la carpeta temporal si solo querías el txt
    # shutil.rmtree(carpeta_destino) 
    
    print(f"🎉 Proceso completado. Revisa el archivo: {archivo_salida}")

# Ejecutar la función
generar_esquema_desde_github()