import os
import random
from datetime import datetime, timezone, timedelta
from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from apscheduler.schedulers.background import BackgroundScheduler
from telemetry import collect_telemetry
from formatter import build_ml_payload
from sender import dispatch

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

def refresh_telemetry():
    global latest_payload, latest_records
    print("[scheduler] Refreshing telemetry...")
    raw = collect_telemetry()
    latest_payload = build_ml_payload(raw)
    latest_records = latest_payload.get("records", [])
    dispatch(latest_payload)
    print("[scheduler] Done.")

refresh_telemetry()

scheduler = BackgroundScheduler()
scheduler.add_job(refresh_telemetry, "interval", minutes=5)
scheduler.start()


@app.get("/")
def root():
    return {"status": "telemetry API is running"}


@app.get("/telemetry")
def get_telemetry():
    return latest_payload


@app.get("/api/ec2-status")
def ec2_status():
    if not latest_records:
        return {"status": "unknown"}
    state = latest_records[0].get("state", "unknown")
    return {"status": state}


@app.get("/api/analysis")
def get_analysis():
    records = latest_records

    # anomalies = instances with cpu below threshold
    anomalies = []
    total_cost = 0.0
    potential_saving = 0.0

    for record in records:
        cpu = record.get("cpu", 0.0)
        state = record.get("state", "stopped")
        instance_id = record.get("instance_id", "unknown")
        cost = round(random.uniform(50, 300), 2)  # estimated cost
        total_cost += cost

        if cpu < 5.0 or state == "stopped":
            saving = round(cost * 0.8, 2)
            potential_saving += saving
            anomalies.append({
                "instance_id": instance_id,
                "cpu": cpu,
                "state": state,
                "explanation": f"Instance {instance_id} has critically low CPU ({cpu}%)",
                "severity": "critical" if cpu == 0 else "warning",
                "estimated_saving": saving
            })

    # 7 day forecast
    today = datetime.now(timezone.utc)
    forecast = []
    for i in range(7):
        day = today + timedelta(days=i)
        projected = round(total_cost * random.uniform(0.9, 1.1), 2)
        optimized = round(projected * 0.7, 2)
        forecast.append({
            "date": day.strftime("%a"),
            "projected": projected,
            "optimized": optimized
        })

    return {
        "summary": {
            "idle_count": len(anomalies),
            "total_cost": round(total_cost, 2),
            "potential_saving": round(potential_saving, 2),
            "anomaly_count": len(anomalies)
        },
        "anomalies": anomalies,
        "forecast": forecast
    }


@app.post("/api/trigger-anomaly")
def trigger_anomaly():
    refresh_telemetry()
    return {"status": "triggered", "message": "Telemetry refreshed and anomaly detection run"}