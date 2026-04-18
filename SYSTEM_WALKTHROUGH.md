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
3. **Backend** passes the text to the **LLM Service** (`backend/llm/`).
4. **LLM Brain** (Prompt Engineering):
   - Decides WHICH table to use (Schools vs Blocks vs Districts).
   - Converts English to SQL (e.g., `WHERE drinking_water = 'No' AND district_name = 'WEST GARO HILLS'`).
5. **PostGIS Execution:**
   - The GeoSQL runs against the Postgres database.
   - It returns real data (lat/long points, polygons, statistics).
6. **Response:**
   - The Backend groups the data into GeoJSON (for the map features) and sends it alongside AI analytical summaries back to the Frontend UI.

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
   - We utilize highly explicit schema definitions (`backend/school_schema.txt` structure) mapped to Database tables so the LLM knows exactly what column names it can utilize.

---

## 5. The "Brain" Logic (LLM Rules)
We programmed robust guardrails into the LLM system prompts (`backend/nlq/prompt_builder.py`) to handle complex queries safely.

### Special Logic We Guard Against:
1. **Averting NULL values:**
   - The LLM forces conditions like `column IS NOT NULL AND column != ''` when looking for specific conditions.
2. **Case Insensitivity:**
   - Standardized `ILIKE` for string matches (e.g., `district ILIKE '%GARO HILLS%'`) instead of strict `=`.

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
