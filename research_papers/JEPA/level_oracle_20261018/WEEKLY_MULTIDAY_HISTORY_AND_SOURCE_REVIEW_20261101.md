# Revisión histórica y fuente weekly/multiday

Nueva revisión bajo la orden expresa del1nov, sin modificar ni repetir la
familia histórica. No acredita rentabilidad causal semanal.

## Lo que ya se probó

`../WEEKLY_MULTIDAY_ORACLE_V1_PREDECLARATION.md` y
`../results/_diagnostics/weekly_multiday_oracle_202201_202512_v1/` documentan un
diagnóstico2022–2025: delta cercana a0,50, ask de10:35, bid del mismo contrato
dos observaciones posteriores, sin solape en el oracle relevante. Elige CALL/PUT
usando el resultado futuro. No es una política causal.

El SUMMARY tiene SHA
`4343bb6e3f12ec16a351d5a60228216fa968e12a7fd459a780c34d45e07d09df`;
status CLOSED_ORACLE_GATE, advance=false. El oracle no solapado reporta PF
12,277/13,960/13,876 para QQQ/SPXW/SPY y sumas de retornos relativos a prima
248,521/257,564/254,866. No son dólares ni retorno porcentual de una cuenta.
Sus peores meses reportados aún tienen PF>1,6 y retorno agregado positivo,
pero la gate conjunta mensual falla: el win rate mínimo mensual cae a37,5% /
33,3% /33,3%, por debajo del requisito>50% en todos los meses. Ese cierre no cambia.

Los controles muestran una diferencia mucho mayor que la elección de horizonte:

| Ticker | ALWAYS_CALL PF | Suma de retornos relativos a prima | ALWAYS_PUT PF |
|---|---:|---:|---:|
| QQQ | 1,041890 | +5,757313 | 0,770526 |
| SPXW | 1,053539 | +7,315438 | 0,807891 |
| SPY | 1,055889 | +7,562252 | 0,804450 |

Fuente `policy_summary.csv`, SHA
`829d38015ead0f32321a620a748b922aeeb9962cd495c28dd0f5b49b45d33b87`,
leída por root. Ask→bid incluye spread; faltan comisión y deslizamiento adicional.
No se extrapola la pequeña ganancia del control a beneficio neto operable.

La revisión estática detecta dos límites del productor
`neural/jepa/audit_weekly_multiday_oracle_v1.py`: usa `ordered[index+2]` dentro
del vencimiento, en lugar de exigir exactamente dos sesiones del calendario;
y filtra10:35 por texto, sin acreditar zona horaria. No se afirma que cada trade
histórico esté mal, pero esa implementación no basta para la nueva prueba.
Tampoco se encontró un auditor económico separado equivalente al FULL_H1 actual.

El archivo ajeno `tmp/weekly_event_option_walkforward_experiment.py` usa0DTE y
salida intradía: weekly describe su frecuencia de ajuste. No es otra prueba de
opciones semanales mantenidas varios días. No se modificó.

## Fuente concreta indicada por el usuario

`D:/ThetaData/data_options/SPXW/greeks/2025/04` contiene21nombres0DTE y21nombres
con vencimiento posterior: 4a1DTE,5a2DTE,5a3DTE,3a4DTE y4a6–8DTE.
Las entradas6–8DTE por nombre son:

| Entrada | Vencimiento | DTE naturales | Fechas nominales posteriores hasta vencimiento |
|---|---|---:|---|
| 20250404 | 20250411 | 7 | 07,08,09,10,11abril |
| 20250411 | 20250417 | 6 | 14,15,16,17abril |
| 20250417 | 20250425 | 8 | 21,22,23,24,25abril |
| 20250425 | 20250502 | 7 | 28,29,30abril;01,02mayo a comprobar |

Root comprobó el listado inicial del directorio. El censo dirigido independiente
de `/root/audit_requirements` verificó los recuentos y footers; no leyó precios.
Los schemas contienen strike/right, identidad, bid/ask y reloj; mezclan timestamp
nativo con sólo underlying_timestamp. La continuidad por vencimiento no prueba
la disponibilidad del mismo strike/right ni quotes válidas al cerrar.

La convención de reloj proxy ya está documentada en
`../restart_20261018/CLOCK_EQUIVALENCE.md`: tiene respaldo en comparadores previos,
pero no demuestra recepción live ni equivalencia de todos los archivos weekly.
La nueva admisión debe conservar ambos tipos, medir sus discrepancias cuando
coexistan y no sustituir un timestamp presente pero inválido por el proxy.

Los inventarios previos de1–8DTE respaldan2619parejas Greek/OI en2023–H12026,
con seis fuentes Greek ausentes y24sesiones cortas. Sólo hay un vencimiento
adicional por ticker-día, no toda la estructura de vencimientos. Los nuevos
datos no se excluyen por que su DTE sea8 en semanas con festivos.

Siguiente paso concreto: piloto de continuidad de identidad/reloj y conteos de
validez bid/ask sobre las cuatro cadenas anteriores y los tres tickers, usando
fechas de calendario fijas. No calcular PnL ni elegir contratos por resultados.
El código nuevo se prepara en `../weekly_multiday_20261101/`; ejecución real
después de revisar contrato, implementación y pruebas sintéticas. Esta admisión
no decide todavía holding, entradas o modelo de la evaluación económica.

Revisiones de agentes `/root/scenario_admission_draft`, `/root/prepare_audit_package`
y `/root/audit_requirements`, contrastadas por root en documentos, código citado
y summaries cerrados. La primera búsqueda metadata no localizó el contrato
histórico; el propio agente corrigió esa afirmación antes de esta síntesis.
