# Fallo técnico del auditor01 y corrección V2 acotada

Auditor01 PID44964 terminóexit1 retenido18:19:50.958521UTC en23,662s,
desde a2b62e2105259edb3296ee6f412655f2defb73e3 publicado. Exit
4b1967c5bc389abbb317491a8d808f35632ffd0b0c659f8c79ee2ec630b30101;
stderr0699efa880ff7b48b27eee460d4d26086ce33727576cc6c692845eb8433b5730.
Observer h2_context_adaptation_audit_observer_01 intacto. No audit.json/PASS.
Se conservan código c6a116d3/testsfd835bbe y todo el paquete productor e8cf5cd4:
42fits cerrados, sin repetirlos ni cambiar pesos, predicciones o reglas.

Fallo observado: KeyError `_ev_base` al ejecutar helper3eb6 replay_risk, línea867,
desde rebuild_continuous_books. El helper selecciona por `_ev_adverse`, pero
serializa ambos EV al crear ENTRY. V1 sólo mapeaba adverse. La misma omisión
existe en rebuild_isolated_gate_role aunque el proceso falló antes de llegar allí.

Inspección posterior de root detecta además una frontera incoherente: V1 pasaba
última sesiónSep17 como last_entry del libro principal. El contrato/productor
fijan Sep15; ambos helpers omiten nuevas decisiones después de last_entry.
V1 habría añadido WAIT/NO_OPPORTUNITY enSep16/17, aunque no hay candidatos.
No se observó ese segundo fallo en runtime: es diagnóstico estático explícito.

V2 nueva audit_weekly_context_adaptation_v2.py y tests separados:

- Añadir `_ev_base` desde el score ya reconstruido en las dos rutas de replay,
  preservando `_ev_adverse`, selección, cantidades y costes.
- Exigir/pasar last_entry contractual20260915 en libros principales. Gates
  aislados conservan su propia última fecha de entrada y calendario de salidas.
- Nueva raíz h2_context_adaptation_audit_02 y observer separado; no reutilizar01.
- Resto de reconstrucción, tolerancias, pesos y mecanismos sin cambios.

Fixtures focales deben llamar al helper real congelado, con ENTRY/EXIT efectivos
en ambos costes, comprobar ambos EV y demostrar que una entradaSep15 saleSep17
sin nuevas decisionesSep16/17. Pruebas originales conservadas/adaptadas sólo a
nombres/ruta. Revisar delta/AST permitido y formal gateRAM/commit2GB,CPU0/env1,
logs/exitretenido. Publicar esta delimitación antes de fixturesV2; código/tests/
review/binding V2 reales antes de nueva auditoría. No es retry automático ni
nuevo experimento económico. Summary seguirá sin interpretar hasta PASS válido.
