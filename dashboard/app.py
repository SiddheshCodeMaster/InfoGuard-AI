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

# ---------------- CONFIG ---------------- #

st.set_page_config(page_title="InfoGuard AI Dashboard", layout="wide")
px.defaults.template = "plotly_white"

MONGO_URI = os.getenv("MONGODB_URI")
client = MongoClient(MONGO_URI)
db = client["infoguard"]

runs = db["runs"]
analysis = db["analysis"]
anomalies = db["anomalies"]
topics_collection = db["topics"]

# ---------------- SAFE LOADERS ---------------- #

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
    return safe_df(list(topics_collection.find()))

# ---------------- LOAD ---------------- #

df_runs = load_runs()
df_analysis = load_analysis()
df_anom = load_anomalies()
df_priority = compute_priority()
df_topics = load_topics()

# =====================================================
# =================== HEADER ==========================
# =====================================================

st.title("🛡 InfoGuard AI")
st.markdown("Production-grade AI system for detecting risky Wikipedia edits, anomaly spikes, and emerging narratives.")

# =====================================================
# ================= SYSTEM HEALTH =====================
# =====================================================

st.markdown("## 📈 System Health Overview")

if not df_runs.empty:

    latest = df_runs.iloc[-1]

    throughput = 0
    if latest["duration_seconds"] > 0:
        throughput = round(latest["pages_checked"] / (latest["duration_seconds"]/60), 2)

    col1, col2, col3, col4, col5 = st.columns(5)

    col1.metric("Pages Scanned", int(latest["pages_checked"]))
    col2.metric("Edits Detected", int(latest["changes_detected"]))
    col3.metric("Flagged Edits", int(latest["flagged"]))
    col4.metric("Runtime (sec)", round(latest["duration_seconds"], 2))
    col5.metric("Throughput (pages/min)", throughput)

else:
    st.info("No monitoring data yet.")

# =====================================================
# ============== MONITORING ACTIVITY ==================
# =====================================================

if not df_runs.empty:

    st.markdown("## 📊 Monitoring Activity")
    st.caption("System coverage and flagged edit detection over time.")

    colA, colB = st.columns(2)

    with colA:
        fig_pages = px.line(
            df_runs,
            x="timestamp",
            y="pages_checked",
            markers=True,
            labels={"timestamp": "Time", "pages_checked": "Pages Scanned"},
            title="Pages Scanned Per Cycle"
        )
        st.plotly_chart(fig_pages, use_container_width=True)

    with colB:
        fig_flagged = px.bar(
            df_runs,
            x="timestamp",
            y="flagged",
            labels={"timestamp": "Time", "flagged": "Flagged Edits"},
            title="Flagged Edits Per Cycle"
        )
        st.plotly_chart(fig_flagged, use_container_width=True)

# =====================================================
# ================= RISK INTELLIGENCE =================
# =====================================================

if not df_analysis.empty:

    st.markdown("## 🧠 Risk Intelligence")

    col1, col2 = st.columns(2)

    # Risk Distribution
    with col1:
        fig_dist = px.histogram(
            df_analysis,
            x="final_risk",
            nbins=25,
            labels={"final_risk": "Risk Score"},
            title="Risk Score Distribution"
        )
        fig_dist.update_layout(xaxis=dict(range=[0,1]))
        st.plotly_chart(fig_dist, use_container_width=True)

    # Rolling Risk Trend
    with col2:
        if "created_at" in df_analysis.columns:
            df_hourly = (
                df_analysis
                .set_index("created_at")
                .resample("6H")
                .mean(numeric_only=True)
                .reset_index()
            )

            fig_trend = px.line(
                df_hourly,
                x="created_at",
                y="final_risk",
                labels={"created_at": "Time", "final_risk": "Avg Risk"},
                title="Smoothed Risk Trend"
            )

            if not df_anom.empty:
                fig_trend.add_scatter(
                    x=df_anom["timestamp"],
                    y=df_anom["final_risk"],
                    mode="markers",
                    marker=dict(color="red", size=8),
                    name="Anomaly"
                )

            fig_trend.update_layout(yaxis=dict(range=[0,1]))
            st.plotly_chart(fig_trend, use_container_width=True)

# =====================================================
# ================= PRIORITIZATION ====================
# =====================================================

st.markdown("## 🚨 Intelligent Prioritization")
st.caption("Pages ranked by combined risk score, anomaly impact, and activity volume.")

if not df_priority.empty and "priority_score" in df_priority.columns:

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
        color_continuous_scale="Reds",
        labels={
            "priority_score": "Priority Score",
            "page": "Page",
            "avg_risk": "Average Risk"
        }
    )

    st.plotly_chart(fig_priority, use_container_width=True)

else:
    st.info("Not enough data yet.")

# =====================================================
# ================= TOPIC ANALYSIS ====================
# =====================================================

st.markdown("## 🧩 Emerging Narratives")
st.caption("Topic clusters derived from high-risk edits.")

if not df_topics.empty and "Count" in df_topics.columns:

    df_topics_sorted = df_topics.sort_values("Count", ascending=True).head(8)

    fig_topics = px.bar(
        df_topics_sorted,
        x="Count",
        y="Name",
        orientation="h",
        labels={"Count": "Edit Count", "Name": "Topic"}
    )

    st.plotly_chart(fig_topics, use_container_width=True)

else:
    st.info("Topic data not yet available.")