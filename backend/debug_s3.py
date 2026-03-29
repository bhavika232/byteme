import boto3
import json

BUCKET = "hackathon-bucket-ryan67"
s3 = boto3.client('s3')

print("Connecting to S3...")
response = s3.list_objects_v2(Bucket=BUCKET, Prefix='logs/')
print(f"Found {len(response.get('Contents', []))} files")

# Just read first 3 files
for obj in response['Contents'][:3]:
    key = obj['Key']
    print(f"Reading: {key}")
    file = s3.get_object(Bucket=BUCKET, Key=key)
    content = json.loads(file['Body'].read())
    print(f"Content: {content}")