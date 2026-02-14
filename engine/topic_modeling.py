from bertopic import BERTopic
from pymongo import MongoClient
import os, pandas as pd

MONGO_URI = os.getenv("MONGODB_URI")
client = MongoClient(MONGO_URI)
db = client["infoguard"]

analysis = db['analysis']
topics_collection = db["topics"]

topic_model = None

def get_topic_model():
    global topic_model
    if topic_model is None:
        topic_model = BERTopic()
    return topic_model

def generate_topics():
    docs = list(
    analysis.find(
        {"clean_content": {"$exists": True}},
        {"clean_content": 1, "final_risk": 1}
        )
    )

    if not docs:
        return None
    
    texts =[d["clean_content"] for d in docs if "clean_content" in d]

    if len(texts) < 5:
        return None # Not enough data
    
    model = get_topic_model()
    topics, probs  = model.fit_transform(texts)

    topic_info = model.get_topic_info()

    topics_collection.delete_many({})
    topics_collection.insert_many(topic_info.to_dict("records"))

    return topic_info