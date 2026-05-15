import pandas as pd
import json

def analyze_excel():
    try:
        # Try to read the first sheet
        df = pd.read_excel('GreeksDealers.xlsx')
        
        analysis = {
            "columns": df.columns.tolist(),
            "head": df.head(10).to_dict(orient='records'),
            "summary": df.describe(include='all').to_dict(),
            "dtypes": df.dtypes.apply(lambda x: str(x)).to_dict()
        }
        
        with open('excel_analysis.json', 'w', encoding='utf-8') as f:
            json.dump(analysis, f, indent=4, ensure_ascii=False)
            
        print("Analysis saved to excel_analysis.json")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    analyze_excel()
