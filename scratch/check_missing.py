import os
import pandas as pd

df = pd.read_parquet('rl_data/episode_index.parquet')
all_dates = set(df['date'].unique().astype(str))
done = set([f.split('.')[0] for f in os.listdir('rl_data/rl_options_cache_chunks') if f.endswith('.pkl')])
missing = all_dates - done
print('Missing dates:', sorted(list(missing)))
print('Total dates:', len(all_dates))
print('Total done:', len(done))
