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

df_priority = compute_priority()

def load_anomalies():
    docs = list(anomalies.find().sort("timestamp", -1))
    for d in docs:
        d.pop("_id", None)
    return pd.DataFrame(docs)

def load_runs():
    docs = list(runs.find().sort("timestamp", -1).limit(100))
    if not docs:
        return pd.DataFrame()

    for d in docs:
        d.pop("_id", None)   # removed Mongo ObjectId

    df = pd.DataFrame(docs)
    df["timestamp"] = pd.to_datetime(df["timestamp"])
    return df

df_runs = load_runs()

df_anom = load_anomalies()

st.dataframe(df_runs)

if not df_runs.empty:
    fig = px.line(
        df_runs.sort_values("timestamp"),
        x="timestamp",
        y="pages_checked",
        title="Pages Checked Over Time"
    )
    st.plotly_chart(fig, use_container_width=True)

    fig2 = px.line(
        df_runs.sort_values("timestamp"),
        x="timestamp",
        y="flagged",
        title="Flagged Edits Over Time"
    )
    st.plotly_chart(fig2, use_container_width=True)

def load_flagged():
    docs = list(
        analysis.find({"flagged": True})
        .sort("created_at", -1)
        .limit(20)
    )
    for d in docs:
        d.pop("_id", None)
    return pd.DataFrame(docs)

df_flagged = load_flagged()

st.subheader("🚨 Recent Flagged Edits")
if df_flagged.empty:
    st.info("No flagged edits yet")
else:
    st.dataframe(df_flagged[["page", "username", "final_risk", "semantic_similarity"]])

st.title("InfoGuard AI Monitoring Dashboard")

if df_runs.empty:
    st.warning("No run data yet")
else:
    col1, col2, col3, col4, col5 = st.columns(5)

    col1.metric("Pages Scanned (Last Run)", int(df_runs.iloc[0]["pages_checked"]))
    col2.metric("Edits Detected (Last Run)", int(df_runs.iloc[0]["changes_detected"]))
    col3.metric("Flagged Edits (Last Run)", int(df_runs.iloc[0]["flagged"]))
    total_flagged = analysis.count_documents({"flagged": True})
    col4.metric("Total Flagged Edits (All Time)", total_flagged)
    col5.metric("Run Duration (seconds)", round(df_runs.iloc[0]["duration_seconds"], 2))


st.subheader("⚠ Risk Anomalies")

if df_anom.empty:
    st.info("No anomalies detected yet")
else:
    st.dataframe(df_anom[["timestamp", "page", "final_risk", "risk_z"]])

    fig3 = px.scatter(
        df_anom,
        x="timestamp",
        y="final_risk",
        color="risk_z",
        title="Risk Spike Anomalies"
    )
    st.plotly_chart(fig3, use_container_width=True)

st.subheader("🔥 Top Priority Pages")

if df_priority.empty:
    st.info("No priority data yet")
else:
    st.dataframe(
        df_priority[["page", "avg_risk", "edit_volume", "anomaly_boost", "priority_score"]]
        .head(10)
    )

if not df_priority.empty:
    fig_priority = px.bar(
        df_priority.head(10),
        x="priority_score",
        y="page",
        orientation="h",
        title="Top 10 Risk Priority Pages"
    )
    st.plotly_chart(fig_priority, use_container_width=True)
