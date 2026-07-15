# KING-GEX-MANAGE30-V1 — aclaración de universo V1R1

Estado: `FROZEN_BEFORE_FIRST_PATH_LABEL`. El primer intento V1 se detuvo al
reconstruir keys, antes de cargar un path de contrato, simular una salida,
persistir un checkpoint de sesión o calcular una métrica.

El master executable contiene filas desde 10:30, mientras la regla King K1 solo
puede decidir 11:20–14:30 porque necesita 45 minutos completos de wall state. El
loader V1 hacía el `LEFT JOIN` antes de aplicar esa ventana y exigía wall state
a filas que nunca pertenecieron al universo King.

La única corrección autorizada es filtrar el master a minute 680..870 antes del
join exacto. El censo outcome-free queda inalterado: 33.902 keys master pasan el
join 33.902/33.902 y la regla K1 conserva exactamente 22.273 candidatos:

- 2022: QQQ 2.492, SPXW 3.594, SPY 2.901;
- 2023: QQQ 4.204, SPXW 4.409, SPY 4.673.

No cambia una señal, acción, feature, target, modelo, gate o partición. El
target V1 contiene solo `RUN_CHECKPOINT.json`, queda `REJECTED_PRE_PATH_LABEL`
y no puede reutilizarse. Relanzar a target inmutable
`train_dev_202201_202312_v1r1` con este documento incluido en la identidad.
