import requests 
from datetime import datetime
import os , re
import logging, time
import mwparserfromhell as mwpf
from pymongo import MongoClient
from engine.core_engine import analyze_edit
from collections import Counter

# Logging Configuration:

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s"
)

logger = logging.getLogger(__name__)

# Connecting to Mongo DB Client:

MONGO_URI = os.getenv("MONGODB_URI")

if not MONGO_URI:
    raise RuntimeError("MONGODB_URI not set")

client = MongoClient(MONGO_URI)
db = client['infoguard']

# Fetching Collections:

pages = db["pages"]
revisions = db["revisions"]
analysis = db["analysis"]
runs = db["runs"]

# To fetch recent information from Wikipedia:

def fetch_recent_changes(limit=100):
    url = "https://en.wikipedia.org/w/api.php"

    params = {
        "action": "query",
        "list": "recentchanges",
        "rclimit": limit,
        "rcnamespace": 0,
        "rcprop": "title|timestamp|user|comment",
        "format": "json"
    }

    headers = {"User-Agent": "InfoguardAI/1.0"}

    response = requests.get(url, params=params, headers=headers)
    response.raise_for_status()
    data = response.json()
    
    return data.get("query", {}).get("recentchanges", [])

def get_top_edited_pages(recent_changes, top_n=10):
    titles = [
        c['title']
        for c in recent_changes
        if "bot" not in c["user"].lower()
    ]

    counts = Counter(titles)
    return [title for title, _ in counts.most_common(top_n)]

def update_watchlist_with_top_pages(top_pages):
    for title in top_pages:
        if pages.find_one({"_id": title}) is None:
            pages.insert_one({
                "_id": title,
                "last_revid": None,
                "last_Checked": None,
                "watch_status": "active"
            })
            logger.info("Added to watchlist: %s", title)
        else:
            logger.info("Already watching: %s", title)

def discover_active_pages(limit=200, top_n=10):
    logger.info("Fetching recent changes.")
    recent_changes = fetch_recent_changes(limit)
    logger.info("Recent changes fetched: %s records", len(recent_changes))

    top_pages = get_top_edited_pages(recent_changes, top_n)
    logger.info("Top edited pages: %s", top_pages)

    update_watchlist_with_top_pages(top_pages)
    logger.info("watchlist updated with active pages.")

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
    logger.info("Checking page: %s", title)

    # 1. Fetch latest Wikipedia revision
    data = fetch_latest_revision(title)
    rev_info = extract_revision_info(data)

    # 2. Check if page exists in DB
    page = get_page_record(title)

    # 3. Auto-register page if first time
    if page is None:
        pages.insert_one({
            "_id": title,
            "last_revid": rev_info["revid"],
            "last_checked": datetime.utcnow(),
            "watch_status": "active"
        })
        logger.info("Page registered. Baseline established.")
        return {"changed": False, "flagged": False}

    # 4. No change → exit early
    if page["last_revid"] == rev_info["revid"]:
        logger.info("No change detected.")
        pages.update_one(
            {"_id": title},
            {"$set": {"last_checked": datetime.utcnow()}}
        )
        return {"changed": False, "flagged": False}

    logger.warning("Change detected on %s!", title)

    # 5. Clean new content
    new_clean_text = clean_wiki_text_nlp(rev_info["content"])

    # 6. Fetch previous clean content
    prev_revision = revisions.find_one(
        {"page": title},
        sort=[("timestamp", -1)]
    )
    old_clean_text = prev_revision["clean_content"] if prev_revision else ""

    # 7. CORE ENGINE CALL (ALL INTELLIGENCE HERE)
    analysis_result = analyze_edit(
        old_text=old_clean_text,
        new_text=new_clean_text,
        username=rev_info["user"]
    )

    # 8. Store revision
    revisions.insert_one({
        "page": title,
        "revid": rev_info["revid"],
        "user": rev_info["user"],
        "timestamp": rev_info["timestamp"],
        "comment": rev_info.get("comment", ""),
        "raw_content": rev_info["content"],
        "clean_content": new_clean_text,
        "previous_revid": page["last_revid"]
    })

    # 9. Store analysis
    analysis.insert_one({
        "page": title,
        "revid": rev_info["revid"],
        "username": rev_info["user"],
        **analysis_result,
        "created_at": datetime.utcnow()
    })

    # 10. Update page tracker
    pages.update_one(
        {"_id": title},
        {"$set": {
            "last_revid": rev_info["revid"],
            "last_checked": datetime.utcnow()
        }}
    )

    # 11. Log outcome
    status = "FLAGGED" if analysis_result["flagged"] else "OK"
    logger.info("%s | Similarity: %s | Risk: %s", status, 
                analysis_result['semantic_similarity'], 
                analysis_result['final_risk'])
    
    return {
        "changed": True,
        "flagged": analysis_result["flagged"]
    }
    # print(
    #     f"{status} | Similarity: {analysis_result['semantic_similarity']} "
    #     f"| Risk: {analysis_result['final_risk']}"
    # )

start_time = time.time()

pages_checked = 0
changes_detected = 0
flagged_count = 0

discover_active_pages(limit=200, top_n=10)

pages_to_monitor = list(
    pages.find({"watch_status": "active"}, {"_id":1})
)

pages_to_monitor = [p["_id"] for p in pages_to_monitor]

# pages_to_monitor = [p["_id"] for p in pages.find({"watch_status": "Active"})]

for title in pages_to_monitor:
    pages_checked += 1
    result = monitor_page(title)

    if result["changed"]:
        changes_detected += 1
    if result["flagged"]:
        flagged_count += 1

duration = round(time.time() - start_time, 2)

logger.info(
    "Run summary | pages=%s changes=%s flagged=%s duration=%ss",
    pages_checked,
    changes_detected,
    flagged_count,
    duration
)

logger.info("Inserting run metrics into MongoDB...")

runs.insert_one({
    "timestamp": datetime.utcnow(),
    "pages_checked": pages_checked,
    "changes_detected": changes_detected,
    "flagged": flagged_count,
    "duration_seconds": duration
})
