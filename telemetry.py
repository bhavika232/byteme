
import os
import boto3
from datetime import datetime, timezone, timedelta
from typing import Any
from dotenv import load_dotenv

load_dotenv()  # Loads .env before any boto3 calls


def get_aws_clients() -> tuple[Any, Any]:
    session = boto3.Session(
        aws_access_key_id=os.environ["AWS_ACCESS_KEY_ID"],
        aws_secret_access_key=os.environ["AWS_SECRET_ACCESS_KEY"],
        region_name=os.environ.get("AWS_REGION", "us-east-1"),
    )
    ec2 = session.client("ec2")
    cloudwatch = session.client("cloudwatch")
    return ec2, cloudwatch


def fetch_ec2_instances(ec2_client: Any) -> list[dict]:
    instances = []
    paginator = ec2_client.get_paginator("describe_instances")
    for page in paginator.paginate():
        for reservation in page["Reservations"]:
            for instance in reservation["Instances"]:
                instances.append({
                    "instance_id": instance["InstanceId"],
                    "state": instance["State"]["Name"],
                })
    return instances


def fetch_cpu_utilization(cloudwatch_client: Any, instance_id: str) -> float | None:
    end_time = datetime.now(timezone.utc)
    start_time = end_time - timedelta(minutes=10)

    response = cloudwatch_client.get_metric_statistics(
        Namespace="AWS/EC2",
        MetricName="CPUUtilization",
        Dimensions=[{"Name": "InstanceId", "Value": instance_id}],
        StartTime=start_time,
        EndTime=end_time,
        Period=600,
        Statistics=["Average"],
    )

    datapoints = response.get("Datapoints", [])
    if not datapoints:
        return None

    latest = sorted(datapoints, key=lambda x: x["Timestamp"])[-1]
    return round(latest["Average"], 4)


def collect_telemetry() -> list[dict]:
    ec2_client, cloudwatch_client = get_aws_clients()
    instances = fetch_ec2_instances(ec2_client)
    telemetry = []
    timestamp = datetime.now(timezone.utc).isoformat()

    for instance in instances:
        instance_id = instance["instance_id"]
        state = instance["state"]
        cpu = None

        if state == "running":
            cpu = fetch_cpu_utilization(cloudwatch_client, instance_id)

        telemetry.append({
            "instance_id": instance_id,
            "state": state,
            "cpu": cpu,
            "timestamp": timestamp,
        })

    return telemetry


if __name__ == "__main__":
    import json
    data = collect_telemetry()
    print(json.dumps(data, indent=2))
