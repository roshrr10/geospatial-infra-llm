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
- VALUES & CONDITIONALS:
  - 1 = Yes/Functional/Available (Green).
  - 0 = No/None/Missing (Red).
  - 2 = Functional Issue / Needs Repair / Not Working (Orange/Issue).
  - For "not working" or "functional issues", the user wants to see schools where the value is 0 OR 2.
  - For "functional" or "working", the user wants to see schools where the value is 1.
- GEOGRAPHIC SCOPE:
  - You ONLY have data for Meghalaya, India. 
  - If asked about other cities/states (e.g., "Bangalore", "Delhi"), respond with: "[CHAT] I am specialized in Meghalaya's infrastructure. I do not have data for [Location]. [/CHAT]"
- INFRASTRUCTURE & HEALTH COLUMNS (meghalaya_infrastructure i):
  - Health: `medical_facilities_medical_rooms_available`, `hand_washing_facility_after_meals`, `hand_washing_facility_near_toilet`, `drinking_water_functional`
  - Safety: `fire_extinguisher_available_1_yes_2_no`, `dilapidated_building`, `boundary_wall_type_1_pucca_2_pucca_but_broken_3_barbed_wire_fen`
  - Facilities: `electricity_connection_available`, `drinking_water_availability`, `playground_available`, `ramp_available`, `solar_panel`, `library_facility`, `girls_toilet_available`, `girls_activity_room_available`, `sport_equiptment`, `store_room_available`
  - Digital: `smart_classroom_available_in_school_1_yes_2_no`, `internet_facility_available_in_school_1_yes_2_no`, `no_of_computer`
- CONTEXT COLUMNS: `i.cluster_name`, `i.village_name`, `i.schlocation` (Rural/Urban), `i.schtype` (Co-ed/Boys/Girls)
- BOTH/COMBINED RULE: For 2+ metrics, select ALL schools and individual columns for dashboard comparison.
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

async def get_sql_from_llm(question: str, language: str = "en"):
    # Check Cache
    cached = llm_cache.get(question)
    if cached:
        logger.info(f"LLM CACHE HIT for: {question}")
        return cached

    # ---- HARDCODED FALLBACKS for common count/density queries ----
    q_lower = question.lower()
    
    # District school counts
    if any(kw in q_lower for kw in ['district', 'districts']) and any(kw in q_lower for kw in ['most school', 'number of school', 'more school', 'total school', 'school count']):
        sql = "SELECT district_name, COUNT(*) as total_schools FROM meghalaya_schools GROUP BY district_name ORDER BY total_schools DESC;"
        result = (sql, "district")
        llm_cache.set(question, result)
        return result
    
    # Block school counts
    if any(kw in q_lower for kw in ['block', 'blocks']) and any(kw in q_lower for kw in ['most school', 'number of school', 'more school', 'total school', 'school count']):
        sql = "SELECT block_name, district_name, total_schools, geometry FROM meghalaya_block_intelligence_final ORDER BY total_schools DESC;"
        result = (sql, "block")
        llm_cache.set(question, result)
        return result

    # DISTRICT-LEVEL FILTERS (e.g., "schools in RI BHOI", "blocks in RI BHOI")
    # MUST be checked BEFORE global "total school" fallback to catch "total schools in east khasi hills"
    if any(d.lower() in q_lower for d in ["east khasi hills", "west khasi hills", "south west khasi hills", "eastern west khasi hills", "ri bhoi", "east jaintia hills", "west jaintia hills", "east garo hills", "west garo hills", "south garo hills", "south west garo hills", "north garo hills"]):
        dists = ["EAST KHASI HILLS", "WEST KHASI HILLS", "SOUTH WEST KHASI HILLS", "EASTERN WEST KHASI HILLS", "RI BHOI", "EAST JAINTIA HILLS", "WEST JAINTIA HILLS", "EAST GARO HILLS", "WEST GARO HILLS", "SOUTH GARO HILLS", "SOUTH WEST GARO HILLS", "NORTH GARO HILLS"]
        target_dist = next((d for d in dists if d.lower() in q_lower), "")
        
        if target_dist:
            # Total/count queries for a specific district
            if any(kw in q_lower for kw in ['total school', 'how many school', 'number of school', 'school count']):
                sql = f"SELECT district_name, COUNT(*) as total_schools FROM meghalaya_schools WHERE district_name = '{target_dist}' GROUP BY district_name;"
                result = (sql, "district")
                llm_cache.set(question, result)
                return result

            if 'block' in q_lower:
                sql = f"SELECT block_name, district_name, total_schools, schools_per_sqkm, geometry FROM meghalaya_block_intelligence_final WHERE district_name = '{target_dist}' ORDER BY total_schools DESC;"
                result = (sql, "block")
            else:
                # Robust Detection for infra metrics
                metrics_map = {
                    'electricity': 'electricity_connection_available',
                    'water': 'drinking_water_availability',
                    'drinking': 'drinking_water_availability',
                    'computer': 'no_of_computer',
                    'smart': 'smart_classroom_available_in_school_1_yes_2_no',
                    'classroom': 'smart_classroom_available_in_school_1_yes_2_no',
                    'library': 'library_facility',
                    'ramp': 'ramp_available',
                    'solar': 'solar_panel',
                    'playground': 'playground_available',
                    'internet': 'internet_facility_available_in_school_1_yes_2_no',
                    'fire': 'fire_extinguisher_available_1_yes_2_no',
                    'handwash': 'hand_washing_facility_near_toilet',
                    'hand wash': 'hand_washing_facility_near_toilet',
                    'vending machine': 'whether_your_school_having_sanitary_pad_vending_machine__for_sc',
                    'incinerator': 'whether_your_school_having_functional_incinerator_in_girls_toil',
                    'activity room': 'girls_activity_room_available',
                    'sports': 'sport_equiptment',
                    'equipment': 'sport_equiptment',
                    'medical': 'medical_facilities_medical_rooms_available',
                    'health': 'medical_facilities_medical_rooms_available',
                    'boundary': 'boundary_wall_type_1_pucca_2_pucca_but_broken_3_barbed_wire_fen',
                    'wall': 'boundary_wall_type_1_pucca_2_pucca_but_broken_3_barbed_wire_fen',
                    'dilapidated': 'dilapidated_building',
                    'unsafe': 'dilapidated_building',
                    'broken': 'dilapidated_building',
                    'functional': 'drinking_water_functional',
                    'working': 'drinking_water_functional',
                    'not working': 'drinking_water_functional',
                    'issue': 'drinking_water_functional'
                }
                
                detected_cols = []
                seen_cols = set()
                for kw, col in metrics_map.items():
                    if kw in q_lower and col not in seen_cols:
                        detected_cols.append(col)
                        seen_cols.add(col)
                
                # If rural/urban mentioned, prioritize those as filters
                location_filter = ""
                if 'rural' in q_lower: location_filter = " AND i.schlocation = 'Rural'"
                elif 'urban' in q_lower: location_filter = " AND i.schlocation = 'Urban'"

                cols_sql = ""
                if detected_cols:
                    cols_sql = ", " + ", ".join([f"i.{c}" for c in detected_cols])
                
                
                extra_cols = ""
                attainment_sql = ""

                if len(detected_cols) > 1:
                    # Scoring logic for multiple metrics
                    score_parts = " + ".join([f"COALESCE(CASE WHEN i.{c} = 1 THEN 1 ELSE 0 END, 0)" for c in detected_cols])
                    total_count = len(detected_cols)
                    extra_cols = f", (({score_parts})::float / {total_count} * 100) as infrastructure_score, ({score_parts}) as met_criteria_count"

                    # Multi-metric attainment logic
                    if len(detected_cols) == 2:
                        c1, c2 = detected_cols
                        attainment_sql = f""",
                            CASE 
                                WHEN (i.{c1} = 1 AND i.{c2} = 1) THEN 'Both'
                                WHEN (i.{c1} = 1) THEN 'Only {c1.split('_')[0].capitalize()}'
                                WHEN (i.{c2} = 1) THEN 'Only {c2.split('_')[0].capitalize()}'
                                ELSE 'Neither'
                            END as multi_metric_attainment"""
                    else:
                        attainment_sql = f""", 
                            CASE 
                                WHEN ({score_parts}) = {total_count} THEN 'All Met'
                                WHEN ({score_parts}) > 0 THEN 'Partial Met'
                                ELSE 'None Met'
                            END as multi_metric_attainment"""

                sql = f"""-- NO_STRIP
                        SELECT s."schoolName", s.district_name, s.block_name, i.cluster_name, i.village_name, i.schlocation, i.schtype, s.udise_num{cols_sql}{extra_cols}{attainment_sql}, s.geometry 
                        FROM meghalaya_schools s 
                        JOIN meghalaya_infrastructure i ON i.udise_code::text = s.udise_num::text 
                        WHERE s.district_name = '{target_dist}'{location_filter} ORDER BY s."schoolName" ASC;"""
                result = (sql, "school")
            
            llm_cache.set(question, result)
            return result

    # Global school counts ("how many schools do we have")
    # This MUST be after the district-specific handler above
    if 'how many school' in q_lower or 'total school' in q_lower:
        if 'district' not in q_lower and 'block' not in q_lower:
            sql = "SELECT 'Meghalaya' as state_name, COUNT(*) as total_schools FROM meghalaya_schools;"
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


    # --- JOINT INFRASTRUCTURE FALLBACKS (Priority) ---
    
    # Computers AND Smart Classrooms (User Test Case)
    if 'computer' in q_lower and ('smart' in q_lower or 'classroom' in q_lower):
        sql = """-- NO_STRIP
                 SELECT s."schoolName", s.district_name, s.block_name, s.udise_num,
                 i.no_of_computer, i.smart_classroom_available_in_school_1_yes_2_no as smart_classroom,
                 CASE 
                    WHEN (i.no_of_computer > 0 AND i.smart_classroom_available_in_school_1_yes_2_no = 1) THEN 'Both'
                    WHEN (i.no_of_computer > 0) THEN 'Only Computer'
                    WHEN (i.smart_classroom_available_in_school_1_yes_2_no = 1) THEN 'Only Smart'
                    ELSE 'Neither'
                 END as comp_smart_attainment,
                 s.geometry
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
                 CASE 
                    WHEN (i.electricity_connection_available = 1 AND i.drinking_water_availability = 1) THEN 'Both'
                    WHEN (i.electricity_connection_available = 1) THEN 'Only Electricity'
                    WHEN (i.drinking_water_availability = 1) THEN 'Only Water'
                    ELSE 'Neither'
                 END as electricity_water_attainment,
                 s.geometry
                 FROM meghalaya_schools s
                 JOIN meghalaya_infrastructure i ON i.udise_code::text = s.udise_num::text;"""
        result = (sql, "school")
        llm_cache.set(question, result)
        return result

    # Internet AND smart classrooms  
    if ('internet' in q_lower and ('smart' in q_lower or 'classroom' in q_lower)):
        sql = """-- NO_STRIP
                 SELECT s."schoolName", s.district_name, s.block_name, s.udise_num,
                 i.internet_facility_available_in_school_1_yes_2_no as internet_available,
                 i.smart_classroom_available_in_school_1_yes_2_no as smart_classroom,
                 CASE 
                    WHEN (i.internet_facility_available_in_school_1_yes_2_no = 1 AND i.smart_classroom_available_in_school_1_yes_2_no = 1) THEN 'Both'
                    WHEN (i.internet_facility_available_in_school_1_yes_2_no = 1) THEN 'Only Internet'
                    WHEN (i.smart_classroom_available_in_school_1_yes_2_no = 1) THEN 'Only Smart'
                    ELSE 'Neither'
                 END as internet_smart_attainment,
                 s.geometry
                 FROM meghalaya_schools s
                 JOIN meghalaya_infrastructure i ON i.udise_code::text = s.udise_num::text;"""
        result = (sql, "school")
        llm_cache.set(question, result)
        return result

    # --- DENSITY & AGGREGATE FALLBACKS ---
    if 'road density' in q_lower and 'district' in q_lower:
        sql = """-- NO_STRIP
                 SELECT district_name, avg_road_density, geometry
                 FROM meghalaya_district_intelligence_final 
                 ORDER BY avg_road_density DESC;"""
        result = (sql, "district")
        llm_cache.set(question, result)
        return result

    if 'school density' in q_lower or 'per sqkm' in q_lower:
        if 'block' in q_lower:
            sql = """-- NO_STRIP
                     SELECT block_name, district_name, schools_per_sqkm as school_density, geometry
                     FROM meghalaya_block_intelligence_final 
                     ORDER BY school_density DESC;"""
            result = (sql, "block")
            llm_cache.set(question, result)
            return result
        elif 'district' in q_lower:
            sql = """-- NO_STRIP
                     SELECT district_name, avg_school_density as school_density, geometry
                     FROM meghalaya_district_intelligence_final 
                     ORDER BY school_density DESC;"""
            result = (sql, "district")
            llm_cache.set(question, result)
            return result

    if 'total schools' in q_lower and 'district' in q_lower:
        sql = """-- NO_STRIP
                 SELECT district_name, COUNT(*) as total_schools FROM meghalaya_schools GROUP BY district_name ORDER BY total_schools DESC;"""
        result = (sql, "district")
        llm_cache.set(question, result)
        return result

    # --- GENERIC MULTI-METRIC INFRASTRUCTURE DETECTION ---
    # This block catches any combination of infra keywords not handled by the priority joint fallbacks above
    infra_metrics_map = {
        'electricity': 'electricity_connection_available',
        'water': 'drinking_water_availability',
        'drinking': 'drinking_water_availability',
        'computer': 'no_of_computer',
        'smart': 'smart_classroom_available_in_school_1_yes_2_no',
        'classroom': 'smart_classroom_available_in_school_1_yes_2_no',
        'library': 'library_facility',
        'ramp': 'ramp_available',
        'solar': 'solar_panel',
        'playground': 'playground_available',
        'internet': 'internet_facility_available_in_school_1_yes_2_no',
        'fire': 'fire_extinguisher_available_1_yes_2_no',
        'handwash': 'hand_washing_facility_near_toilet',
        'hand wash': 'hand_washing_facility_near_toilet',
        'toilet': 'girls_toilet_available',
        'vending machine': 'whether_your_school_having_sanitary_pad_vending_machine__for_sc',
        'incinerator': 'whether_your_school_having_functional_incinerator_in_girls_toil',
        'activity room': 'girls_activity_room_available',
        'sports': 'sport_equiptment',
        'equipment': 'sport_equiptment',
        'medical': 'medical_facilities_medical_rooms_available',
        'health': 'medical_facilities_medical_rooms_available',
        'boundary': 'boundary_wall_type_1_pucca_2_pucca_but_broken_3_barbed_wire_fen',
        'wall': 'boundary_wall_type_1_pucca_2_pucca_but_broken_3_barbed_wire_fen',
        'dilapidated': 'dilapidated_building',
        'unsafe': 'dilapidated_building',
        'broken': 'dilapidated_building',
        'functional': 'drinking_water_functional',
        'working': 'drinking_water_functional',
        'not working': 'drinking_water_functional',
        'issue': 'drinking_water_functional'
    }
    
    detected_infra_cols = []
    seen_infra_cols = set()
    for kw, col in infra_metrics_map.items():
        if kw in q_lower and col not in seen_infra_cols:
            detected_infra_cols.append(col)
            seen_infra_cols.add(col)
            
    # Location filters
    loc_filter = ""
    if 'rural' in q_lower: loc_filter = " WHERE i.schlocation = 'Rural'"
    elif 'urban' in q_lower: loc_filter = " WHERE i.schlocation = 'Urban'"

    if detected_infra_cols or loc_filter:
        cols_sql = ""
        if detected_infra_cols:
            cols_sql = ", " + ", ".join([f"i.{c}" for c in detected_infra_cols])
        
        extra_cols = ""
        attainment_sql = ""

        if len(detected_infra_cols) > 1:
            # Scoring logic for multiple metrics
            score_parts = " + ".join([f"COALESCE(CASE WHEN i.{c} = 1 THEN 1 ELSE 0 END, 0)" for c in detected_infra_cols])
            total_count = len(detected_infra_cols)
            extra_cols = f", (({score_parts})::float / {total_count} * 100) as infrastructure_score, ({score_parts}) as met_criteria_count"

            if len(detected_infra_cols) == 2:
                c1, c2 = detected_infra_cols
                l1 = c1.split('_')[0].capitalize()
                l2 = c2.split('_')[0].capitalize()
                attainment_sql = f""",
                    CASE 
                        WHEN (i.{c1} = 1 AND i.{c2} = 1) THEN 'Both'
                        WHEN (i.{c1} = 1) THEN 'Only {l1}'
                        WHEN (i.{c2} = 1) THEN 'Only {l2}'
                        ELSE 'Neither'
                    END as multi_metric_attainment"""
            else:
                attainment_sql = f""", 
                    CASE 
                        WHEN ({score_parts}) = {total_count} THEN 'All Met'
                        WHEN ({score_parts}) > 0 THEN 'Partial Met'
                        ELSE 'None Met'
                    END as multi_metric_attainment"""

        sql = f"""-- NO_STRIP
                 SELECT s."schoolName", s.district_name, s.block_name, i.cluster_name, i.village_name, i.schlocation, i.schtype, s.udise_num{cols_sql}{extra_cols}{attainment_sql}, s.geometry 
                 FROM meghalaya_schools s 
                 JOIN meghalaya_infrastructure i ON i.udise_code::text = s.udise_num::text{loc_filter};"""
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

async def get_summary_from_llm(question: str, data: list, language: str = "en"):
    """Refined AI Summary Engine: Provides deep insights with Government of Meghalaya persona."""
    cache_key = f"summary_ai_{question}_{len(data)}_{language}"
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
    try:
        if not target_cols:
            target_cols = [next((c for c in infra_cols if c in data[0]), 'electricity_connection_available')]

        # Calculate Overlap Stats (Venn Logic)
        total_both = 0
        total_only_x = 0
        total_only_y = 0
        total_neither = 0
        
        individual_stats = {c: {'yes': 0, 'no': 0, 'issue': 0} for c in target_cols}
        
        def get_status(val, col_name):
            if val is None: return 'no'
            s_val = str(val).lower().strip()
            if col_name == 'no_of_computer':
                try: return 'yes' if int(val) > 0 else 'no'
                except: return 'no'
            if s_val in ['1', 'yes', 'available', 'true']: return 'yes'
            if s_val in ['2', 'issue', 'partial', 'not functional']: return 'issue'
            return 'no'

        for d in data:
            statuses = {col: get_status(d.get(col), col) for col in target_cols}
            for col, stat in statuses.items():
                individual_stats[col][stat] += 1
            
            # Venn logic for multi-metric queries
            if len(target_cols) >= 2:
                s1, s2 = target_cols[0], target_cols[1]
                v1, v2 = statuses[s1], statuses[s2]
                if v1 == 'yes' and v2 == 'yes': total_both += 1
                elif v1 == 'yes' and v2 != 'yes': total_only_x += 1
                elif v2 == 'yes' and v1 != 'yes': total_only_y += 1
                elif v1 != 'yes' and v2 != 'yes': total_neither += 1
            else:
                if any(s == 'yes' for s in statuses.values()): total_both += 1

        # 2. Optimized Prompt with Multi-Metric Context
        sc = f"Total Records: {total_analyzed}\nCriteria: {', '.join(target_cols)}\n"
        for col, stats in individual_stats.items():
            sc += f"- {col}: {stats['yes']} Equipped, {stats['no']} Missing\n"
        
        if len(target_cols) == 2:
            sc += f"\nOverlap Analysis (Venn-Logic):\n- Both {target_cols[0]} AND {target_cols[1]}: {total_both}\n- ONLY {target_cols[0]}: {total_only_x}\n- ONLY {target_cols[1]}: {total_only_y}\n- Neither: {total_neither}\n"
        
        # Build prompt without nested f-string complexity to avoid "Invalid format specifier"
        lang_instructions = {
            "en": "Respond in English.",
            "kh": "Respond in Khasi language. Use simple and professional Khasi for a government report. Terms like 'District' or 'Infrastructure' can be kept in English if no direct Khasi term exists.",
            "ga": "Respond in Garo language. Use professional Garo for a government report."
        }
        lang_prompt = lang_instructions.get(language, lang_instructions["en"])

        prompt = "System: You are the Meghalaya GeoAI Assistant. Summarize the spatial data findings below.\n"
        prompt += f"Persona: Analytical, professional Government Consultant. {lang_prompt}\n"
        prompt += f"Context: Analyzed {total_analyzed} schools for gaps in {', '.join(target_cols)}.\n\n"
        prompt += sc
        prompt += f"\n- Met all criteria: {total_both}\n\n"
        prompt += "Rules:\n"
        prompt += "1. Return your response as a valid JSON object only.\n"
        prompt += '2. Structure: { "summary": ["Point 1", "Point 2", "Point 3"], "recommendations": ["Point 1", "Point 2", "Point 3"] }\n'
        prompt += "3. Do NOT use any Markdown characters like #, ##, *, **, or _ inside the text.\n"
        prompt += "4. Keep each point short, crisp, and clear (1 sentence preferred).\n"
        prompt += "5. Provide precisely 3 points for the summary and 3 points for recommendations.\n"
        prompt += "6. Return a JSON array of strings for both keys.\n\n"
        prompt += "Output:"

        payload = {
            "model": MODEL,
            "prompt": prompt,
            "stream": False,
            "options": {"temperature": 0.0, "num_predict": 250}
        }

        async with httpx.AsyncClient() as client:
            response = await client.post(OLLAMA_URL, json=payload, timeout=45.0)
            response.raise_for_status()
            raw_res = response.json().get("response", "").strip()
            
            import json
            import re
            
            try:
                # Use regex to find the JSON block in case there is chatter
                match = re.search(r"(\{.*\})", raw_res, re.DOTALL)
                if match:
                    parsed = json.loads(match.group(1))
                    # Ensure both keys exist
                    if "summary" in parsed and "recommendations" in parsed:
                        summary_cache.set(cache_key, parsed)
                        return parsed
                
                # Fallback if parsing fails but there is text
                fallback = {
                    "summary": [raw_res if raw_res else "Spatial analysis complete."],
                    "recommendations": ["Further policy interventions recommended for identified gaps."]
                }
                summary_cache.set(cache_key, fallback)
                return fallback
                
            except Exception as e:
                logger.error(f"JSON Parse Error: {e}")
                return {
                    "summary": [raw_res if raw_res else "Spatial analysis complete."],
                    "recommendations": ["Data-driven policy measures suggested for this region."]
                }
    except Exception as e:
        logger.error(f"AI Summary Error: {e}")
        # Ensure fallback variables are safe
        j_met = total_both if 'total_both' in locals() else 0
        return {
            "summary": [f"Analyzed {total_analyzed} records. Jointly met: {j_met}."],
            "recommendations": ["Manual infrastructure audit recommended."]
        }

async def get_heatmap_summary(metric: str, level: str, data: list, intent: str = "all", language: str = "en"):
    """
    Generates a summary for heatmap visualizations using aggregated trends.
    """
    if not data: return "No spatial density data available."
    
    lang_instructions = {
        "en": "Respond in English.",
        "kh": "Respond in Khasi language.",
        "ga": "Respond in Garo language."
    }
    lang_prompt = lang_instructions.get(language, lang_instructions["en"])

    prompt = f"""
    Analyze the spatial distribution of {metric} across Meghalaya at {level} level.
    The user is looking for intent: {intent}.
    
    DATA: {json.dumps(data)}
    
    Provide 2 bullet points about the geographical clusters of high and low values.
    {lang_prompt}
    """

    total = len(data)
    # The spatial_service now sends flat_data populated with 'intensity' and 'region_name'
    avg_score = sum(d.get('intensity', 0) for d in data) / total if total > 0 else 0
    top_regions = sorted(data, key=lambda x: x.get('intensity', 0), reverse=True)[:3]
    region_names = ", ".join(list(set([d.get('region_name', 'Unknown') for d in top_regions])))
    
    # Calculate school concentration info to satisfy the 'school numbers' narrative
    high_intensity_count = len([d for d in data if d.get('intensity', 0) > 0.5])
    
    metric_label = metric.replace('_', ' ')
    if intent == 'no':
        metric_label = f"Missing/Absence of {metric_label}"

    prompt = f"""
System: You are a GeoAI Analyst. Summarize the spatial pattern of {metric_label} intensity in Meghalaya.
Avoid technical jargon. Note that darker red areas on the heatmap represent higher concentration/numbers. 

Context:
- Target Metric: {metric_label}
- Granularity Level: {level}
- Average Heatmap Intensity (0-1): {round(avg_score, 2)}
- Top Impacted/Concentrated Areas: {region_names}
- Regions with high density of schools/facilities: {high_intensity_count} out of {total} total points mapped.

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
