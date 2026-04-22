# Meghalaya GeoAI Infrastructure Platform

This project is a comprehensive geospatial intelligence system that integrates a PostGIS spatial database, administrative infrastructure datasets, and Large Language Models (LLMs) to enable natural-language querying of geospatial infrastructure data.

## 🏗️ Architecture & Tech Stack
- **Frontend**: Next.js (React) + Leaflet.js
- **Backend**: FastAPI (Python)
- **Database**: PostGIS (PostgreSQL)
- **AI Intelligence**: LLM (Mistral via Ollama)
- **Local Tunnels**: ngrok (for bridging local backend to cloud frontend)

## 📁 Repository Structure
- `/backend/` - FastAPI web server, database schemas, and LLM NLQ routes.
- `/frontend/` - Next.js React application for the user interface.
- `/scripts/` - Python utilities for data loading, syncing, error checking, and schema verification.
- `/data/` - Raw structural datasets (CSV, XLSX) containing infrastructure intelligence.

---

## 🚀 Getting Started (Initial Setup)

### 1. Prerequisites
Before you begin, ensure you have the following installed on your machine:
- **Python 3.9+**
- **Node.js 18+**
- **PostgreSQL** with the **PostGIS** extension enabled
- **Ollama** (Running the Mistral model: `ollama run mistral`)
- **ngrok** (Required if testing with a deployed Vercel frontend)

### 2. Environment Variables (.env)
You must set up your local environment variables before running the application. **Never commit this file to version control.**
1. Copy `.env.example` in the root folder and rename the copy to `.env`.
2. Open your new `.env` file and update the configuration strings:
   - `DB_URL` (Use your local Postgres credentials, formatted as: `postgresql://user:password@localhost:5432/db_name`)
   - Update SMTP details (if email reporting functionality is needed)
   - Ensure the Ollama URL is correct (usually `http://localhost:11434`)

---

## 🏃‍♂️ How to Run the Application

To run the full stack locally, you will need **3 separate terminal windows**.

### Terminal 1: The Backend (FastAPI)
1. Open a terminal in the root directory of the project.
2. Initialize and activate a Python Virtual Environment:
   ```bash
   # On Windows
   python -m venv venv
   venv\Scripts\activate
   
   # On macOS/Linux
   python3 -m venv venv
   source venv/bin/activate
   ```
3. Install the required backend dependencies:
   ```bash
   pip install -r requirements.txt
   ```
4. Start the backend server:
   ```bash
   uvicorn backend.main:app --reload --port 8000
   ```
   *The backend is now live at `http://localhost:8000`*.

### Terminal 2: Exposing the Backend (ngrok)
If you are testing your local backend against the **deployed frontend on Vercel** (or exposing it externally), you must expose your local port 8000 to the secure internet.

1. Open a second terminal.
2. Run ngrok to tunnel to your backend port:
   ```bash
   ngrok http 8000
   ```
3. Copy the **Forwarding URL** provided by ngrok (it will look like `https://<random-id>.ngrok-free.app`).
4. **Vercel Hookup**: Go to your deployed project's settings on Vercel. Navigate to Environment Variables, update the API backend URL variable (like `NEXT_PUBLIC_API_URL` or standard backend config) to this ngrok URL, and redeploy.

### Terminal 3: The Frontend (Next.js)
If you prefer to run the User Interface fully locally rather than using the Vercel deployed version:

1. Open a third terminal.
2. Navigate into the frontend folder:
   ```bash
   cd frontend
   ```
3. Install frontend Node.js packages:
   ```bash
   npm install
   ```
4. Start the React development frontend:
   ```bash
   npm run dev
   ```
   *The Local UI is now live at `http://localhost:3000`*.
