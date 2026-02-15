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
topics_collection = db["topics"]

# ---------------- SAFE DATA LOADERS ---------------- #

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
    if not df.empty and "created_at" in df.columns:
        df["created_at"] = pd.to_datetime(df["created_at"])
    return df

def load_anomalies():
    df = safe_df(list(anomalies.find()))
    if not df.empty and "timestamp" in df.columns:
        df["timestamp"] = pd.to_datetime(df["timestamp"])
    return df

def load_topics():
    df = safe_df(list(topics_collection.find()))
    return df

# ---------------- LOAD DATA ---------------- #

df_runs = load_runs()
df_analysis = load_analysis()
df_anom = load_anomalies()
df_priority = compute_priority()
df_topics = load_topics()

# ---------------- DASHBOARD HEADER ---------------- #

st.title("🛡 InfoGuard AI — Wikipedia Risk Monitoring System")
st.markdown("AI-powered monitoring system detecting suspicious edit behavior, anomaly spikes, and high-risk pages in real-time.")

# ==========================================================
# ================== MONITORING METRICS ====================
# ==========================================================

if not df_runs.empty:

    latest = df_runs.iloc[-1]

    col1, col2, col3, col4, col5 = st.columns(5)
    col1.metric("Pages Scanned (Last Run)", int(latest["pages_checked"]))
    col2.metric("Edits Detected (Last Run)", int(latest["changes_detected"]))
    col3.metric("Flagged Edits (Last Run)", int(latest["flagged"]))
    col4.metric("Total Flagged (All Time)", analysis.count_documents({"flagged": True}))
    col5.metric("Run Duration (sec)", round(latest["duration_seconds"], 2))

    st.markdown("## 📊 Monitoring Activity Over Time")
    st.caption("Shows how system coverage and flagged edits evolve across monitoring cycles.")

    # Pages scanned trend
    fig_pages = px.line(
        df_runs,
        x="timestamp",
        y="pages_checked",
        markers=True,
        labels={"timestamp": "Time", "pages_checked": "Pages Scanned"},
        title="Pages Scanned Per Monitoring Cycle"
    )
    st.plotly_chart(fig_pages, use_container_width=True)

    # Flagged edits trend
    fig_flagged = px.line(
        df_runs,
        x="timestamp",
        y="flagged",
        markers=True,
        labels={"timestamp": "Time", "flagged": "Flagged Edits"},
        title="Flagged Edits Per Monitoring Cycle"
    )
    st.plotly_chart(fig_flagged, use_container_width=True)

# ==========================================================
# ================== RISK ANALYTICS ========================
# ==========================================================

if not df_analysis.empty:

    st.markdown("## 📊 Risk Distribution")
    st.caption("Distribution of computed edit risk scores (0 = safe, 1 = highly suspicious).")

    fig_dist = px.histogram(
        df_analysis,
        x="final_risk",
        nbins=25,
        labels={"final_risk": "Risk Score"},
        title="Distribution of Edit Risk Levels"
    )
    fig_dist.update_layout(xaxis=dict(range=[0,1]))
    st.plotly_chart(fig_dist, use_container_width=True)

    # -------- Smoothed Risk Trend -------- #

    if "created_at" in df_analysis.columns:

        df_daily = (
            df_analysis
            .set_index("created_at")
            .resample("6H")   # smoother trend
            .mean(numeric_only=True)
            .reset_index()
        )

        st.markdown("## 📈 Risk Evolution Over Time")
        st.caption("Average risk level across edits. Red markers highlight anomaly spikes.")

        fig_trend = px.line(
            df_daily,
            x="created_at",
            y="final_risk",
            markers=True,
            labels={
                "created_at": "Time",
                "final_risk": "Average Risk"
            },
            title="Average Risk Trend"
        )

        if not df_anom.empty:
            fig_trend.add_scatter(
                x=df_anom["timestamp"],
                y=df_anom["final_risk"],
                mode="markers",
                marker=dict(color="red", size=10),
                name="Detected Anomaly"
            )

        fig_trend.update_layout(yaxis=dict(range=[0,1]))
        st.plotly_chart(fig_trend, use_container_width=True)

    # -------- Most Edited Pages -------- #

    st.markdown("## 🔥 Most Actively Edited Pages")
    st.caption("Pages receiving the highest number of edits (higher exposure to manipulation).")

    page_counts = (
        df_analysis["page"]
        .value_counts()
        .head(10)
        .reset_index()
    )
    page_counts.columns = ["Page", "Edit Count"]

    page_counts = page_counts.sort_values("Edit Count")

    fig_activity = px.bar(
        page_counts,
        x="Edit Count",
        y="Page",
        orientation="h",
        title="Top 10 Most Edited Pages"
    )

    st.plotly_chart(fig_activity, use_container_width=True)

# ==========================================================
# ================== PRIORITIZATION ========================
# ==========================================================

st.markdown("## 🚨 Intelligent Risk Prioritization")
st.caption("AI-ranked pages combining historical risk, anomaly detection, and edit activity.")

if df_priority.empty or "priority_score" not in df_priority.columns:
    st.info("Not enough data yet to compute intelligent priorities.")
else:

    df_top = (
        df_priority
        .sort_values("priority_score", ascending=False)
        .head(10)
        .sort_values("priority_score")
    )

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

# ==========================================================
# ================== TOPIC ANALYSIS ========================
# ==========================================================

st.markdown("## 🧠 Emerging Edit Narratives")
st.caption("Topic modeling clusters high-risk edits into thematic narratives.")

if not df_topics.empty and "Count" in df_topics.columns:

    df_topics_sorted = df_topics.sort_values("Count", ascending=True).head(10)

    fig_topics = px.bar(
        df_topics_sorted,
        x="Count",
        y="Name",
        orientation="h",
        title="Top Emerging Edit Themes",
        labels={"Count": "Number of Edits", "Name": "Topic"}
    )

    st.plotly_chart(fig_topics, use_container_width=True)

    st.markdown("### 📊 Topic Share Distribution")

    fig_topic_dist = px.pie(
        df_topics.head(8),
        values="Count",
        names="Name",
        title="Narrative Share Across High-Risk Edits"
    )

    st.plotly_chart(fig_topic_dist, use_container_width=True)
else:
    st.info("Not enough topic data available yet.")