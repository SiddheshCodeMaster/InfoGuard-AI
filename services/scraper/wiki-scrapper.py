import requests 
from datetime import datetime
import os
import re
import mwparserfromhell as mwpf
from pymongo import MongoClient

# Connecting to Mongo DB Client:

client = MongoClient("mongodb://localhost:27017/")
db = client["infoguard"]

# Fetching Collections:

pages = db["pages"]
revisions = db["revisions"]
analysis = db["analysis"]

def fetch_page(title):
    url = "https://en.wikipedia.org/w/api.php"
    
    headers = {
        "User-Agent": "InfoGuardAI/1.0 (https://github.com/SiddheshCodeMaster/InfoGuard-AI.git)"
    }
    
    params = {
        "action": "query",
        "prop": "extracts",
        "explaintext": True,
        "format": "json",
        "titles": title
    }

    response = requests.get(url, params=params, headers=headers)
    response.raise_for_status()
    return response.json()

def fetch_latest_revision(title):
    url = "https://en.wikipedia.org/w/api.php"

    params = {
        "action": "query",
        "prop": "revisions",
        "rvprop": "ids|timestamp|user|comment|content",
        "rvslots": "main",
        "format": "json",
        "formatversion": "2",
        "titles": title
    }

    headers = {
        "User-Agent": "InfoGuardAI/1.0 (https://github.com/SiddheshCodeMaster/InfoGuard-AI)"
    }

    response = requests.get(url, params=params, headers=headers)
    response.raise_for_status()
    return response.json()

def extract_text(data):
    pages = data["query"]["pages"]
    page = next(iter(pages.values()))
    return page.get("extract", "")

def extract_revision_info(data):
    page = data["query"]["pages"][0]
    rev = page["revisions"][0]

    return {
        "revid": rev["revid"],
        "user": rev["user"],
        "timestamp": rev["timestamp"],
        "comment": rev.get("comment", ""),
        "content": rev["slots"]["main"]["content"]
    }

def get_page_record(title):
    return pages.find_one({"_id": title})

def has_page_changed(title, latest_revid):
    page = get_page_record(title)
    return page["last_revid"] != latest_revid

def save_revision(title, rev_info, clean_text):
    last_page = get_page_record(title)

    revisions.insert_one({
        "page": title,
        "revid": rev_info["revid"],
        "user": rev_info["user"],
        "timestamp": rev_info["timestamp"],
        "comment": rev_info["comment"],
        "raw_content": rev_info["content"],
        "clean_content": clean_text,
        "previous_revid": last_page["last_revid"]
    })

def insert_username_analysis(title, rev_info, username_analysis):
    analysis.insert_one({
        "page": title,
        "revid": rev_info["revid"],
        "username_flag": username_analysis["risk_score"] > 0.5,
        "username_risk": username_analysis,
        "content_flag": False,        # placeholder for next phase
        "risk_score": username_analysis["risk_score"],
        "similarity": None,           # placeholder for NLP diff
        "summary": "Username risk analysis"
    })

def update_page(title, new_revid):
    pages.update_one(
        {"_id": title},
        {"$set": {
            "last_revid": new_revid,
            "last_checked": datetime.utcnow()
        }}
    )

def clean_wiki_text_nlp(text):
    # Parse wiki markup
    wikicode = mwpf.parse(text)

    # Convert to plain readable text
    clean_text = wikicode.strip_code()

    # Remove leftover references like [1], [2]
    clean_text = re.sub(r"\[\d+\]", "", clean_text)

    # Normalize whitespace
    clean_text = re.sub(r"\s+", " ", clean_text)
    clean_text = re.sub(r"\n{2,}", "\n", clean_text)

    return clean_text.strip()

def monitor_page(title):
    print(f"Checking {title}...")

    data = fetch_latest_revision(title)
    rev_info = extract_revision_info(data)

    page = get_page_record(title)

    # Auto-register page if not present
    if page is None:
        print("Page not found in DB. Registering now...")
        pages.insert_one({
            "_id": title,
            "last_revid": rev_info["revid"],
            "last_checked": None,
            "watch_status": "active"
        })
        print("Page registered. No analysis on first insert.")
        return

    if has_page_changed(title, rev_info["revid"]):
        print("Change detected!")

        clean_text = clean_wiki_text_nlp(rev_info["content"])
        save_revision(title, rev_info, clean_text)

        username_analysis = compute_username_risk(rev_info["user"])
        insert_username_analysis(title, rev_info, username_analysis)

        update_page(title, rev_info["revid"])

        print("Revision + username analysis stored.")
    else:
        print("No change.")

monitor_page("World War II")