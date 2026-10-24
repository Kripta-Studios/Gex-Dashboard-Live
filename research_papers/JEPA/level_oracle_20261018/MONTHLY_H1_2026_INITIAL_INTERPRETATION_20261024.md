# H1 2026: interpretación inicial del reporte mensual auditado

24 de octubre de 2026. Los tres modos tienen suma neta negativa en H1 2026,
tanto con costes base como adverse. La selección congelada sigue siendo
`selected_mode=null`; la auditoría confirma que no se volvió a seleccionar con
2026. Esta lectura cubre todos los modos y tickers, sin rescatar un subconjunto.

| Modo | Ticker | Fills | Neto base USD | Neto adverse USD | PF base | PF adverse |
|---|---|---:|---:|---:|---:|---:|
| static | SPXW | 593 | -5.295,80 | -6.479,80 | 0,9685 | 0,9616 |
| static | SPY | 511 | -3.998,60 | -5.018,60 | 0,7507 | 0,7015 |
| static | QQQ | 486 | +548,40 | -422,60 | 1,0301 | 0,9776 |
| static | ALL | 1.590 | -8.746,00 | -11.921,00 | 0,9568 | 0,9418 |
| expanding | SPXW | 702 | -14.570,20 | -15.970,20 | 0,9195 | 0,9122 |
| expanding | SPY | 301 | -5.442,60 | -6.043,60 | 0,4988 | 0,4657 |
| expanding | QQQ | 372 | -603,20 | -1.344,20 | 0,9577 | 0,9091 |
| expanding | ALL | 1.375 | -20.616,00 | -23.358,00 | 0,9000 | 0,8877 |
| rolling12 | SPXW | 698 | -30.927,80 | -32.320,80 | 0,8339 | 0,8273 |
| rolling12 | SPY | 472 | -2.950,20 | -3.893,20 | 0,7911 | 0,7370 |
| rolling12 | QQQ | 541 | -13.469,60 | -14.549,60 | 0,4773 | 0,4523 |
| rolling12 | ALL | 1.711 | -47.347,60 | -50.763,60 | 0,7906 | 0,7779 |

ALL es una agregación descriptiva por modo. No se suman los fills de los tres
modos como si fueran operaciones de una única política ejecutada.

QQQ static es la única combinación con neto base positivo, +548,40 USD y
PF 1,0301; pasa a -422,60 USD y PF 0,9776 con costes adverse. Ese dato no
rescata el resultado de la familia ni justifica una selección posterior.
Los agregados no permiten atribuir causas ni afirmar estabilidad mensual.

El calendario contiene 369 ticker-días esperados y 363 disponibles por modo.
SPXW tiene 123 disponibles; SPY y QQQ, 120 cada uno. Las seis ausencias son
SPY/QQQ en 20260401, 20260409 y 20260415; siguen siendo NO_EVALUABLE con
economía ausente, no PnL cero. Entre días disponibles, los días sin fill son
8/61/26 para static/expanding/rolling12. SPXW static cumple el requisito
descriptivo de tener fill en cada día disponible, pero su neto es negativo;
ese status diario PASS no es un PASS económico.

## Evidencia utilizada y alcance

Sólo se leyeron `reports/2026.json`, la auditoría compuesta y sus recibos de
exit/cierre, después de verificar los cuatro SHA externos siguientes. También
se comprobó que el reporte pertenece al inventario verificado de la auditoría
con el mismo hash; los cuatro archivos se rehashearon al terminar la lectura.

Base local: `D:/GexResearchArtifacts/level_oracle_20261018/`.

| Archivo relativo a la base | SHA256 |
|---|---|
| monthly_walk_forward_v1/reports/2026.json | `76b8b1f72a569fc5327c009b6b554b7c8193797cc380be70b3d94be0e6248071` |
| monthly_walk_forward_test_audit_20261024_01/audit.json | `87bfea586be13e02fd7fd0fe59c819195c62a430f34c867f9ec661812569fd4e` |
| monthly_test_index_v2_audit_launch_20261024_01/exit.json | `f7fadc58144d9934f38e2f3af81355b322ac45b36430742fbd42230d704cc259` |
| monthly_test_index_v2_audit_launch_20261024_01/completion.json | `1045866ea9fdf7d926a51a221e9e5f453ead5146d835197ec99fabe3466b0165` |

La auditoría declara PASS dado scores sellados, scope compuesto 2025–H1 2026,
18 meses completos, 36 ventanas de fit totales y 12 nuevas. El recibo registra
exit 0 observado del PID 49820, sin retry. Ese PASS acredita reconstrucción e
integridad bajo su contrato; no convierte estas pérdidas en evidencia rentable.

No se abrieron features, labels, scores, modelos o raw, ni se ejecutó el
reporter de 18 meses o la gráfica H1 para redactar esta nota. Su consolidación
y revisión visual quedan como entregas documentales separadas. El periodo es
desarrollo visto, sin atribución causal, nueva política, nueva familia económica
o autorización de promoción. No constituye evidencia prospectiva ni paridad live.
