import boto3
import json
from datetime import datetime
import time

s3 = boto3.client('s3')
BUCKET = "hackathon-bucket-ryan67"

spikes = [
    {"usage": 95, "cpu": 95, "cost": 50.0, "invocations": 500},
    {"usage": 92, "cpu": 92, "cost": 48.0, "invocations": 480},
    {"usage": 98, "cpu": 98, "cost": 55.0, "invocations": 600},
    {"usage": 90, "cpu": 90, "cost": 45.0, "invocations": 450},
    {"usage": 97, "cpu": 97, "cost": 52.0, "invocations": 550},
]

for spike in spikes:
    spike["timestamp"] = datetime.now().timestamp()
    s3.put_object(
        Bucket=BUCKET,
        Key=f'logs/spike_{datetime.now().timestamp()}.json',
        Body=json.dumps(spike)
    )
    time.sleep(0.1)

print("5 spikes injected!")
