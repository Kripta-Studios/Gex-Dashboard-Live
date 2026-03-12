import pandas as pd
import pyarrow.parquet as pq
from pathlib import Path

# Configuration
DIRS_TO_INSPECT = {
    "Options Data": Path("./data_options"),
    "Derived Underlying Data (Spot Proxy)": Path("./data_underlying_derived")
}
OUTPUT_DOC = Path("./docs/DATA_STRUCTURE.md")

def get_parquet_schema(file_path):
    """Reads the parquet file and extracts column names and types."""
    table = pq.read_table(file_path)
    schema = table.schema
    details = []
    for name in schema.names:
        field = schema.field(name)
        details.append(f"| {name} | {field.type} |")
    return details

def generate_markdown():
    OUTPUT_DOC.parent.mkdir(parents=True, exist_ok=True)
    
    md_content = "# ThetaData Project Data Structure\n\n"
    md_content += "This document describes the storage structure and data schemas for the options and underlying datasets used in the MLP (Multi-Layer Perceptron) training pipeline.\n\n"
    
    for label, base_path in DIRS_TO_INSPECT.items():
        if not base_path.exists():
            print(f"Skipping {label}: Path {base_path} not found.")
            continue
        
        md_content += f"## {label} (`{base_path.name}/`)\n"
        
        # 1. Directory Tree Representation
        md_content += "### Directory Structure\n"
        md_content += "The data is partitioned by Ticker, Data Type, and Date (Year/Month) to optimize I/O performance.\n"
        md_content += "```text\n"
        md_content += f"{base_path.name}/\n"
        md_content += "└── [TICKER]/\n"
        
        if base_path.name == "data_options":
            md_content += "    └── [DATA_TYPE] (ohlc, iv, greeks, oi)/\n"
            md_content += "        └── [YYYY]/\n"
            md_content += "            └── [MM]/\n"
            md_content += "                └── TICKER_EXPIRATION_TRADEDATE_TYPE.parquet\n"
        else:
            md_content += "    └── [YYYY]/\n"
            md_content += "        └── [MM]/\n"
            md_content += "            └── TICKER_TRADEDATE.parquet\n"
        md_content += "```\n\n"

        # 2. Schema Inspection
        md_content += "### Data Schema\n"
        # Find the first parquet file available to extract the schema
        sample_file = next(base_path.rglob("*.parquet"), None)
        
        if sample_file:
            md_content += f"Sample file used for this schema: `{sample_file.name}`\n\n"
            md_content += "| Column | Data Type |\n|--- |--- |\n"
            md_content += "\n".join(get_parquet_schema(sample_file)) + "\n"
        else:
            md_content += "*No parquet files found to extract schema.*\n"
            
        md_content += "\n---\n"

    # Save the file
    with open(OUTPUT_DOC, "w", encoding="utf-8") as f:
        f.write(md_content)
    
    print(f"✅ Documentation successfully generated in English at: {OUTPUT_DOC}")

if __name__ == "__main__":
    generate_markdown()
