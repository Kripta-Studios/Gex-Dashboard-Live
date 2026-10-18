# Memoria causal de zona: contrato técnico de preparación

Estado: **IMPLEMENTACIÓN SINTÉTICA; EXPERIMENTO NO ACTIVO**. Se fija este contrato antes de implementar el módulo separado. No cambia `features.py`, motor, acciones, etiquetas, modelos, planes ni presupuestos congelados. No autoriza construir datos de mercado, abrir outcomes o entrenar. La integración requiere una decisión posterior y que termine la auditoría en curso.

## Entradas y salida

`build_episode_features(states, levels)` consume únicamente las tablas causales del motor, ordenadas por `state_i`. No lee caché, archivos, acciones, labels o predicciones. Cada fila se procesa una vez, sin consultar filas futuras. Rechaza minutos duplicados o desordenados. Un minuto omitido equivale a hueco; no se inserta un precio.

Devuelve `state_i`, matriz float64 `values`, matriz booleana `valid` de igual forma, nombres de canales y una traza de diagnóstico separada. Los valores no observados tienen máscara falsa y cero de almacenamiento. La traza puede contener IDs, centro/banda originales y componentes; **ningún ID entra como número al modelo**. Las procedencias se expresan mediante cinco indicadores independientes FIB/CALL_OI/PUT_OI/CALL_GAMMA/PUT_GAMMA.

El adaptador usa `state_valid`, `spot`, `band`, `eligible`, `entry_level_id`, `ib_low` e `ib_range`. Resuelve la zona exclusivamente en `levels` de ese minuto. Reproduce el desempate del motor: menor distancia absoluta y, en empate, menor centro entre niveles a distancia ≤ banda. Si `eligible` o `entry_level_id` discrepan, falla; no inventa otra zona. Los componentes iniciales se congelan como texto diagnóstico, sin decodificarlos como features. Las tablas futuras no participan en validación económica ni cálculo del prefijo.

## Ciclo del episodio

Al no haber episodio abierto y existir zona elegible válida, se abre un episodio en ese minuto. Se fijan centro, banda, tipos, número de componentes e IB de apertura; no migran cuando cambian las walls o la zona elegible. Apertura cuenta como primer contacto observado, incluso si no conocemos el lado de llegada.

Un episodio termina cuando **dos minutos consecutivos, ambos válidos**, tienen distancia absoluta al ancla estrictamente mayor que dos bandas. No hace falta que sean del mismo lado. A igualdad de dos bandas no cierra. Un hueco o precio inválido reinicia la confirmación. En el minuto de cierre se emite `episode_open=0` y el resto de atributos del episodio queda enmascarado. No se abre otro episodio en ese mismo minuto; puede abrirse en el siguiente si es elegible. No se cambia la elegibilidad ni se retira ninguna acción del motor.

El módulo representa solo el prefijo disponible; no fuerza un cierre al terminar una tabla truncada, porque eso introduciría dependencia del fin del archivo. El episodio queda administrativamente terminado al descartar el tracker al final de sesión, sin reescribir su última fila. Nunca persiste entre sesiones.

## Canales y reglas exactas

- Disponibilidad: `episode_open` y `current_zone_valid` siempre conocidos.
- Ancla: centro expresado en el IB de apertura; banda/IB de apertura; número de componentes; cinco tipos congelados.
- Edad: minutos transcurridos desde apertura (cero al abrir), observaciones válidas incluyendo apertura, observaciones dentro de ±1 banda (bordes incluidos), fracción dentro sobre observaciones válidas, fracción observada sobre minutos transcurridos+1.
- Contactos: 1 en apertura; aumenta con transición exterior→interior en minutos válidos adyacentes. Reentradas = contactos−1. Permanecer dentro no suma. Tras un hueco, volver dentro no confirma una reentrada.
- Cruces exteriores: aumenta al observar el lado exterior opuesto al último exterior confirmado dentro de un tramo sin huecos; puede haber minutos interiores entre ambos. Cada hueco olvida ese lado. No confunde el simple cruce del centro con cruce de toda la banda.
- Penetración por lado: máximos de `max(d−1,0)` y `max(−d−1,0)` acumulados en el prefijo, con `d=(spot−ancla)/banda_ancla`. Recuperación superior = máximo d observado−d actual si hubo penetración superior; inferior = d actual−mínimo d observado si hubo penetración inferior. Si todavía no hubo penetración por ese lado y el spot actual es válido, su recuperación es **cero conocido con máscara válida**; con spot actual inválido queda enmascarada. Son distancias, no etiquetas de éxito; no implican cierre ni operación.
- Trayectoria: d actual; cambios de spot exactos a 1 y 5 minutos divididos por banda_ancla. Solo válidos si todo el intervalo está observado y pertenece al episodio; nunca nearest, forward-fill o interpolación. El lado de llegada usa únicamente el minuto inmediatamente anterior a abrir y el ancla ya conocida al abrir: +1 por encima de la banda, −1 por debajo; desconocido si estaba dentro o faltaba el precio.
- Zona elegible actual: cinco tipos y número de componentes; desplazamiento de su centro frente al ancla en bandas del ancla, cociente banda_actual/banda_ancla y distancia spot−centro_actual en bandas actuales. Se mantiene separada del ancla y de objetivo/stop. Geometría actual enmascarada si no existe zona elegible; tipos no se rellenan desde una wall antigua.

En un minuto inválido de un episodio abierto siguen observables el ancla y los contadores del prefijo, edad y fracción observada; distancia, recuperación actual y velocidades quedan enmascaradas. Los máximos históricos válidos no se borran. Los huecos reinician solo la continuidad requerida por contactos, cruces y cierre. No se añade evolución de masas por strike, identidades top-3 ni etiquetas auxiliares en esta variante.

## Validación prevista

Fixtures exclusivamente sintéticos: invariancia del prefijo ante perturbación futura y truncamiento; misma OHLC con distintos contactos; persistencia al migrar la zona; cierre estricto y huecos; reapertura; máscaras de lags; cruces con interior intermedio; IDs renumerados sin cambio numérico; errores de empate/identidad; separación entre tipos actuales y ancla. La salida no demuestra edge o rentabilidad y no activa una búsqueda nueva.

Implementado el 2026-10-18 en `episode_features.py`, sin integración: **35 canales** con máscaras paralelas. `python -m pytest research_papers/JEPA/level_oracle_20261018/test_episode_features.py -q`: **19 passed**. Ruff focal: **PASS**. Incluye rechazo de `entry_level_id` distinto de −1 sin zona o en estado inválido, y cero conocido de recuperación antes de penetración. Las pruebas no abren archivos de mercado, modelos u outcomes. No se ha ejecutado builder de mercado ni fit para esta propuesta.
