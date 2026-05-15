import re
from pathlib import Path

# Texto de prueba extraído de tus logs reales
sample_lines = [
    "  |- Current:    PF=1.88 WR=44.1% PnL=+0.1759 Hold=38m L/S=124/127 Stop=25%",
    "  -> New best Model found at step 25",
    "     Score: 1.621 (PF: 1.61 * HoldFactor: 1.17 * WRFactor: 0.86)",
    "  |- Entropy:    0.6972 (target: 0.03-0.10) H[S/E]=1.82/0.67",
    "  |- Approx KL:  0.0075 (avg:0.0075)"
]

print("=== TEST DE REGEX PARA AUTO-TUNER ===")

# 1. Test de PnL (por si acaso lo necesitamos)
pnl_regex = r"PnL=([\+\-]?[\d\.]+)"
# 2. Test de Score (el que usaremos ahora)
score_regex = r"Score:\s+([\d\.]+)"
# 3. Test de Colapso (Entropía)
entropy_regex = r"Entropy:\s+([\d\.]+)"

for line in sample_lines:
    print(f"\nAnalizando: {line.strip()}")
    
    score_match = re.search(score_regex, line)
    if score_match:
        print(f"  [OK] Score encontrado: {score_match.group(1)}")
        
    pnl_match = re.search(pnl_regex, line)
    if pnl_match:
        print(f"  [OK] PnL encontrado: {pnl_match.group(1)}")
        
    ent_match = re.search(entropy_regex, line)
    if ent_match:
        print(f"  [OK] Entropía encontrada: {ent_match.group(1)}")

print("\n=== FIN DEL TEST ===")
