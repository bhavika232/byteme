def predict(telemetry):
    if (telemetry["temperature"] > 85 or
        telemetry["pressure"] > 120 or
        telemetry["vibration"] > 0.75):
        return "anomaly"
    return "normal"