# Dirección de investigación: revisitas multi-day a zonas

Estado: `DRAFT_NOT_EXECUTABLE`. Fecha: 2026-11-02.

Esta nota recoge la propuesta del usuario: en trades weekly multi-day, estudiar
si el precio vuelve a visitar una zona y después rebota, rechaza o rompe, y si
esa zona coincide aproximadamente con IB, walls u otras geometrías causales.
Es una dirección de trabajo, no un contrato de runtime, un dataset nuevo, una
regla de trading ni un resultado. No autoriza leer nuevos outcomes, fijar
thresholds, crear labels, entrenar o ejecutar un replay.

## Hipótesis investigable

La hipótesis no es simplemente «el precio tocó una línea». Es condicional:

> Dada una zona conocida en el instante de decisión, o una zona nueva conocida
> al comienzo de una sesión posterior, ¿la forma causal de la visita/revisita y
> la confluencia con otras zonas cambian las probabilidades y el valor esperado
> neto de rebote, rechazo, ruptura o ausencia de resolución?

El análisis debe separar tres objetos que no pueden mezclarse:

1. La geometría de zona disponible antes del evento.
2. La detección causal de visita o revisita.
3. El movimiento posterior, que sólo puede ser label.

Una zona no es predictiva por definición. Su utilidad tendría que aparecer en
probabilidades calibradas y EV neto estable, con WAIT permitido.

## Qué aportaría la fase B y qué no

El [contrato B publicado](WEEKLY_ZONE_EVENT_VALUE_PATH_CONTRACT_20261102.md),
SHA-256
`e7cf56f8fba5dc50937dcb4e3625752b83e4d73ebbeed77ee19f97f8bf219ac9`,
es una predeclaración, no un resultado ejecutado. Si su productor y auditor
cerrasen PASS, aportarían:

- contratos CALL/PUT congelados causalmente a las 10:30 para 1620 planes;
- cotizaciones del mismo contrato en D, D1 y H2, con cobertura y minutos
  ausentes explícitos;
- spot minuteado causalmente ligado a 2790 ticker-sesiones, incluyendo máscaras
  y 18 caches missing;
- clocks, procedencia y pines necesarios para no reeleccionar con futuro.

B no aporta geometrías de zonas por sesión, eventos, labels, probabilidades,
costes económicos ni PnL. En particular, no reconstruye:

- IB high/low y niveles Fibonacci derivados, con su instante de disponibilidad;
- walls de OI/gamma y sus máscaras, reloj y vigencia;
- una correspondencia entre zonas antiguas y zonas recalculadas en D1/H2;
- definición de visita/revisita, rebote, rechazo, ruptura o maduración;
- evidencia intraminuto. Un sample por minuto no prueba el orden dentro del
  minuto ni un toque entre dos samples.

El B81 contextual anterior describe IB/walls 0DTE a las 10:30; no equivale a
una serie multi-day auditada de geometrías ni debe leerse desde los arrays de
features para fabricar este estudio. Hace falta una admisión separada de las
fuentes compactas que generaron cada geometría.

## Baseline geométrico existente, todavía no validado multi-day

Ya existe una regla trazable que evita inventar un grid nuevo. Debe tratarse
como baseline candidato a una futura predeclaración, no como una regla que haya
demostrado eficacia multi-day:

- En `state_i=60`/10:30, IB es mínimo/máximo del spot consenso de 09:30–10:29;
  requiere al menos 57 de 60 slots válidos y rango no nulo. Ese IB queda fijo
  dentro de la sesión.
- Los 13 centros Fibonacci usan ratios
  `[-1,-.618,-.272,0,.236,.382,.5,.618,.786,1,1.272,1.618,2]` sobre ese IB.
- Los walls son top3 por CALL/PUT para OI causal más reciente y para proxy
  unsigned de dollar-gamma Black–Scholes, con desempate `(-mass,strike)`. OI
  sólo cambia al llegar una disponibilidad nueva; el proxy gamma cambia con
  spot, IV 0DTE y tiempo restante hasta el cierre.
- La confluencia ya agrupa Fib+walls cuando el diámetro del cluster es
  `<=2*band`, usa la media como centro y OR de máscaras de fuente, con
  `band=max(.05*IB_width,.0001*spot)`.

Ese band y clustering son el control primario natural: si se adoptan, deben
congelarse antes de nuevos outcomes. No se probará primero una parrilla de
radios para sustituirlos por el que mejor explique 2026. Sensibilidades, si las
hay, deberán quedar limitadas y predeclaradas.

El `level_id` existente se reenumera por el orden de clusters de cada minuto:
no es una identidad persistente de zona ni permite concluir que el mismo número
en D1 representa la zona de D. Las revisitas multi-day requerirán un `anchor_id`
formado por fuente, sesión/instante de creación y geometría causal, más una regla
explícita de correspondencia entre anchors. Esa regla no puede mirar qué pareja
produjo después el mejor bounce/rejection.

El spot que alimenta esa geometría es consenso minuteado de valores subyacentes
finitos, positivos y con edad 0–60 segundos; todos deben coincidir exactamente.
Un minuto inconsistente es inválido y no se rellena. OI usa timestamp nativo
cuando existe; si no, asume 09:30 como
`ASSUMED_PRIOR_CLOSE_UNVERIFIED_RECEIPT`. Un reporte nuevo inválido invalida el
anterior, sin backfill. Los walls son proxies, no inventario dealer observado.

Las fuentes son 0DTE aunque el instrumento cuyo path económico se estudia sea
una opción weekly. La columna raw `gamma` weekly opcional/ausente de B no es el
wall gamma: `call_gamma/put_gamma` se deriva separadamente de IV+OI+spot 0DTE.
La hipótesis futura debe decir expresamente que usa geometría 0DTE para informar
el comportamiento de un contrato weekly, no geometría del expiry weekly.

Autoridades locales leídas sólo a nivel metadata/código:

- [`level_engine.py`](../level_oracle_20261018/level_engine.py) —
  `70cc5d20990d971d16299fd008ff8e05ac99f99a6a2917a202fcb9a5f413b7c6`.
- [`features.py`](../level_oracle_20261018/features.py) —
  `b5c63f918319f844793abb3346a34515526073374f5e71af2129a94f2369d4e0`.
- [`session_level_engine.py`](../level_oracle_20261018/session_level_engine.py) —
  `f93d3be334a2326dbec5d742e217bce63449e1beaf46b35fa46be83f25548883`.
- [`session_features.py`](../level_oracle_20261018/session_features.py) —
  `595ef9a5327533e7c57190f8970ad76df428b5a62878a6004a961bf4249f2d74`.
- [`session_cache.py`](../level_oracle_20261018/session_cache.py) —
  `6300a7f8e5c6c99101d32d642081f4b8dec170d3c40f2751c27f1642d55466f1`.
- [`session_clock.py`](../level_oracle_20261018/session_clock.py) —
  `1e63cf2d314caea14dd8b0b8f025f647d67bf8df58f246613975891a256f51e9`.
- [`build_cache.py`](../level_oracle_20261018/build_cache.py) —
  `985e87dcbd1e73289b58e4576445e47e73a6edea13e5ac73dde3ad629180d69f`.
- [`build_weekly_context_q3.py`](build_weekly_context_q3.py) —
  `caa049caccd79a1c344bee03cce70df7e6a4446fa1ab087c31de64692f78845a`.

Autoridades compactas existentes: H1 manifest `77aaf00d60accc071ff1f58ec099cee72bc3a4150f89e4ad41a601821a74a38a`,
context `28ce7e455dc1466c2f0e002db2bb50d49f2e379a2c2f99a8d3949f607dd38937`,
inventory `b347523c8638825c822100cf78b5a03ab4f56fc948bc7aa23674b0b73866df5e`,
feature contract `777890230663b0f683d0007117c58b5818047699fe8b25d27b5b819bac7f83db`
y dataset contract `437f480794dc89b80ff0c4999c3053d19d936fab779b99cb75b923433d641a43`.
Q3 manifest `1429bb4dc227843cbb988d552d3b463443b6ae1046e2a53e11118dee4d9fda66`,
context `d78ef5d53d75faf5f3e5774cf83788bf15aff690bf578ba6b2d1bbc1963990cd`
e inventory `25da3398984c633a044eef4f20c5525c6224a1b076a5941d0311fae93eab68cf`.

Una futura C necesita admisión uniforme de las 2772 identidades disponibles,
incluidos FULL, SHORT y Q3, con las 18 missing explícitas. No puede validar sólo
H1 FULL y asumir que SHORT/Q3 comparten geometría o clocks.

## Reloj causal y primera disponibilidad

Cada zona futura debe llevar, como mínimo, `zone_id`, ticker, sesión, tipo,
límites o centro, escala, fuente, `formed_from_start`, `formed_from_end` y
`first_available_at`. Una zona sólo puede intervenir en un evento con
`event_time >= first_available_at`.

- El IB de 09:30–10:29 y sus derivados no están disponibles antes de finalizar
  esa ventana; 10:30 sería su primera disponibilidad si esa definición se fija.
- Un wall sólo está disponible desde el clock causal del snapshot que lo
  produce. El reloj almacenado no demuestra receipt live; un proxy mantiene
  edad desconocida.
- Una zona recalculada con datos de D1 no puede explicar una visita de D ni una
  observación anterior de D1.
- Correcciones o geometrías calculadas al cierre sólo pueden entrar desde la
  siguiente disponibilidad declarada, nunca retroactivamente.

Debe conservarse la diferencia entre:

- `ENTRY_FROZEN`: todos los niveles de D en `state_i=60` se mantienen sin
  cambios durante D/D1/H2. Es la única modalidad que puede emparejar el spot B
  con una referencia sellada de geometría 10:30 sin extraer una serie nueva de
  geometrías. Como `band=max(.05*IB_width,.0001*spot)` depende del spot, aquí
  también se congela el band calculado a las 10:30 de D.
- `SESSION_1030_RESET`: cada sesión D/D1/H2 reinicia IB, Fib, walls y
  confluencias con su propio `state_i=60`; nada de D1/H2 existe antes de las
  10:30 de esa sesión, y su band se fija con el spot 10:30 de esa sesión.
- `INTRADAY_WALL_UPDATED`: en cada sesión IB/Fib quedan fijos desde 10:30, pero
  walls y clusters de confluencia se actualizan minuto a minuto usando sólo OI,
  IV, spot y tiempo causalmente disponibles; el band cambia causalmente con el
  spot de cada minuto según la misma fórmula, sin threshold nuevo.

Las modalidades segunda y tercera requieren una extracción C de arrays/cache
separadamente contratada y no pueden mutar la selección B1. La comparación
futura debería mantenerlas separadas junto con un control sin zonas; una vista
de solapamiento puede ser descriptiva, pero no una cuarta modalidad elegida
retrospectivamente.

## Visita, revisita y labels posteriores

La futura definición matemática deberá fijarse antes de abrir outcomes. Esta
nota sólo fija su estructura:

- `VISIT`: primera observación causal que entra en la banda predeclarada de una
  zona después de que la zona esté disponible.
- `DEPARTURE`: salida de una banda exterior predeclarada. Sin departure no hay
  una nueva oportunidad independiente.
- `REVISIT`: entrada posterior a la banda interior después de una visita y una
  departure válidas; no es simplemente contar minutos consecutivos dentro.
- `NO_VISIT`/`NO_REVISIT`: horizonte maduro sin evento, distinto de datos
  missing o cobertura insuficiente.

Una vez fijado el evento, el futuro determina labels mutuamente excluyentes:

- `BOUNCE`: desplazamiento mínimo en la dirección esperada desde la zona antes
  de invalidación.
- `REJECTION`: penetración admitida y regreso confirmado al lado de origen
  antes de invalidación. No es sinónimo automático de bounce.
- `BREAK`: penetración y confirmación al otro lado según distancia y persistencia
  predeclaradas.
- `UNRESOLVED`: ningún criterio anterior madura dentro del horizonte.
- `AMBIGUOUS` o `NOT_EVALUABLE`: orden intraminuto imposible, gaps, mask inválida
  o cobertura insuficiente; nunca se fuerza a la clase más conveniente.

Dirección y lado deben ser explícitos: una zona de soporte/resistencia, CALL/PUT
y aproximación desde arriba/abajo no comparten necesariamente el mismo label.
Los mismos minutos futuros no pueden usarse simultáneamente para escoger la
zona, declarar el evento y optimizar su desenlace.

No se fijan aquí anchos de banda, distancias, número de minutos de confirmación,
horizonte o prioridad entre labels. Deben aparecer como una única receta previa,
justificada por unidades de mercado y no por un grid que maximice 2026.

## Confluencia aproximada, pero causal y normalizada

«Aproximadamente coincide» debe convertirse en distancia normalizada, no en una
tolerancia fija en puntos que trate igual QQQ, SPY y SPXW. Para dos zonas ya
disponibles en t, una forma futura posible es:

`distance_norm = abs(center_a - center_b) / scale_t`

`scale_t` debe ser positiva, causal y fijada antes del resultado: por ejemplo
IB range ya completado, spot causal o una escala de volatilidad previamente
admitida. No se puede elegir por sesión la escala que genere más confluencias.
Bandas solapadas, centros cercanos y número de zonas confluyentes son conceptos
distintos y deberán tener campos separados.

La futura receta deberá fijar una sola tolerancia primaria y, como máximo,
análisis de sensibilidad predeclarados. Probar muchos radios, persistencias y
horizontes sobre enero–septiembre de 2026 y publicar el mejor sería selección
retrospectiva, no evidencia.

## Ambigüedad de samples minuteados

Con spot de un minuto se puede afirmar que un sample estaba dentro/fuera de una
banda. No se puede afirmar que:

- el precio tocó un nivel entre dos samples exteriores;
- dentro del mismo minuto tocó primero target y después invalidación;
- el rebote ocurrió antes de la ruptura cuando ambos caben en el intervalo;
- una quote de opción estaba disponible exactamente al tocar el subyacente.

La receta futura debe operar sobre orden observable entre samples. Un salto de
un lado al otro sin sample dentro, o target e invalidación resueltos en el mismo
sample, debe quedar `AMBIGUOUS` o recibir una convención conservadora fijada de
antemano. No se interpolan máximos/mínimos intraminuto que los datos no contienen.

## Maduración y separación temporal

Cada evento/label necesita `event_time`, `horizon_end` y `label_available_at`.
`label_available_at` es el máximo timestamp necesario para conocer clase,
liquidación y cualquier cota por missing; no el instante de visita. Un ejemplo
multi-day que usa H2 no está maduro en D o D1.

En entrenamiento o calibración prequential sólo entran ejemplos con
`label_available_at < decision_time` del fit. Los no maduros permanecen pending;
no se etiquetan como UNRESOLVED. Ventanas solapadas de un mismo plan/sesión
requieren agrupación para evitar tratar revisitas correlacionadas como muestras
independientes.

## Probabilidades, EV, WAIT y riesgo

La futura comparación debe estimar probabilidades calibradas de los escenarios
y el payoff neto condicional usando las quotes bid/ask del mismo contrato:

`EV_net = sum_s P(s | information_at_event) * E[net_payoff | s, information_at_event]`

Costes base y adversos, spread, slippage, comisión, salida missing conservadora
y latencia deben mantenerse separados y aplicarse una sola vez. Una mayor tasa
de bounce no basta si las rupturas pierden más. Deben reportarse calibración de
probabilidades, error de payoff y error de EV por separado.

WAIT es una acción válida y puede producir días sin operar cuando ninguna
oportunidad tiene EV neto favorable con margen de incertidumbre. No hay rescate
forzado mediante otra zona, ticker o side. NO_FILL, WAIT y NOT_EVALUABLE son
estados distintos.

El control económico debe conservar riesgo comparable al replay weekly previo,
incluido el mismo presupuesto máximo por entrada y costes, salvo que un futuro
contrato declare antes de outcomes una comparación adicional. No se redimensiona
post hoc para rescatar una variante. Deben mostrarse fills, exposición, mayor
trade, concentración, PF, drawdown realizado, meses/tickers/sides y resultados
sin el mayor ganador.

## Criterio de éxito y frontera de desarrollo

El criterio económico permanece: los ocho meses completos enero–agosto deben
ser netos positivos bajo costes adversos; septiembre parcial se informa aparte
y no cuenta como noveno mes completo. El agregado positivo, tres meses ganadores
o un único trade grande no satisfacen el criterio. También deben pasar límites
de drawdown/concentración y comparación probabilística que se fijen antes.

2023–17 septiembre 2026 ya ha intervenido en desarrollo. Esta dirección no crea
un holdout futuro limpio ni promete que exista en los datos locales. Por ello:

- los thresholds de zonas/eventos/confluencia y la regla EV/WAIT se congelan
  antes de materializar nuevos outcomes;
- no se hace grid ni selección mensual sobre 2026 visto;
- análisis sobre esos años se etiqueta `SEEN_DEVELOPMENT`;
- cualquier afirmación de generalización exige datos posteriores realmente no
  usados, que hoy no están acreditados.

## Próximo documento necesario

Antes de cualquier código o lectura de valores hace falta un contrato separado
que admita, por sesión y clock, las geometrías IB/Fibonacci/walls y sus fuentes,
defina exactamente bands, escalas, eventos, prioridades, maduración, costes,
splits y auditoría independiente. Ese contrato deberá publicarse antes de
fixtures y antes de abrir outcomes. Hasta entonces no hay modelo, evento, replay,
selección ni rentabilidad nueva atribuible a esta propuesta.
