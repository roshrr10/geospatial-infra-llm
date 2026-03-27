import pandas as pd
import json
import time
import logging
from backend.database.db import engine
from backend.services.cache_service import query_cache, basemap_cache
from sqlalchemy import text

logger = logging.getLogger("geoai.spatial")
logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(name)s | %(message)s")


def _round_coords(geojson: dict, precision: int = 5) -> dict:
    """Reduce GeoJSON coordinate precision to shrink payload size."""
    def _round(coords):
        if isinstance(coords, (int, float)):
            return round(coords, precision)
        return [_round(c) for c in coords]

    if geojson and "features" in geojson:
        for feat in geojson["features"]:
            if feat.get("geometry") and feat["geometry"].get("coordinates"):
                feat["geometry"]["coordinates"] = _round(feat["geometry"]["coordinates"])
    return geojson


def _strip_nulls(table: list) -> list:
    """Remove null-valued keys from each row to reduce payload."""
    return [{k: v for k, v in row.items() if v is not None} for row in table]


def _clean_keys(row: dict) -> dict:
    """Standardize column names for the UI (remove _1_yes_2_no etc)."""
    renames = {
        "fire_extinguisher_available_1_yes_2_no": "fire_extinguisher",
        "internet_facility_available_in_school_1_yes_2_no": "internet_facility",
        "smart_classroom_available_in_school_1_yes_2_no": "smart_classroom",
        "whether_receiving_free_textbook_for_primary_1_yes_2_no": "free_textbooks_primary",
        "whether_receiving_free_textbook_for_upper_primary_1_yes_2_no": "free_textbooks_upper_primary",
        "whether_receiving_free_uniform_1_yes_2_no": "free_uniforms",
        "building_status_1_private_owned_2_rented_3_government_owned_4_g": "building_status"
    }
    new_row = {}
    for k, v in row.items():
        clean_k = renames.get(k, k)
        # Fallback categorical cleaning
        if "_1_yes_2_no" in clean_k:
            clean_k = clean_k.replace("_1_yes_2_no", "")
        new_row[clean_k] = v
    return new_row


def execute_spatial_query(sql: str, user_query: str = ""):
    """
    Executes a SQL query and returns GeoJSON + table data.
    Includes caching and execution timing.
    """
    # 1. Clean SQL (remove explanations often appended by LLM)
    sql = sql.strip()
    is_markdown = False
    if "```sql" in sql:
        sql = sql.split("```sql")[1].split("```")[0].strip()
        is_markdown = True
    elif "```" in sql:
        sql = sql.split("```")[1].strip()
        is_markdown = True

    if not is_markdown:
        # Remove trailing natural-language lines only if not in a markdown block
        lines = sql.split('\n')
        filtered_lines = []
        has_started_sql = False
        allowed_keywords = (
            'SELECT', 'WITH', 'FROM', 'WHERE', 'AND', 'OR', 'ORDER', 'GROUP',
            'LIMIT', 'JOIN', 'LEFT', 'RIGHT', 'INNER', 'OUTER', 'ON', 'AS',
            'CASE', 'WHEN', 'THEN', 'END', 'IN', 'EXISTS', 'UPPER', 'LOWER',
            'CAST', '(', ')', '*', ',', 'ST_', 'ST_DISTANCE', 'ST_UNION'
        )
        
        for line in lines:
            stripped = line.strip()
            if not stripped:
                if filtered_lines: filtered_lines.append(line)
                continue

            upper_stripped = stripped.upper()
            starts_with_keyword = upper_stripped.startswith(allowed_keywords) or stripped.startswith('--')
            
            # If we've started, we continue until we hit a line that's obviously NOT SQL
            # (e.g., doesn't contain common SQL symbols or keywords) or we find a semicolon
            if has_started_sql:
                filtered_lines.append(line)
                if ';' in stripped:
                    break
                # Heuristic: if a line is long, has many spaces, and no SQL characters, it might be prose
                if len(stripped) > 40 and ' ' in stripped and not any(c in stripped for c in '(),=<>*|_'):
                    # Probable prose, but let's be careful. 
                    # If it doesn't match any keyword and looks like a sentence, break.
                    if not starts_with_keyword and stripped[0].isupper() and stripped.endswith('.'):
                        filtered_lines.pop()
                        break
            elif starts_with_keyword:
                has_started_sql = True
                filtered_lines.append(line)
                if ';' in stripped:
                    break
            elif stripped.startswith('--'):
                filtered_lines.append(line)

        sql = '\n'.join(filtered_lines).strip()

    if ';' in sql:
        sql = sql.split(';')[0].strip() + ';'

    # 1.5 Auto-fix: Convert 'Yes'/'No' string comparisons to numeric 1/0
    # This handles LLM drift where it generates = 'Yes' instead of = 1
    import re
    string_to_num = {
        "'yes'": "1", "'Yes'": "1", "'YES'": "1",
        "'no'": "0", "'No'": "0", "'NO'": "0",
        "'functional'": "1", "'Functional'": "1",
        "'satisfactory'": "1", "'Satisfactory'": "1",
        "'yes, but not functional'": "2", "'Yes, but not functional'": "2",
        "'not functional'": "2", "'Not Functional'": "2",
    }
    original_sql = sql
    for old, new in string_to_num.items():
        sql = sql.replace(f"= {old}", f"= {new}")
        sql = sql.replace(f"!= {old}", f"!= {new}")
        sql = sql.replace(f"<> {old}", f"<> {new}")

    # 1.5.1 Auto-fix: Reverse alias mapping — LLM uses clean names in WHERE/CASE
    # but the actual DB column has the full name. Map back to real column names.
    reverse_aliases = {
        "internet_facility": "internet_facility_available_in_school_1_yes_2_no",
        "fire_extinguisher": "fire_extinguisher_available_1_yes_2_no",
        "smart_classroom": "smart_classroom_available_in_school_1_yes_2_no",
        "free_textbooks_primary": "whether_receiving_free_textbook_for_primary_1_yes_2_no",
        "free_textbooks_upper_primary": "whether_receiving_free_textbook_for_upper_primary_1_yes_2_no",
        "free_uniforms": "whether_receiving_free_uniform_1_yes_2_no",
        "building_status": "building_status_1_private_owned_2_rented_3_government_owned_4_g",
        "computers": "no_of_computer",
    }
    for alias, real_col in reverse_aliases.items():
        # Replace alias with real column name everywhere using word boundaries.
        # If it hits an AS clause, _clean_keys will map it back in the response.
        sql = re.sub(r'\b' + re.escape(alias) + r'\b', real_col, sql)

    # 1.5.2 Auto-fix: Remove MySQL backticks (PostgreSQL uses double quotes)
    sql = sql.replace('`', '')

    # 1.5.3 Auto-fix: Fix non-existent table references
    sql = re.sub(r'\bmeghalaya_districts\b', 'meghalaya_district_intelligence_final', sql)
    
    # 1.5.5 Auto-fix: Convert 's.' to 's.*' (Common LLM typo)
    sql = re.sub(r'SELECT\s+s\.\s*(,|$)', r'SELECT s.*\1', sql, flags=re.IGNORECASE)
    
    # 1.5.6 Auto-fix: Avoid duplicate geometry when s.* is used
    sql = re.sub(r'SELECT\s+(\w+)\.\*,\s+(\w+\.)?geometry', r'SELECT \1.*', sql, flags=re.IGNORECASE)
    sql = re.sub(r'SELECT\s+geometry,\s+(\w+)\.\*', r'SELECT \1.*', sql, flags=re.IGNORECASE)

    # 1.5.7 Auto-fix: Standardize school name references
    # meghalaya_schools has "schoolName" (quoted), infrastructure has school_name
    sql = sql.replace('s.school_name', 's."schoolName"')
    sql = sql.replace('s.schoolname', 's."schoolName"')
    sql = sql.replace('i."schoolName"', 'i.school_name')

    # 1.5.8 Auto-fix: Fix LLM hallucinating 's.' alias for infrastructure columns
    infra_cols = ['electricity_connection_available', 'drinking_water_availability', 'library_facility', 'computer_room', 'playground_available', 'ramp_available', 'internet_facility_available_in_school_1_yes_2_no', 'smart_classroom_available_in_school_1_yes_2_no', 'fire_extinguisher_available_1_yes_2_no', 'boy_toilet_available', 'girls_toilet_available', 'solar_panel', 'hand_washing_facility_near_toilet', 'no_of_computer', 'building_status_1_private_owned_2_rented_3_government_owned_4_g']
    for col in infra_cols:
        sql = re.sub(r'\bs\.' + re.escape(col) + r'\b', f'i.{col}', sql, flags=re.IGNORECASE)
    
    # Hallucinated computer mapping
    sql = re.sub(r'\bi\.computer_available\b', 'i.computer_room', sql, flags=re.IGNORECASE)
    sql = re.sub(r'\bi\.computer_facility\b', 'i.computer_room', sql, flags=re.IGNORECASE)
    
    # Hallucinated electricity mapping derived from drinking_water_availability structure
    sql = re.sub(r'\belectricity_connection_availability\b', 'electricity_connection_available', sql, flags=re.IGNORECASE)


    if sql != original_sql:
        logger.warning("AUTO-FIX | Cleaned SQL syntax: %s", sql[:100])

    # 1.6 Auto-fix: Fix common misspelling and case issues
    # 1.6.2 DATA TYPE FIX: Redirection for the new normalized column
    # Use word boundaries (\b) and replace in a specific order to avoid corruption
    sql = re.sub(r'\b"udiseCode"\b', 'udise_num', sql, flags=re.IGNORECASE)
    sql = re.sub(r'\budiseCode\b', 'udise_num', sql, flags=re.IGNORECASE)
    sql = sql.replace('udisecode', 'udise_code') # Simple string replace for lowercase case

    # 1.6.3 PREFIX JOIN FIX: Force 11-digit prefix matching for UDISE codes
    # This regex ONLY catches raw s.udise_num = i.udise_code joins if NOT already wrapped in LEFT(...)
    if 'LEFT(' not in sql.upper():
        sql = re.sub(r'([\w\.]+)\.udise_num\s*=\s*([\w\.]+)\.udise_code', r'LEFT(\1.udise_num::text, 11) = LEFT(\2.udise_code::text, 11)', sql, flags=re.IGNORECASE)
        sql = re.sub(r'([\w\.]+)\.udise_code\s*=\s*([\w\.]+)\.udise_num', r'LEFT(\1.udise_code::text, 11) = LEFT(\2.udise_num::text, 11)', sql, flags=re.IGNORECASE)

    # 1.6.4 INCOMPLETE JOIN FIX: Fix cases where the LLM outputs "ON LEFT(s.udise_num::text, 11)" but forgets the rest
    sql = re.sub(r'ON\s+LEFT\s*\(\s*s\.udise_num::text\s*,\s*11\s*\)(?!\s*(?:=|<|>|!|IS|IN))', 
                 'ON LEFT(s.udise_num::text, 11) = LEFT(i.udise_code::text, 11) ', 
                 sql, flags=re.IGNORECASE)

    # 1.6.5 HALLUCINATED COLUMNS: Fix s.district -> s.district_name, s.block -> s.block_name
    sql = re.sub(r'\bs\.district\b', 's.district_name', sql, flags=re.IGNORECASE)
    sql = re.sub(r'\bs\."?districtName"?\b', 's.district_name', sql, flags=re.IGNORECASE)
    sql = re.sub(r'\bs\.block\b', 's.block_name', sql, flags=re.IGNORECASE)
    sql = re.sub(r'\bs\."?blockName"?\b', 's.block_name', sql, flags=re.IGNORECASE)

    # 1.7 Auto-fix missing geometry
    # Only inject geometry if the query references a table that has geometry
    # meghalaya_infrastructure does NOT have geometry; schools/district/block tables do
    tables_with_geometry = ['meghalaya_schools', 'meghalaya_district_intelligence_final', 'meghalaya_block_intelligence_final']
    query_has_spatial_table = any(t in sql.lower() for t in tables_with_geometry)
    has_wildcard = bool(re.search(r'\b\w+\.\*', sql))
    if query_has_spatial_table and not has_wildcard and "GEOMETRY" not in sql.upper() and "SELECT " in sql.upper():
        if "FROM" in sql.upper():
            parts = sql.split(";", 1)
            main_sql = parts[0]
            if " *" not in main_sql and "geometry" not in main_sql.lower():
                from_match = re.search(r'\s+FROM\s+', main_sql, re.IGNORECASE)
                if from_match:
                    start, end = from_match.span()
                    sql = main_sql[:start] + ", geometry " + main_sql[start:]
                    if "GROUP BY" in sql.upper():
                        if "geometry" not in sql.lower().split("group by")[-1]:
                            sql = sql.replace(";", "").strip()
                            sql += ", geometry;"
                            logger.warning("AUTO-FIX | Added missing geometry to both SELECT and GROUP BY")
                        else:
                            sql += ";"
                    else:
                        sql += ";"
                    logger.warning("AUTO-FIX | Added missing geometry column")
                else:
                    sql = main_sql + ";"


    # 1.8 Auto-fix: Strip invalid GROUP BY s.* or if it causes errors
    if "GROUP BY" in sql.upper() and ("s.*" in sql.lower() or "s.*" in sql or "*" in sql):
        # If we have s.* and a GROUP BY, it's almost certainly a broken LLM query 
        # for a listing page. We strip the GROUP BY.
        sql = sql.split("GROUP BY")[0].strip() + ";"
        logger.warning("AUTO-FIX | Stripped invalid GROUP BY clause: %s", sql)

    # 1.9 Auto-fix: Remove invalid 'WHERE s.geometry' or 'AND s.geometry'
    sql = re.sub(r'\s+AND\s+(\w+\.)?geometry\b', '', sql, flags=re.IGNORECASE).strip()
    sql = re.sub(r'WHERE\s+(\w+\.)?geometry\b\s+AND\s+', 'WHERE ', sql, flags=re.IGNORECASE).strip()
    sql = re.sub(r'WHERE\s+(\w+\.)?geometry\b;?$', ';', sql, flags=re.IGNORECASE).strip()
    
    # 1.10 Auto-fix: Strip illegal WHERE filters on infrastructure status (User requirement: show totals)
    # This ensures that the dashboard shows AND/NOT/ISSUE distribution even if user asks for one.
    infra_status_cols = [
        'electricity_connection_available', 
        'eletricity_connection_available',
        'drinking_water_availability', 
        'playground_available', 
        'ramp_available', 
        'solar_panel', 
        'computer_room', 
        'library_facility', 
        'smart_classroom',
        'internet_facility',
        'computer_room',
        'smart_classroom_available_in_school_1_yes_2_no',
        'internet_facility_available_in_school_1_yes_2_no'
    ]
    
    # 1.10.1 Metric Selection Injection: Detect columns in WHERE and add to SELECT
    select_match = re.search(r'SELECT\s+(.*?)\s+FROM', sql, re.IGNORECASE | re.DOTALL)
    if select_match:
        select_part = select_match.group(1).upper()
        cols_to_add = []
        for col in infra_status_cols:
            if re.search(r'\b' + re.escape(col) + r'\b', sql, re.IGNORECASE) and col.upper() not in select_part and "*" not in select_part:
                cols_to_add.append(col)
        
        if cols_to_add:
            # Inject columns before FROM
            replacement = ", ".join(cols_to_add) + ", "
            sql = re.sub(r'SELECT\s+', f'SELECT {replacement}', sql, count=1, flags=re.IGNORECASE)

    # 1.10.2 Robust Filter Stripping
    if "-- NO_STRIP" not in sql:
        for col in infra_status_cols:
            # Remove 'AND i.col = X'
            sql = re.sub(r'\s+AND\s+([\w\.]+\.)?' + re.escape(col) + r'\s*[=<>!]+\s*[\d\w\']+', '', sql, flags=re.IGNORECASE)
        # Remove 'WHERE i.col = X AND ...' -> 'WHERE ...'
        sql = re.sub(r'WHERE\s+([\w\.]+\.)?' + re.escape(col) + r'\s*[=<>!]+\s*[\d\w\']+\s+AND\s+', 'WHERE ', sql, flags=re.IGNORECASE)
        # Remove 'WHERE i.col = X' at the end or before order/limit
        sql = re.sub(r'WHERE\s+([\w\.]+\.)?' + re.escape(col) + r'\s*[=<>!]+\s*[\d\w\']+', '', sql, flags=re.IGNORECASE)
        # Final cleanup for empty WHERE
        sql = sql.replace('WHERE ;', ';').replace('WHERE  ORDER', 'ORDER').replace('WHERE  GROUP', 'GROUP').replace('WHERE  LIMIT', 'LIMIT')
        sql = re.sub(r'WHERE\s*;?$', ';', sql, flags=re.IGNORECASE).strip()

    # 1.11 Auto-fix: Ensure geometry and udise_num are in SELECT
    # BUT ONLY for school-level queries (with 's.' alias)
    is_school_query = 'meghalaya_schools' in sql.lower() and ' s ' in sql.lower()
    select_match = re.search(r'SELECT\s+(.*?)\s+FROM', sql, re.IGNORECASE | re.DOTALL)
    if select_match and is_school_query:
        select_part = select_match.group(1).upper()
        has_wildcard = "*" in select_part
        # Inject ONLY if not already there
        if "GEOMETRY" not in select_part and not has_wildcard:
            sql = re.sub(r'SELECT\s+', 'SELECT s.geometry, ', sql, count=1, flags=re.IGNORECASE)
        if "UDISE_NUM" not in select_part and "UDISE_CODE" not in select_part and not has_wildcard:
            sql = re.sub(r'SELECT\s+', 'SELECT s.udise_num, ', sql, count=1, flags=re.IGNORECASE)

    # 1.12 Auto-fix: Strip duplicates if they were generated anyway
    sql = re.sub(r',\s+s\.geometry\s*,\s*s\.geometry', ', s.geometry', sql, flags=re.IGNORECASE)
    sql = re.sub(r'SELECT\s+s\.geometry,\s+s\.geometry', 'SELECT s.geometry', sql, flags=re.IGNORECASE)
    sql = re.sub(r',\s+s\.udise_num\s*,\s*s\.udise_num', ', s.udise_num', sql, flags=re.IGNORECASE)

    # 1.13 Auto-fix: Strip ST_AsText from geometry since GeoPandas expects WKB
    sql = re.sub(r'ST_AsText\(\s*([\w\.]*geometry)\s*\)', r'\1', sql, flags=re.IGNORECASE)
    sql = re.sub(r'ST_AsGeoJSON\(\s*([\w\.]*geometry)\s*\)', r'\1', sql, flags=re.IGNORECASE)



    # 2. Safety check
    validation_sql = "\n".join([l for l in sql.split("\n") if not l.strip().startswith("--")]).strip().upper()
    if not validation_sql.startswith("SELECT") and not validation_sql.startswith("WITH"):
        raise ValueError(f"Only SELECT queries allowed. Generated: {sql[:100]}...")

    # 3. Check cache
    cached = query_cache.get(sql)
    if cached:
        logger.info("CACHE HIT | sql=%s...", sql[:60])
        return cached

    # 4. Execute with timing
    try:
        import geopandas as gpd
        t0 = time.time()
        
        # Check if query has geometry — if not, use plain pandas
        sql_upper = sql.upper()
        has_geometry_col = 'GEOMETRY' in sql_upper or bool(re.search(r'\b\w+\.\*', sql))
        tables_with_geom = ['meghalaya_schools', 'meghalaya_district_intelligence_final', 'meghalaya_block_intelligence_final']
        references_spatial_table = any(t in sql.lower() for t in tables_with_geom)
        
        if has_geometry_col and references_spatial_table:
            gdf = gpd.read_postgis(sql, engine, geom_col="geometry")
        else:
            # Fallback: non-spatial query (e.g., state-level infrastructure counts)
            logger.info("NON-SPATIAL QUERY | Using pd.read_sql fallback")
            df = pd.read_sql(sql, engine)
            elapsed = time.time() - t0
            logger.info("QUERY OK (non-spatial) | %.2fs | rows=%d | sql=%s...", elapsed, len(df), sql[:80])
            table_data = _strip_nulls(json.loads(df.to_json(orient="records")))
            table_data = [_clean_keys(row) for row in table_data]
            result = {"table": table_data, "geojson": None, "query_time_ms": round(elapsed * 1000)}
            query_cache.set(sql, result)
            return result
        
        elapsed = time.time() - t0
        logger.info("QUERY OK | %.2fs | rows=%d | sql=%s...", elapsed, len(gdf), sql[:80])

        if gdf.empty:
            result = {"table": [], "geojson": None}
            query_cache.set(sql, result)
            return result

        if 'id' not in gdf.columns:
            gdf['id'] = range(len(gdf))

        # Clean column names in the dataframe before converting to JSON/GeoJSON
        table_data = _strip_nulls(json.loads(gdf.drop(columns="geometry").to_json(orient="records")))
        table_data = [_clean_keys(row) for row in table_data]

        geojson = json.loads(gdf.to_json())
        if "features" in geojson:
            for feat in geojson["features"]:
                if "properties" in feat:
                    feat["properties"] = _clean_keys(feat["properties"])
        
        geojson = _round_coords(geojson)

        result = {
            "table": table_data,
            "geojson": geojson,
            "query_time_ms": round(elapsed * 1000),
        }
        query_cache.set(sql, result)
        return result
    except ValueError as ve:
        # Handle 'Query missing geometry column' by falling back to pd.read_sql
        if "geometry" in str(ve).lower():
            logger.warning("GEOMETRY FALLBACK | %s | Retrying with pd.read_sql", str(ve))
            try:
                df = pd.read_sql(sql, engine)
                elapsed = time.time() - t0
                table_data = _strip_nulls(json.loads(df.to_json(orient="records")))
                table_data = [_clean_keys(row) for row in table_data]
                result = {"table": table_data, "geojson": None, "query_time_ms": round(elapsed * 1000)}
                query_cache.set(sql, result)
                return result
            except Exception as inner_e:
                logger.error("FALLBACK FAIL | sql=%s | err=%s", sql[:100], str(inner_e))
                raise inner_e
        raise ve
    except Exception as e:
        err_str = str(e)
        # Attempt recovery from specific common errors if they weren't caught by pre-execution regex
        if "Duplicate geometry column" in err_str:
            # Last ditch: try to select just the wildcard if present
            wildcard_match = re.search(r'\b(\w+)\.\*', sql)
            if wildcard_match:
                alias = wildcard_match.group(1)
                new_sql = f"SELECT {alias}.* FROM (" + sql.split("FROM", 1)[1]
                logger.warning("AUTO-FIX RECOVERY | Retrying with wildcard-only SELECT")
                return execute_spatial_query(new_sql, user_query)
        
        logger.error("QUERY FAIL | sql=%s | err=%s", sql[:100], err_str)
        raise e


def get_drilldown_data(level: str, name: str):
    """Handles spatial drill-down requests."""
    if level == "district":
        sql = f"SELECT * FROM meghalaya_block_intelligence_final WHERE TRIM(UPPER(district_name)) = TRIM(UPPER('{name}'));"
    elif level == "block":
        # Explicit columns to avoid duplicate column names from JOINs
        sql = f"""
            SELECT s."udiseCode", s."schoolName", s.block_name, s.district_name,
                   s."schoolType", s."Latitude", s."Longitude", s.geometry,
                   i.electricity_connection_available as electricity, 
                   i.drinking_water_availability as drinking_water, 
                   i.library_facility as library, 
                   i.no_of_computer as computers, 
                   i.playground_available as playground, 
                   i.ramp_available as ramp, 
                   i.internet_facility_available_in_school_1_yes_2_no as internet,
                   i.smart_classroom_available_in_school_1_yes_2_no as smart_classroom, 
                   i.solar_panel,
                   i.no_of_computer
            FROM meghalaya_schools s 
            LEFT JOIN meghalaya_infrastructure i ON LEFT(s."udiseCode"::text, 11) = LEFT(i.udise_code::text, 11)
            WHERE TRIM(UPPER(s.block_name)) = TRIM(UPPER('{name}'));
        """
    else:
        return None

    try:
        import geopandas as gpd
        gdf = gpd.read_postgis(sql, engine, geom_col="geometry")
        logger.info("DRILLDOWN OK | level=%s | name=%s | rows=%d", level, name, len(gdf))

        if level == "block" and not gdf.empty:
            # Postgres returns lowercase if not quoted, but schema says schoolName. 
            # We check for both to be safe.
            col_target = 'schoolName' if 'schoolName' in gdf.columns else 'schoolname'
            if col_target in gdf.columns:
                gdf['display_name'] = gdf[col_target]
            else:
                gdf['display_name'] = "Unknown School"

        return json.loads(gdf.to_json())
    except Exception as e:
        logger.error("DRILLDOWN FAIL | level=%s | name=%s | err=%s", level, name, str(e))
        raise e


def get_basemap(level: str = "district"):
    """Returns Meghalaya boundaries for a given admin level. Cached."""
    cache_key = f"basemap_{level}"
    cached = basemap_cache.get(cache_key)
    if cached:
        logger.info("BASEMAP CACHE HIT | level=%s", level)
        return cached

    import geopandas as gpd
    if level == "state":
        sql = "SELECT ST_Union(geometry) as geometry FROM meghalaya_district_intelligence_final;"
    elif level == "district":
        sql = "SELECT district_name, geometry FROM meghalaya_district_intelligence_final;"
    elif level == "block":
        sql = "SELECT block_name, district_name, geometry FROM meghalaya_block_intelligence_final;"
    elif level == "school":
        sql = 'SELECT "schoolName", block_name, district_name, geometry FROM meghalaya_schools;'
    else:
        sql = "SELECT district_name, geometry FROM meghalaya_district_intelligence_final;"

    t0 = time.time()
    gdf = gpd.read_postgis(sql, engine, geom_col="geometry")
    elapsed = time.time() - t0
    logger.info("BASEMAP OK | %.2fs | level=%s", elapsed, level)

    if level == "state" and not gdf.empty:
        gdf['name'] = 'Meghalaya'

    result = json.loads(gdf.to_json())
    result = _round_coords(result)
    basemap_cache.set(cache_key, result)
    return result

# Clear query cache on module load to ensure fresh results after logic updates
query_cache.invalidate()


def get_nearest_facility(facility: str, udise_code: str):
    """Find the nearest school WITH the given facility relative to a target school."""
    # Map user-friendly facility names to DB columns
    facility_map = {
        'solar_panel': 'solar_panel',
        'solar': 'solar_panel',
        'electricity': 'electricity_connection_available',
        'water': 'drinking_water_availability',
        'library': 'library_facility',
        'computer': 'computer_room',
        'playground': 'playground_available',
        'internet': 'internet_facility_available_in_school_1_yes_2_no',
        'smart_classroom': 'smart_classroom_available_in_school_1_yes_2_no',
        'ict_lab': 'ict_lab_available',
        'toilet': 'boy_toilet_available',
        'ramp': 'ramp_available',
        'fire_extinguisher': 'fire_extinguisher_available_1_yes_2_no',
        'fire': 'fire_extinguisher_available_1_yes_2_no',
    }
    
    col = facility_map.get(facility.lower(), facility)
    
    sql = f"""
        WITH target AS (
            SELECT geometry FROM meghalaya_schools WHERE udise_num::text LIKE '{udise_code}%' LIMIT 1
        )
        SELECT s."schoolName", s.block_name, s.district_name,
               ROUND(ST_Distance(s.geometry::geography, t.geometry::geography)::numeric / 1000, 2) as distance_km
        FROM meghalaya_schools s
        JOIN meghalaya_infrastructure i ON LEFT(s.udise_num::text, 11) = LEFT(i.udise_code::text, 11)
        CROSS JOIN target t
        WHERE i.{col} = 1
          AND s.udise_num::text NOT LIKE '{udise_code}%'
        ORDER BY s.geometry <-> t.geometry
        LIMIT 5;
    """
    
    try:
        import pandas as pd
        import time
        from sqlalchemy import text
        t0 = time.time()
        with engine.connect() as conn:
            df = pd.read_sql(text(sql), conn)
        elapsed = time.time() - t0
        logger.info("NEAREST OK | %.2fs | facility=%s | udise=%s | results=%d", elapsed, facility, udise_code, len(df))
        return df.to_dict(orient='records')
    except Exception as e:
        logger.error("NEAREST FAIL | facility=%s | err=%s", facility, str(e))
        raise e


def get_comparison_data(level: str, name1: str, name2: str):
    """Compare two districts or blocks side-by-side on all infrastructure metrics."""
    if level == "district":
        table = "meghalaya_district_intelligence_final"
        name_col = "district_name"
    else:
        table = "meghalaya_block_intelligence_final"
        name_col = "block_name"
    
    sql = f"""
        SELECT * FROM {table}
        WHERE UPPER({name_col}) IN ('{name1.upper()}', '{name2.upper()}');
    """
    
    try:
        import geopandas as gpd
        t0 = time.time()
        gdf = gpd.read_postgis(sql, engine, geom_col="geometry")
        elapsed = time.time() - t0
        logger.info("COMPARE OK | %.2fs | level=%s | %s vs %s | rows=%d", elapsed, level, name1, name2, len(gdf))
        
        if gdf.empty:
            return {"regions": [], "comparison": []}
        
        # Drop geometry for JSON output
        df = gdf.drop(columns=["geometry"]).fillna(0)
        records = df.to_dict(orient='records')
        
        # Build comparison array with diffs
        if len(records) == 2:
            r1, r2 = records[0], records[1]
            comparison = []
            skip = ['id', 'geometry', 'sl_no']
            for key in r1:
                if any(s in key.lower() for s in skip):
                    continue
                if key == name_col:
                    continue
                v1, v2 = r1.get(key, 0), r2.get(key, 0)
                if isinstance(v1, (int, float)) and isinstance(v2, (int, float)):
                    comparison.append({
                        "metric": key.replace('_', ' ').title(),
                        "region1": v1,
                        "region2": v2,
                        "diff": round(v1 - v2, 4),
                        "winner": r1.get(name_col, name1) if v1 >= v2 else r2.get(name_col, name2)
                    })
            return {
                "regions": records,
                "comparison": comparison,
                "name1": r1.get(name_col, name1),
                "name2": r2.get(name_col, name2)
            }
        
        return {"regions": records, "comparison": []}
    except Exception as e:
        logger.error("COMPARE FAIL | level=%s | err=%s", level, str(e))
        raise e


def get_heatmap_data(metric: str, level: str):
    """Generates intensity points for heatmap based on school counts or specific metrics."""
    if level == "school": # Not usually used but for completeness
        level = "block"
        
    # Standardize metric to DB column
    facility_map = {
        'priority_score': 'priority_score',
        'electricity': 'electricity_connection_available',
        'drinking_water': 'drinking_water_availability',
        'library': 'library_facility',
        'computers': 'no_of_computer',
        'ramp': 'ramp_available',
        'smart_classroom': 'smart_classroom_available_in_school_1_yes_2_no',
    }
    col = facility_map.get(metric, metric)
    
    # If it's a count/density metric, we join with intelligence tables
    if col in ['total_schools', 'schools_per_sqkm', 'avg_road_density', 'avg_school_density']:
        table = "meghalaya_district_intelligence_final" if level == "district" else "meghalaya_block_intelligence_final"
        sql = f"SELECT {col} as intensity, ST_AsGeoJSON(ST_Centroid(geometry)) as geometry FROM {table}"
    else:
        # For infrastructure metrics at school level intensity
        # Intensity = 1 if Met, 0 if not Met. Centered on schools.
        sql = f"""
            SELECT i.{col} as intensity, ST_AsGeoJSON(s.geometry) as geometry
            FROM meghalaya_schools s
            JOIN meghalaya_infrastructure i ON LEFT(s."udiseCode"::text, 11) = LEFT(i.udise_code::text, 11)
            WHERE i.{col} IS NOT NULL
        """
        
    try:
        import geopandas as gpd
        with engine.connect() as conn:
            df = pd.read_sql(text(sql), conn)
            
        if df.empty:
            return {"type": "FeatureCollection", "features": []}
            
        # Normalize intensity to 0-1 if it's not already
        if not df['intensity'].empty:
            imax = df['intensity'].max()
            imin = df['intensity'].min()
            if imax > imin:
                df['intensity'] = (df['intensity'] - imin) / (imax - imin)
            else:
                df['intensity'] = 1.0 if imax > 0 else 0.0

        features = []
        for _, row in df.iterrows():
            features.append({
                "type": "Feature",
                "geometry": json.loads(row['geometry']),
                "properties": {"intensity": float(row['intensity'])}
            })
            
        return {"type": "FeatureCollection", "features": features}
    except Exception as e:
        logger.error("HEATMAP FAIL | metric=%s | err=%s", metric, str(e))
        return {"type": "FeatureCollection", "features": []}
