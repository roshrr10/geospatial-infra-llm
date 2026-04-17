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
- JOIN RULE (Schools): Always use this exact join clause with explicit type casting:
  `FROM meghalaya_schools s JOIN meghalaya_infrastructure i ON i.udise_code::text = s.udise_num::text`
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
  - CRITICAL: "number of schools" OR "total schools" are ONLY available in the BLOCK table (`meghalaya_block_intelligence_final`).
  - If asked for "number of schools" by district, you MUST use `SUM(total_schools)` from `meghalaya_block_intelligence_final` and GROUP BY `district_name`. NEVER use `total_schools` on the district table.
  - If asked for "blocks in [District]", use `SELECT block_name, district_name, total_schools, geometry FROM meghalaya_block_intelligence_final WHERE district_name ILIKE '%[District]%';`
  - If asked for "road density" or "school density", use `avg_road_density` or `avg_school_density` from `meghalaya_district_intelligence_final`.
- MULTI-METRIC RULE: If multiple items are mentioned (e.g. "both computers and smart classrooms"), include ALL relevant infra columns INDIVIDUALLY in your `SELECT` statement. This ensures the dashboard charts can show each metric.
- ALIASING RULE: NEVER return a column without a clear name. If you use a calculation or boolean expression (e.g., `i.no_of_computer > 0`), you MUST alias it: `(i.no_of_computer > 0) as has_computers`.
- MANDATORY COLUMNS: Always include `geometry`, identifiers (`udise_num`), AND context columns (`district_name`, `block_name`).
- SCAN RULE: When asked for "Schools with X" or "Schools lacking Y", generate SQL that selects ALL schools (with status columns) but do NOT include `WHERE X = 1` or `WHERE Y = 0`. The dashboard needs ALL data points to calculate the full status breakdown (With, Without, Issues).
- EXAMPLE: User "Schools with both electricity and water" -> Response "SELECT s."schoolName", s.district_name, s.block_name, s.udise_num, i.electricity_connection_available, i.drinking_water_availability, s.geometry FROM meghalaya_schools s JOIN meghalaya_infrastructure i ON i.udise_code::text = s.udise_num::text;"
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
    if 'road density' in q_lower and 'district' in q_lower:
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
    if ('school density' in q_lower or 'per sqkm' in q_lower or 'sq.km' in q_lower) and 'block' in q_lower:
        sql = "SELECT block_name, district_name, schools_per_sqkm, geometry FROM meghalaya_block_intelligence_final ORDER BY schools_per_sqkm DESC; -- cache-v2"
        result = (sql, "block")
        llm_cache.set(question, result)
        return result
    
    # DISTRICT-LEVEL FILTERS (e.g., "schools in RI BHOI", "blocks in RI BHOI")
    if any(d.lower() in q_lower for d in ["east khasi hills", "west khasi hills", "south west khasi hills", "ri bhoi", "east jaintia hills", "west jaintia hills", "east garo hills", "west garo hills", "south garo hills", "south west garo hills", "north garo hills"]):
        dists = ["EAST KHASI HILLS", "WEST KHASI HILLS", "SOUTH WEST KHASI HILLS", "RI BHOI", "EAST JAINTIA HILLS", "WEST JAINTIA HILLS", "EAST GARO HILLS", "WEST GARO HILLS", "SOUTH GARO HILLS", "SOUTH WEST GARO HILLS", "NORTH GARO HILLS"]
        target_dist = next((d for d in dists if d.lower() in q_lower), "")
        
        if target_dist:
            if 'block' in q_lower:
                sql = f"SELECT block_name, district_name, total_schools, schools_per_sqkm, geometry FROM meghalaya_block_intelligence_final WHERE district_name = '{target_dist}' ORDER BY total_schools DESC;"
                result = (sql, "block")
            else:
                # Default: Show all schools in this district with potential infra Join
                # Check if specific infra column is mentioned
                infra_col = next((c for c in ['electricity_connection_available', 'drinking_water_availability', 'no_of_computer', 'smart_classroom_available_in_school_1_yes_2_no', 'library_facility'] if c.split('_')[0] in q_lower), 'electricity_connection_available')
                sql = f"""-- NO_STRIP
                        SELECT s."schoolName", s.district_name, s.block_name, s.udise_num, i.{infra_col}, s.geometry 
                        FROM meghalaya_schools s 
                        JOIN meghalaya_infrastructure i ON i.udise_code::text = s.udise_num::text 
                        WHERE s.district_name = '{target_dist}' ORDER BY s."schoolName" ASC;"""
                result = (sql, "school")
            
            llm_cache.set(question, result)
            return result

    # Computers
    if 'computer' in q_lower:
        sql = """-- NO_STRIP
                 SELECT s."schoolName", s.district_name, s.block_name, s.udise_num,
                 i.no_of_computer, s.geometry
                 FROM meghalaya_schools s
                 JOIN meghalaya_infrastructure i ON i.udise_code::text = s.udise_num::text;"""
        result = (sql, "school")
        llm_cache.set(question, result)
        return result

    # Smart Classrooms
    if 'smart' in q_lower or 'classroom' in q_lower:
        sql = """-- NO_STRIP
                 SELECT s."schoolName", s.district_name, s.block_name, s.udise_num,
                 i.smart_classroom_available_in_school_1_yes_2_no as smart_classroom, s.geometry
                 FROM meghalaya_schools s
                 JOIN meghalaya_infrastructure i ON i.udise_code::text = s.udise_num::text;"""
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
                 LEFT JOIN meghalaya_infrastructure i ON LEFT(s.udise_num::text, 11) = LEFT(i.udise_code::text, 11);"""
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
                 LEFT JOIN meghalaya_infrastructure i ON LEFT(s.udise_num::text, 11) = LEFT(i.udise_code::text, 11);"""
        result = (sql, "school")
        llm_cache.set(question, result)
        return result

    # --- DENSITY & AGGREGATE FALLBACKS ---
    if 'road density' in q_lower and 'district' in q_lower:
        sql = """-- NO_STRIP
                 SELECT district_name, avg_road_density 
                 FROM meghalaya_district_intelligence_final 
                 ORDER BY avg_road_density DESC;"""
        result = (sql, "district")
        llm_cache.set(question, result)
        return result

    if 'school density' in q_lower or 'per sqkm' in q_lower:
        if 'block' in q_lower:
            sql = """-- NO_STRIP
                     SELECT block_name, district_name, schools_per_sqkm as school_density 
                     FROM meghalaya_block_intelligence_final 
                     ORDER BY school_density DESC;"""
            result = (sql, "block")
            llm_cache.set(question, result)
            return result
        elif 'district' in q_lower:
            sql = """-- NO_STRIP
                     SELECT district_name, avg_school_density as school_density 
                     FROM meghalaya_district_intelligence_final 
                     ORDER BY school_density DESC;"""
            result = (sql, "district")
            llm_cache.set(question, result)
            return result

    if 'total schools' in q_lower and 'district' in q_lower:
        sql = """-- NO_STRIP
                 SELECT district_name, avg_total_schools as total_schools 
                 FROM meghalaya_district_intelligence_final 
                 ORDER BY total_schools DESC;"""
        result = (sql, "district")
        llm_cache.set(question, result)
        return result

    # SOLAR PANEL
    if 'solar' in q_lower or 'panel' in q_lower:
        sql = """-- NO_STRIP
                 SELECT s."schoolName", s.district_name, s.block_name, s.udise_num,
                 i.solar_panel, s.geometry
                 FROM meghalaya_schools s
                 JOIN meghalaya_infrastructure i ON i.udise_code::text = s.udise_num::text;"""
        result = (sql, "school")
        llm_cache.set(question, result)
        return result

    # LIBRARY
    if 'library' in q_lower:
        sql = """-- NO_STRIP
                 SELECT s."schoolName", s.district_name, s.block_name, s.udise_num,
                 i.library_facility, s.geometry
                 FROM meghalaya_schools s
                 JOIN meghalaya_infrastructure i ON i.udise_code::text = s.udise_num::text;"""
        result = (sql, "school")
        llm_cache.set(question, result)
        return result

    # PLAYGROUND
    if 'playground' in q_lower:
        sql = """-- NO_STRIP
                 SELECT s."schoolName", s.district_name, s.block_name, s.udise_num,
                 i.playground_available, s.geometry
                 FROM meghalaya_schools s
                 JOIN meghalaya_infrastructure i ON i.udise_code::text = s.udise_num::text;"""
        result = (sql, "school")
        llm_cache.set(question, result)
        return result

    # TOILET
    if 'toilet' in q_lower:
        sql = """-- NO_STRIP
                 SELECT s."schoolName", s.district_name, s.block_name, s.udise_num,
                 i.boy_toilet_available, i.girls_toilet_available, s.geometry
                 FROM meghalaya_schools s
                 JOIN meghalaya_infrastructure i ON i.udise_code::text = s.udise_num::text;"""
        result = (sql, "school")
        llm_cache.set(question, result)
        return result

    # INTERNET (standalone, not combined with smart classroom)
    if 'internet' in q_lower:
        sql = """-- NO_STRIP
                 SELECT s."schoolName", s.district_name, s.block_name, s.udise_num,
                 i.internet_facility_available_in_school_1_yes_2_no as internet_available, s.geometry
                 FROM meghalaya_schools s
                 JOIN meghalaya_infrastructure i ON i.udise_code::text = s.udise_num::text;"""
        result = (sql, "school")
        llm_cache.set(question, result)
        return result

    # FIRE EXTINGUISHER
    if 'fire' in q_lower or 'extinguisher' in q_lower:
        sql = """-- NO_STRIP
                 SELECT s."schoolName", s.district_name, s.block_name, s.udise_num,
                 i.fire_extinguisher_available_1_yes_2_no as fire_extinguisher, s.geometry
                 FROM meghalaya_schools s
                 JOIN meghalaya_infrastructure i ON i.udise_code::text = s.udise_num::text;"""
        result = (sql, "school")
        llm_cache.set(question, result)
        return result

    # HAND WASHING
    if 'handwash' in q_lower or 'hand wash' in q_lower:
        sql = """-- NO_STRIP
                 SELECT s."schoolName", s.district_name, s.block_name, s.udise_num,
                 i.hand_washing_facility_near_toilet, s.geometry
                 FROM meghalaya_schools s
                 JOIN meghalaya_infrastructure i ON i.udise_code::text = s.udise_num::text;"""
        result = (sql, "school")
        llm_cache.set(question, result)
        return result

    # RAMPS (Specific Sidebar Fix)
    if 'ramp' in q_lower:
        sql = """-- NO_STRIP
                 SELECT s."schoolName", s.district_name, s.block_name, s.udise_num,
                 i.ramp_available, s.geometry
                 FROM meghalaya_schools s
                 JOIN meghalaya_infrastructure i ON i.udise_code::text = s.udise_num::text;"""
        result = (sql, "school")
        llm_cache.set(question, result)
        return result

    # ELECTRICITY (Broad Baseline Fix)
    if 'electricity' in q_lower:
        sql = """-- NO_STRIP
                 SELECT s."schoolName", s.district_name, s.block_name, s.udise_num,
                 i.electricity_connection_available, s.geometry
                 FROM meghalaya_schools s
                 JOIN meghalaya_infrastructure i ON i.udise_code::text = s.udise_num::text;"""
        result = (sql, "school")
        llm_cache.set(question, result)
        return result

    # WATER (Broad Baseline Fix)
    if 'water' in q_lower or 'drinking water' in q_lower:
        sql = """-- NO_STRIP
                 SELECT s."schoolName", s.district_name, s.block_name, s.udise_num,
                 i.drinking_water_availability, s.geometry
                 FROM meghalaya_schools s
                 JOIN meghalaya_infrastructure i ON i.udise_code::text = s.udise_num::text;"""
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
    """Refined AI Summary Engine: Provides deep insights with Government of Meghalaya persona."""
    cache_key = f"summary_ai_{question}_{len(data)}"
    cached = summary_cache.get(cache_key)
    if cached: return cached

    if not data: return "No data points found for the requested analysis."

    total_analyzed = len(data)
    # 1. Pre-calculate Stats to guide the LLM
    infra_cols = [
        'electricity_connection_available', 'drinking_water_availability', 'playground_available', 
        'ramp_available', 'solar_panel', 'library_facility', 'fire_extinguisher_available_1_yes_2_no', 
        'smart_classroom_available_in_school_1_yes_2_no', 'internet_facility_available_in_school_1_yes_2_no', 
        'no_of_computer'
    ]
    q_low = question.lower()
    
    # Identify ALL target columns mentioned in the question and present in data
    target_cols = [c for c in infra_cols if c in data[0] and (c.split('_')[0] in q_low or (c=='smart_classroom_available_in_school_1_yes_2_no' and 'smart' in q_low))]
    
    # Fallback if none detected by keyword
    if not target_cols:
        target_cols = [next((c for c in infra_cols if c in data[0]), 'electricity_connection_available')]

    # Calculate Joint Stats
    joint_met = 0
    joint_no = 0
    joint_issue = 0
    individual_stats = {c: {'yes': 0, 'no': 0, 'issue': 0} for c in target_cols}
    
    def get_status(val, col_name):
        v = int(val) if val is not None else 0
        if col_name == 'no_of_computer':
            return 'yes' if v > 0 else 'no'
        if v == 1: return 'yes'
        if v == 2: return 'issue'
        return 'no'

    for d in data:
        statuses = {col: get_status(d.get(col), col) for col in target_cols}
        for col, stat in statuses.items():
            individual_stats[col][stat] += 1
        
        if all(s == 'yes' for s in statuses.values()): joint_met += 1
        if any(s == 'no' for s in statuses.values()): joint_no += 1
        if any(s == 'issue' for s in statuses.values()) and not any(s == 'no' for s in statuses.values()): joint_issue += 1

    # 2. Optimized Prompt with Multi-Metric Context
    stats_context = f"Total Records: {total_analyzed}\nCriteria: {', '.join(target_cols)}\n"
    for col, stats in individual_stats.items():
        stats_context += f"- {col}: {stats['yes']} With, {stats['no']} Without, {stats['issue']} Issues\n"
    
    prompt = f"""
System: You are the Meghalaya GeoAI Assistant. Summarize the spatial data findings below.
Persona: Analytical, professional Government Consultant.
Context: Analyzed {total_analyzed} schools for gaps in {', '.join(target_cols)}.

{stats_context}
- Met all criteria: {joint_met}

Rules:
1. Start with "### Analytics Summary"
2. Provide exactly 3 bullet points: Key Findings (mention counts for all 3 categories: With, Without, Issue), Spatial Gaps, and Priority Recommendations.
3. Be specific and data-driven.

Output:
"""

    payload = {
        "model": MODEL,
        "prompt": prompt,
        "stream": False,
        "options": {"temperature": 0.0, "num_predict": 250}
    }

    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(OLLAMA_URL, json=payload, timeout=25.0)
            result = response.json().get("response", "").strip()
            summary_cache.set(cache_key, result)
            return result
    except Exception as e:
        logger.error(f"AI Summary Error: {e}")
        return f"### Analytics Summary\n\nAnalyzed {total_analyzed} records. Jointly met: {joint_met}."

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
