# Revisión del binding y launcher prequential

Dictamen de scenario_admission_draft, materializado por root:
**CLEAR_CONDITIONED_ON_PUBLICATION**; lectura estática, ninguna ejecución.
Bindingafbd68d1faad971d5cf78bab50856f05a0b3d6ad76cf230dd4ad8dbf35930bfb;
launcherf6f92cad00a0d75c48cc6dcce80585d84acea7f48db107f38d334d363beeecfa.

Pins locales exactos: code4b17e651, testsdf5e9f6a, contrato0b81b77b/reviewd108aa68,
reviewfinal312eef6c, receiptsd3265e49 (19copias228520B) y1214f2ff (9copias78300B).
Root verificó28pares fuente/copia y bytes/hashes exactos. Contrato/review ya
publicados432b0f71; los demás necesitan publicación antes de uso real.
Upstreammanifest e8cf5cd4/audit9a487fba/exit5d59d1a3 íntegros y exit_code0.
Output prequential_ev_filter_01 y observer prequential_ev_filter_observer_01 ausentes.

CLI execute-reviewed-experiment + output + cuatroSHA coincide con productor.
Helper3cfe55a6, afinidadCPU0, ocho variables1, observación/gate>=2e9 antes dePopen.
Proceso oculto, argslist, logs, identidad y wait porhandle retenido. Launcher
comprueba publicación byte-exacta del paquete yHEADremoto antes del observer.
La publicación pendiente actualmente bloquea mediante git show.

Observer se crea antes del gate para conservar resource_observation. Si éste
rechaza, no existe hijo y la raíz ocupada impide reintento automático. Es
intencional; no se elimina ni adopta un parcial. No hay FIX pendiente.
Tras publicar bytes exactos y verificar remoto, root podrá hacer un único
lanzamiento conforme al contrato; auditor independiente y economía pendientes.
