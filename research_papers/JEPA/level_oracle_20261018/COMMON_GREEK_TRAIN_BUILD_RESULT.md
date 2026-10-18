# Matriz TRAIN 152 + 272 completada

Ejecución local única `common_greek_train_v1`, PID28156, iniciada
2026-10-18 20:39:28 UTC y terminada20:58:16 UTC con código0 (18min48s).
El monitor30s observó máximos de189.706.240 bytes privados y779.300.864 bytes RSS;
son máximos muestreados, no una cota del pico real. Builder revisado
`8c4684281f397709cd1dd0c04f84255225b9e1045a66f5d8d584425c2024a024`;
review `7da70447666f0f968c1953031a85a1decbc2a8de9a429fda011ba4e6eb7e8d20`.
Las nueve dependencias revisadas se preservaron sin cambios durante la ejecución.

Se construyeron 270.377 filas float32 ×424 columnas, 1.491 ticker-días TRAIN de
2023–2024 y 155.222 estados únicos. Son exactamente las acciones y pesos IPW de
la muestra original. Las primeras152 columnas coinciden bit a bit con el control.
Las272 columnas adicionales siguen el contrato de identidades comunes por griega,
lado y lag5/15, sin imputar IV/OI/griegas ausentes. Se aplicó row_flags4 además
de los restantes checks de validez. Todas las sesiones TRAIN son completas,
con cierre explícito390; este build no acredita medias sesiones.

El productor rehasheó5.994 fuentes antes del cierre. La verificación posterior
comprobó nuevamente hashes de los outputs, finitud de las424 columnas, prefijo
bitexact y las siete claves/pesos contra la muestra original. Es verificación del
productor, **no una reconstrucción independiente de todas las features raw**.
Las13 fixtures del builder/extractor y su revisión independiente de código
precedieron a la ejecución. Cero ajustes de modelos, cero outcomes leídos y
ninguna lectura de validación/test en este build.

## Cobertura nueva medida

Las siguientes medias usan pesos TRAIN IPW por acción. Equivalen a sumar los
pesos de las acciones de cada estado único. Incluyen ceros explícitos donde la
comparación no está disponible; no son promedios condicionados a cobertura
positiva. `coverage.json` conserva también medias sin pesos por acción y por
estado único, y los indicadores de denominador positivo.

| Griega/lado/lag | Comparación disponible | Identidades comunes / conocidas ahora | Masa ABS observable actual retenida | Masa ABS observable pasada retenida |
|---|---:|---:|---:|---:|
| Gamma CALL5 |99,9364%|53,0159%|99,5243%|99,4831%|
| Gamma CALL15 |99,9368%|52,5480%|99,4991%|99,3377%|
| Gamma PUT5 |99,9364%|73,3589%|99,5882%|99,5281%|
| Gamma PUT15 |99,9368%|73,1993%|99,5555%|99,3510%|
| Delta, vega y theta; CALL/PUT,5/15 |99,9364–99,9368%|99,2355–99,2363%|99,9364–99,9368%|99,9364–99,9368%|

Los denominadores de masa incluyen sólo sensibilidad observable en cada extremo;
estos porcentajes no estiman la masa desconocida de contratos inválidos. Gamma
usa menos identidades por su requisito IV, pero conserva casi toda la masa gamma
observable. Delta/vega/theta no heredan ese requisito IV. Los ceros legítimos de OI
y de griegas se conservan. No se observó cambio del OI reportado entre extremos
comunes: el canal `common_oi_relative_change` es cero en los16 grupos. No es flujo
de dealers ni prueba de inventario intradía constante.

Gamma sigue siendo proxy BS r=q0, tiempo físico a cierre, sin signo de inventario.
Delta/theta conservan signo; la masa absoluta se usa sólo en cobertura/denominadores.
Vega almacenada se divide100 según la documentación Theta. Theta conserva la
unidad almacenada, cuya base temporal no se acreditó; tampoco se acreditó la
versión histórica del cálculo del proveedor. El modelo ampliado aún no se había
ajustado al cerrar esta matriz. La cobertura no demuestra edge ni generalización.

## Artefactos

Raíz: `D:/GexResearchArtifacts/level_oracle_20261018/common_greek_train_v1`.
Logs, monitor30s, código de salida y verificación final:
`D:/GexResearchArtifacts/level_oracle_20261018/common_greek_train_v1_logs`.

| Artefacto | SHA256 |
|---|---|
| matrix.complete.json |33a9664688697881b924e06a939e638fd24c7e0536b57e4e94acb8c067ecba54|
| run_contract.json |5d91ae62a0498813b7435878edd7afac1e79106bf872986addd2142cbc1651ce|
| train_x.npy |60b7e3c56ab011bf74144da1e861981846a90ec55fbe49e95523b092380c2214|
| row_keys.npz |8488a79d1d14cb2cab46c0ba26a63459c04222f1d915b64beff8dec5a52f50a4|
| coverage.json |bcf8e403169d87cca59d9bc467f93d5b75dca07715aa04728f6274422cb61081|

Todo permanece investigación de desarrollo sobre histórico ya visto. La siguiente
etapa separada reutiliza CONFIG, targets, escalas e IPW del control; requiere su
review de implementación y el gate de recursos. El control original no se refittea.
