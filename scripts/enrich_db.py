import pandas as pd
import geopandas as gpd
from sqlalchemy import create_engine
import os

# Connect to PostGIS
DB_URL = "postgresql://postgres:7654@localhost:5433/meghalaya_geo_llm"
engine = create_engine(DB_URL)

print("--- Enriching Database with Advanced Features ---")

# 1. Enrich meghalaya_schools with Infra & Student data from MDM Report
print("Loading MDM Infra Report...")
mdm_file = "data/raw/meghalaya/health/MDM_Infra_Report.csv"
if os.path.exists(mdm_file):
    mdm_df = pd.read_csv(mdm_file)
    mdm_clean = mdm_df[[
        "UDISE Code",
        "Kitchen Sheds Available",
        "Kitchen Device Available",
        "Food Grain Available",
        "School Fencing Facilities",
        "Handwashing Facilities",
        "Drinking Water Facilities",
        "Total Student Enrolment without Aadhaar",
        "Total Aadhaar Based Student Enrolment"
    ]].copy()
    
    mdm_clean.columns = [
        "udiseCode", "kitchen_shed", "kitchen_device", "food_grain", 
        "fencing", "handwash", "drinking_water", 
        "students_without_aadhaar", "students_with_aadhaar"
    ]
    
    mdm_clean["udiseCode"] = mdm_clean["udiseCode"].astype(str).str.split('.').str[0]
    
    print("Fetching existing schools from PostGIS...")
    schools_gdf = gpd.read_postgis("SELECT * FROM meghalaya_schools", engine, geom_col="geometry")
    schools_gdf["udiseCode"] = schools_gdf["udiseCode"].astype(str).str.split('.').str[0]
    
    # Drop existing infra columns if they exist to avoid duplicates
    cols_to_drop = [c for c in mdm_clean.columns if c in schools_gdf.columns and c != 'udiseCode']
    if cols_to_drop:
        schools_gdf = schools_gdf.drop(columns=cols_to_drop)

    print("Merging infra data...")
    enriched_schools = schools_gdf.merge(mdm_clean, on="udiseCode", how="left")
    
    enriched_schools.to_postgis("meghalaya_schools", engine, if_exists="replace", index=False)
    print("Done: meghalaya_schools enriched.")
else:
    print(f"File not found: {mdm_file}")

# 2. Enrich meghalaya_block_intelligence with Health Coverage
print("Loading Health Reports (IFA & Deworming)...")
ifa_blue = "data/raw/meghalaya/health/ifa-Blue-tablet.csv"
deworm = "data/raw/meghalaya/health/MDM_Deworming_Report.csv"

if os.path.exists(ifa_blue) and os.path.exists(deworm):
    df_ifa = pd.read_csv(ifa_blue)
    df_deworm = pd.read_csv(deworm)
    
    # Agg IFA
    block_ifa = df_ifa.groupby('block')['ifaGiven'].apply(lambda x: (x == 'Yes').mean() * 100).reset_index()
    block_ifa.columns = ['block_name', 'avg_ifa_coverage_girls']
    block_ifa['block_name'] = block_ifa['block_name'].str.upper().str.strip()
    block_ifa['avg_ifa_coverage_girls'] = pd.to_numeric(block_ifa['avg_ifa_coverage_girls'], errors='coerce').fillna(0)
    
    # Agg Deworm
    mapping = pd.read_sql("SELECT \"udiseCode\", block_name FROM meghalaya_schools", engine)
    mapping["udiseCode"] = mapping["udiseCode"].astype(str).str.split('.').str[0]
    
    df_deworm["udiseCode"] = df_deworm["UDISE Code"].astype(str).str.split('.').str[0]
    block_deworm = df_deworm.merge(mapping, on="udiseCode", how="inner")
    block_deworm_agg = block_deworm.groupby('block_name')['Deworming tablets given (Yes/No)'].apply(lambda x: (x == 'Yes').mean() * 100).reset_index()
    block_deworm_agg.columns = ['block_name', 'avg_deworm_coverage_girls']
    block_deworm_agg['block_name'] = block_deworm_agg['block_name'].str.upper().str.strip()
    
    print("Fetching existing blocks from PostGIS...")
    blocks_gdf = gpd.read_postgis("SELECT * FROM meghalaya_block_intelligence", engine, geom_col="geometry")
    blocks_gdf['block_name'] = blocks_gdf['block_name'].str.upper().str.strip()

    # Drop existing health columns if they exist
    for c in ['avg_ifa_coverage_girls', 'avg_deworm_coverage_girls']:
        if c in blocks_gdf.columns:
            blocks_gdf = blocks_gdf.drop(columns=[c])

    print("Merging health data...")
    blocks_gdf = blocks_gdf.merge(block_ifa, on="block_name", how="left")
    blocks_gdf = blocks_gdf.merge(block_deworm_agg, on="block_name", how="left")
    
    blocks_gdf['avg_ifa_coverage_girls'] = blocks_gdf.get('avg_ifa_coverage_girls', pd.Series([0]*len(blocks_gdf))).fillna(0)
    blocks_gdf['avg_deworm_coverage_girls'] = blocks_gdf.get('avg_deworm_coverage_girls', pd.Series([0]*len(blocks_gdf))).fillna(0)
    
    blocks_gdf.to_postgis("meghalaya_block_intelligence", engine, if_exists="replace", index=False)
    print("Done: meghalaya_block_intelligence enriched.")
else:
    print("Health data files missing.")

print("--- Data Enrichment Complete ---")
