import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT_DIR))

import streamlit as st
import pandas as pd
import os
from pymongo import MongoClient
import plotly.express as px

from engine.prioritization import compute_priority

st.set_page_config(page_title="InfoGuard AI Dashboard", layout="wide")

MONGO_URI = os.getenv("MONGODB_URI")
client = MongoClient(MONGO_URI)
db = client["infoguard"]

runs = db["runs"]
analysis = db["analysis"]
anomalies = db["anomalies"]

# ---------------- SAFE LOADERS ---------------- #

def safe_df(docs):
    if not docs:
        return pd.DataFrame()
    for d in docs:
        d.pop("_id", None)
    return pd.DataFrame(docs)

def load_runs():
    return safe_df(list(runs.find().sort("timestamp", -1).limit(100)))

def load_anomalies():
    return safe_df(list(anomalies.find().sort("timestamp", -1)))

def load_analysis():
    docs = list(analysis.find())
    cleaned = [d for d in docs if "page" in d and "final_risk" in d]
    return safe_df(cleaned)

# ---------------- LOAD DATA ---------------- #

df_runs = load_runs()
df_anom = load_anomalies()
df_analysis = load_analysis()
df_priority = compute_priority()

# ---------------- DASHBOARD ---------------- #

st.title("InfoGuard AI Monitoring Dashboard")

if not df_runs.empty:
    df_runs["timestamp"] = pd.to_datetime(df_runs["timestamp"])

    col1, col2, col3, col4, col5 = st.columns(5)
    col1.metric("Pages Scanned (Last Run)", int(df_runs.iloc[0]["pages_checked"]))
    col2.metric("Edits Detected (Last Run)", int(df_runs.iloc[0]["changes_detected"]))
    col3.metric("Flagged Edits (Last Run)", int(df_runs.iloc[0]["flagged"]))
    col4.metric("Total Flagged Edits", analysis.count_documents({"flagged": True}))
    col5.metric("Run Duration (s)", round(df_runs.iloc[0]["duration_seconds"], 2))

    st.plotly_chart(px.line(df_runs.sort_values("timestamp"),
                            x="timestamp", y="pages_checked",
                            title="Pages Checked Over Time"), use_container_width=True)

    st.plotly_chart(px.line(df_runs.sort_values("timestamp"),
                            x="timestamp", y="flagged",
                            title="Flagged Edits Over Time"), use_container_width=True)

# ---------------- RISK ANALYTICS ---------------- #

if not df_analysis.empty:
    st.subheader("📊 Risk Distribution")
    st.plotly_chart(px.histogram(df_analysis, x="final_risk", nbins=20),
                    use_container_width=True)

    df_analysis["created_at"] = pd.to_datetime(df_analysis.get("created_at", pd.Timestamp.utcnow()))

    st.subheader("📈 Risk Trend")
    st.plotly_chart(px.line(df_analysis.sort_values("created_at"),
                            x="created_at", y="final_risk"),
                    use_container_width=True)

    st.subheader("🔥 Most Active Pages")
    page_counts = df_analysis["page"].value_counts().head(10).reset_index()
    page_counts.columns = ["page", "edit_count"]

    st.plotly_chart(px.bar(page_counts, x="edit_count", y="page", orientation="h"),
                    use_container_width=True)

# ---------------- PRIORITY ---------------- #

st.subheader("🚨 Top Priority Pages")

if df_priority.empty:
    st.info("No priority data yet")
else:
    st.dataframe(df_priority.head(10))
    st.plotly_chart(
        px.bar(df_priority.head(10),
               x="priority_score",
               y="page",
               orientation="h"),
        use_container_width=True
    )
