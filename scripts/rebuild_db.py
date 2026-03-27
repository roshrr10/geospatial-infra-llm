import pandas as pd
import geopandas as gpd
from sqlalchemy import create_engine
import os

DB_URL = "postgresql://postgres:7654@localhost:5433/meghalaya_geo_llm"
engine = create_engine(DB_URL)

def clean_name(name):
    if pd.isna(name): return name
    return str(name).upper().strip()

print("--- DEFINITIVE DATABASE REBUILD ---")

# 1. Base Districts
print("Loading Districts...")
dist_path = "data/raw/meghalaya/boundaries/district/district.shp"
dist_gdf = gpd.read_file(dist_path)
dist_gdf = dist_gdf[['name', 'geometry']].rename(columns={'name': 'district_name'})
dist_gdf['district_name'] = dist_gdf['district_name'].apply(clean_name)
dist_gdf.to_postgis("meghalaya_districts", engine, if_exists="replace", index=False)
print(f"Loaded {len(dist_gdf)} districts.")

# 2. Base Blocks
print("Loading Blocks...")
block_path = "data/raw/meghalaya/boundaries/block/block.shp"
blocks_gdf = gpd.read_file(block_path)
# Correct columns based on audit: ['district', 'block', 'length', 'area_sqkm', 'area_ha', 'geometry']
blocks_gdf = blocks_gdf[['block', 'district', 'geometry']].rename(columns={'block': 'block_name', 'district': 'district_name'})
blocks_gdf['block_name'] = blocks_gdf['block_name'].apply(clean_name)
blocks_gdf['district_name'] = blocks_gdf['district_name'].apply(clean_name)
blocks_gdf.to_postgis("meghalaya_blocks", engine, if_exists="replace", index=False)
print(f"Loaded {len(blocks_gdf)} blocks.")

# 3. Base Schools (Enriched)
print("Loading Schools & Infra...")
schools_path = "data/raw/meghalaya/boundaries/school/schools.shp"
schools_gdf = gpd.read_file(schools_path)

# Map columns for schools
# Check columns: schools_gdf.columns
print(f"School columns: {schools_gdf.columns.tolist()}")
# Common school columns: schoolName, udiseCode, block_name, district_n
schools_gdf = schools_gdf.rename(columns={
    'schoolName': 'schoolName',
    'udiseCode': 'udiseCode',
    'Block_Name': 'block_name',
    'District_N': 'district_name',
    'Village_Na': 'Village_Na'
})

# Load MDM Infra for additional columns
mdm_file = "data/raw/meghalaya/infra/MDM_Infra_Report.csv"
if os.path.exists(mdm_file):
    mdm_df = pd.read_csv(mdm_file)
    mdm_clean = mdm_df[[
        "UDISE Code", "Kitchen Sheds Available", "Kitchen Device Available",
        "Food Grain Available", "School Fencing Facilities", "Handwashing Facilities",
        "Drinking Water Facilities", "Total Student Enrolment without Aadhaar",
        "Total Aadhaar Based Student Enrolment"
    ]].copy()
    mdm_clean.columns = [
        "udiseCode", "kitchen_shed", "kitchen_device", "food_grain", 
        "fencing", "handwash", "drinking_water", 
        "students_without_aadhaar", "students_with_aadhaar"
    ]
    mdm_clean["udiseCode"] = mdm_clean["udiseCode"].astype(str).str.split('.').str[0]
    
    if 'udiseCode' in schools_gdf.columns:
        schools_gdf["udiseCode"] = schools_gdf["udiseCode"].astype(str).str.split('.').str[0]
        schools_gdf = schools_gdf.merge(mdm_clean, on="udiseCode", how="left")

schools_gdf['block_name'] = schools_gdf.get('block_name', pd.Series([None]*len(schools_gdf))).apply(clean_name)
schools_gdf['district_name'] = schools_gdf.get('district_name', pd.Series([None]*len(schools_gdf))).apply(clean_name)
schools_gdf.to_postgis("meghalaya_schools", engine, if_exists="replace", index=False)
print(f"Loaded {len(schools_gdf)} enriched schools.")

# 4. Thematic & Intelligence (Blocks)
print("Integrating Block Intelligence (Infra + Health)...")
infra_path = "data/processed/meghalaya/block_infrastructure_intelligence.geojson"
health_path = "data/processed/meghalaya/block_health_intelligence.geojson"

infra_df = gpd.read_file(infra_path)
health_df = gpd.read_file(health_path)

# Prepare Intel Table
intel_blocks = infra_df[['block_name', 'district_name', 'block_area_sqkm', 'total_road_km', 'road_density_km_per_sqkm', 'total_schools', 'schools_per_sqkm', 'geometry']].copy()
health_cols = ['avg_ifa_coverage_girls', 'avg_ifa_coverage_boys', 'avg_deworm_coverage_girls', 'avg_deworm_coverage_boys']
# Merge health metrics
intel_blocks = intel_blocks.merge(health_df[['block_name'] + health_cols], on='block_name', how='left')

# Force numeric types for health columns
for col in health_cols:
    intel_blocks[col] = pd.to_numeric(intel_blocks[col], errors='coerce').fillna(0)

intel_blocks['block_name'] = intel_blocks['block_name'].apply(clean_name)
intel_blocks['district_name'] = intel_blocks['district_name'].apply(clean_name)
intel_blocks.to_postgis("meghalaya_block_intelligence_final", engine, if_exists="replace", index=False)

# Thematic subsets
intel_blocks[['block_name', 'district_name', 'block_area_sqkm', 'total_road_km', 'road_density_km_per_sqkm', 'total_schools', 'schools_per_sqkm', 'geometry']].to_postgis("meghalaya_block_infra", engine, if_exists="replace", index=False)
intel_blocks[['block_name', 'district_name'] + health_cols + ['geometry']].to_postgis("meghalaya_block_health", engine, if_exists="replace", index=False)
print(f"Loaded/Enriched intelligence for {len(intel_blocks)} blocks.")

# 5. District Intelligence (Aggregated)
print("Aggregating District Intelligence...")
dist_intel = intel_blocks.groupby('district_name').agg({
    'road_density_km_per_sqkm': 'mean',
    'schools_per_sqkm': 'mean',
    'avg_ifa_coverage_girls': 'mean',
    'avg_ifa_coverage_boys': 'mean',
    'avg_deworm_coverage_girls': 'mean',
    'avg_deworm_coverage_boys': 'mean'
}).reset_index()

dist_intel.columns = [
    'district_name', 'avg_road_density', 'avg_school_density',
    'avg_ifa_coverage_girls', 'avg_ifa_coverage_boys', 
    'avg_deworm_coverage_girls', 'avg_deworm_coverage_boys'
]

# Join geometry
dist_intel = dist_gdf.merge(dist_intel, on='district_name', how='left')
dist_intel.to_postgis("meghalaya_district_intelligence_final", engine, if_exists="replace", index=False)
print(f"Loaded {len(dist_intel)} district intelligence records.")

print("--- REBUILD COMPLETE ---")
