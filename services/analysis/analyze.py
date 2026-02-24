import os, pandas as pd
from pymongo import MongoClient
import plotly.express as px

# Connecting to MONGO DB:

MONGO_URI = os.getenv("MONGODB_URI")
client = MongoClient(MONGO_URI)
db = client["infoguard"]

# Load data:
runs = db["runs"]
topics = db["topics"]

df = pd.DataFrame(list(runs.find()))
df_topic = pd.DataFrame(list(topics.find()))

if df.empty and df_topic.empty:
    print("No run data found")
    exit()

# Cleaning data:
df.drop(columns=["_id"], inplace = True)
df_topic.drop(columns=["_id"], inplace = True)

df["pages_per_minute"] = df["pages_checked"] / (df["duration_seconds"] / 60)
df["timestamp"] = pd.to_datetime(df["timestamp"])

# Converting seconds -> minutes:
df["duration_minutes"] = df["duration_seconds"] / 60

# Print stats
print("\n=== Runtime Statistics ===\n")

print("Total Runs:", len(df))
print("Average runtime:", round(df["duration_minutes"].mean(), 2), "minutes")
print("Minimum runtime:", round(df["duration_minutes"].min(), 2), "minutes")
print("Maximum runtime:", round(df["duration_minutes"].max(), 2), "minutes")

print("\n=== Throughput Statistics ===\n")

print("Average pages/minute:", round(df["pages_per_minute"].mean(), 2))
print("Minimum pages/minute:", round(df["pages_per_minute"].min(), 2))
print("Maximum pages/minute:", round(df["pages_per_minute"].max(), 2))

print("\n=== Topic Quality Statistics ===\n")

print("Total topics discovered:", len(df_topic))
print("Average edits per topic:", round(df_topic["Count"].mean(), 2))
print("Largest topic size:", df_topic["Count"].max())
print("Smallest topic size:", df_topic["Count"].min())

print("\nTop 10 topics:")
print(df_topic.sort_values("Count", ascending=False).head(10)[["Name","Count"]])

print("\n=== Topic Stability Analysis ===\n")

large_topics = df_topic[df_topic["Count"] >= 15]

print("Stable topics (Count >= 15):")
print(large_topics[["Name","Count"]])

print("\nPercentage of stable topics:",
      round(len(large_topics)/len(df)*100, 2), "%")

# Save CSV for record
df.to_csv("runtime_analysis.csv", index=False)
df.to_csv("throughput_analysis.csv", index=False)

print("\nSaved runtime_analysis.csv")
print("\nSaved throughput_analysis.csv")

# # Plot runtime trend
# fig = px.line(
#     df,
#     x="timestamp",
#     y="duration_minutes",
#     title="Pipeline Runtime Over Time",
#     labels={
#         "timestamp": "Run Time",
#         "duration_minutes": "Runtime (minutes)"
#     }
# )