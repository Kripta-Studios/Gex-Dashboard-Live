# KING-GEX-EXIT1 — aclaración runtime V1R1

Estado: `FROZEN_BEFORE_POLICY_METRICS`. La primera ejecución V1 fue detenida
después de persistir únicamente el source checkpoint SPXW-202301. No se había
completado un ticker-mes adicional, no existía policy checkpoint y no se había
calculado ranking, PF/WR/PnL agregado ni elegibilidad de ninguna alternativa.

El checkpoint era correcto pero la implementación reconstruía un DataFrame y
recorría el mismo quote path 16 veces. El ritmo observado proyectaba horas. La
única reparación autorizada es vectorizar las 16 simulaciones sobre arrays del
mismo path, sin cambiar una configuración ni una regla económica.

La versión V1R1 debe:

- conservar exactamente entrada ask y secuencia de bids/timestamps;
- conservar forced mark, min hold, prioridad stop->trail->TP y bid real;
- producir igualdad exacta o tolerancia `1e-12` frente al algoritmo escalar en
  tests deterministas y paths aleatorios para return, minutes, status, max/min y
  reason;
- volver a exigir paridad B00 contra el master en cada evento/right;
- incluir este documento y el nuevo código en la identidad del checkpoint;
- relanzar a target inmutable `development_2023_v1r1` y no reutilizar V1.

No se permite usar el checkpoint V1 para seleccionar, excluir o estimar una
configuración. 2024/2025/2026 y producción permanecen cerrados.
