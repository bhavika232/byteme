from flask import Flask, request, jsonify
from model import predict

app = Flask(__name__)

@app.route("/telemetry", methods=["POST"])
def telemetry():
    data = request.get_json()
    print(f"Received: {data}")
    result = predict(data)
    print(f"Prediction: {result}")
    return jsonify({"status": "ok", "prediction": result, "data": data})

if __name__ == "__main__":
    app.run(port=5000)