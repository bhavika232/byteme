# main.py — THE ONLY APP TO RUN
import os
from dotenv import load_dotenv
from fastapi import FastAPI, Query, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse

from telemetry import collect_telemetry
from formatter import build_ml_payload
from sender import dispatch
from anomaly_detection import run_analysis
from ec2_actions import downsize_instance, get_ec2_status
from apscheduler.schedulers.background import BackgroundScheduler

load_dotenv()

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

latest_payload = {}
latest_records = []

# Track ongoing optimization so UI can poll status
optimization_status = {"running": False, "result": None}

def refresh_telemetry():
    global latest_payload, latest_records
    print("[scheduler] Refreshing telemetry...")
    raw            = collect_telemetry()
    latest_payload = build_ml_payload(raw)
    latest_records = latest_payload.get("records", [])
    dispatch(latest_payload)
    print("[scheduler] Done.")

refresh_telemetry()

scheduler = BackgroundScheduler()
scheduler.add_job(refresh_telemetry, "interval", minutes=5)
scheduler.start()

# ── Serve frontend ─────────────────────────────────────────
@app.get("/", response_class=HTMLResponse)
def serve_frontend():
    with open("code.html", "r", encoding="utf-8") as f:
        content = f.read()
    return HTMLResponse(content=content, headers={"Cache-Control": "no-store"})

# ── Telemetry ──────────────────────────────────────────────
@app.get("/telemetry")
def get_telemetry():
    return latest_payload

# ── EC2 status ─────────────────────────────────────────────
@app.get("/api/ec2-status")
def ec2_status():
    if not latest_records:
        return {"status": "unknown"}
    state = latest_records[0].get("state", "unknown")
    return {"status": state}

# ── Analysis with optional threshold param ─────────────────
# Frontend sends ?threshold=15 — backend uses it to calculate idle_count
@app.get("/api/analysis")
def get_analysis(threshold: float = Query(default=15.0, ge=0, le=100)):
    return run_analysis(
        raw_records=latest_records if latest_records else None,
        cpu_threshold=threshold
    )

# ── Anomalies ──────────────────────────────────────────────
@app.get("/api/anomalies")
def get_anomalies(threshold: float = Query(default=15.0, ge=0, le=100)):
    result = run_analysis(
        raw_records=latest_records if latest_records else None,
        cpu_threshold=threshold
    )
    return {
        "status":    "anomaly" if result["anomalies"] else "normal",
        "anomalies": result["anomalies"],
        "summary":   result["summary"]
    }

# ── Optimize — downsize EC2 instance ──────────────────────
def _run_optimization():
    global optimization_status
    optimization_status["running"] = True
    optimization_status["result"]  = None
    try:
        result = downsize_instance()
        optimization_status["result"] = result
        # Refresh telemetry after optimization
        refresh_telemetry()
    except Exception as e:
        optimization_status["result"] = {"success": False, "message": str(e)}
    finally:
        optimization_status["running"] = False

@app.post("/api/optimize")
async def optimize(background_tasks: BackgroundTasks):
    if optimization_status["running"]:
        return JSONResponse(
            status_code=409,
            content={"message": "Optimization already in progress. Please wait."}
        )
    background_tasks.add_task(_run_optimization)
    return {"message": "Optimization started. Downsizing EC2 instance...", "status": "started"}

@app.get("/api/optimize/status")
def optimize_status():
    return optimization_status

# ── Manual refresh trigger ─────────────────────────────────
@app.post("/api/trigger-anomaly")
def trigger_anomaly():
    refresh_telemetry()
    return {"status": "triggered", "message": "Telemetry refreshed"}

if __name__ == "__main__":
    import uvicorn
    print("=" * 44)
    print("  CloudOptim Backend Starting")
    print("  Dashboard → http://localhost:8000")
    print("=" * 44)
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)