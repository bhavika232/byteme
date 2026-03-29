import json
import os
import boto3
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

ML_ENDPOINT = os.environ.get("ML_ENDPOINT")          # teammate's REST API URL
S3_BUCKET   = os.environ.get("S3_BUCKET")            # fallback: S3 bucket name
S3_KEY_PREFIX = os.environ.get("S3_KEY_PREFIX", "telemetry/")


def send_to_ml_api(payload: dict) -> bool:
    """POST payload to ML teammate's REST endpoint."""
    try:
        import requests
        response = requests.post(
            ML_ENDPOINT,
            json=payload,
            headers={"Content-Type": "application/json"},
            timeout=10,
        )
        response.raise_for_status()
        print(f"[sender] ML API accepted {payload['record_count']} records.")
        return True
    except Exception as e:
        print(f"[sender] ML API failed: {e}")
        return False


def send_to_s3(payload: dict) -> bool:
    """Fallback: write payload as JSON to S3 for ML to poll."""
    try:
        s3 = boto3.client(
            "s3",
            aws_access_key_id=os.environ["AWS_ACCESS_KEY_ID"],
            aws_secret_access_key=os.environ["AWS_SECRET_ACCESS_KEY"],
            region_name=os.environ.get("AWS_REGION", "us-east-2"),
        )
        key = f"{S3_KEY_PREFIX}{payload['collected_at'].replace(':', '-')}.json"
        s3.put_object(
            Bucket=S3_BUCKET,
            Key=key,
            Body=json.dumps(payload),
            ContentType="application/json",
        )
        print(f"[sender] Written to s3://{S3_BUCKET}/{key}")
        return True
    except Exception as e:
        print(f"[sender] S3 upload failed: {e}")
        return False


def send_to_file(payload: dict, path: str = "telemetry_output.json") -> bool:
    """Local fallback for development / offline testing."""
    try:
        Path(path).write_text(json.dumps(payload, indent=2))
        print(f"[sender] Written to {path}")
        return True
    except Exception as e:
        print(f"[sender] File write failed: {e}")
        return False


def dispatch(payload: dict) -> None:
    """Try ML API → S3 → local file, in order."""
    if ML_ENDPOINT and send_to_ml_api(payload):
        return
    if S3_BUCKET and send_to_s3(payload):
        return
    send_to_file(payload)