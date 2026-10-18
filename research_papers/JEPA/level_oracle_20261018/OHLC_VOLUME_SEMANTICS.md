# Semántica del volumen OHLC local

Revisión de documentación pública primaria el 18-oct-2026 y de los descargadores locales como texto. No se ejecutaron descargadores, endpoints Terminal, lecturas nuevas de valores de mercado, features ni fits.

**Documentado por ThetaData.** En `option/history/ohlc`, `timestamp` identifica el comienzo de la barra: un trade pertenece al intervalo desde ese instante, incluido, hasta `timestamp + interval`, excluido. `volume` mide unidades negociadas —contratos en este endpoint de opciones— y `count` el número de trades. Son agregados del intervalo, no OI ni tamaño cotizado. `interval` admite 30s, 1m y 5m, entre otras duraciones. [Referencia OHLC de opciones v3](https://thetadata.net/docs/operations/option_history_ohlc.html).

Theta describe `volume` como suma de tamaños incrementales y distingue los filtros de volumen/count de los aplicados a OHLC. Las condiciones SIP influyen en la agregación; una operación descartada de los precios puede seguir contribuyendo al volumen. También documenta barras OHLC cero cuando no existen trades aptos. Esto no convierte una fila ausente en volumen cero. La documentación actual no demuestra qué versión exacta de esas reglas produjo cada descarga histórica. [Reglas OHLC & EOD](https://thetadata.net/docs/Articles/Data-And-Requests/OHLC-EOD.html).

**Comprobado en el código local, no en todos los archivos históricos.** `D:/ThetaData/options_bulk.py:52` selecciona ese endpoint v3. En líneas 301–355 solicita todos los strikes y ambos derechos para fecha/vencimiento, aplana contrato y datos, sustituye etiquetas de símbolo/expiration/date por las solicitadas e inserta `interval_used`. No desplaza timestamps, no remuestrea y no cambia unidades de `volume`/`count` en ese recorrido. `thetadata_utils.py:36,250–308` prueba **1m → 30s → 5m** ante determinados fallos. Un 404 o una respuesta vacía terminan el intento del día; no todos los fallos recorren las tres opciones. `interval_used` registra el intervalo solicitado que devolvió la respuesta, no una medición independiente del ancho observado. Los footers representativos ya inventariados dicen 1m; aún no existe comprobación de intervalos/valores para todos los OHLC.

**Consecuencia causal propuesta.** La barra etiquetada 10:30 con intervalo 1m contiene actividad hasta antes de 10:31 y no puede usarse como barra completa a las 10:30. El mismo principio desplaza 30s y 5m a sus cierres reales. Igualar directamente timestamp OHLC y timestamp Greek introduciría información posterior al estado. La disponibilidad efectiva tras el cierre, las revisiones posteriores y la latencia de recepción siguen sin observarse; un retardo declarado sería un supuesto de investigación. Este análisis no acredita paridad live ni modifica las features actuales.

Antes de usar este volumen podrían comprobarse localmente, mediante una lectura acotada y posterior, los siguientes puntos:

- Identidad real frente a etiquetas insertadas, 0DTE, duplicados, reloj/zona/DST, `interval_used` por archivo y separación de ceros válidos, NaN y filas ausentes.
- Rejilla por contrato y cierre efectivo: ninguna barra incompleta o posterior al cierre NYSE debe entrar en el estado; preservar máscaras sin repartir una barra 5m entre cinco minutos inventados.
- No negatividad e integralidad de volume/count; coherencia entre actividad y OHLC, sin exigir que los filtros de precio y volumen sean idénticos.
- Si existe tape local coincidente y apto, reconstrucción de sumas/counts sólo en su intersección. La cinta inventariada cubre parcialmente QQQ/SPY hasta10:35, no todo el universo; sus límites anteriores permanecen.
- Perturbar barras futuras y contratos que aparecen después del corte: las features previas deben mantenerse idénticas. Una normalización futura debe usar sólo pasado y universo conocido.

El volumen permitiría medir intensidad de actividad alrededor de una zona. Por sí solo no identifica lado agresor, órdenes absorbidas, apertura/cierre de posiciones ni inventario de dealers. `tick_count` del subyacente derivado continúa siendo número de observaciones, no contratos negociados.

Identidad de los textos locales leídos: `options_bulk.py` SHA256 `0a15b716b50022d43f8e98b42d9fa75b1c99fa45e19d979eaf12bfb65232e4f0`; `thetadata_utils.py` SHA256 `05d82115f9d4a2c7ea1037967659f832cf250efff38c6f26fa1aab0b1fa701a3`. No se afirma que estos bytes actuales sean la procedencia demostrada de cada parquet histórico.
