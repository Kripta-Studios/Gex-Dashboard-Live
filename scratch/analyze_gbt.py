import pandas as pd
import numpy as np
import joblib
import sys

# Load feature columns
sys.path.insert(0, r"c:\Users\Álvaro Schwiedop\Desktop\KriptaStudios\Gex-Dashboard-Live\neural")
from hybrid_model import FEATURE_COLUMNS, load_ensemble_model

def analyze_models():
    tickers = ["QQQ", "SPX", "SPY"]
    for ticker in tickers:
        print(f"\n{'='*50}\nAnalyzing {ticker}\n{'='*50}")
        model_path = rf"c:\Users\Álvaro Schwiedop\Desktop\KriptaStudios\Gex-Dashboard-Live\neural\models\codex_exp\gbt_12m_econ_pf150_minsel10_avail_{ticker}_history.joblib"
        try:
            ensemble = joblib.load(model_path)
            
            # The ensemble is a list of models. Let's average their feature importances.
            # Assuming LightGBM models inside
            if hasattr(ensemble, 'models'):
                models = ensemble.models
            elif isinstance(ensemble, list):
                models = ensemble
            else:
                print(f"Unknown ensemble format for {ticker}")
                continue
                
            if not models:
                print(f"No models found for {ticker}")
                continue
                
            print(f"Found {len(models)} models in ensemble.")
            
            # Sum feature importances
            importance_sums = np.zeros(len(FEATURE_COLUMNS))
            for m in models:
                # lgb model feature_importances_
                # Hybrid_model wraps LightGBM maybe?
                if hasattr(m, 'feature_importances_'):
                    importance_sums += m.feature_importances_
                elif hasattr(m, 'booster_'):
                    importance_sums += m.booster_.feature_importance()
                else:
                    try:
                        importance_sums += m.clf.feature_importances_
                    except:
                        pass
            
            importance_sums /= len(models)
            
            # Create dataframe and sort
            df_imp = pd.DataFrame({
                'feature': FEATURE_COLUMNS,
                'importance': importance_sums
            })
            df_imp = df_imp.sort_values(by='importance', ascending=False)
            print("Top 15 Features:")
            print(df_imp.head(15).to_string(index=False))
            
        except Exception as e:
            print(f"Error analyzing {ticker}: {e}")

if __name__ == "__main__":
    analyze_models()
