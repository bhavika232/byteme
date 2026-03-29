import math
import numpy as np
import pandas as pd
import json
import random
import requests
from datetime import datetime, timedelta
from sklearn.ensemble import IsolationForest


USE_AWS      = False
USE_S3       = False
USE_TEAMMATE = False
BUCKET_NAME  = "hackathon-bucket-ryan67"
AWS_REGION   = "us-east-2"
USD_TO_INR   = 83
TEAMMATE_URL = "http://localhost:8000/telemetry"


def generate_simulated_data(days=30):
    data = []
    base_cost = 320

    for i in range(days):
        date    = (datetime.today() - timedelta(days=days - i)).strftime("%Y-%m-%d")
        cpu     = random.uniform(20, 55)
        storage = random.uniform(40, 65)
        cost    = base_cost + random.uniform(-25, 25)

        if i in [8, 18, 25]:
            cpu     = random.uniform(88, 99)
            cost    = base_cost * random.uniform(2.8, 3.5)
            storage = random.uniform(85, 97)

        data.append({
            "date":    date,
            "cpu":     round(cpu, 1),
            "storage": round(storage, 1),
            "cost":    round(cost, 2)
        })

    return data


def get_teammate_data():
    try:
        print("🤝 Fetching data from teammate's backend...")
        response = requests.get(TEAMMATE_URL, timeout=5)
        data     = response.json()
        records  = data["records"]

        today = datetime.today()
        converted = []

        for i, r in enumerate(records):
            date   = (today - timedelta(days=len(records) - i)).strftime("%Y-%m-%d")
            cpu    = round(float(r.get("cpu", 0)) * 100, 1)
            memory = round(float(r.get("memory", 0)) * 100, 1)
            cost   = round((cpu / 100) * 500 * USD_TO_INR / 83, 2)
            cost   = max(cost, 50)

            converted.append({
                "date":    date,
                "cpu":     cpu,
                "storage": memory,
                "cost":    round(cost * USD_TO_INR / 100, 2)
            })

        print(f"✅ Got {len(converted)} records from teammate.")

        if len(converted) < 10:
            print("⚠️  Too few records, padding with simulated data...")
            simulated = generate_simulated_data(30 - len(converted))
            converted = simulated + converted

        return converted

    except Exception as e:
        print(f"⚠️  Teammate fetch failed: {e}")
        print("↩️  Falling back to simulated data.")
        return generate_simulated_data()


def convert_aws_record(record):
    ts = record.get("timestamp")
    if isinstance(ts, (int, float)):
        date = datetime.fromtimestamp(ts).strftime("%Y-%m-%d")
    elif isinstance(ts, str):
        try:
            date = datetime.fromisoformat(ts).strftime("%Y-%m-%d")
        except Exception:
            date = datetime.today().strftime("%Y-%m-%d")
    elif isinstance(ts, datetime):
        date = ts.strftime("%Y-%m-%d")
    else:
        date = datetime.today().strftime("%Y-%m-%d")

    cpu_raw = record.get("cpu") or record.get("usage") or 0
    cpu_raw = float(cpu_raw)
    cpu = cpu_raw * 100 if cpu_raw <= 1.0 else cpu_raw

    raw_cost = record.get("cost", 0) or 0
    if raw_cost == 0:
        raw_cost = (cpu / 100) * 5
    cost_inr = round(float(raw_cost) * USD_TO_INR, 2)

    storage = record.get("storage", round(random.uniform(40, 65), 1))

    return {
        "date":        date,
        "cpu":         round(cpu, 1),
        "storage":     round(float(storage), 1),
        "cost":        cost_inr,
        "instance_id": record.get("instance_id", ""),
        "state":       record.get("state", "unknown"),
    }


def get_aws_data(days=30):
    try:
        import boto3

        ce         = boto3.client("ce",         region_name=AWS_REGION)
        cloudwatch = boto3.client("cloudwatch", region_name=AWS_REGION)

        end   = datetime.today()
        start = end - timedelta(days=days)

        print("📡 Fetching cost data from AWS Cost Explorer...")
        cost_response = ce.get_cost_and_usage(
            TimePeriod={
                "Start": start.strftime("%Y-%m-%d"),
                "End":   end.strftime("%Y-%m-%d")
            },
            Granularity="DAILY",
            Metrics=["UnblendedCost"]
        )

        print("📡 Fetching CPU data from AWS CloudWatch...")
        cpu_response = cloudwatch.get_metric_statistics(
            Namespace="AWS/EC2",
            MetricName="CPUUtilization",
            Period=86400,
            StartTime=start,
            EndTime=end,
            Statistics=["Average"]
        )

        cpu_by_date = {}
        for point in cpu_response.get("Datapoints", []):
            date_key = point["Timestamp"].strftime("%Y-%m-%d")
            cpu_by_date[date_key] = round(point["Average"], 1)

        data = []
        for day in cost_response["ResultsByTime"]:
            date     = day["TimePeriod"]["Start"]
            cost_usd = float(day["Total"]["UnblendedCost"]["Amount"])
            raw_record = {
                "timestamp": datetime.strptime(date, "%Y-%m-%d").timestamp(),
                "usage":     cpu_by_date.get(date, random.uniform(20, 55)),
                "cpu":       cpu_by_date.get(date, 0),
                "cost":      cost_usd,
            }
            data.append(convert_aws_record(raw_record))

        print(f"✅ Pulled {len(data)} days of real AWS data.")
        return data

    except Exception as e:
        print(f"⚠️  AWS fetch failed: {e}")
        print("↩️  Falling back to simulated data.")
        return generate_simulated_data(days)


def load_from_live_feed(raw_records):
    today = datetime.today()
    converted = []

    for i, record in enumerate(raw_records):
        cpu_raw = record.get("cpu") or 0
        cpu = float(cpu_raw)  # CloudWatch already returns 0-100

        cost_usd = max((cpu / 100) * 5, 0.10)
        cost_inr = round(cost_usd * USD_TO_INR, 2)

        converted.append({
            "date":        today.strftime("%Y-%m-%d"),
            "instance_id": record.get("instance_id", f"i-unknown-{i}"),
            "state":       record.get("state", "unknown"),
            "cpu":         round(cpu, 1),
            "storage":     round(random.uniform(40, 65), 1),
            "cost":        cost_inr,
        })

    sim_days = max(30 - len(converted), 10)
    simulated = generate_simulated_data(sim_days)
    return simulated + converted


def detect_anomalies(data):
    df        = pd.DataFrame(data)
    features  = df[["cost", "cpu"]]
    mean_cost = df["cost"].mean()

    model         = IsolationForest(contamination=0.1, random_state=42)
    df["anomaly"] = model.fit_predict(features)

    results = []
    for _, row in df[df["anomaly"] == -1].iterrows():
        high_cost = row["cost"] > mean_cost * 1.5
        high_cpu  = row["cpu"] > 80

        if not (high_cost or high_cpu):
            continue

        if high_cost and high_cpu:
            severity, impact, score = "critical", "severe",   10
        elif high_cost:
            severity, impact, score = "critical", "high",      8
        else:
            severity, impact, score = "warning",  "moderate",  6

        results.append({
            "date":        row["date"],
            "instance_id": row.get("instance_id", ""),
            "cost":        row["cost"],
            "cpu":         row["cpu"],
            "severity":    severity,
            "impact":      impact,
            "score":       score,
            "explanation": (
                f"Cost spiked to ₹{row['cost']:.0f} with CPU at {row['cpu']:.0f}%. "
                f"This is {row['cost'] / mean_cost:.1f}× the daily average. "
                f"Impact classified as {impact}."
            )
        })

    return results


def generate_suggestions(data, anomalies):
    df          = pd.DataFrame(data)
    avg_cpu     = df["cpu"].mean()
    avg_storage = df["storage"].mean()
    suggestions = []

    if avg_cpu < 35:
        suggestions.append({
            "type":    "Idle EC2 Instance",
            "icon":    "💤",
            "message": f"Avg CPU is {avg_cpu:.1f}% — well below threshold. Downsize instance.",
            "action":  "t3.large → t3.small",
            "saving":  "₹3,800/month"
        })

    if avg_storage > 75:
        suggestions.append({
            "type":    "Cold Storage",
            "icon":    "🗄️",
            "message": f"Storage at {avg_storage:.1f}%. Move cold data to S3 Glacier.",
            "action":  "Enable S3 Intelligent-Tiering",
            "saving":  "₹2,200/month"
        })

    if len(anomalies) >= 2:
        suggestions.append({
            "type":    "Missing Billing Alert",
            "icon":    "🔔",
            "message": f"{len(anomalies)} spikes went undetected. Add CloudWatch billing alarms.",
            "action":  "Set ₹500/day alert threshold",
            "saving":  "Prevent future overruns"
        })

    suggestions.append({
        "type":    "Reserved Instances",
        "icon":    "📋",
        "message": "Stable baseline workload detected. Reserved Instances save on predictable usage.",
        "action":  "Commit to 1-year Reserved Instance",
        "saving":  "Up to 30%"
    })

    return suggestions


def forecast_costs(data, days_ahead=7):
    df               = pd.DataFrame(data)
    recent           = df.tail(10).reset_index(drop=True)
    x                = np.arange(len(recent))
    slope, intercept = np.polyfit(x, recent["cost"], 1)

    avg_cost  = df["cost"].mean()
    last_date = datetime.strptime(df["date"].iloc[-1], "%Y-%m-%d")
    forecast  = []

    for i in range(1, days_ahead + 1):
        projected = round(intercept + slope * (len(recent) + i), 2)
        optimized = round(projected * 0.70, 2)

        forecast.append({
            "date":      (last_date + timedelta(days=i)).strftime("%Y-%m-%d"),
            "projected": max(projected, 0),
            "optimized": max(optimized, 0),
            "risk":      "high" if projected > avg_cost * 1.5 else "normal"
        })

    return forecast


def upload_to_s3(filepath, bucket):
    try:
        import boto3
        s3 = boto3.client("s3", region_name=AWS_REGION)
        s3.upload_file(filepath, bucket, "data.json")
        print(f"☁️  Uploaded data.json to s3://{bucket}/data.json")
    except Exception as e:
        print(f"⚠️  S3 upload failed: {e}")


def sanitize(obj):
    """Recursively replace nan/inf with None so JSON serialization never crashes."""
    if isinstance(obj, float):
        if math.isnan(obj) or math.isinf(obj):
            return None
        return obj
    if isinstance(obj, dict):
        return {k: sanitize(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [sanitize(i) for i in obj]
    return obj


def run_analysis(raw_records=None, cpu_threshold=15.0):
    if raw_records:
        print("📥 Using live feed records...")
        data = load_from_live_feed(raw_records)
    elif USE_AWS:
        print("🔌 USE_AWS=True — connecting to AWS...")
        data = get_aws_data()
    elif USE_TEAMMATE:
        print("🤝 USE_TEAMMATE=True — pulling from teammate's backend...")
        data = get_teammate_data()
    else:
        print("🧪 Using simulated data...")
        data = generate_simulated_data()

    anomalies   = detect_anomalies(data)
    suggestions = generate_suggestions(data, anomalies)
    forecast    = forecast_costs(data)

    df      = pd.DataFrame(data)
    highest = max(data, key=lambda x: x["cost"])

    result = {
        "metrics":     data,
        "anomalies":   anomalies,
        "suggestions": suggestions,
        "forecast":    forecast,
        "summary": {
            "total_days":       len(data),
            "anomaly_count":    len(anomalies),
            "avg_cost":         round(df["cost"].mean(), 2),
            "total_cost":       round(df["cost"].sum(), 2),
            "potential_saving": round(df["cost"].sum() * 0.30, 2),
            "avg_cpu":          round(df["cpu"].mean(), 1),
            "idle_count": sum(1 for d in data if d["cpu"] < cpu_threshold),
            "highest_spike": {
                "date": highest["date"],
                "cost": highest["cost"]
            }
        }
    }

    with open("data.json", "w") as f:
        json.dump(result, f, indent=2)

    if USE_S3:
        upload_to_s3("data.json", BUCKET_NAME)

    source = "Live Feed" if raw_records else ("AWS" if USE_AWS else ("Teammate" if USE_TEAMMATE else "Simulated"))
    print(f"\n{'='*45}")
    print(f"  Anomalies found  : {len(anomalies)}")
    print(f"  Total cost       : ₹{result['summary']['total_cost']:,.2f}")
    print(f"  Potential saving : ₹{result['summary']['potential_saving']:,.2f}")
    print(f"  Idle instances   : {result['summary']['idle_count']}")
    print(f"  Highest spike    : ₹{highest['cost']} on {highest['date']}")
    print(f"  Data source      : {source}")
    print(f"{'='*45}\n")

    return sanitize(result)  # ← fixes "Out of range float values" JSON crash


if __name__ == "__main__":
    run_analysis()