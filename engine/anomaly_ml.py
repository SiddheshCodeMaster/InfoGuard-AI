import pandas as pd, os
from pymongo import MongoClient
from sklearn.ensemble import IsolationForest

MONGO_URI = os.getenv("MONGODB_URI")
client = MongoClient(MONGO_URI)

db = client["infoguard"]

analysis = db["analysis"]
ml_anomalies = db["ml_anomalies"]

def load_features():
    docs = list(analysis.find())

    cleaned = []
    for d in docs:
        if "final_risk" in d and "semantic_similarity" in d:
            cleaned.append({
                "page": d["page"],
                "final_risk": d["final_risk"],
                "semantic_similarity": d["semantic_Similarity"]
            })
    
    return pd.DataFrame(cleaned)

def run_ml_anomaly_detection():
    df = load_features()

    if df.empty or len(df) < 10:
        return

    X = df[["final_risk", "semantic_similarity"]]

    model = IsolationForest(
        n_estimators=150,
        contamination=0.05,
        random_state=42
    )

    preds = model.fit_predict(X)

    df["is_anomaly"] = preds == -1

    ml_anomalies.delete_many({})

    for _, row in df[df["is_anomaly"]].iterrows():
        ml_anomalies.insert_one({
            "page": row["page"],
            "final_risk": float(row["final_risk"]),
            "semantic_similarity": float(row["semantic_similarity"])
        })