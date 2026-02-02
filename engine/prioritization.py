import pandas as pd
from pymongo import MongoClient
import os

MONGO_URI = os.getenv("MONGODB_URI")
client = MongoClient(MONGO_URI)
db = client["infoguard"]

analysis = db["analysis"]
anomalies = db["anomalies"]

def compute_priority():
    docs = list(analysis.find())

    cleaned = []
    for d in docs:
        if "page" in d and "final_risk" in d:
            cleaned.append(d)

    if not cleaned:
        return pd.DataFrame()

    df = pd.DataFrame(cleaned)

    if "flagged" not in df.columns:
        df["flagged"] = False

    df["created_at"] = pd.to_datetime(df.get("created_at", pd.Timestamp.utcnow()))

    grouped = df.groupby("page")

    features = grouped.agg(
        avg_risk=("final_risk", "mean"),
        max_risk=("final_risk", "max"),
        edit_volume=("final_risk", "count"),
        flag_rate=("flagged", "mean")
    ).reset_index()

    anomaly_counts = pd.DataFrame(
        anomalies.aggregate([
            {"$group": {"_id": "$page", "count": {"$sum": 1}}}
        ])
    )

    if not anomaly_counts.empty:
        anomaly_counts.columns = ["page", "anomaly_count"]
        features = features.merge(anomaly_counts, on="page", how="left")
    else:
        features["anomaly_count"] = 0

    features["anomaly_count"] = features["anomaly_count"].fillna(0)

    # normalize volume
    features["edit_velocity"] = features["edit_volume"] / features["edit_volume"].max()

    # intelligent weighted score
    features["priority_score"] = (
        0.35 * features["avg_risk"] +
        0.25 * features["max_risk"] +
        0.2 * features["flag_rate"] +
        0.1 * features["anomaly_count"] +
        0.1 * features["edit_velocity"]
    )

    return features.sort_values("priority_score", ascending=False)
