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

    # Districts with highest road density
    if 'road density' in q_lower:
        sql = "SELECT district_name, avg_road_density, geometry FROM meghalaya_district_intelligence_final ORDER BY avg_road_density DESC;"
        result = (sql, "district")
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
        sql = """SELECT s."schoolName", s.district_name, s.block_name, s.udise_num,
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
        sql = """SELECT s."schoolName", s.district_name, s.block_name, s.udise_num,
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
        sql = """SELECT s."schoolName", s.district_name, s.block_name, s.udise_num,
                 i.internet_facility_available_in_school_1_yes_2_no as internet_available,
                 i.smart_classroom_available_in_school_1_yes_2_no as smart_classroom,
                 s.geometry
                 FROM meghalaya_schools s
                 LEFT JOIN meghalaya_infrastructure i ON LEFT(s.udise_num::text, 11) = LEFT(i.udise_code::text, 11)
                 WHERE i.internet_facility_available_in_school_1_yes_2_no = 1 AND i.smart_classroom_available_in_school_1_yes_2_no = 1;"""
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
    # Check Cache
    cache_key = f"{question}_{len(data)}"
    cached = summary_cache.get(cache_key)
    if cached:
        logger.info(f"SUMMARY CACHE HIT for: {question}")
        return cached

    if not data:
        return "No data points found for the requested query."

    total_records = len(data)
    
    # Identify the primary numeric metric or binary field with robust skip-list and prioritization
    sample = data[0]
    skip_keywords = [
        'id', 'code', 'udise', 'sl_no', 'geometry', 'pinc', 'index', 'serial', 
        'mobi', 'phone', 'latitude', 'longitude', 'altitude', 'accuracy',
        'class', 'grade', 'year', 'month'
    ]
    
    # Identify keys by checking up to 50 rows (handle NULLs)
    all_keys = sample.keys()
    metric_keys = []
    for k in all_keys:
        k_lower = k.lower()
        if any(skip in k_lower for skip in skip_keywords):
            continue
        if any(isinstance(row.get(k), (int, float)) for row in data[:50]):
            metric_keys.append(k)
    
    def score_metric(k):
        k_lower = k.lower()
        if 'solar' in k_lower: return 200
        if 'electricity' in k_lower or 'eletricity' in k_lower: return 150
        if 'computer' in k_lower or 'water' in k_lower: return 140
        if 'available' in k_lower or 'facility' in k_lower: return 130
        if 'class' in k_lower or 'grade' in k_lower: return -100
        return 0

    metric_keys.sort(key=score_metric, reverse=True)
    primary_metric = metric_keys[0] if metric_keys else None
    
    def check_val(v, target):
        if v is None: return False
        v_str = str(v).lower().strip()
        if not v_str or v_str in ['n/a', 'null', 'nan']:
            return False
        # Unified YES Definition: Matches GeoMap and Page logic
        positives = ['1', '1.0', 'yes', 'true', 'functional', 'satisfactory', 'available', 'provided']
        negatives = ['0', '0.0', 'no', 'false', 'none', 'unavailable', 'missing']
        
        if target == 'yes':
            return v == 1 or v == 1.0 or v_str in positives
        if target == 'no':
            return v == 0 or v == 0.0 or v_str in negatives
        if target == 'issue':
            return v == 2 or v == 2.0 or 'issue' in v_str or 'partial' in v_str or 'repair' in v_str or 'not functional' in v_str
        return False

    # Detection of multi-infrastructure queries
    infra_keywords = ['solar', 'panel', 'electricity', 'eletricity', 'water', 'toilet', 'computer', 'facility', 'internet', 'smart', 'ramp', 'playground', 'lab', 'library', 'boundary', 'quarters', 'furniture', 'books', 'extinguisher', 'uniform', 'textbook', 'hostel', 'room', 'handwash', 'equipment', 'laboratory', 'board', 'projector', 'tablet', 'desktop', 'laptop', 'sanitary']
    
    # Filter detected_infra based on what's actually in the data
    detected_infra = [k for k in metric_keys if any(ik in k.lower() for ik in infra_keywords)]
    
    # If the user's question mentions specific items, we prioritize those but keep others for context
    q_lower = question.lower()
    targeted = [k for k in detected_infra if any(ik in k.lower() and ik in q_lower for ik in infra_keywords)]
    if targeted:
        detected_infra = targeted

    is_multi_infra = len(detected_infra) > 1

    stats_prompt = f"Total records analyzed: {total_records}\n"
    
    if is_multi_infra:
        # INTERSECTION LOGIC: All facilities must be 'Yes'
        yes = len([d for d in data if all(check_val(d.get(k), 'yes') for k in detected_infra)])
        no = len([d for d in data if all(check_val(d.get(k), 'no') for k in detected_infra)])
        partial = total_records - yes - no
        
        infra_labels = [k.replace('_', ' ').title() for k in detected_infra]
        stats_prompt += f"Selected Infrastructure Suite: {', '.join(infra_labels)}\n"
        stats_prompt += f"- Fully Equipped (All Met) Count: {yes}\n"
        stats_prompt += f"- Completely Lacking (None Met) Count: {no}\n"
        stats_prompt += f"- Partially Equipped Count: {partial}\n"
    elif primary_metric:
        label = primary_metric.replace('_', ' ').title()
        # Check if it's binary
        is_binary = all(check_val(d.get(primary_metric), 'yes') or 
                       check_val(d.get(primary_metric), 'no') or 
                       check_val(d.get(primary_metric), 'issue') or 
                       d.get(primary_metric) is None 
                       for d in data[:300])
        
        if is_binary:
            yes = len([d for d in data if check_val(d.get(primary_metric), 'yes')])
            no = len([d for d in data if check_val(d.get(primary_metric), 'no')])
            issue = len([d for d in data if check_val(d.get(primary_metric), 'issue')])
            stats_prompt += f"Metric: {label}\n"
            stats_prompt += f"- Positive/Available: {yes}\n"
            stats_prompt += f"- Negative/Unavailable: {no}\n"
            stats_prompt += f"- Functional Issues/Partial: {issue}\n"
        else:
            try:
                numeric_vals = [float(d.get(primary_metric, 0)) for d in data if d.get(primary_metric) is not None]
                stats_prompt += f"- Average Value: {round(avg_val, 2)}\n"
                best_id = max_item.get('schoolName') or max_item.get('block_name') or max_item.get('district_name') or 'N/A'
                stats_prompt += f"- Highest Value: {best_id} ({max_item.get(primary_metric)})\n"
            except:
                stats_prompt += f"Data Column: {label}\n- Primary values detected: {data[0].get(primary_metric)}\n"

    # Add localized samples for geographic grounding
    stats_prompt += "\nGeographic Samples (Top 5):\n"
    for d in data[:5]:
        name = d.get('schoolName') or d.get('display_name') or d.get('schname') or "N/A"
        block = d.get('block_name') or d.get('BLOCK') or "N/A"
        dist = d.get('district_name') or d.get('DISTRICT') or "N/A"
        stats_prompt += f"- {name} in {block} Block, {dist} District\n"

    # Context for LLM - STRICT ENFORCEMENT OF AGGREGATES
    prompt = f"""
System: You are an expert GeoAI Analyst for the Government of Meghalaya.
Your task is to summarize the following SPATIAL STATISTICS.

CRITICAL RULES:
1. USE ONLY the exact numbers provided in the 'Summarized Data' section below.
2. NEVER invent, guess, or copy numbers from outside the 'Summarized Data'.
3. DO NOT mention local details unless they are listed in the 'Summarized Data' or 'Sample Locations' sections.
4. If there is a count for 'Positive/Available' or 'All Requirements Met', highlight that and refer to a few representative blocks/districts from the samples if they align.
5. Provide exactly 3 bullet points.
6. STICK TO THE FACTS: Output only the exact counts calculated in the Summarized Data.

User Question: {question}
Summarized Data:
{stats_prompt}

Insight (exactly 3 bullets):
1. Key Findings: [Summary of counts and percentages]
2. Geographic Focus: [Identify the most affected blocks or districts based on regional data]
3. Recommendation: [One actionable step for government intervention based on these specific results]
"""

    # Debug Log
    print(f"--- AI Summary Prompt (Aggregated) ---\n{stats_prompt}\n----------------------------------")

    payload = {
        "model": MODEL,
        "prompt": prompt,
        "stream": False,
        "options": {
            "temperature": 0.0,
            "num_predict": 200
        }
    }

    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(OLLAMA_URL, json=payload, timeout=30.0)
            data_json = response.json()
            return data_json.get("response", "Spatial analysis complete.").strip()
    except Exception as e:
        print(f"Summary LLM Error: {e}")
        return f"Analysis complete for {total_records} records."

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
