from datetime import datetime, timezone
from typing import Any


REQUIRED_FIELDS = ["instance_id", "state"]


def validate_record(record: dict) -> bool:
    return all(field in record for field in REQUIRED_FIELDS)


def normalize_record(record: dict) -> dict | None:
    if not validate_record(record):
        return None

    return {
        "instance_id": str(record["instance_id"]),
        "state": str(record["state"]),
        "cpu": float(record["cpu"]) if record.get("cpu") is not None else 0.0,
        "memory": float(record.get("memory", 0.0)),
        "network_in": float(record.get("network_in", 0.0)),
        "network_out": float(record.get("network_out", 0.0)),
        "disk_read": float(record.get("disk_read", 0.0)),
        "disk_write": float(record.get("disk_write", 0.0)),
        "timestamp": record["timestamp"],
    }


def build_ml_payload(raw_records: list[dict]) -> dict:
    normalized = []
    skipped = 0

    for record in raw_records:
        cleaned = normalize_record(record)
        if cleaned:
            normalized.append(cleaned)
        else:
            skipped += 1

    return {
        "schema_version": "1.0",
        "collected_at": datetime.now(timezone.utc).isoformat(),
        "record_count": len(normalized),
        "skipped_count": skipped,
        "records": normalized,
    }