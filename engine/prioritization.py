import pandas as pd, os
from pymongo import MongoClient

MONGO_URI = os.getenv("MONGODB_URI")
client = MongoClient(MONGO_URI)
db = client["infoguard"]

analysis = db["analysis"]
anomalies = db["anomalies"]
revisions = db["revisions"] 

def load_recent_risk(window=20):
    docs = list(analysis.find().sort("created_at", -1).limit(500))
    for d in docs:
        d.pop("_id", None)

    df = pd.DataFrame(docs)
    df["created_at"] = pd.to_datetime(df["created_at"])

    return df

def compute_priority():
    df = load_recent_risk()

    if df.empty:
        return pd.DataFrame()

    risk_by_page = df.groupby("page")["final_risk"].mean()

    edit_volume = df.groupby("page").size()

    anomaly_pages = set(anomalies.distinct("page"))

    rows = []

    for page in risk_by_page.index:
        rows.append({
            "page": page,
            "avg_risk": risk_by_page[page],
            "edit_volume": edit_volume[page],
            "anomaly_boost": 1 if page in anomaly_pages else 0
        })

    dfp = pd.DataFrame(rows)

    dfp["priority_score"] = (
        0.5 * dfp["avg_risk"] +
        0.3 * dfp["anomaly_boost"] +
        0.2 * (dfp["edit_volume"] / dfp["edit_volume"].max())
    )

    return dfp.sort_values("priority_score", ascending=False)

