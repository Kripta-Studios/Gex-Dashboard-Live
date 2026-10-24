# OOF V2R1: recibo de inicio de la ejecución

Esta evidencia conserva exclusivamente el inicio observado a `2026-10-24T05:29:43.200600+00:00`, desde la publicación `98dde07684716512310c15aeb8f48b4a7bf5a7d3`. Identidades comunicadas por root y fijadas por los cuatro recibos: supervisor PID 44916, creación `1792819745.6139894`; hijo PID 28256, creación `1792819783.154357`. Ambos usan afinidad a CPU 0.

La admisión registra RAM disponible de 7.443.410.944 bytes y commit disponible de 5.691.486.208 bytes, por encima del gate de 2.000.000.000 bytes. Es una medición de admisión, no una reserva permanente ni una garantía de recursos durante toda la ejecución.

Root conserva el handle de la sesión 45379, comunicada como activa al encargar este archivo. Ese estado es un corte histórico de inicio; esta tarea no polleó la sesión, no comprobó el estado actual ni leyó progreso, valores de fases o resultados. No se infiere exit 0, cierre completo, PASS económico ni rentabilidad. La auditoría económica posterior es un paso separado.

[Manifest del archivo de inicio](continuation_20261024/oof_v2r1_pipeline_start_01/MANIFEST.json): cuatro copias exactas, 41377 bytes; SHA256 `da7081fdeb37345d6d8bc45a6b15edd58fb91e55018a151264c24d0c29401af8`. Contiene preflight, process, admission e initial del observador, con rutas de origen y SHA externos verificados antes y después de copiar. No incluye stdout, stderr ni exit en crecimiento. No hubo retry, relanzamiento, pruebas ni acceso a payloads científicos.
