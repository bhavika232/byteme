# ☁️ CloudOptim — Cloud Cost Intelligence System

> Built at **Manipal Institute of Technology Bengaluru Hackathon** in 36 hours by a 4-person team.

---

## 🚀 What is CloudOptim?

CloudOptim is a **real-time autonomous cloud cost intelligence system** that monitors live AWS resources, detects cost anomalies using Machine Learning, and automatically remediates wasteful usage — all without human intervention.

> "It doesn't just alert you about waste. It fixes it."

---

## 🎯 Problem Statement

Companies running cloud infrastructure waste thousands of dollars monthly on:
- Idle EC2 instances left running after testing
- Lambda functions with runaway invocations
- Unmonitored storage and database costs

Manual monitoring is impossible at scale. CloudOptim solves this autonomously.

---

## ⚙️ How It Works

```
AWS Resources (EC2, Lambda, S3)
        ↓
Telemetry Pipeline (boto3 + CloudWatch)
        ↓
Data stored in S3 bucket
        ↓
Isolation Forest ML detects anomalies
        ↓
Confidence threshold check (≥ 0.7)
        ↓
Auto-remediation via AWS API (stop EC2)
        ↓
SNS email alert sent to team
        ↓
Live dashboard on Vercel
```

---

## 🧱 Architecture

| Layer | Technology |
|---|---|
| Cloud Infrastructure | AWS EC2, Lambda, S3, RDS |
| Telemetry Collection | boto3, AWS CloudWatch |
| Data Pipeline | AWS Lambda → S3 (EventBridge every 1 min) |
| Anomaly Detection | Isolation Forest (scikit-learn) |
| Auto-Remediation | boto3 EC2 API |
| Alerting | AWS SNS (email notifications) |
| Backend API | Flask (hosted on EC2) |
| Frontend | HTML/CSS/TailwindCSS (deployed on Vercel) |

---

## 🤖 ML Model

- **Algorithm:** Isolation Forest
- **Features:** CPU utilization, cost per day
- **Contamination:** 10% (flags top 10% as anomalies)
- **Confidence threshold:** 0.7 (suppresses false alerts)
- **Severity levels:** Critical (score 8-10), Warning (score 6)

---

## 🔁 Automated Remediation

When an anomaly is detected with confidence ≥ 0.7:
1. EC2 instance is automatically stopped via AWS API
2. Action is logged to S3 with timestamp and confidence score
3. SNS email alert is sent with full anomaly details
4. Dashboard updates to reflect new EC2 status

---

## 📊 Dashboard Features

- **Live EC2 instance table** with CPU and cost status
- **Cost overview chart** — actual vs optimized
- **7-day cost forecast** using linear extrapolation
- **Anomaly detection feed** with severity badges
- **Real-time savings tracker**
- **Risk assessment panel**
- **Auto-refresh every 30 seconds**

---

## 🛠️ Setup

### Prerequisites
```bash
pip install flask flask-cors boto3 pandas numpy scikit-learn requests
```

### AWS Setup
1. Create AWS free tier account
2. Launch EC2 (t3.micro), Lambda, S3 bucket, RDS
3. Create IAM user with EC2FullAccess + S3ReadOnly + SNSFullAccess
4. Set up EventBridge to trigger Lambda every minute
5. Configure S3 trigger → Lambda for anomaly detection

### Run Locally
```bash
python app.py
```

### Deploy Backend on EC2
```bash
ssh -i hackathon-key.pem ec2-user@YOUR-EC2-IP
python3 app.py
```

---

## 📡 API Endpoints

| Method | Endpoint | Description |
|---|---|---|
| GET | `/api/analysis` | Full ML analysis, anomalies, forecast, suggestions |
| GET | `/api/ec2-status` | Current EC2 instance state |
| POST | `/api/trigger-anomaly` | Trigger live detection + auto-remediation |

---

## 👥 Team

| Member | Role |
|---|---|
| Ryan | AWS Infrastructure + Flask Backend |
| Bhavika | Telemetry Pipeline + Frontend |
| Sashia | ML Model (Isolation Forest) |
| Shreya | Frontend Design |

---

## 🏫 Hackathon

**Event:** Manipal Institute of Technology Bengaluru Hackathon
**Duration:** 36 hours
**Problem Statement:** PS2 — Cloud Cost Intelligence System

---

## 📄 License

MIT License — feel free to build on this!
