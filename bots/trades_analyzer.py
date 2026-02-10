import os
import json
import glob
import pandas as pd
from datetime import datetime

# --- CONFIGURACIÓN ---
# Cambia esto por la ruta donde tienes tus archivos .json
CARPETA_JSONS = "./trades_live" 

def cargar_trades(carpeta):
    """Lee todos los archivos .json de la carpeta y devuelve un DataFrame."""
    ruta_busqueda = os.path.join(carpeta, "*.json")
    archivos = glob.glob(ruta_busqueda)
    
    lista_trades = []

    if not archivos:
        print(f"⚠️ No se encontraron archivos .json en: {carpeta}")
        return pd.DataFrame()

    print(f"📂 Procesando {len(archivos)} archivos...")

    for archivo in archivos:
        try:
            with open(archivo, 'r', encoding='utf-8') as f:
                data = json.load(f)
                
                # Aplanamos la estructura para extraer lo importante
                trade = {
                    'Trade ID': data.get('trade_id'),
                    'Ticker': data.get('ticker'),
                    'Direction': data.get('direction'),
                    'Entry Time': data['entry'].get('time'),
                    'Exit Time': data['exit'].get('time'),
                    'Entry Price': data['entry'].get('price'),
                    'Exit Price': data['exit'].get('price'),
                    'PnL Points': data['pnl'].get('points'),
                    'PnL Percent': data['pnl'].get('percent'),
                    'Exit Reason': data['exit'].get('reason'),
                    # Agregamos señales clave por si quieres filtrar después
                    'Gamma Regime': data['signals'].get('gamma_regime'),
                    'Vanna Signal': data['signals'].get('vanna_signal')
                }
                lista_trades.append(trade)
        except Exception as e:
            print(f"❌ Error leyendo {archivo}: {e}")

    return pd.DataFrame(lista_trades)

def generar_reporte(df):
    """Genera estadísticas y medias basadas en el DataFrame."""
    if df.empty:
        return

    # Conversión de tipos de datos
    df['Entry Time'] = pd.to_datetime(df['Entry Time'])
    df['Exit Time'] = pd.to_datetime(df['Exit Time'])
    df['Duration'] = df['Exit Time'] - df['Entry Time']
    
    # Cálculos básicos
    total_trades = len(df)
    win_trades = df[df['PnL Points'] > 0]
    loss_trades = df[df['PnL Points'] <= 0]
    win_rate = (len(win_trades) / total_trades) * 100

    # Medias
    avg_pnl_points = df['PnL Points'].mean()
    avg_pnl_percent = df['PnL Percent'].mean()
    avg_duration = df['Duration'].mean()
    
    # Sumas
    total_pnl_points = df['PnL Points'].sum()

    print("\n" + "="*40)
    print("📊 RESUMEN GENERAL DE TRADING")
    print("="*40)
    print(f"Total Trades:      {total_trades}")
    print(f"Win Rate:          {win_rate:.2f}% ({len(win_trades)}W - {len(loss_trades)}L)")
    print("-" * 40)
    print(f"💰 PnL Total (pts): {total_pnl_points:.2f}")
    print(f"📈 PnL Medio (pts): {avg_pnl_points:.2f} pts por trade")
    print(f"📈 PnL Medio (%):   {avg_pnl_percent:.2f}% por trade")
    print(f"⏱️ Duración Media:  {avg_duration}")
    print("="*40)

    # Agrupación por Ticker
    print("\n🔹 DESGLOSE POR TICKER")
    print(df.groupby('Ticker')[['PnL Points', 'PnL Percent']].mean())

    # Agrupación por Dirección (LONG/SHORT)
    print("\n🔹 DESGLOSE POR DIRECCIÓN")
    print(df.groupby('Direction')[['PnL Points', 'PnL Percent']].mean())
    
    return df

# --- EJECUCIÓN ---
if __name__ == "__main__":
    # Asegúrate de crear la carpeta o cambiar la ruta arriba
    # Si tus json están en la misma carpeta que el script, usa "."
    df_trades = cargar_trades(CARPETA_JSONS)
    
    if not df_trades.empty:
        # Opcional: Guardar resumen en Excel/CSV
        # df_trades.to_csv("resumen_trades.csv", index=False)
        generar_reporte(df_trades)
