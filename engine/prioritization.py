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

    if not docs:
        return pd.DataFrame()

    cleaned = []
    for d in docs:
        d.pop("_id", None)

        if "page" in d and "final_risk" in d:
            cleaned.append(d)

    if not cleaned:
        return pd.DataFrame()

    df = pd.DataFrame(cleaned)

    if "created_at" not in df.columns:
        df["created_at"] = pd.Timestamp.utcnow()

    df["created_at"] = pd.to_datetime(df["created_at"], errors="coerce")

    risk_by_page = df.groupby("page")["final_risk"].mean()
    edit_volume = df.groupby("page").size()

    anomaly_pages = set(anomalies.distinct("page"))

    rows = []
    for page in risk_by_page.index:
        rows.append({
            "page": page,
            "avg_risk": float(risk_by_page[page]),
            "edit_volume": int(edit_volume[page]),
            "anomaly_boost": 1 if page in anomaly_pages else 0
        })

    dfp = pd.DataFrame(rows)

    dfp["priority_score"] = (
        0.5 * dfp["avg_risk"] +
        0.3 * dfp["anomaly_boost"] +
        0.2 * (dfp["edit_volume"] / dfp["edit_volume"].max())
    )

    return dfp.sort_values("priority_score", ascending=False)
