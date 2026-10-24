# Reporte OOF H1: implementación y pruebas sintéticas

El [postprocesador](report_oof_h1_audit_20261024.py) exporta 108 grupos mensuales y 18 H1, con cobertura y netos/PF base y adverse, desde un único audit FULL_H1 pineado externamente. La figura incluye todas las seis políticas, tres tickers y seis meses; no selecciona ganador. [Diseño y límites](OOF_H1_AUDIT_REPORT_DESIGN_20261024.md). No se abrió un audit real ni se ejecutó el reporte sobre resultados de mercado.

Los tres intentos sintéticos permanecen separados en [el manifest de evidencia](continuation_20261024/oof_h1_report_synthetic/MANIFEST.json):

| Intento | Resultado pytest | Cambio posterior |
|---|---|---|
| [01](continuation_20261024/oof_h1_report_synthetic/attempt_01/result.json) | 24 PASS, 2,45 s | Ruff detectó 23 incidencias de estilo: import no usado y sentencias compactas. Se retiró el import y se formatearon código/tests. Ninguna prueba falló. |
| [02](continuation_20261024/oof_h1_report_synthetic/attempt_02/result.json) | 24 PASS, 2,12 s | La revisión independiente detectó RPT-OOF-01: el hash del script sólo se capturaba al final. Se fijó también al inicio, se exige igualdad al cierre y se añadió una prueba de mutación simulada del hash. |
| [03](continuation_20261024/oof_h1_report_synthetic/attempt_03/result.json) | 25 PASS, 2,12 s | Candidato final; Ruff y parseo AST PASS. No quedan cambios pendientes de implementación. |

Los tres hijos terminaron con exit 0 observado mediante `Popen.wait`, pins sin cambios y stderr vacío. Cada ejecución tuvo gate Windows de RAM y commit antes de lanzar pytest. En la final fueron 7.362.494.464 y 5.339.840.512 bytes, respectivamente, con mínimo de 2.000.000.000 bytes. Python: `C:/Program Files/Python314/python.exe`; hilos de librerías numéricas limitados a uno. La orden pytest exacta y los pins están en cada admission; los tiempos de pytest se distinguen de los tiempos del wrapper (3,386777 / 2,976301 / 3,077925 s). El intento 01 conserva pins y recibos, sin inventar retrospectivamente un snapshot del código anterior.

La [revisión independiente](OOF_H1_AUDIT_REPORT_IMPLEMENTATION_REVIEW_20261024.md) concluye CLEAR: 24 focales propios PASS y una prueba de figura deseleccionada, 0,61 s, además de referencia literal independiente para PF y agregación de seis meses. Es evidencia distinta de las 25 pruebas del autor. Se inspeccionó visualmente la figura sintética: nueve paneles legibles, cuatro barras por mes, escala común entre modos del mismo ticker y abril incompleto señalado. [PNG artificial](continuation_20261024/oof_h1_report_synthetic/SYNTHETIC_monthly_net_usd.png) y [SVG artificial](continuation_20261024/oof_h1_report_synthetic/SYNTHETIC_monthly_net_usd.svg) son fixtures, no resultados científicos.

Hashes SHA256 finales:

| Artefacto | SHA256 |
|---|---|
| report_oof_h1_audit_20261024.py | a52191e2154cec9e6abf12920352a07dbe92c88468c613cd49ec7a21c5cace33 |
| test_report_oof_h1_audit_20261024.py | c591894b9530842f0bc2b11589953dca37ec9683aaa516cc2795fb24fee542e8 |
| OOF_H1_AUDIT_REPORT_DESIGN_20261024.md | bc4affd24fbf6b43ed87c0a081bcf029d7274843ec6a44052c0d0d1ebeaa3ac4 |
| Manifest de evidencia: 23 copias, 497.745 bytes | 90e1f0a0622ec5f1ae70876b4684479b7226c533ab9657ede2c7dd7f43d200dc |
| Recibo autor final 03 | 6552ea6d99451e7166992aebea008cab523db8a51a395db801d34e31a054f531 |
| Review independiente JSON | ec8d484e8d3be8a64d1157733ff59874f6cb7316182058a2938aab8ab8db0ad7 |
| PNG artificial | 1e3acdc4a83a623d08b03fe1f3fa644faab0e5d664930f96f31a542eb315f45e |
| SVG artificial | 2605aeba8e002bc5525d7fb26a17f96f81f1eaaaa86dc46215482676e2d7590b |

La revisión es de implementación. Publicación, cierre real de la auditoría, SHA externo y autorización de root preceden el único reporte real. No se reconstruyen quotes, scores, fits, inferencia, WR, drawdown o cartera; no se rehashean payloads del inventario del audit. Los calendarios se contrastan dentro del audit pineado, no con una reconstrucción bursátil independiente. El pipeline activo no se consultó ni modificó para preparar esta nota.
