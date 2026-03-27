# Geospatial Infrastructure LLM Model

This project builds a geospatial intelligence system that integrates
PostGIS, infrastructure datasets, and Large Language Models (LLMs)
to enable natural-language querying of infrastructure conditions.

## Features
- PostGIS-based spatial database
- Block-level infrastructure intelligence
- Road connectivity analysis using OpenStreetMap
- School availability analysis
- Natural Language → GeoSQL querying
- TerraMind-compatible LLM architecture
- Streamlit-based UI

## Architecture
- **Frontend**: Next.js (React) + Leaflet.js
- **Backend**: FastAPI (Python)
- **Database**: PostGIS (PostgreSQL)
- **Intelligence**: LLM (mistral via Ollama)

## Core Table
`hp_block_infra_intelligence`

## How to Run

### 1. Prerequisites
- Python 3.9+
- Node.js 18+
- Ollama (running mistral)
- PostgreSQL with PostGIS

### 2. Run Backend
Open a terminal, activate the virtual environment from the root directory, and start the backend server:

```bash
# On Windows
venv\Scripts\activate
# On Linux/macOS
source venv/bin/activate

# Start the FastAPI server
uvicorn backend.main:app --reload --port 8000
```

### 3. Run Frontend
Open a **new terminal**, navigate to the `frontend` directory, and start the frontend server:

```bash
cd frontend
npm run dev
```
The app will be available at `http://localhost:3000`.
