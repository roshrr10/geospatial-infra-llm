import json
import logging
import httpx
from backend.services.cache_service import llm_cache, summary_cache

logger = logging.getLogger("geoai.ollama")

OLLAMA_URL = "http://127.0.0.1:11434/api/generate"
MODEL = "mistral"

SYSTEM_PROMPT = """
You are the "Meghalaya GeoAI Assistant". You have TWO EXCLUSIVE MODES:

### MODE 1: CONVERSATIONAL (Greetings/Help)
If the user says "Hi", "Hello", "Thanks", or asks "Who are you?" / "How can you help?":
- RESPONSE: Return text wrapped IN ONLY: [CHAT] Your response here [/CHAT].
- EXAMPLE: User "Hi" -> Response "[CHAT] Hello! I am the Meghalaya GeoAI Assistant. How can I help you? [/CHAT]"

### MODE 2: DATA QUERY (PostGIS Expert)
If the user asks for ANY infrastructure data or counts (e.g., "schools with...", "no electricity", "districts with most schools", "how many..."):
- RESPONSE: Return ONLY valid PostGIS SQL. No prose, no [CHAT] tags, no explanations.
- STRICT RULE: Do NOT write "Here is the SQL query". Start your response immediately with `SELECT`.
- JOIN RULE (Schools): Always use this exact join clause:
  `FROM meghalaya_schools s LEFT JOIN meghalaya_infrastructure i ON LEFT(s.udise_num::text, 11) = LEFT(i.udise_code::text, 11)`
- COLUMNS RULE: Always use `s."schoolName"` for the school name. NEVER use `s.name`.
- ADMIN INTELLIGENCE TABLES (use for district/block level trends):
  - `meghalaya_district_intelligence_final` (Columns: `district_name`, `geometry`, `avg_school_density`, `avg_road_density`)
  - `meghalaya_block_intelligence_final` (Columns: `block_name`, `district_name`, `geometry`, `total_schools`, `schools_per_sqkm`)
- INFRASTRUCTURE COLUMNS (use these exact names in `meghalaya_infrastructure i`):
  - `electricity_connection_available`, `drinking_water_availability`, `playground_available`, `ramp_available`, `solar_panel`, `library_facility`
  - `fire_extinguisher_available_1_yes_2_no`, `smart_classroom_available_in_school_1_yes_2_no`, `internet_facility_available_in_school_1_yes_2_no`, `no_of_computer`
- VALUES:
  - 1 = Yes/Functional/Available, 0 = No/None/Needs/Unavailable, 2 = Functional Issue/Partial.
  - For `no_of_computer`, use `i.no_of_computer > 0` for "has computers".
- SPECIAL RULE (Counts/Density/Admin):
  - If asked for "number of schools" by block, use `total_schools` from `meghalaya_block_intelligence_final`.
  - If asked for "number of schools" by district, use `SUM(total_schools)` from `meghalaya_block_intelligence_final` GROUP BY `district_name`.
  - If asked for "blocks in [District]", use `SELECT block_name, district_name, total_schools, geometry FROM meghalaya_block_intelligence_final WHERE district_name ILIKE '%[District]%';`
  - If asked for "road density" or "school density", use `avg_road_density` or `avg_school_density` from `meghalaya_district_intelligence_final`.
- MULTI-METRIC RULE: If multiple items are mentioned (e.g. "both computers and smart classrooms"), include ALL relevant infra columns INDIVIDUALLY in your `SELECT` statement. This ensures the dashboard charts can show each metric.
- ALIASING RULE: NEVER return a column without a clear name. If you use a calculation or boolean expression (e.g., `i.no_of_computer > 0`), you MUST alias it: `(i.no_of_computer > 0) as has_computers`.
- MANDATORY COLUMNS: Always include `geometry`, identifiers (`udise_num`), AND context columns (`district_name`, `block_name`).
- EXAMPLE: User "Schools with both electricity and water" -> Response "SELECT s."schoolName", s.district_name, s.block_name, s.udise_num, i.electricity_connection_available, i.drinking_water_availability, s.geometry FROM meghalaya_schools s JOIN meghalaya_infrastructure i ON LEFT(s.udise_num::text, 11) = LEFT(i.udise_code::text, 11) WHERE i.electricity_connection_available = 1 AND i.drinking_water_availability = 1;"
"""
_model_warmed = False

async def warm_up_model():
    """Ensure the model is loaded in Ollama memory."""
    global _model_warmed
    if _model_warmed: return
    try:
        payload = {"model": MODEL, "prompt": "hi", "stream": False}
        async with httpx.AsyncClient() as client:
            await client.post(OLLAMA_URL, json=payload, timeout=10.0)
        _model_warmed = True
        print(f"Model {MODEL} warmed up.")
    except Exception as e:
        print(f"Warm up failed: {e}")

async def get_sql_from_llm(question: str):
    # Check Cache
    cached = llm_cache.get(question)
    if cached:
        logger.info(f"LLM CACHE HIT for: {question}")
        return cached

    # ---- HARDCODED FALLBACKS for common count/density queries ----
    q_lower = question.lower()
    
    # District school counts
    if any(kw in q_lower for kw in ['district', 'districts']) and any(kw in q_lower for kw in ['most school', 'number of school', 'more school', 'total school', 'school count']):
        sql = "SELECT district_name, SUM(total_schools) as total_schools, ST_Union(geometry) as geometry FROM meghalaya_block_intelligence_final GROUP BY district_name ORDER BY total_schools DESC;"
        result = (sql, "district")
        llm_cache.set(question, result)
        return result
    
    # Block school counts
    if any(kw in q_lower for kw in ['block', 'blocks']) and any(kw in q_lower for kw in ['most school', 'number of school', 'more school', 'total school', 'school count']):
        sql = "SELECT block_name, district_name, total_schools, geometry FROM meghalaya_block_intelligence_final ORDER BY total_schools DESC;"
        result = (sql, "block")
        llm_cache.set(question, result)
        return result

    # Global school counts ("how many schools do we have")
    if 'how many school' in q_lower or 'total school' in q_lower:
        if 'district' not in q_lower and 'block' not in q_lower:
            sql = "SELECT 'Meghalaya' as state_name, SUM(total_schools) as total_schools, ST_Union(geometry) as geometry FROM meghalaya_district_intelligence_final;"
            result = (sql, "state")
            llm_cache.set(question, result)
            return result

    # Districts with highest road density / Compare road density
    if 'road density' in q_lower:
        sql = "SELECT district_name, avg_road_density, geometry FROM meghalaya_district_intelligence_final ORDER BY avg_road_density DESC;"
        result = (sql, "district")
        llm_cache.set(question, result)
        return result

    # Districts with highest school density
    if 'school density' in q_lower and 'district' in q_lower:
        sql = "SELECT district_name, avg_school_density, geometry FROM meghalaya_district_intelligence_final ORDER BY avg_school_density DESC;"
        result = (sql, "district")
        llm_cache.set(question, result)
        return result

    # Blocks with highest school density
    if 'school density' in q_lower and 'block' in q_lower:
        sql = "SELECT block_name, district_name, schools_per_sqkm, geometry FROM meghalaya_block_intelligence_final ORDER BY schools_per_sqkm DESC;"
        result = (sql, "block")
        llm_cache.set(question, result)
        return result
    
    # Blocks in a specific district (e.g., RI BHOI)
    if 'block' in q_lower and any(kw in q_lower for kw in ['district', 'in ', 'for ']):
        dists = ["EAST KHASI HILLS", "WEST KHASI HILLS", "SOUTH WEST KHASI HILLS", "RI BHOI", "EAST JAINTIA HILLS", "WEST JAINTIA HILLS", "EAST GARO HILLS", "WEST GARO HILLS", "SOUTH GARO HILLS", "SOUTH WEST GARO HILLS", "NORTH GARO HILLS"]
        target_dist = next((d for d in dists if d.lower() in q_lower), "")
        if target_dist:
            sql = f"SELECT block_name, district_name, total_schools, schools_per_sqkm, road_density_km_per_sqkm, geometry FROM meghalaya_block_intelligence_final WHERE district_name = '{target_dist}' ORDER BY total_schools DESC;"
            result = (sql, "block")
            llm_cache.set(question, result)
            return result

    # ---- MULTI-INFRASTRUCTURE FALLBACKS ----
    # Computers AND smart classrooms
    if ('computer' in q_lower and 'smart' in q_lower) or ('computer' in q_lower and 'classroom' in q_lower):
        sql = """-- NO_STRIP
                 SELECT s."schoolName", s.district_name, s.block_name, s.udise_num,
                 i.no_of_computer, i.smart_classroom_available_in_school_1_yes_2_no as smart_classroom,
                 s.geometry
                 FROM meghalaya_schools s
                 LEFT JOIN meghalaya_infrastructure i ON LEFT(s.udise_num::text, 11) = LEFT(i.udise_code::text, 11)
                 WHERE i.no_of_computer > 0 AND i.smart_classroom_available_in_school_1_yes_2_no = 1;"""
        result = (sql, "school")
        llm_cache.set(question, result)
        return result

    # Electricity AND water
    if ('electricity' in q_lower and 'water' in q_lower):
        sql = """-- NO_STRIP
                 SELECT s."schoolName", s.district_name, s.block_name, s.udise_num,
                 i.electricity_connection_available, i.drinking_water_availability,
                 s.geometry
                 FROM meghalaya_schools s
                 LEFT JOIN meghalaya_infrastructure i ON LEFT(s.udise_num::text, 11) = LEFT(i.udise_code::text, 11)
                 WHERE i.electricity_connection_available = 1 AND i.drinking_water_availability = 1;"""
        result = (sql, "school")
        llm_cache.set(question, result)
        return result

    # Internet AND smart classrooms  
    if ('internet' in q_lower and 'smart' in q_lower):
        sql = """-- NO_STRIP
                 SELECT s."schoolName", s.district_name, s.block_name, s.udise_num,
                 i.internet_facility_available_in_school_1_yes_2_no as internet_available,
                 i.smart_classroom_available_in_school_1_yes_2_no as smart_classroom,
                 s.geometry
                 FROM meghalaya_schools s
                 LEFT JOIN meghalaya_infrastructure i ON LEFT(s.udise_num::text, 11) = LEFT(i.udise_code::text, 11)
                 WHERE i.internet_facility_available_in_school_1_yes_2_no = 1 AND i.smart_classroom_available_in_school_1_yes_2_no = 1;"""
        result = (sql, "school")
        llm_cache.set(question, result)
        return result

    # NO ELECTRICITY (Direct Sidebar Fix)
    if 'no electricity' in q_lower or 'lack electricity' in q_lower:
        sql = """-- NO_STRIP
                 SELECT s."schoolName", s.district_name, s.block_name, s.udise_num,
                 i.electricity_connection_available, s.geometry
                 FROM meghalaya_schools s
                 LEFT JOIN meghalaya_infrastructure i ON LEFT(s.udise_num::text, 11) = LEFT(i.udise_code::text, 11)
                 WHERE (i.electricity_connection_available = 0 OR i.electricity_connection_available IS NULL);"""
        result = (sql, "school")
        llm_cache.set(question, result)
        return result


    await warm_up_model()
    prompt = f"System: {SYSTEM_PROMPT}\n\nUser Question: {question}\n\nResponse:"
    
    payload = {
        "model": MODEL,
        "prompt": prompt,
        "stream": False,
        "options": {"temperature": 0, "num_predict": 500}
    }
    
    async with httpx.AsyncClient() as client:
        response = await client.post(OLLAMA_URL, json=payload, timeout=120.0)
        response.raise_for_status()
        data = response.json()
        raw_res = data.get("response", "").strip()
        
        # SQL Mode Enforcement (PRIORITIZE SQL)
        sql = raw_res
        
        # If it's a mix or has SELECT hidden in prose
        if "SELECT " in sql.upper():
            # If it's wrapped in [CHAT] but contains SELECT, it's likely a mis-tagged SQL response
            if "[CHAT]" in sql:
                sql = sql.split("[CHAT]")[1].split("[/CHAT]")[0].strip()
            
            # Extract from markdown blocks
            if "```sql" in sql:
                sql = sql.split("```sql")[1].split("```")[0].strip()
            elif "```" in sql:
                sql = sql.split("```")[1].strip()
            
            # Snip any prose before SELECT (case insensitive search for START)
            start_idx = sql.upper().find("SELECT")
            if start_idx > -1:
                sql = sql[start_idx:]
            
            # Snip any prose after the last semicolon
            if ';' in sql:
                sql = sql.split(';')[0].strip() + ';'
            
            sql = sql.strip('`').strip()
            if not sql.upper().startswith("SELECT"):
                # One last attempt to find the first SELECT in what's left
                retry_idx = sql.upper().find("SELECT")
                if retry_idx > -1:
                    sql = sql[retry_idx:]

            if ';' not in sql: sql += ';'
            
            level = "school"
            q_lower = question.lower()
            if "district" in q_lower: level = "district"
            elif "block" in q_lower: level = "block"
            
            result = (sql, level)
            llm_cache.set(question, result)
            return result

        # Intent Detection: Conversational (FALLBACK)
        if "[CHAT]" in raw_res:
            chat_text = raw_res.split("[CHAT]")[1].split("[/CHAT]")[0].strip()
            result = (f"-- CHAT: {chat_text}", "chat")
            llm_cache.set(question, result)
            return result
        
        # If no tags and no SELECT, treat as raw CHAT
        result = (f"-- CHAT: {raw_res}", "chat")
        llm_cache.set(question, result)
        return result
        
        # If no mode detected but has content, treat as chat (fail-safe)
        result = (f"-- CHAT: {raw_res}", "chat")
        llm_cache.set(question, result)
        return result

async def get_summary_from_llm(question: str, data: list):
    """Instant Python-based summary generator to avoid slow LLM sequential calls."""
    cache_key = f"summary_{question}_{len(data)}"
    cached = summary_cache.get(cache_key)
    if cached: return cached

    if not data: return "No data points found."
    
    total = len(data)
    q_lower = question.lower()
    
    # 1. Detect Infrastructure Columns
    infra_cols = [
        'electricity_connection_available', 'drinking_water_availability', 
        'playground_available', 'ramp_available', 'no_of_computer', 
        'smart_classroom_available_in_school_1_yes_2_no', 'internet_facility_available_in_school_1_yes_2_no'
    ]
    
    target_col = next((c for c in infra_cols if c in data[0]), None)
    label = target_col.replace('_', ' ').title() if target_col else "Infrastructure"

    # 2. Calculate Aggregates Instantly
    yes = 0
    no = 0
    issue = 0
    
    for d in data:
        v = d.get(target_col)
        if v == 1 or v == 1.0 or str(v).lower() == 'yes': yes += 1
        elif v == 0 or v == 0.0 or str(v).lower() == 'no' or v is None: no += 1
        elif v == 2 or v == 2.0 or 'issue' in str(v).lower(): issue += 1

    # 3. Dynamic Template Injection
    insight = f"### Analytics Summary\n\n"
    insight += f"Analyzed **{total}** records for **{label}**.\n\n"
    
    if yes + no + issue > 0:
        insight += f"• **Coverage:** {yes} sites ({round(yes/total*100, 1)}%) meet the full operational requirements.\n"
        insight += f"• **Missing Assets:** {no} sites completely lack the required infrastructure.\n"
        insight += f"• **Repair Backlog:** {issue} sites have partial or defective equipment requiring intervention.\n"
    else:
        # Fallback for non-binary metrics (counts/density)
        metric_col = next((k for k in data[0].keys() if any(m in k for m in ['total', 'density', 'count', 'per_sqkm'])), None)
        if metric_col:
            try:
                max_item = max([d for d in data if d.get(metric_col) is not None], key=lambda x: float(x.get(metric_col, 0)), default={})
                highest_name = max_item.get('schoolName') or max_item.get('block_name') or max_item.get('district_name') or 'N/A'
                insight += f"• **Top Metric:** Found {highest_name} with the highest values for {metric_col.replace('_', ' ')}.\n"
                insight += f"• **Regional Snapshot:** Analyzed distribution across {total} administrative units."
            except:
                insight += f"• **Analysis Complete:** Successfully processed {total} records for map visualization."
        else:
            insight += f"• **Analysis Complete:** Successfully processed {total} records for map visualization."

    # Cache and return instantly
    summary_cache.set(cache_key, insight.strip())
    return insight.strip()

async def get_heatmap_summary(metric: str, level: str, data: list):
    """
    Generates a summary for heatmap visualizations using aggregated trends.
    """
    if not data:
        return "No intensity data available for the selected metric."

    total = len(data)
    avg_score = sum(d.get('priority_score', 0) for d in data) / total if total > 0 else 0
    top_regions = sorted(data, key=lambda x: x.get('priority_score', 0), reverse=True)[:3]
    region_names = ", ".join([d.get('district_name') or d.get('block_name') or 'N/A' for d in top_regions])

    prompt = f"""
System: You are a GeoAI Analyst. Summarize the spatial pattern of {metric.replace('_', ' ')} intensity in Meghalaya.
Avoid technical jargon. Focus on which areas are most affected.

Context:
- Metric: {metric}
- Level: {level}
- Average Priority Score: {round(avg_score, 2)}
- Top Impacted Areas: {region_names}

Summary (2 sentences):"""

    payload = {
        "model": MODEL,
        "prompt": prompt,
        "stream": False,
        "options": {"temperature": 0.2}
    }

    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(OLLAMA_URL, json=payload, timeout=30.0)
            data_json = response.json()
            return data_json.get("response", "Heatmap density analysis complete.").strip()
    except Exception as e:
        return f"Concentration of {metric} identified across {total} {level}s."
