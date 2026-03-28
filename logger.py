import boto3
import json
from datetime import datetime

BUCKET = "hackathon-bucket-ryan67"
s3 = boto3.client('s3')

def log_action(action, confidence):
    log = {
        "timestamp": str(datetime.now()),
        "action": action,
        "confidence": round(confidence, 2),
        "status": "executed"
    }
    s3.put_object(
        Bucket=BUCKET,
        Key=f'action-logs/{datetime.now().timestamp()}.json',
        Body=json.dumps(log)
    )
    print(f"Logged: {action} with confidence {confidence}")

