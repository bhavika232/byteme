import requests
import random
import time

URL = "http://localhost:5000/telemetry"

while True:
    payload = {
        "temperature": round(random.uniform(60, 100), 2),
        "pressure":    round(random.uniform(100, 130), 2),
        "vibration":   round(random.uniform(0.1, 1.0), 3),
        "timestamp":   time.time()
    }
    try:
        response = requests.post(URL, json=payload, timeout=3)
        print(response.json())
    except Exception as e:
        print(f"Error: {e}")
    time.sleep(1)