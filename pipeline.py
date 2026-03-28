# add this to main.py
from fastapi import FastAPI
from dotenv import load_dotenv
from telemetry import collect_telemetry
from formatter import build_ml_payload
from sender import dispatch
from apscheduler.schedulers.background import BackgroundScheduler
import threading

load_dotenv()

app = FastAPI()
latest_payload = {}  # stores latest data in memory

def refresh_telemetry():
    global latest_payload
    print("[scheduler] Refreshing telemetry...")
    raw = collect_telemetry()
    latest_payload = build_ml_payload(raw)
    dispatch(latest_payload)
    print("[scheduler] Done.")

# run once immediately on startup
refresh_telemetry()

# then auto-refresh every 5 minutes
scheduler = BackgroundScheduler()
scheduler.add_job(refresh_telemetry, "interval", minutes=5)
scheduler.start()

@app.get("/")
def root():
    return {"status": "telemetry API is running"}

@app.get("/telemetry")
def get_telemetry():
    return latest_payload