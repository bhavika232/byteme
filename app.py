from flask import Flask, jsonify, send_from_directory
from flask_cors import CORS
from anomaly_detection import run_analysis
from ec2_actions import get_ec2_status, stop_ec2
from logger import log_action
import os

app = Flask(__name__, static_folder='static')
CORS(app)

@app.route('/')
def index():
    return send_from_directory('static', 'index.html')

@app.route('/telemetry')
def telemetry():
    return jsonify({"status": "ok", "message": "telemetry running"})

@app.route('/anomalies')
def anomalies():
    return jsonify({"anomalies": [], "status": "ok"})

@app.route('/api/analysis')
def get_analysis():
    result = run_analysis()
    return jsonify(result)

@app.route('/api/ec2-status')
def ec2_status():
    status = get_ec2_status()
    return jsonify({"status": status})

@app.route('/api/trigger-anomaly', methods=['POST'])
def trigger_anomaly():
    result = run_analysis()
    anomalies = result["anomalies"]
    if len(anomalies) > 0:
        top = max(anomalies, key=lambda x: x["score"])
        confidence = top["score"] / 10
        if confidence >= 0.7:
            stop_ec2()
            log_action(f"EC2 stopped — {top['explanation']}", confidence)
            return jsonify({"action": "EC2 stopped", "confidence": confidence, "anomaly": top})
    return jsonify({"action": "No anomaly detected"})

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)