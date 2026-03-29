import boto3
import json
from datetime import datetime

s3 = boto3.client('s3')

test_data = {
    "schema_version": "1.0",
    "records": [
        {
            "instance_id": "i-0c46dfa3a28a086d0",
            "state": "stopped",
            "cpu": 0,
            "timestamp": datetime.now().isoformat()
        }
    ]
}

s3.put_object(
    Bucket='hackathon-bucket-ryan67',
    Key=f'telemetry/test_{datetime.now().timestamp()}.json',
    Body=json.dumps(test_data)
)

print("Test file uploaded — check your email!")