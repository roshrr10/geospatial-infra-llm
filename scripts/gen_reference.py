
import os
import sys
import pandas as pd
from sqlalchemy import text

# Fix path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from backend.database.db import engine

def dump_names():
    print("Generating Reference Data...")
    
    with engine.connect() as conn:
        # Districts
        districts = pd.read_sql("SELECT DISTINCT district_name FROM meghalaya_district_intelligence_final ORDER BY district_name", conn)
        
        # Blocks (Grouped by District)
        blocks = pd.read_sql("SELECT DISTINCT district_name, block_name FROM meghalaya_block_intelligence_final ORDER BY district_name, block_name", conn)
        
    output_path = "REFERENCE_DATA.md"
    with open(output_path, "w") as f:
        f.write("# Meghalaya Administrative Reference\n\n")
        f.write("Use these exact names in your natural language queries.\n\n")
        
        f.write("## Districts\n")
        for d in districts['district_name']:
            f.write(f"- {d}\n")
            
        f.write("\n## Blocks by District\n")
        current_dist = ""
        for _, row in blocks.iterrows():
            if row['district_name'] != current_dist:
                current_dist = row['district_name']
                f.write(f"\n### {current_dist}\n")
            f.write(f"- {row['block_name']}\n")
            
        # Add some sample school queries
        f.write("\n## Example Queries\n")
        f.write("1. Which schools in SHILLONG have no electricity?\n")
        f.write("2. List schools with library facilities in RI BHOI.\n")
        f.write("3. Show schools with computers in MAWKYRWAT block.\n")
        f.write("4. District with highest solar panel penetration.\n")
        f.write("5. Schools needing ramps in WEST JAINTIA HILLS.\n")

    print(f"✅ Generated {output_path}")

if __name__ == "__main__":
    dump_names()
