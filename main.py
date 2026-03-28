import time
from fetch_data import fetch_logs
from ec2_actions import stop_ec2, get_ec2_status
from logger import log_action
from anomaly_detection import run_analysis

def run_pipeline():
    print("Fetching data from S3...")
    raw_records = fetch_logs()
    print(f"Got {len(raw_records)} records")

    result = run_analysis(raw_records=raw_records)
    anomalies = result["anomalies"]

    if len(anomalies) > 0:
        top = max(anomalies, key=lambda x: x["score"])
        confidence = top["score"] / 10
        if confidence >= 0.7:
            print(f"Anomaly detected! Taking action...")
            stop_ec2()
            log_action(
                action=f"EC2 stopped — {top['explanation']}",
                confidence=confidence
            )
        else:
            print("Anomaly found but confidence too low, suppressing.")
    else:
        print("All normal.")

if __name__ == "__main__":
    while True:
        print("\n--- Running pipeline ---")
        run_pipeline()
        print("Waiting 60 seconds...")
        time.sleep(60)  # runs every 60 seconds
