# Auditoría acotada de IB y Fibonacci

## Conclusión de código y fixtures

No se encontró uso de extremos posteriores a la primera hora para definir el
IB o los Fibonacci en el pipeline congelado. El IB utiliza exclusivamente los
precios muestreados de índices **0..59**, correspondientes a 09:30..10:29 ET.
Las decisiones empiezan en **60, a las 10:30 ET**. Son extremos de snapshots
de un minuto; esta revisión no los convierte en máximos/mínimos intraminuto.

Productores inspeccionados, sin modificaciones:

- `features.py`, SHA256 `b5c63f918319f844793abb3346a34515526073374f5e71af2129a94f2369d4e0`.
- `level_engine.py`, SHA256 `70cc5d20990d971d16299fd008ff8e05ac99f99a6a2917a202fcb9a5f413b7c6`.

`features.py:97` y `level_engine.py:207` toman `spot[:60]`, filtrado por
validez, finitud y precio positivo. Exigen al menos 57 observaciones y rango
positivo. No utilizan máximo/mínimo del resto del día para este cálculo.
Los ratios de `level_engine.py:33` son constantes:
−1, −0,618, −0,272, 0, 0,236, 0,382, 0,5, 0,618, 0,786, 1, 1,272, 1,618, 2.
Cada componente Fibonacci tiene centro `IB_low + ratio * IB_range`.

Una zona fusionada puede tener un centro distinto del componente Fibonacci
original: el motor agrupa niveles cercanos con walls usando una banda dependiente
del estado actual. Cambiar el spot actual puede cambiar esa agrupación, su
elegibilidad y sus acciones. Eso no significa que el IB o sus componentes
Fibonacci hayan utilizado el futuro.

## Reproyección histórica y disponibilidad

Los kernels espaciales y las velas históricas se expresan en el IB completo
de la primera hora. Así, una barra de 09:30..09:34 aparece en coordenadas del
IB que ya se conoce a las 10:30. Es una transformación retrospectiva del
historial **disponible en una decisión posterior al cierre del IB**.

`encode_state` rechaza índices anteriores a60. `build_day` genera sólo
60..375. Cada vela del tensor termina estrictamente antes de su decisión:
en60 y61 la última barra completa termina en59. Las barras 5m/15m se anclan
a09:30; los slots sin suficiente historial conservan máscaras.

`features.py:180–183` normaliza cada mapa por el máximo de ese mismo mapa
promediado dentro de una barra ya cerrada; no por el máximo del día. Los OHLC
se calculan dentro de cada barra. El resto del día puede precalcularse en memoria,
pero la selección de barras y del contexto usa el índice de la decisión.

Estos intermediarios históricos no certifican disponibilidad al cierre original
de cada barra pre-IB. Reutilizarlos como ejemplos de decisiones anteriores a60
sería un uso distinto e incorrecto sin cambiar el contrato. El helper de bajo
nivel `causal_levels` recibe los límites IB del llamador; el control horario
del pipeline está en `build_day` y `encode_state`, no en ese helper aislado.

Las acciones se seleccionan con niveles, delta y quotes del estado `i`.
`entry_i=i+1` programa la ejecución posterior. `action_features` toma quotes
en `state_i`, no en `entry_i`; las etiquetas y fills futuros no forman parte
de su whitelist. Esta revisión no lee etiquetas ni evalúa rentabilidad.

## Fixtures nuevos, independientes

`test_ib_feature_leakage_audit.py`: **8 PASS en32,89s**, Ruff PASS.
Se usa un cache sintético con extremos conocidos98/102 en la primera hora.

- Rechazo de i59; validez de i60/i61; reloj10:29/10:30 y primera acción en60
  con entrada61.
- Sustituir todos los precios desde60 por extremos alternos0,001/1.000.000
  mantiene el IB y todos los componentes Fibonacci. El contexto de una
  decisión cuyo spot cambió puede cambiar legítimamente.
- Alterar exclusivamente datos desde `corte+1`, incluidos spot, Greeks,
  quotes y OI tardío, deja idénticos bit a bit todos los tensores y máscaras
  del prefijo60..corte, para cortes60/61/120/375. Los estados, niveles y
  acciones causales del motor conservan igualdad exacta; también las features
  de acciones.
- Control positivo: cambiar el extremo del minuto59 modifica IB/Fibs y el
  tensor en60. Esto comprueba que la prueba no pasa por ignorar el IB.
- Reconstrucción independiente de la geometría de una barra temprana y del
  mapa Fibonacci emitidos en60, usando exclusivamente el IB ya completado.

## Recorrido de todas las exportaciones

`audit_ib_feature_exports.py` terminó con **un worker** sobre los
2.595 caches completos. Leyó únicamente `time_ns`, `spot`, `spot_valid`;
`states.state_i/ib_low/ib_high/ib_range/ib_observed`; y
`features.state_i/bar_end_i/base`. No abre quotes, labels, acciones ni mapas.

Comprueba el reloj09:30..16:00, recomputa IB sólo con0..59, contrasta los
límites y conteo constantes de cada estado, el rango60..375 y todos los
anclajes de barras. Contrasta además las columnas base `spot_ib`,
`ib_range_over_spot`, `ib_valid`, `ib_valid_fraction` con el IB recomputado y
el spot actual. No reconstruye los20 tensores completos por estado.

Los hashes completos de cache, states y features se registran como
**reportados por manifests**. La ejecución calcula hashes propios de los
manifests y de los arrays/columnas seleccionados que efectivamente leyó.
No sustituye el rehash completo ni las auditorías previas de fuentes.

Resultado a las17:24:08 UTC del18-oct-2026:
**PASS_IB_FEATURE_EXPORT_INVARIANTS**, código de salida0.

- 2.595/2.595 días: QQQ864, SPXW867, SPY864; **cero diferencias**.
- 820.020 estados comprobados; ningún estado anterior a60 ni barra cerrando
  en su decisión o después.
- Las cuatro columnas base coinciden exactamente en float32 con su
  reconstrucción causal independiente.
- Primera hora: entre58 y60 observaciones válidas por día; ningún IB inválido.
  Las ausencias no se imputan.

Evidencia completa:
`D:/GexResearchArtifacts/level_oracle_20261018/ib_feature_audit_v1/summary.json`
y `days.csv`. SHA256 del índice de días:
`ae0e88913c9096c9aa62c969d31d84e6de9299959242135f106ee4fd8b7afb44`.
El ejecutable preservado tiene SHA256
`7f21f479374602cf7b63e27a60e2399bdc5c4ab8ad1ac2ad494eb80bf2020b3b`.

Esta revisión respalda la causalidad del IB, los Fibonacci y su incorporación
a estas features. No acredita ausencia universal de cualquier otra fuga, la
equivalencia histórica/live de los relojes de origen ni rentabilidad.
