# Sensibilidad de la estrategia weekly H2 cerrada

El resultado de +11.486 USD no acredita una ventaja generalizada: los 75 fills
fueron CALL, el beneficio está concentrado en SPXW y la normalización por prima
comprometida cambia la lectura. No se reajustó el modelo ni se eligieron nuevas
operaciones. Las sensibilidades usan exactamente los 75 trades ya sellados.

## Costes

Spread ask→bid y comisión de 1,30 USD por lado, más el deslizamiento indicado.
Los puntos son de prima por opción y por lado; cada punto equivale a 100 USD
por contrato. No se interpreta cada escenario como una política ejecutable
nueva ni se reajusta el capital o la decisión por sus costes.

| Puntos por lado | Neto USD | PF |
|---:|---:|---:|
| 0,02 | 11.486 | 1,2625 |
| 0,05 | 11.045 | 1,2508 |
| 0,10 | 10.310 | 1,2317 |
| 0,25 | 8.105 | 1,1765 |
| 0,50 | 4.430 | 1,0917 |
| 1,00 | −2.848 | 0,9466 |

## Prima comprometida y concentración

Con los costes originales adversos, `suma(netos)/suma(débitos de entrada)` es
−18,2948% en SPY, −9,6468% en QQQ y +13,7583% en SPXW. El promedio aritmético
con igual peso por ticker es **−4,7278%**. Esta razón normalizada NO es el retorno
de una cartera: no simula cantidades enteras, capital ni reinversión. Expone el
peso desproporcionado de las primas de SPXW en el neto de un contrato por trade.

La mediana de retorno por débito es negativa en los tres tickers, incluido
SPXW (−21,5362%). No se deduce de ello que ningún trade futuro pueda ganar.

Sensibilidad mecánica, sin reejecutar o seleccionar una política:

- Sin la mayor ganancia: −507,40 USD.
- Sin las tres mayores ganancias: −18.674,20 USD.
- Sin las cinco mayores ganancias: −28.881 USD.
- Sin los trades cuya salida fue en abril: −12.883 USD.

El remuestreo exploratorio usa las 123 sesiones H1, incluidos 82 días sin PnL,
con todos los tickers de una fecha agrupados y PnL atribuido al día de entrada.
Diez mil remuestras, semilla 20261101 y bloques circulares de cinco sesiones:
percentiles 2,5–97,5% del neto remuestreado **[−29.589,40; +57.260,90] USD**.
Supone estacionariedad aproximada y dependencia capturada por esos bloques.
No es una distribución bajo el nulo, prueba de significancia, garantía de
cobertura ni simulación futura de la cartera; no se calcula p-value.

## Evidencia y siguiente paso

Única ejecución PID24468, exit0 retenido a 2026-11-01T14:47:15.347376Z,
0,378s, CPU0/un hilo y gate RAM/commit vigente. Código bdaa9afc, contrato a9488cda.
Diagnóstico SHA026faf1b879db3564451c0e70c8907924354c93c1827f6e04700dc2860185bff;
manifest4e00c615a2d5690d7819b3eead8636861cdae9049573b9643554f6c30f81c8ed.

Review_producer_exit comprobó cierre, hashes, universo y soportes, sin recalcular
el bootstrap. Root reconstruyó por separado los seis netos, las razones de los
tres tickers, nueve sensibilidades y ambos percentiles con fórmulas independientes:
cero discrepancias materiales. Recibo d6cbaaca6a52570888bfac4c57f1fd66f522f478dcb28ba7fa09f3e539cd6e82.
Los archivos originales mantienen su etiqueta de diagnóstico exploratorio,
no de auditoría nueva ni de selección. Copias: h2_robustness_evidence_01.

No se promociona ni se rescata SPXW. La prueba posterior aplicará el mismo
modelo congelado a julio–septiembre parcial, con todas las fechas y ausencias.
Q3 también se etiquetará SEEN_DEVELOPMENT por exposición previa o linaje
incompleto. El objetivo de rentabilidad robusta permanece abierto.
