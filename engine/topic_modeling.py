from bertopic import BERTopic
from pymongo import MongoClient
import os
import pandas as pd

MONGO_URI = os.getenv("MONGODB_URI")
client = MongoClient(MONGO_URI)
db = client["infoguard"]

analysis = db['analysis']
topics_collection = db["topics"]

topic_model = None

STOPWORDS = {
    "the","and","for","with","in","on","at","to","of","by","from","is","was"
}

def clean_topic_label(words):

    clean = [
        w.capitalize()
        for w in words
        if w not in STOPWORDS and len(w) > 2
    ]

    return ", ".join(clean[:3])


def get_topic_model():

    global topic_model

    if topic_model is None:

        topic_model = BERTopic(
            verbose=False,
            calculate_probabilities=False
        )

    return topic_model


def generate_topics():

    docs = list(
        analysis.find(
            {"final_risk": {"$gte": 0.35}},
            {"clean_content": 1}
        )
    )

    if not docs:
        return None

    texts = [d["clean_content"] for d in docs if "clean_content" in d]

    if len(texts) < 5:
        return None

    model = get_topic_model()

    topics, probs = model.fit_transform(texts)

    topic_info = model.get_topic_info()

    # Convert to clean labels
    topic_records = []

    for topic_id in topic_info["Topic"]:

        if topic_id == -1:
            continue

        words = model.get_topic(topic_id)

        if not words:
            continue

        word_list = [w for w, _ in words]

        clean_label = clean_topic_label(word_list)

        topic_records.append({

            "Topic": topic_id,

            "Count": int(topic_info[
                topic_info["Topic"] == topic_id
            ]["Count"].values[0]),

            "Name": clean_label,

            "Keywords": word_list[:5]

        })

    topics_collection.delete_many({})
    topics_collection.insert_many(topic_records)

    return topic_records