import streamlit as st
import pandas as pd, os
from pymongo import MongoClient
import plotly.express as px

st.set_page_config(page_title="InfoGuard AI Dashboard", layout="wide")

MONGO_URI = os.getenv("MONGODB_URI")

client = MongoClient(MONGO_URI)
db = client["infoguard"]

runs = db["runs"]
analysis = db["analysis"]
anomalies = db["anomalies"]

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
    col1, col2, col3, col4 = st.columns(4)

    col1.metric("Pages Checked", int(df_runs.iloc[0]["pages_checked"]))
    col2.metric("Changes Detected", int(df_runs.iloc[0]["changes_detected"]))
    col3.metric("Flagged Edits", int(df_runs.iloc[0]["flagged"]))
    col4.metric("Duration (s)", round(df_runs.iloc[0]["duration_seconds"], 2))

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