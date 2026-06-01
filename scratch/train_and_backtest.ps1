
Write-Host 'Running GBT Training...'
python neural/train_walkforward.py --data training_data/training_data_derived.parquet
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

Write-Host 'Running GBT Backtest...'
python backtest/backtest_gbt_parquet.py

