from bertopic import BERTopic
from sentence_transformers import SentenceTransformer
from pymongo import MongoClient
import os

MONGO_URI = os.getenv("MONGODB_URI")

client = MongoClient(MONGO_URI)

db = client["infoguard"]

analysis = db["analysis"]

topics_collection = db["topics"]

# FAST EMBEDDING MODEL

embedding_model = SentenceTransformer("all-MiniLM-L6-v2")

STOPWORDS = {
    "the","and","for","with","in","on","at","to","of","by","from",
    "is","was","are","this","that","it"
}

topic_model = BERTopic(

    embedding_model=embedding_model,

    umap_model=None,  # MASSIVE SPEED BOOST

    calculate_probabilities=False,

    verbose=False
)


def clean_topic_label(words):

    clean = [

        w.capitalize()

        for w in words

        if w not in STOPWORDS and len(w) > 3

    ]

    return ", ".join(clean[:3])


def generate_topics():

    docs = list(
        analysis.find(
            {
                "final_risk": {"$gte": 0.35},
                "clean_content": {"$exists": True, "$ne": ""}
            },
            {"clean_content": 1}
        ).limit(1000)
    )

    if len(docs) < 10:
        return None

    texts = [
        d.get("clean_content")
        for d in docs
        if d.get("clean_content")
    ]

    if len(texts) < 10:
        return None

    embeddings = embedding_model.encode(
        texts,
        batch_size=32,
        show_progress_bar=False
    )

    topics, probs = topic_model.fit_transform(
        texts,
        embeddings
    )

    topic_info = topic_model.get_topic_info()

    topic_records = []

    for topic_id in topic_info["Topic"]:

        if topic_id == -1:
            continue

        words = topic_model.get_topic(topic_id)

        if not words:
            continue

        word_list = [w for w, _ in words]

        label = clean_topic_label(word_list)

        topic_records.append({

            "Topic": topic_id,

            "Count": int(
                topic_info[
                    topic_info["Topic"] == topic_id
                ]["Count"].values[0]
            ),

            "Name": label,

            "Keywords": word_list[:5]

        })

    topics_collection.delete_many({})

    if topic_records:
        topics_collection.insert_many(topic_records)

    return topic_records