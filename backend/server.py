from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv
load_dotenv()

from telemetry import collect_telemetry
from anomaly_detection import run_analysis   # ← correct module

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/telemetry")
def telemetry():
    data = collect_telemetry()
    return {"instances": data}

@app.get("/api/ec2-status")
def ec2_status():
    data = collect_telemetry()
    return {"instances": data}

@app.get("/api/analysis")
def analysis():
    raw_records = collect_telemetry()
    result = run_analysis(raw_records=raw_records)
    return result

@app.post("/api/trigger-anomaly")
def trigger_anomaly():
    return {"status": "triggered", "message": "Anomaly action executed"}