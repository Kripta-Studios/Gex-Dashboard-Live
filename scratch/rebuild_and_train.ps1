
Write-Host 'Running Data Collection...'
python neural/collect_training_data_spx_qqq.py --days 1200
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

Write-Host 'Running GBT Training...'
python neural/train_walkforward.py
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

Write-Host 'Running GBT Backtest...'
python backtest/backtest_gbt_parquet.py

