def generate_sql(user_query: str) -> dict:
    """
    Always returns a dictionary:
    {
        "level": "block" | "district" | "state" | "unknown",
        "sql": "<SQL QUERY>"
    }
    """

    query = user_query.lower().strip()

    # -------------------------------
    # 1. SPECIAL CASES (Worst/Priority)
    # -------------------------------
    if "worst" in query or "priority" in query:
        return {
            "level": "block",
            "sql": """
            SELECT block_name, district_name,
                   total_schools, road_connectivity_score
            FROM hp_block_infra_intelligence
            ORDER BY road_connectivity_score ASC, total_schools ASC
            LIMIT 10;
            """
        }

    # -------------------------------
    # 2. DETERMINE LEVEL & CONDITION
    # -------------------------------
    # Default level is block (covers "areas", "blocks", or unspecified)
    level = "block"
    if "district" in query:
        level = "district"

    # Determine condition
    condition = None
    if "good" in query:
        condition = "> 0.7"
    elif "medium" in query:
        condition = "BETWEEN 0.3 AND 0.7"
    elif "poor" in query:
        condition = "< 0.3"

    # -------------------------------
    # 3. GENERATE SQL
    # -------------------------------
    if condition:
        if level == "district":
            return {
                "level": "district",
                "sql": f"""
            SELECT district_name,
                   AVG(road_connectivity_score) AS road_connectivity_score
            FROM hp_block_infra_intelligence
            GROUP BY district_name
            HAVING AVG(road_connectivity_score) {condition};
            """
            }
        else:
            return {
                "level": "block",
                "sql": f"""
            SELECT block_name, district_name,
                   road_connectivity_score
            FROM hp_block_infra_intelligence
            WHERE road_connectivity_score {condition};
            """
            }

    # -------------------------------
    # FALLBACK
    # -------------------------------
    return {
        "level": "unknown",
        "sql": "SELECT 'Query not understood' AS message;"
    }
