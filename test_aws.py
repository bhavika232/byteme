print("HELLO - FILE IS RUNNING")
 
import boto3
import os
from dotenv import load_dotenv
 
load_dotenv()
 
region = os.getenv("AWS_REGION", "us-east-1")
print(f"Region loaded: {region}")
 
ec2 = boto3.client(
    'ec2',
    aws_access_key_id=os.getenv("AWS_ACCESS_KEY_ID"),
    aws_secret_access_key=os.getenv("AWS_SECRET_ACCESS_KEY"),
    region_name=region
)
 
response = ec2.describe_instances()
 
print("Connected to AWS successfully")
print(response)
