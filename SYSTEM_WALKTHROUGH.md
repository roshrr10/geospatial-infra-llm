# Meghalaya GeoAI Platform - System Walkthrough

## 1. Project Overview
**What this is:** An intelligent geospatial infrastructure platform for Meghalaya.
**Goal:** Deeply analyze school infrastructure, utility access, and connectivity using natural language queries (e.g., "Show schools with no electricity in West Garo Hills").
**Core capability:** You ask a question in plain English, and the system dynamically generates a Map layout, Data Table, and an AI-driven Analytical Summary.

---

## 2. Technology Stack (What we used)
- **Frontend:** Next.js (React) + Leaflet.js (Interactive Maps) + Tailwind CSS
- **Backend:** Python FastAPI
- **AI/LLM:** Local Ollama (Model: `mistral`) - *Runs 100% offline/locally*
- **Database:** PostgreSQL + PostGIS (Spatial Database Extension)
- **Data Processing:** Python (Pandas, GeoPandas, SQLAlchemy)

---

## 3. How It Works (The Flow)
1. **User asks:** "Show schools without drinking water in West Garo Hills"
2. **Frontend** sends this text to the **Backend API** via ngrok/localhost.
3. **Backend** passes the text to the **Ollama Service** (`backend/services/ollama_service.py`).
4. **LLM Brain** (Prompt Engineering):
   - Uses hardcoded high-performance fallbacks for common queries (Counts, Density).
   - Generates dynamic SQL for complex infrastructure filters.
   - Converts English to SQL (e.g., `WHERE electricity_connection_available = 1 AND district_name = 'WEST GARO HILLS'`).
5. **Spatial Service Execution (`backend/services/spatial_service.py`):**
   - Cleans and auto-fixes LLM-generated SQL (handling case sensitivity, missing geometry, etc.).
   - Executes the GeoSQL against the Postgres database using SQLAlchemy and GeoPandas.
   - Returns real data (GeoJSON features and formatted tables).
6. **Response:**
   - The Backend sends the GeoJSON and table data alongside AI-generated analytical summaries back to the Frontend.

---

## 4. The Database Strategy (How we built the data)
We don't just dump raw files. We utilize a strong **ETL Pipeline** built into the `/scripts/` folder.

### The automated ingestion scripts perform:
1. **Reading Raw Files in `/data/`:**
   - Excel/CSV files for administrative infrastructure logic (`infrastructure.csv`).
2. **Cleaning & Merging:**
   - Normalizes text casing, stripping whitespaces.
   - Validates values (e.g. converting 'Yes'/'No' text fields into strict querying columns where applicable).
3. **Data Schemas:**
   - We utilize a unified data model across `meghalaya_schools` and intelligence tables.
   - The system uses a strict mapping between natural language metrics and database columns defined in the service layer.

---

## 5. The "Brain" Logic (LLM Rules)
We programmed robust guardrails into the LLM system prompts (`backend/services/ollama_service.py`) to handle complex queries safely.

### Special Logic We Guard Against:
1. **Multi-Metric Scoring**: 
   - When 2+ facilities are queried, the system calculates a **Composite Infrastructure Score (0-100)**.
   - Automatically categorizes schools as **"All Met"**, **"Partial Met"**, or **"None Met"**.
2. **Girls' Hygiene Audit**:
   - Specialized mapping for sanitary vending machines, incinerators, and girls' toilets.
3. **Condition Awareness**:
   - Handles "functional issues" and "not working" queries by filtering for values `0` or `2`.
4. **Geographic Guardrails**:
   - Strictly focused on Meghalaya; prevents hallucination for non-local geographic queries.
5. **Averting NULL values**:
   - The LLM forces conditions like `column IS NOT NULL AND column != ''` when looking for specific conditions.

---

## 6. How to Run It (For New Developers)
Please reference the primary **`README.md`** file for the complete, step-by-step terminal instructions.

**Quick Reference:**
1. **Database:** Ensure PostgreSQL is running (default port `5432`). 
   - Load `.env.example` into `.env`.
2. **Backend:** 
   - `python -m venv venv`
   - `venv\Scripts\activate`
   - `uvicorn backend.main:app --reload --port 8000`
3. **Frontend:** 
   - `npm install`
   - `npm run dev` (running on port `3000`)
4. **Tunnels (Optional for Vercel):** `ngrok http 8000`
