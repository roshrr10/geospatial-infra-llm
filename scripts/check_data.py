
import sys
import os
import pandas as pd

# Fix path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from backend.database.db import engine

def check_data():
    try:
        print("Checking 'meghalaya_block_intelligence_final'...")
        # Note: Using road_density_km_per_sqkm instead of road_connectivity_score
        query = "SELECT MIN(road_density_km_per_sqkm) as min_score, MAX(road_density_km_per_sqkm) as max_score, AVG(road_density_km_per_sqkm) as avg_score FROM meghalaya_block_intelligence_final;"
        df = pd.read_sql(query, engine)
        print(f"Road Density - Min: {df['min_score'][0]}")
        print(f"Road Density - Max: {df['max_score'][0]}")
        print(f"Road Density - Avg: {df['avg_score'][0]}")
        
        print("\nDistribution (Road Density):")
        # Assuming similar logic but for density, exact thresholds might need adjustment based on data range
        query_dist = """
        SELECT 
            SUM(CASE WHEN road_density_km_per_sqkm > 50 THEN 1 ELSE 0 END) as high_density,
            SUM(CASE WHEN road_density_km_per_sqkm BETWEEN 20 AND 50 THEN 1 ELSE 0 END) as medium_density,
            SUM(CASE WHEN road_density_km_per_sqkm < 20 THEN 1 ELSE 0 END) as low_density
        FROM meghalaya_block_intelligence_final;
        """
        df_dist = pd.read_sql(query_dist, engine)
        print(f"High (>50): {df_dist['high_density'][0]}")
        print(f"Medium (20-50): {df_dist['medium_density'][0]}")
        print(f"Low (<20): {df_dist['low_density'][0]}")
        
        print("\nOverlap Check (Schools in Blocks):")
        # Check if schools resolve to blocks
        query_overlap = """
        SELECT COUNT(*) as mapped_schools
        FROM meghalaya_schools
        WHERE block_name IS NOT NULL;
        """
        df_ov = pd.read_sql(query_overlap, engine)
        print(f"Mapped Schools: {df_ov['mapped_schools'][0]}")

        print("\nTotal Counts:")
        print(f"Districts: {pd.read_sql('SELECT COUNT(*) as c FROM meghalaya_district_intelligence_final', engine)['c'][0]}")
        print(f"Blocks: {pd.read_sql('SELECT COUNT(*) as c FROM meghalaya_block_intelligence_final', engine)['c'][0]}")
        print(f"Schools: {pd.read_sql('SELECT COUNT(*) as c FROM meghalaya_schools', engine)['c'][0]}")

        print("\nDistrict Check (Avg Road Density):")
        query_d = """
        SELECT district_name, AVG(road_density_km_per_sqkm) as avg_density
        FROM meghalaya_block_intelligence_final
        GROUP BY district_name
        ORDER BY avg_density DESC
        LIMIT 5;
        """
        df_d = pd.read_sql(query_d, engine)
        print(f"Top 5 Districts by Avg Block Road Density:")
        print(df_d)
        
        print("\nInfrastructure Check:")
        count_infra = pd.read_sql("SELECT COUNT(*) as c FROM meghalaya_infrastructure", engine)['c'][0]
        print(f"Total Infrastructure Records: {count_infra}")
        if count_infra > 0:
            query_samp = "SELECT * FROM meghalaya_infrastructure LIMIT 1;"
            df_samp = pd.read_sql(query_samp, engine)
            print("Sample Infrastructure Record columns:")
            print(list(df_samp.columns))
        
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    check_data()
