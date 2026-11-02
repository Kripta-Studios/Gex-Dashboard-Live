# Revisión estática del módulo spot

Dictamen independiente de `/root/daily_producer_review`, materializado por root
el 2 de noviembre de 2026: **CLEAR_STATIC_PRE_SUITE_SPOT_REFRESHED**.

- Contrato: `e7cf56f8fba5dc50937dcb4e3625752b83e4d73ebbeed77ee19f97f8bf219ac9`.
- Módulo `weekly_zone_event_spot_paths.py`: 40814 bytes,
  `0953d344b28992da4b92c561daa7663bb48fe89ea309f6323f53b39c6a0dbd38`.
- Tests `test_weekly_zone_event_spot_paths.py`: 33144 bytes,
  `80d91442dafbf8b2beace31b46eb117913e410a1ccb820ee467f2d0c24d9d3eb`.

El revisor leyó ambos archivos completos contra las secciones 8–12 del contrato.
H1 deriva tres rutas nominales antes del contexto y confirma source/binding dentro;
Q3 usa dos rutas y missing ninguna. El features NPZ sólo se compara en metadata,
sin stat ni open. El NPZ permite únicamente time_ns, spot y spot_valid y se cierra
antes del hash posterior. Eje NY naive y máscaras se preservan; AVAILABLE con
mask false mantiene NaN/inf como valores no-null, MISSING usa null.

Se verificaron guards lexicales/físicos, registry de aliases, hashes/stats
before/after, campos nullable completos y sidecar de raw cache inequívoco.
Cada identidad tiene un CACHE_SPOT_PATH; los tres WRITE_OUTPUTS son secuenciales
y envuelven escritura, fsync y pin. No se anidan contextos cache.

La primera revisión pidió fixtures integrales. Los tests finales ejercen extract,
begin-before-open, paths 3/0/2, substeps, pins, admitted inputs, outputs, errores,
schemas, nulls y drift/aliases. Las cardinalidades reales 2790/2772/18/1086570/8163
siguen fijas; sólo el fixture pequeño sustituye el comprobador de cardinalidad.

El CLEAR anterior y su recibo local d89d8a7b quedan sustituidos: root detectó que
el gate H1 contaba 2595 disponibles sin incluir 24 SHORT, mientras el loop sí
los incluía. La corrección fija H1 disponible en 2619 y añade un test directo
sin sustituir el gate: acepta 2619 y rechaza 2595. La revisión focal independiente
confirmó también 2619+153=2772 disponibles; 6+12=18 missing; FULL2766+SHORT24;
1079532+7038=1086570 filas y 2619*3+153*2=8163 archivos admitidos.

Este dictamen no es evidencia de tests ejecutados. No hubo compile, Ruff, pytest,
lectura de valores reales, footer, arrays ni runtime económico. Se requiere suite
formal observada y revisión final antes de binding/publicación y run real.
