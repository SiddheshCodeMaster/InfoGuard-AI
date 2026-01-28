import pandas as pd, os
from pymongo import MongoClient

MONGO_URI = os.getenv("MONGODB_URI")
client = MongoClient(MONGO_URI)
db = client["infoguard"]

runs = db["runs"]

def load_runs_df(limit=200):
    docs = list(runs.find().sort("timestamp", 1).limit(limit))
    for d in docs:
        d.pop("_id", None)
    df = pd.DataFrame(docs)
    df["timestamp"] = pd.to_datetime(df["timestamp"])
    return df

def detect_volume_anomalies(df, window = 10, threshold = 2):
    df["rolling_mean"] = df["changes_detected"].rolling(window).mean()
    df["rolling_std"] = df["changes_detected"].rolling(window).std()

    df['z_score'] = (
        (df["changes_detected"] - df["rolling_mean"])/ df["rolling_std"]
    )

    df["is_anomaly"] = df["z_score"].abs() > threshold

    return df

if __name__ == "__main__":
    df = load_runs_df()
    df = detect_volume_anomalies(df)

    print(df[["timestamp", "changes_detected", "z_score", "is_anomaly"]].tail(10))