# Diagnóstico TRAIN de cobertura de gamma y contratos comunes

2026-10-18, antes de ejecución. Sólo 2023–2024; ningún ajuste, label, PnL,
predicción nueva o lectura de validación/test. No se cambia market_cues.py,
extractor, modelos, features o experimentos congelados.

Se proyectan únicamente ticker/date/state_i/weight de la muestra TRAIN existente.
Se cuentan los estados únicos y también su multiplicidad de acciones y la suma
de pesos IPW de sus acciones TRAIN (no un peso uniforme por estado) para
explicar la disponibilidad del diagnóstico previo. Se leen caches diarios
sellados sólo de esas fechas: spot, IV, identidad, presencia y OI con tiempo
de disponibilidad; no bid/ask, futuros labels ni archivos de modelos.

Se reconstruye la condición actual: ahora frente a última barra cerrada
programada 5/15m, todas las muestras de spot válidas y OI/IV/presencia completos.
La cue vigente resta logmasa actual menos promedio de logmasas de la barra;
no equivale a comparar los endpoints t y t−5/15. Se informan gates marginales
y fallos superpuestos, no se adjudica una causa exclusiva arbitraria.

En cada endpoint se separa OI no reportado de último reporte inválido, IV no
finita/<=0/>5, y ausencia de Greek entre identidades conocidas causalmente.
Para IV inválida presente, se informa si el strike es OTM y los buckets fijos
de |log(K/S)|: <=0,5%, 0,5–1%, 1–2%, >2%. No se deduce valor de una IV ausente.

Nueva medida descriptiva: intersección de identidades (misma fecha/expiración,
right y strike) presentes y con IV válida y OI conocido en t y t−5/15. Spot
válido en ambos endpoints. Se calcula masa BS gamma sin signo, separada CALL/
PUT, sobre EXACTAMENTE esa intersección a ambos tiempos. Se incluyen contratos
OI cero conocido, sin rellenar ausencias. No se exige cobertura100% para emitir
la medida; se publican Ncomunes/Nconocidos, Ncomunes/Nválidos de cada endpoint,
fracción de OI conocido y gamma observada retenida en ambos extremos, conteo
de entradas/salidas de la intersección y flag si no existe denominador positivo.

La medida es gamma BS×OI×100×S²×0,01, r=q=0, IV decimal y tiempo calendario
hasta16:00, como motor congelado. No es gamma dealer firmada, flujo ni inventario.
Una descomposición exacta pero dependiente del orden se documenta: spot→IV→
tiempo→OI reportado, manteniendo las mismas identidades y sin usar datos >t.
Se reportará el límite de esa atribución, sin inventar una recepción observada.

El diagnóstico guarda agregados por ticker/año, hashes de caches/metadata,
script/spec/muestra, y rehash final de archivos leídos. CPU un proceso/un hilo,
memoria de un día, checkpoints diarios. Ningún resultado selecciona un modelo.
