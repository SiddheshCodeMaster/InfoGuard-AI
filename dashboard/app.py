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

# ---------------- CONFIGURATION ---------------- #

st.set_page_config(page_title="InfoGuard AI Dashboard", layout="wide")
px.defaults.template = "plotly_white"

MONGO_URI = os.getenv("MONGODB_URI")
client = MongoClient(MONGO_URI)
db = client["infoguard"]

runs = db["runs"]
analysis = db["analysis"]
anomalies = db["anomalies"]

# ---------------- DATA LOADERS ---------------- #

def safe_df(docs):
    if not docs:
        return pd.DataFrame()
    for d in docs:
        d.pop("_id", None)
    return pd.DataFrame(docs)

def load_runs():
    df = safe_df(list(runs.find().sort("timestamp", 1)))
    if not df.empty:
        df["timestamp"] = pd.to_datetime(df["timestamp"])
    return df

def load_analysis():
    df = safe_df(list(analysis.find()))
    if not df.empty:
        df["created_at"] = pd.to_datetime(df["created_at"])
    return df

def load_anomalies():
    df = safe_df(list(anomalies.find()))
    if not df.empty:
        df["timestamp"] = pd.to_datetime(df["timestamp"])
    return df

def load_topics():
    docs = list(db["topics"].find())
    for d in docs:
        d.pop("_id", None)
    return pd.DataFrame(docs)

# ---------------- LOAD ---------------- #

df_runs = load_runs()
df_analysis = load_analysis()
df_anom = load_anomalies()
df_priority = compute_priority()
df_topics = load_topics()

# ---------------- DASHBOARD ---------------- #

st.title("🛡 InfoGuard AI — Wikipedia Risk Monitoring System")

# ===== RUN METRICS ===== #

if not df_runs.empty:

    latest = df_runs.iloc[-1]

    col1, col2, col3, col4, col5 = st.columns(5)
    col1.metric("Pages Scanned (Last Run)", int(latest["pages_checked"]))
    col2.metric("Edits Detected", int(latest["changes_detected"]))
    col3.metric("Flagged Edits", int(latest["flagged"]))
    col4.metric("Total Flagged (All Time)", analysis.count_documents({"flagged": True}))
    col5.metric("Run Duration (sec)", round(latest["duration_seconds"], 2))

    st.markdown("### 📊 Monitoring Activity Over Time")
    st.caption("How many pages the system scans and how many suspicious edits are detected per run.")

    fig_pages = px.line(
        df_runs,
        x="timestamp",
        y="pages_checked",
        title="Pages Scanned Per Monitoring Run",
        labels={"timestamp": "Time", "pages_checked": "Pages Scanned"}
    )
    st.plotly_chart(fig_pages, use_container_width=True)

    fig_flagged = px.bar(
        df_runs,
        x="timestamp",
        y="flagged",
        title="Suspicious Edits Detected Per Run",
        labels={"timestamp": "Time", "flagged": "Flagged Edits"}
    )
    st.plotly_chart(fig_flagged, use_container_width=True)

# ===== RISK ANALYTICS ===== #

if not df_analysis.empty:

    st.markdown("### 📊 Risk Score Distribution")
    st.caption("Shows how risky Wikipedia edits typically are (0 = safe, 1 = high risk).")

    fig_dist = px.histogram(
        df_analysis,
        x="final_risk",
        nbins=25,
        labels={"final_risk": "Risk Score"},
        title="Distribution of Edit Risk Levels"
    )
    fig_dist.update_layout(xaxis=dict(range=[0,1]))
    st.plotly_chart(fig_dist, use_container_width=True)

    # ---- Aggregate risk by day (cleaner trend) ---- #

    df_daily = (
        df_analysis
        .set_index("created_at")
        .resample("1H")
        .mean(numeric_only=True)
        .reset_index()
    )

    st.markdown("### 📈 Risk Trend With Anomaly Detection")
    st.caption("Average edit risk over time. Red dots highlight abnormal spikes detected by AI.")

    fig_trend = px.line(
        df_daily,
        x="created_at",
        y="final_risk",
        labels={"created_at": "Time", "final_risk": "Average Risk"},
        title="Risk Evolution Over Time"
    )

    if not df_anom.empty:
        fig_trend.add_scatter(
            x=df_anom["timestamp"],
            y=df_anom["final_risk"],
            mode="markers",
            marker=dict(color="red", size=10),
            name="Anomalies"
        )

    fig_trend.update_layout(yaxis=dict(range=[0,1]))
    st.plotly_chart(fig_trend, use_container_width=True)

    # ---- Activity ---- #

    st.markdown("### 🔥 Most Actively Edited Pages")
    st.caption("Pages that receive the highest number of edits (higher exposure to manipulation).")

    page_counts = (
        df_analysis["page"]
        .value_counts()
        .head(10)
        .reset_index()
    )
    page_counts.columns = ["Page", "Edit Count"]

    fig_activity = px.bar(
        page_counts,
        x="Edit Count",
        y="Page",
        orientation="h",
        title="Top Edited Wikipedia Pages"
    )
    st.plotly_chart(fig_activity, use_container_width=True)

# ===== PRIORITIZATION ===== #

st.markdown("### 🚨 Intelligent Risk Prioritization")
st.caption("AI-ranked pages combining historical risk, anomalies, and edit activity.")

if df_priority.empty or "priority_score" not in df_priority.columns:
    st.info("Not enough data yet to compute intelligent priorities.")
else:
    df_top = df_priority.sort_values("priority_score", ascending=False).head(10)
    df_top = df_top.sort_values("priority_score")

    fig_priority = px.bar(
        df_top,
        x="priority_score",
        y="page",
        orientation="h",
        color="avg_risk",
        color_continuous_scale="reds",
        labels={
            "priority_score": "Priority Level",
            "page": "Wikipedia Page",
            "avg_risk": "Average Risk"
        },
        title="Highest Priority Pages to Monitor"
    )

    st.plotly_chart(fig_priority, use_container_width=True)

st.subheader("🧠 Emerging Narrative Topics")

if not df_topics.empty:
    fig_topics = px.bar(
        df_topics.head(10),
        x="Count",
        y="Name",
        orientation="h",
        title="Top Emerging Edit Themes"
    )
    st.plotly_chart(fig_topics, use_container_width=True)   

st.subheader("📊 Topic Distribution")

fig_topic_dist = px.pie(
    df_topics.head(8),
    values="Count",
    names="Name",
    title="Risk Narrative Share"
)
st.plotly_chart(fig_topic_dist)