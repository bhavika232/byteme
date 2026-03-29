import time
import threading

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from fetch_data import fetch_logs
from ec2_actions import stop_ec2, get_ec2_status
from logger import log_action
from anomaly_detection import run_analysis

app = FastAPI()

# ✅ CORS (VERY IMPORTANT)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Shared data storage (acts like memory cache)
latest_records = []
latest_anomalies = []

# ─────────────────────────────────────────────
# PIPELINE (runs in background)
# ─────────────────────────────────────────────
def run_pipeline():
    global latest_records, latest_anomalies

    print("Fetching data from S3...")
    raw_records = fetch_logs()
    latest_records = raw_records

    print(f"Got {len(raw_records)} records")

    result = run_analysis(raw_records=raw_records)
    anomalies = result["anomalies"]
    latest_anomalies = anomalies

    if len(anomalies) > 0:
        top = max(anomalies, key=lambda x: x["score"])
        confidence = top["score"] / 10

        if confidence >= 0.7:
            print("Anomaly detected! Taking action...")
            stop_ec2()

            log_action(
                action=f"EC2 stopped — {top['explanation']}",
                confidence=confidence
            )
        else:
            print("Anomaly found but confidence too low.")
    else:
        print("All normal.")


def start_pipeline_loop():
    while True:
        print("\n--- Running pipeline ---")
        run_pipeline()
        print("Waiting 60 seconds...")
        time.sleep(60)


# Run pipeline in background thread
@app.on_event("startup")
def start_background_tasks():
    thread = threading.Thread(target=start_pipeline_loop)
    thread.daemon = True
    thread.start()


# ─────────────────────────────────────────────
# API ENDPOINTS (frontend will call these)
# ─────────────────────────────────────────────

@app.get("/telemetry")
def get_telemetry():
    return {
        "records": latest_records
    }


@app.get("/api/anomalies")
def get_anomalies():
    return {
        "anomalies": latest_anomalies
    }


@app.get("/api/ec2-status")
def ec2_status():
    return get_ec2_status()