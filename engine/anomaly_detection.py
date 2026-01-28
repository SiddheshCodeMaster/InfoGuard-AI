import pandas as pd, os
from pymongo import MongoClient

MONGO_URI = os.getenv("MONGODB_URI")
client = MongoClient(MONGO_URI)
db = client["infoguard"]

analysis = db["analysis"]
runs = db["runs"]
anomalies = db["anomalies"]

def load_runs_df(limit=200):
    docs = list(runs.find().sort("timestamp", 1).limit(limit))
    for d in docs:
        d.pop("_id", None)
    df = pd.DataFrame(docs)
    df["timestamp"] = pd.to_datetime(df["timestamp"])
    return df

def load_risk_df(limit=300):
    docs = list(analysis.find().sort("created_at", 1).limit(limit))
    for d in docs:
        d.pop("_id", None)
    df = pd.DataFrame(docs)
    df["created_at"] = pd.to_datetime(df["created_at"])
    return df

def detect_volume_anomalies(df, window = 10, threshold = 2):
    df["rolling_mean"] = df["changes_detected"].rolling(window).mean()
    df["rolling_std"] = df["changes_detected"].rolling(window).std()

    df['z_score'] = (
        (df["changes_detected"] - df["rolling_mean"])/ df["rolling_std"]
    )

    df["is_anomaly"] = df["z_score"].abs() > threshold

    return df

def detect_risk_anomalies(df, window = 10, threshold = 2):
    df["risk_mean"] = df["flagged"].rolling(window).mean()
    df["risk_std"] = df["flagged"].rolling(window).std()
    
    df["risk_z"] = (df["flagged"] - df["risk_mean"]) / df["risk_std"]
    df["risk_anomaly"] = df["risk_z"].abs() > threshold

    return df

def detect_risk_spikes(df, window = 10, threshold = 2):
    df["rolling_risk_mean"] = df["final_risk"].rolling(window).mean()
    df["rolling_risk_std"] = df["final_risk"].rolling(window).std()

    df["risk_z"] = (
        (df["final_risk"] - df["rolling_risk_mean"]) / df["rolling_risk_std"]
    )

    df["risk_anomaly"] = df["risk_z"].abs() > threshold

    return df

def store_risk_anomalies(df):
    spikes = df[df["risk_anomaly"] == True]

    for _, row in spikes.iterrows():
        anomalies.update_one(
            {
                "timestamp": row["created_at"],
                "page": row["page"]
            },
            {"$set": {
                "final_risk": row["final_risk"],
                "risk_z": row["risk_z"],
                "detected_at": pd.Timestamp.utcnow()
            }},
            upsert=True
        )