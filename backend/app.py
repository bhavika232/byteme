from flask import Flask, jsonify, send_from_directory
from flask_cors import CORS
import boto3
import os
from dotenv import load_dotenv
from datetime import datetime, timedelta

load_dotenv()

app = Flask(__name__, static_folder='static')
CORS(app)  # Allow requests from file:// and any origin

# ── AWS clients ────────────────────────────────────────────
def get_clients():
    creds = {
        'aws_access_key_id':     os.getenv("AWS_ACCESS_KEY_ID"),
        'aws_secret_access_key': os.getenv("AWS_SECRET_ACCESS_KEY"),
        'region_name':           os.getenv("AWS_REGION", "us-east-1")
    }
    ec2        = boto3.client('ec2',        **creds)
    cloudwatch = boto3.client('cloudwatch', **creds)
    ce         = boto3.client('ce',
                     region_name='us-east-1',
                     aws_access_key_id=os.getenv("AWS_ACCESS_KEY_ID"),
                     aws_secret_access_key=os.getenv("AWS_SECRET_ACCESS_KEY"))
    return ec2, cloudwatch, ce

# ── Helpers ────────────────────────────────────────────────
def get_cpu(instance_id, cloudwatch):
    try:
        end   = datetime.utcnow()
        start = end - timedelta(hours=24)
        r = cloudwatch.get_metric_statistics(
            Namespace='AWS/EC2', MetricName='CPUUtilization',
            Dimensions=[{'Name': 'InstanceId', 'Value': instance_id}],
            StartTime=start, EndTime=end, Period=3600, Statistics=['Average']
        )
        pts = r.get('Datapoints', [])
        if not pts:
            return None
        return round(sum(d['Average'] for d in pts) / len(pts), 2)
    except:
        return None

def get_instances():
    ec2, cloudwatch, _ = get_clients()
    response  = ec2.describe_instances()
    instances = []
    for res in response['Reservations']:
        for inst in res['Instances']:
            name    = next((t['Value'] for t in inst.get('Tags', []) if t['Key'] == 'Name'), 'N/A')
            cpu_avg = get_cpu(inst['InstanceId'], cloudwatch)
            instances.append({
                'id':       inst['InstanceId'],
                'name':     name,
                'type':     inst['InstanceType'],
                'state':    inst['State']['Name'],
                'ip':       inst.get('PublicIpAddress', 'N/A'),
                'launched': str(inst['LaunchTime'])[:10],
                'cpu':      cpu_avg,
                'anomaly':  cpu_avg is not None and cpu_avg < 5.0
            })
    return instances

def get_cost_data():
    try:
        _, _, ce = get_clients()
        end   = datetime.utcnow().strftime('%Y-%m-%d')
        start = (datetime.utcnow() - timedelta(days=30)).strftime('%Y-%m-%d')
        r = ce.get_cost_and_usage(
            TimePeriod={'Start': start, 'End': end},
            Granularity='DAILY',
            Metrics=['UnblendedCost']
        )
        # Convert USD → INR (approximate rate)
        USD_TO_INR = 83.5
        return [
            {
                'date': d['TimePeriod']['Start'],
                'cost': round(float(d['Total']['UnblendedCost']['Amount']) * USD_TO_INR, 2)
            }
            for d in r['ResultsByTime']
        ]
    except Exception as e:
        print(f"Cost fetch error: {e}")
        return []

# ── Serve CloudOptim frontend ──────────────────────────────
@app.route('/')
def index():
    # Serve the SPA from project root so API + UI share origin
    return send_from_directory('.', 'code.html')

# ── /telemetry — EC2 instance records ─────────────────────
@app.route('/telemetry')
def telemetry():
    try:
        instances = get_instances()
        records   = [
            {
                'instance_id': inst['id'],
                'name':        inst['name'],
                'type':        inst['type'],
                'state':       inst['state'],
                'ip':          inst['ip'],
                'launched':    inst['launched'],
                'cpu':         inst['cpu'],
                'status':      'running' if inst['state'] == 'running' else 'stopped'
            }
            for inst in instances
        ]
        print(f"[telemetry] Returning {len(records)} records")
        return jsonify({'records': records, 'data_source': 'Live Feed'})
    except Exception as e:
        print(f"[telemetry] Error: {e}")
        return jsonify({'records': [], 'error': str(e)}), 500

# ── /api/anomalies — main dashboard data ──────────────────
@app.route('/api/anomalies')
def api_anomalies():
    try:
        instances = get_instances()
        cost_data = get_cost_data()

        # ── Cost calculations ──────────────────────────────
        total_cost_inr    = round(sum(d['cost'] for d in cost_data), 2) if cost_data else 0.0
        idle_instances    = [i for i in instances if i['anomaly']]
        idle_count        = len(idle_instances)

        # Potential saving: idle instances cost ~30% of total proportionally
        potential_saving  = round(total_cost_inr * 0.30, 2) if idle_count > 0 else 0.0

        # Highest spike from cost data
        highest_entry     = max(cost_data, key=lambda d: d['cost']) if cost_data else {}
        highest_spike     = highest_entry.get('cost', 0.0)
        highest_spike_date = highest_entry.get('date', '')

        # Avg CPU across all running instances
        cpu_values = [i['cpu'] for i in instances if i['cpu'] is not None]
        avg_cpu    = round(sum(cpu_values) / len(cpu_values), 2) if cpu_values else 0.0

        # ── Build anomaly list ─────────────────────────────
        anomalies = []
        for inst in idle_instances:
            # Estimate per-instance cost as equal share of total
            per_instance_cost = round(total_cost_inr / max(len(instances), 1), 2)
            anomalies.append({
                'instance_id': inst['id'],
                'date':        inst['launched'],
                'cpu':         inst['cpu'] or 0.0,
                'cost':        per_instance_cost,
                'score':       round(10 - (inst['cpu'] or 0) * 2, 1),  # lower CPU = higher anomaly score
                'severity':    'critical' if (inst['cpu'] or 0) < 2.0 else 'warning',
                'explanation': (
                    f"Instance {inst['id']} ({inst['name']}) has CPU at "
                    f"{inst['cpu']}% — below idle threshold. "
                    f"Potential saving by stopping: {inr(per_instance_cost)}/mo"
                )
            })

        # ── 7-day forecast (from cost_data tail) ──────────
        forecast = []
        if cost_data:
            recent = cost_data[-7:] if len(cost_data) >= 7 else cost_data
            for day in recent:
                forecast.append({
                    'date':      day['date'],
                    'projected': day['cost'],
                    'risk':      'high' if day['cost'] > (total_cost_inr / max(len(cost_data), 1)) * 1.3 else 'normal'
                })

        result = {
            'anomalies_found':    len(anomalies),
            'total_cost':         total_cost_inr,
            'potential_saving':   potential_saving,
            'idle_instances':     idle_count,
            'highest_spike':      highest_spike,
            'highest_spike_date': highest_spike_date,
            'avg_cpu':            avg_cpu,
            'data_source':        'Live Feed',
            'anomalies':          anomalies,
            'forecast':           forecast,
            'records':            [
                {
                    'instance_id': i['id'],
                    'state':       i['state'],
                    'cpu':         i['cpu']
                } for i in instances
            ]
        }

        # ── Terminal-style print (matches what you see) ────
        print("=" * 44)
        print(f"  Anomalies found  : {len(anomalies)}")
        print(f"  Total cost       : ₹{total_cost_inr:,.2f}")
        print(f"  Potential saving : ₹{potential_saving:,.2f}")
        print(f"  Idle instances   : {idle_count}")
        print(f"  Highest spike    : ₹{highest_spike} on {highest_spike_date}")
        print(f"  Data source      : Live Feed")
        print("=" * 44)

        return jsonify(result)

    except Exception as e:
        print(f"[api/anomalies] Error: {e}")
        return jsonify({'error': str(e), 'anomalies_found': 0}), 500

# ── /api/instances — legacy route (kept for compatibility) ─
@app.route('/api/instances')
def api_instances():
    try:
        instances = get_instances()
        cost_data = get_cost_data()
        total_cost = round(sum(d['cost'] for d in cost_data), 2) if cost_data else None
        return jsonify({'instances': instances, 'total_cost': total_cost, 'cost_trend': cost_data})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# ── /api/trigger-anomaly — called by Refresh button ───────
@app.route('/api/trigger-anomaly', methods=['POST'])
def trigger_anomaly():
    print("[trigger-anomaly] Manual refresh triggered from dashboard")
    return jsonify({'status': 'ok', 'message': 'Anomaly detection triggered'})

# ── Helpers ────────────────────────────────────────────────
def inr(n):
    return f"₹{float(n):,.2f}"

if __name__ == '__main__':
    print("=" * 44)
    print("  CloudOptim Backend Starting")
    print("  Dashboard → http://localhost:5000")
    print("  Ngrok     → https://angelia-unaccustomed-daniele.ngrok-free.dev")
    print("=" * 44)
    app.run(debug=True, port=5000)
