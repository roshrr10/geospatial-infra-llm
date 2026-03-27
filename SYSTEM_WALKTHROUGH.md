# Meghalaya GeoAI Platform - System Walkthrough

## 1. Project Overview
**What this is:** An intelligent geospatial infrastructure platform for Meghalaya.
**Goal:** deeply analyze school infrastructure, road connectivity, and health indicators (IFA, Deworming) using natural language queries (e.g., "Show high risk blocks").
**Core capability:** You ask a question in plain English, and the system generates a Map, Data Table, and AI Summary.

---

## 2. Technology Stack (What we used)
- **Frontend:** Next.js (React) + Leaflet (Maps)
- **Backend:** Python FastAPI
- **AI/LLM:** Local Ollama (Model: `mistral:latest`) - *Runs 100% offline/locally*
- **Database:** PostgreSQL + PostGIS (Spatial Database)
- **Data Processing:** Python (Pandas, GeoPandas, SQLAlchemy)

---

## 3. How It Works (The Flow)
1. **User asks:** "Show schools without drinking water in West Garo Hills"
2. **Frontend** sends this text to the **Backend API**.
3. **Backend** passes the text to the **LLM Service** (`ollama_service.py`).
4. **LLM Brain** (Prompt Engineering):
   - Decides WHICH table to use (Schools vs Blocks vs Districts).
   - Converts English to SQL (e.g., `WHERE drinking_water = 'No'`).
5. **PostGIS Execution:**
   - The SQL runs against the database.
   - It returns real data (lat/long points, polygons, counts).
6. **Response:**
   - The Backend sends GeoJSON (for the map) + Analytics (for the summary) back to the Frontend.

---

## 4. The Database Strategy (How we built the data)
We don't just dump raw files. We built a custom **ETL Pipeline** (`scripts/rebuild_db.py`).

### The automated script does 3 things:
1. **Reads Raw Files:**
   - Shapefiles: Districts (`.shp`), Blocks (`.shp`), Schools (`.shp`)
   - Excel/CSV: `MDM_Infra_Report.csv` (Kitchen, Water), `MDM_Deworming.csv` (Health)
2. **Cleans & Merges:**
   - Fixes messy names (e.g., "  W. Garo Hills " -> "WEST GARO HILLS").
   - Merges CSV data into Shapefiles using `UDISE Code` or `Block Name`.
   - **Crucially:** Forces health numbers (like 25.5%) to be **Numeric** (Float), not Text.
3. **Creates "Intelligence" Tables:**
   - Instead of 10 disparate tables, we create 3 powerful "Final" tables.

### The 3 Core Tables (The `_final` Schema)
| Table Name | Type | content |
| :--- | :--- | :--- |
| `meghalaya_districts` | Polygon | Just the district boundaries. |
| `meghalaya_block_intelligence_final` | Polygon | **The Master Table.** Contains Block shapes + Road Density + Health Stats + School Counts. |
| `meghalaya_schools` | Point | Individual schools + Drinking Water + Toilets + Handwash status. |

*(We successfully deprecated the old `_raw` tables).*

---

## 5. The "Brain" Logic (LLM Rules)
We programmed specific logic into `backend/services/ollama_service.py` to handle complex queries.

### Special Logic We Added:
1. **"High Risk Blocks"**
   - **Rule:** If health coverage (IFA) is < 40% **OR** Road Density is < 0.2.
   - **SQL:** `SELECT * ... WHERE avg_ifa_coverage_girls < 40 OR road_density_km_per_sqkm < 0.2`
2. **"Low / Poor Performance"**
   - **Rule:** Always sort **Ascending** (ASC). The lowest number is the "worst".
   - **SQL:** `ORDER BY column ASC`
3. **"Road-School Gap"**
   - **Rule:** Selects both metrics so you can spot mismatched areas (Lots of schools but no roads).
4. **"Missing Handwash"**
   - **Rule:** Specifically checks `WHERE handwash = 'No'`.

---

## 6. How to Run It (For New Developers)

### Step 1: Start the Database & LLM
- Ensure PostgreSQL is running on port `5433`.
- Ensure Ollama is running (`ollama serve`).

### Step 2: Populate the Data (If anything is missing)
Run the magic rebuild script. This fixes missing columns or empty tables.
```bash
python scripts/rebuild_db.py
```

### Step 3: Start the Backend
```bash
uvicorn backend.main:app --reload
```
*API runs at: http://localhost:8000*

### Step 4: Start the Frontend
```bash
cd frontend
npm run dev
```
*App runs at: http://localhost:3000*

---

## 7. Troubleshooting History (What we fixed)
- **Problem:** "Read timed out" / 500 Error.
  - **Fix:** Fixed missing FastAPI boilerplate in `main.py`.
- **Problem:** "Schools with no water" showed 0 results.
  - **Fix:** Found that `MDM_Infra_Report.csv` was in a different folder (`infra/` vs `health/`). Corrected path in `rebuild_db.py`.
- **Problem:** "High Risk" query crashed.
  - **Fix:** Health columns were Text. Updated script to force `pd.to_numeric()`.
- **Problem:** Sorting was random.
  - **Fix:** Hardcoded `ORDER BY ASC/DESC` rules into the LLM system prompt.
