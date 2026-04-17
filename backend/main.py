import time
import logging
import asyncio
from typing import List, Optional, Any
from dotenv import load_dotenv
load_dotenv() # Load env vars from .env file

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from backend.services.report_service import generate_pdf_report
from backend.services.email_service import send_pdf_email
from backend.services.ollama_service import get_sql_from_llm, get_summary_from_llm, get_heatmap_summary
from backend.services.spatial_service import (
    execute_spatial_query, get_drilldown_data, get_basemap, 
    get_nearest_facility, get_comparison_data, get_heatmap_data
)
from backend.services.cache_service import query_cache, basemap_cache
from fastapi.responses import StreamingResponse, JSONResponse, ORJSONResponse
import io

logger = logging.getLogger("geoai.api")
logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(name)s | %(message)s")

app = FastAPI(title="Meghalaya GeoAI API")

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Request timing middleware ──
@app.middleware("http")
async def timing_middleware(request: Request, call_next):
    t0 = time.time()
    response = await call_next(request)
    elapsed = time.time() - t0
    response.headers["X-Query-Time-Ms"] = str(round(elapsed * 1000))
    logger.info("HTTP %s %s | %dms", request.method, request.url.path, round(elapsed * 1000))
    return response


# ── Models ──
class QueryRequest(BaseModel):
    question: str

class SummaryRequest(BaseModel):
    question: str
    data: list

class ReportRequest(BaseModel):
    metric: str
    level: str = "district"
    data: list
    summary: Any = None

class EmailRequest(BaseModel):
    email: str
    report_data: ReportRequest


# ── Endpoints ──
@app.post("/query")
async def handle_query(request: QueryRequest):
    sql = ""
    # Retry mechanism for robustness against cold LLM or malformed SQL
    max_retries = 2
    last_error = None
    
    for attempt in range(max_retries):
        try:
            sql, level = await get_sql_from_llm(request.question)
            
            # Handle conversational/chat responses
            if level == "chat":
                return {
                    "type": "chat",
                    "message": sql.replace("-- CHAT: ", "").strip(),
                    "summary": sql.replace("-- CHAT: ", "").strip()
                }

            result = execute_spatial_query(sql, request.question)
            result["level"] = level
            result["summary"] = "Loading analysis..."
            result["sql"] = sql
            return result
        except Exception as e:
            last_error = e
            logger.warning(f"Query Attempt {attempt+1} failed: {str(e)}")
            # Small delay before retry
            if attempt < max_retries - 1:
                await asyncio.sleep(0.5)

    import traceback
    with open("backend_error.log", "a") as f:
        f.write(f"\n\nFINAL ERROR AFTER {max_retries} RETRIES:\n{str(last_error)}\n\nTRACE:\n")
        traceback.print_exc(file=f)
        f.write(f"\nSQL: {sql}\n")
    raise HTTPException(status_code=500, detail=f"Search failed after {max_retries} attempts: {repr(last_error)}")


@app.post("/query/summary")
async def handle_summary(request: SummaryRequest):
    try:
        summary = await get_summary_from_llm(request.question, request.data)
        return {"summary": summary}
    except Exception as e:
        import traceback
        with open("backend_error.log", "a") as f:
            f.write(f"\n\nSUMMARY ERROR:\n{str(e)}\n\nTRACE:\n")
            traceback.print_exc(file=f)
        return {"summary": "Analysis unavailable at this time."}


@app.get("/drilldown/{level}/{name}")
async def handle_drilldown(level: str, name: str):
    try:
        result = get_drilldown_data(level, name)
        if not result:
            raise HTTPException(status_code=404, detail="Data not found")
        return result
    except Exception as e:
        import traceback
        with open("backend_error.log", "a") as f:
            f.write(f"\n\nDRILLDOWN ERROR ({level}/{name}):\n{str(e)}\n\nTRACE:\n")
            traceback.print_exc(file=f)
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/basemap")
def handle_basemap(level: str = "district"):
    return get_basemap(level)


@app.get("/nearest/{facility}/{udise_code}")
async def handle_nearest_facility(facility: str, udise_code: str):
    try:
        data = get_nearest_facility(facility, udise_code)
        return {"data": data}
    except Exception as e:
        import traceback
        with open("backend_error.log", "a") as f:
            f.write(f"\n\nNEAREST ERROR ({facility}/{udise_code}):\n{str(e)}\n\nTRACE:\n")
            traceback.print_exc(file=f)
        logger.error(f"Nearest Facility Error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/compare/{level}/{name1}/{name2}")
async def handle_compare(level: str, name1: str, name2: str):
    try:
        data = get_comparison_data(level, name1, name2)
        return {"data": data}
    except Exception as e:
        logger.error(f"Comparison Error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/heatmap")
def handle_heatmap(metric: str = "priority_score", level: str = "block"):
    try:
        return get_heatmap_data(metric, level)
    except Exception as e:
        logger.error(f"Heatmap Data Error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/heatmap/summary")
async def handle_heatmap_summary(metric: str = "priority_score", level: str = "block"):
    try:
        # Heatmap summary needs some basic data stats
        data = get_heatmap_data(metric, level)
        # We only pass a sample or aggregated stats to LLM to avoid token limits
        sample_data = data.get("features", [])[:100]
        # Map to flat list for LLM
        flat_data = [f["properties"] for f in sample_data]
        summary = await get_heatmap_summary(metric, level, flat_data)
        return {"summary": summary}
    except Exception as e:
        logger.error(f"Heatmap Summary Error: {str(e)}")
        return {"summary": "Spatial density analysis unavailable."}



@app.post("/report")
async def handle_report(request: ReportRequest):
    try:
        pdf_buffer = generate_pdf_report(
            metric=request.metric,
            data=request.data,
            summary=request.summary
        )
        return StreamingResponse(
            pdf_buffer,
            media_type="application/pdf",
            headers={"Content-Disposition": f"attachment; filename=GeoAI_Report_{request.metric}.pdf"}
        )
    except Exception as e:
        import traceback
        with open("backend_error.log", "a") as f:
            f.write(f"\n\nREPORT ERROR:\n{str(e)}\n\nTRACE:\n")
            traceback.print_exc(file=f)
        logger.error(f"Report Error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/send-email")
async def handle_send_email(request: EmailRequest):
    try:
        pdf_buffer = generate_pdf_report(
            metric=request.report_data.metric,
            data=request.report_data.data,
            summary=request.report_data.summary
        )
        pdf_bytes = pdf_buffer.getvalue()
        
        subject = f"GeoAI Analysis Report: {request.report_data.metric.replace('_', ' ').title()}"
        body = f"Please find attached the latest GeoAI Analysis Report for {request.report_data.metric}."
        
        result = send_pdf_email(
            email_to=request.email,
            subject=subject,
            body=body,
            pdf_bytes=pdf_bytes,
            filename=f"GeoAI_Report_{request.report_data.metric}.pdf"
        )
        return result
    except Exception as e:
        import traceback
        with open("backend_error.log", "a") as f:
            f.write(f"\n\nEMAIL ERROR:\n{str(e)}\n\nTRACE:\n")
            traceback.print_exc(file=f)
        logger.error(f"Email Error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/cache/stats")
def cache_stats():
    return {
        "query_cache": query_cache.stats(),
        "basemap_cache": basemap_cache.stats(),
    }


@app.get("/health")
def health_check():
    return {"status": "ok"}
