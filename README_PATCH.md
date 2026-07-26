# Archivos para Gex-Dashboard-Live/main

Copiar conservando las rutas relativas desde la raíz del repositorio.

## Reemplazar

- `services/king_node_service.py`
- `scripts/check_king_node_health.py`
- `scripts/deploy_king_node_vps.sh`
- `.env.king-node.example`
- `tests/test_king_node_engine.py`
- `tests/test_king_node_deployment.py`

## Añadir

- `modules/volatility_indices.py`
- `scripts/check_thetadata_options_standard.py`
- `tests/test_volatility_indices.py`
- `docs/KING_NODE_OPTIONS_STANDARD.md`

No se modifica `modules/king_node_engine.py`: el servicio conserva `king-node.v1`, entrega al engine los tres valores y, después del cálculo, restaura en `source.indices` la procedencia completa de Options STANDARD.

## Copia automática desde esta carpeta

```bash
cd /home/Option-Greeks-Plotting-Discord-Bot
cp -a /ruta/king_node_options_standard_patch/. ./
```

No copies `README_PATCH.md` a la raíz si no quieres versionarlo.

## Validación

```bash
python3 -m pytest \
  tests/test_volatility_indices.py \
  tests/test_king_node_engine.py \
  tests/test_king_node_deployment.py \
  tests/test_king_node_server.py \
  tests/test_king_node_web.py -q

python3 -m compileall -q \
  modules/volatility_indices.py \
  modules/king_node_engine.py \
  services/king_node_service.py \
  scripts/check_king_node_health.py \
  scripts/check_thetadata_options_standard.py

bash -n scripts/deploy_king_node_vps.sh
```

## Despliegue

```bash
git add \
  .env.king-node.example \
  docs/KING_NODE_OPTIONS_STANDARD.md \
  modules/volatility_indices.py \
  services/king_node_service.py \
  scripts/check_king_node_health.py \
  scripts/check_thetadata_options_standard.py \
  scripts/deploy_king_node_vps.sh \
  tests/test_volatility_indices.py \
  tests/test_king_node_engine.py \
  tests/test_king_node_deployment.py

git commit -m "feat(king-node): reconstruct volatility from Theta options"
git push origin main

sudo bash scripts/deploy_king_node_vps.sh
```
