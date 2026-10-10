# Despliegue de KING NODE en el VPS

Actualizado para las fórmulas recibidas el 10 de octubre de 2026. El productor
vigente usa ThetaData v3: SPXW para spot/cadena, VIX desde el subyacente de
opciones VIX, y reconstrucciones de VIX1D/VVIX desde NBBO. Los otros gráficos
pueden seguir usando sus feeds existentes.

```text
Theta Terminal → king-node.service → /var/lib/king-node/latest.json
                                  → state.json / current-attempt.json / health.json
snapshot válido → financial-server.service → /api/king-node
                                         → KING NODE y Market Structure
```

La adaptación de fórmulas y sus límites están en
[KING_NODE_FORMULAS_20261010.md](KING_NODE_FORMULAS_20261010.md).

## Dependencias y configuración

El checkout está en `/home/Option-Greeks-Plotting-Discord-Bot`. El servicio usa
`/opt/king-node-venv`, un entorno con acceso a las dependencias Python ya
instaladas en el VPS. Sus dependencias adicionales están fijadas en
`requirements-king-node.txt`.

```bash
cd /home/Option-Greeks-Plotting-Discord-Bot
sudo /usr/bin/python3 -m venv --system-site-packages /opt/king-node-venv
sudo /opt/king-node-venv/bin/python -m pip install -r requirements-king-node.txt
/opt/king-node-venv/bin/python -c 'from services.king_node_service import KingNodeV2Service; KingNodeV2Service._engine_v2_builder()'
```

La configuración privada continúa en `/etc/kripta/king-node.env`. No reemplazar
ese archivo por el ejemplo ni publicar credenciales. Las rutas de salida son:

- live: `/var/lib/king-node/latest.json`;
- estado: `/var/lib/king-node/state.json`;
- referencia: `config/king_node_reference.json`;
- API autenticada ADMIN: `/api/king-node?session=live` y
  `/api/king-node?session=last_completed`.

El productor necesita Theta Terminal conectado, permisos de opciones, datos
vigentes y 47 strikes consecutivos separados por 5 puntos, con CALL/PUT en
cada strike. La ausencia de cierre previo deja vacía la variación diaria; no
se usa el spot actual como cierre ficticio.

## Actualización de fórmulas sobre un VPS existente

Preservar cambios locales antes de actualizar Git; usar un avance fast-forward
que solo modifique los archivos revisados. Verificar las pruebas descritas en
el documento de fórmulas. Guardar una copia de la unidad systemd y del estado
existente antes de instalar la unidad nueva.

```bash
sudo install -m 0644 systemd/king-node.service /etc/systemd/system/king-node.service
sudo systemctl daemon-reload
sudo systemctl restart king-node.service financial-server.service
sudo systemctl is-active king-node.service financial-server.service
sudo journalctl -u king-node.service -n 30 --no-pager
```

Esta actualización no necesita reiniciar Theta Terminal ni `gex_daemon`.
El instalador general `scripts/deploy_king_node_vps.sh` conserva su alcance
más amplio y reinicia también esos feeds; no es necesario ejecutarlo para
una actualización de fórmulas aislada.

Durante una sesión abierta:

```bash
/opt/king-node-venv/bin/python scripts/check_king_node_health.py \
  --snapshot /var/lib/king-node/latest.json --json
```

Comprobar `workbook_calculation.release=2026-10-10`, el hash del libro,
`quality.valid=true`, frescura y 47 filas. `formula_coverage.status=inventoried`
significa inventario de fórmulas, no paridad íntegra Excel/live.
Fuera de sesión, `CALENDAR_CLOSED` es el resultado correcto; que el proceso
esté activo no demuestra disponibilidad de datos de la siguiente apertura.
No escribir fixtures ni precios sintéticos en `/var/lib/king-node`.

## Reversión

Conservar el commit anterior y las copias de la unidad y del estado. Para
revertir en un checkout con cambios locales, aplicar la reversión del commit
concreto conservando esos cambios; evitar `reset --hard`.
Restaurar la unidad anterior, ejecutar `daemon-reload` y reiniciar únicamente
`king-node` y `financial-server`. El nuevo entorno Python puede quedarse
instalado sin afectar a los feeds. La versión anterior de estado se conserva
en la copia, pues las confirmaciones nuevas usan estado versión 3.
