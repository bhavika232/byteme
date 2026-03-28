from flask import Flask, render_template_string, jsonify
import boto3
import os
from dotenv import load_dotenv
from datetime import datetime, timedelta
 
load_dotenv()
 
app = Flask(__name__)
 
def get_clients():
    creds = {
        'aws_access_key_id': os.getenv("AWS_ACCESS_KEY_ID"),
        'aws_secret_access_key': os.getenv("AWS_SECRET_ACCESS_KEY"),
        'region_name': os.getenv("AWS_REGION", "us-east-1")
    }
    ec2 = boto3.client('ec2', **creds)
    cloudwatch = boto3.client('cloudwatch', **creds)
    ce = boto3.client('ce', region_name='us-east-1',
                      aws_access_key_id=os.getenv("AWS_ACCESS_KEY_ID"),
                      aws_secret_access_key=os.getenv("AWS_SECRET_ACCESS_KEY"))
    return ec2, cloudwatch, ce
 
def get_instances():
    ec2, cloudwatch, _ = get_clients()
    response = ec2.describe_instances()
    instances = []
    for res in response['Reservations']:
        for inst in res['Instances']:
            name = next((t['Value'] for t in inst.get('Tags', []) if t['Key'] == 'Name'), 'N/A')
            cpu_avg = get_cpu(inst['InstanceId'], cloudwatch)
            instances.append({
                'id': inst['InstanceId'],
                'name': name,
                'type': inst['InstanceType'],
                'state': inst['State']['Name'],
                'ip': inst.get('PublicIpAddress', 'N/A'),
                'launched': str(inst['LaunchTime'])[:10],
                'cpu': cpu_avg,
                'anomaly': cpu_avg is not None and cpu_avg < 5.0
            })
    return instances
 
def get_cpu(instance_id, cloudwatch):
    try:
        end = datetime.utcnow()
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
 
def get_cost():
    try:
        _, _, ce = get_clients()
        end = datetime.utcnow().strftime('%Y-%m-%d')
        start = (datetime.utcnow() - timedelta(days=30)).strftime('%Y-%m-%d')
        r = ce.get_cost_and_usage(
            TimePeriod={'Start': start, 'End': end},
            Granularity='DAILY',
            Metrics=['UnblendedCost']
        )
        return [
            {'date': d['TimePeriod']['Start'],
             'cost': float(d['Total']['UnblendedCost']['Amount'])}
            for d in r['ResultsByTime']
        ]
    except Exception as e:
        return []
 
DASHBOARD_HTML = """
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1.0"/>
<title>Cloud Cost Intelligence</title>
<link href="https://fonts.googleapis.com/css2?family=Space+Mono:wght@400;700&family=DM+Sans:wght@300;400;600&display=swap" rel="stylesheet"/>
<style>
  :root {
    --bg: #0a0e1a;
    --card: #111827;
    --border: #1e293b;
    --accent: #00e5ff;
    --warn: #ff6b35;
    --ok: #00e676;
    --text: #e2e8f0;
    --muted: #64748b;
  }
  * { margin:0; padding:0; box-sizing:border-box; }
  body { background:var(--bg); color:var(--text); font-family:'DM Sans',sans-serif; min-height:100vh; }
  header { padding:2rem 2.5rem 1rem; border-bottom:1px solid var(--border); display:flex; justify-content:space-between; align-items:center; }
  header h1 { font-family:'Space Mono',monospace; font-size:1.2rem; color:var(--accent); letter-spacing:0.05em; }
  header span { font-size:0.8rem; color:var(--muted); font-family:'Space Mono',monospace; }
  .grid { display:grid; grid-template-columns:repeat(auto-fit,minmax(200px,1fr)); gap:1rem; padding:2rem 2.5rem 1rem; }
  .stat-card { background:var(--card); border:1px solid var(--border); border-radius:12px; padding:1.5rem; }
  .stat-card .label { font-size:0.75rem; color:var(--muted); text-transform:uppercase; letter-spacing:0.1em; margin-bottom:0.5rem; }
  .stat-card .value { font-family:'Space Mono',monospace; font-size:2rem; font-weight:700; }
  .stat-card .value.accent { color:var(--accent); }
  .stat-card .value.warn { color:var(--warn); }
  .stat-card .value.ok { color:var(--ok); }
  section { padding:1rem 2.5rem 2rem; }
  section h2 { font-family:'Space Mono',monospace; font-size:0.85rem; color:var(--muted); text-transform:uppercase; letter-spacing:0.1em; margin-bottom:1rem; }
  table { width:100%; border-collapse:collapse; background:var(--card); border-radius:12px; overflow:hidden; border:1px solid var(--border); }
  th { text-align:left; padding:0.9rem 1rem; font-size:0.75rem; color:var(--muted); text-transform:uppercase; letter-spacing:0.08em; border-bottom:1px solid var(--border); }
  td { padding:0.85rem 1rem; font-size:0.88rem; border-bottom:1px solid var(--border); }
  tr:last-child td { border-bottom:none; }
  .badge { display:inline-block; padding:0.2rem 0.6rem; border-radius:999px; font-size:0.72rem; font-weight:600; }
  .badge.running { background:#00e67622; color:var(--ok); border:1px solid #00e67644; }
  .badge.stopped { background:#64748b22; color:var(--muted); border:1px solid #64748b44; }
  .badge.anomaly { background:#ff6b3522; color:var(--warn); border:1px solid #ff6b3544; }
  .cpu-bar { background:#1e293b; border-radius:4px; height:6px; width:100px; overflow:hidden; }
  .cpu-fill { height:100%; border-radius:4px; transition:width 0.5s; }
  .refresh-btn { background:transparent; border:1px solid var(--accent); color:var(--accent); padding:0.5rem 1rem; border-radius:8px; cursor:pointer; font-family:'Space Mono',monospace; font-size:0.8rem; }
  .refresh-btn:hover { background:var(--accent); color:var(--bg); }
  .no-data { color:var(--muted); font-size:0.85rem; padding:2rem; text-align:center; }
</style>
</head>
<body>
<header>
  <h1>⚡ CLOUD COST INTELLIGENCE</h1>
  <div style="display:flex;align-items:center;gap:1rem;">
    <span id="last-updated">Loading...</span>
    <button class="refresh-btn" onclick="loadData()">↻ REFRESH</button>
  </div>
</header>
 
<div class="grid" id="stats-grid">
  <div class="stat-card"><div class="label">Total Instances</div><div class="value accent" id="stat-total">—</div></div>
  <div class="stat-card"><div class="label">Running</div><div class="value ok" id="stat-running">—</div></div>
  <div class="stat-card"><div class="label">Idle / Anomalies</div><div class="value warn" id="stat-idle">—</div></div>
  <div class="stat-card"><div class="label">Est. Monthly Cost</div><div class="value accent" id="stat-cost">—</div></div>
</div>
 
<section>
  <h2>EC2 Instances</h2>
  <table>
    <thead>
      <tr><th>Instance ID</th><th>Name</th><th>Type</th><th>State</th><th>CPU (24h avg)</th><th>Status</th><th>Launched</th></tr>
    </thead>
    <tbody id="instance-table"><tr><td colspan="7" class="no-data">Loading instances...</td></tr></tbody>
  </table>
</section>
 
<script>
async function loadData() {
  document.getElementById('last-updated').textContent = 'Refreshing...';
  try {
    const res = await fetch('/api/instances');
    const data = await res.json();
    renderInstances(data.instances);
    updateStats(data.instances, data.total_cost);
    document.getElementById('last-updated').textContent = 'Updated: ' + new Date().toLocaleTimeString();
  } catch(e) {
    document.getElementById('last-updated').textContent = 'Error loading data';
  }
}
 
function renderInstances(instances) {
  const tbody = document.getElementById('instance-table');
  if (!instances.length) {
    tbody.innerHTML = '<tr><td colspan="7" class="no-data">No instances found</td></tr>';
    return;
  }
  tbody.innerHTML = instances.map(inst => {
    const cpu = inst.cpu !== null ? inst.cpu : null;
    const cpuDisplay = cpu !== null
      ? `<div style="display:flex;align-items:center;gap:8px;">
           <div class="cpu-bar"><div class="cpu-fill" style="width:${Math.min(cpu,100)}%;background:${cpu<5?'#ff6b35':cpu<50?'#00e5ff':'#00e676'}"></div></div>
           <span style="font-family:'Space Mono',monospace;font-size:0.8rem;">${cpu}%</span>
         </div>`
      : '<span style="color:#64748b;font-size:0.8rem;">N/A</span>';
    const stateClass = inst.state === 'running' ? 'running' : 'stopped';
    const anomalyBadge = inst.anomaly
      ? '<span class="badge anomaly">⚠ IDLE</span>'
      : inst.state === 'running' ? '<span class="badge running">✓ OK</span>' : '<span class="badge stopped">Stopped</span>';
    return `<tr>
      <td style="font-family:'Space Mono',monospace;font-size:0.8rem;">${inst.id}</td>
      <td>${inst.name}</td>
      <td style="font-family:'Space Mono',monospace;font-size:0.8rem;">${inst.type}</td>
      <td><span class="badge ${stateClass}">${inst.state}</span></td>
      <td>${cpuDisplay}</td>
      <td>${anomalyBadge}</td>
      <td style="color:#64748b;font-size:0.82rem;">${inst.launched}</td>
    </tr>`;
  }).join('');
}
 
function updateStats(instances, totalCost) {
  document.getElementById('stat-total').textContent = instances.length;
  document.getElementById('stat-running').textContent = instances.filter(i => i.state === 'running').length;
  document.getElementById('stat-idle').textContent = instances.filter(i => i.anomaly).length;
  document.getElementById('stat-cost').textContent = totalCost ? '$' + totalCost : 'N/A';
}
 
loadData();
setInterval(loadData, 60000);
</script>
</body>
</html>
"""
 
@app.route('/')
def dashboard():
    return render_template_string(DASHBOARD_HTML)
 
@app.route('/api/instances')
def api_instances():
    instances = get_instances()
    cost_data = get_cost()
    total_cost = round(sum(d['cost'] for d in cost_data), 2) if cost_data else None
    return jsonify({'instances': instances, 'total_cost': total_cost, 'cost_trend': cost_data})
 
if __name__ == '__main__':
    print("Starting Cloud Cost Intelligence Dashboard on http://localhost:5000")
    app.run(debug=True, port=5000)