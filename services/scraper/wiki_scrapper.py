import requests
from datetime import datetime, timedelta
import os, re
import logging, time
import mwparserfromhell as mwpf
from pymongo import MongoClient
from engine.core_engine import analyze_edit
from services.scraper.http_client import safe_get
from collections import Counter
from engine.topic_modeling import generate_topics

# ---------------- CONFIG ---------------- #

MAX_PAGES_PER_RUN = 100

# Only run BERTopic if at least this many new risky edits
MIN_RISKY_DOCS_FOR_TOPIC = 5

# Only consider edits from last X hours
TOPIC_LOOKBACK_HOURS = 6


# ---------------- LOGGING ---------------- #

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s"
)

logger = logging.getLogger(__name__)


# ---------------- MONGO ---------------- #

MONGO_URI = os.getenv("MONGODB_URI")

if not MONGO_URI:
    raise RuntimeError("MONGODB_URI not set")

client = MongoClient(MONGO_URI)
db = client['infoguard']

pages = db["pages"]
revisions = db["revisions"]
analysis = db["analysis"]
runs = db["runs"]


# ---------------- DISCOVERY ---------------- #

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

    data = safe_get(url, params, headers)

    if not data:
        return []

    return data["query"]["recentchanges"]


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
                "last_checked": None,
                "watch_status": "active",
                "priority_score": 0
            })

            logger.info("Added to watchlist: %s", title)


def discover_active_pages(limit=80, top_n=10):

    logger.info("Discovering active Wikipedia pages")

    recent_changes = fetch_recent_changes(limit)

    top_pages = get_top_edited_pages(recent_changes, top_n)

    update_watchlist_with_top_pages(top_pages)


# ---------------- TEXT CLEANING ---------------- #

def clean_wiki_text_nlp(text):

    wikicode = mwpf.parse(text)

    clean_text = wikicode.strip_code()

    clean_text = re.sub(r"\[\d+\]", "", clean_text)

    clean_text = re.sub(r"\s+", " ", clean_text)

    return clean_text.strip()


# ---------------- REVISION FETCH ---------------- #

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
        "User-Agent": "InfoGuardAI/1.0"
    }

    return safe_get(url, params, headers)


def extract_revision_info(data):

    page = data["query"]["pages"][0]

    if "revisions" not in page:
        return None

    rev = page["revisions"][0]

    return {
        "revid": rev["revid"],
        "user": rev["user"],
        "timestamp": rev["timestamp"],
        "comment": rev.get("comment", ""),
        "content": rev["slots"]["main"]["content"]
    }


# ---------------- CORE MONITOR ---------------- #

def monitor_page(title):

    logger.info("Checking: %s", title)

    data = fetch_latest_revision(title)

    if not data:
        return {"changed": False, "flagged": False}

    rev_info = extract_revision_info(data)

    if not rev_info:
        return {"changed": False, "flagged": False}

    page = pages.find_one({"_id": title})

    if page is None:

        pages.insert_one({
            "_id": title,
            "last_revid": rev_info["revid"],
            "last_checked": datetime.utcnow(),
            "watch_status": "active",
            "priority_score": 0
        })

        return {"changed": False, "flagged": False}

    if page["last_revid"] == rev_info["revid"]:

        pages.update_one(
            {"_id": title},
            {"$set": {"last_checked": datetime.utcnow()}}
        )

        return {"changed": False, "flagged": False}

    logger.warning("Change detected on %s", title)

    new_clean = clean_wiki_text_nlp(rev_info["content"])

    prev = revisions.find_one(
        {"page": title},
        sort=[("timestamp", -1)]
    )

    old_clean = prev["clean_content"] if prev else ""

    analysis_result = analyze_edit(
        old_text=old_clean,
        new_text=new_clean,
        username=rev_info["user"]
    )

    revisions.insert_one({
        "page": title,
        "revid": rev_info["revid"],
        "user": rev_info["user"],
        "timestamp": rev_info["timestamp"],
        "clean_content": new_clean,
        "previous_revid": page["last_revid"]
    })

    analysis.insert_one({
        "page": title,
        "revid": rev_info["revid"],
        "username": rev_info["user"],
        "clean_content": new_clean,
        **analysis_result,
        "created_at": datetime.utcnow()
    })

    pages.update_one(
        {"_id": title},
        {"$set": {
            "last_revid": rev_info["revid"],
            "last_checked": datetime.utcnow()
        }}
    )

    return {
        "changed": True,
        "flagged": analysis_result["flagged"]
    }


# ---------------- TOPIC MODEL CONDITION ---------------- #

def should_run_topic_model():

    cutoff = datetime.utcnow() - timedelta(hours=TOPIC_LOOKBACK_HOURS)

    risky_docs = analysis.count_documents({

        "final_risk": {"$gte": 0.35},

        "created_at": {"$gte": cutoff}

    })

    logger.info("Recent risky edits: %s", risky_docs)

    return risky_docs >= MIN_RISKY_DOCS_FOR_TOPIC


# ---------------- MAIN ---------------- #

start_time = time.time()

pages_checked = 0
changes_detected = 0
flagged_count = 0


discover_active_pages()


pages_cursor = pages.find(
    {"watch_status": "active"}
).sort([
    ("priority_score", -1),
    ("last_checked", 1)
]).limit(MAX_PAGES_PER_RUN)


pages_to_monitor = [p["_id"] for p in pages_cursor]

logger.info("Monitoring %s pages", len(pages_to_monitor))


for title in pages_to_monitor:

    pages_checked += 1

    result = monitor_page(title)

    if result["changed"]:
        changes_detected += 1

    if result["flagged"]:
        flagged_count += 1

logger.info("Running BERTopic model")

generate_topics()


duration = round(time.time() - start_time, 2)


runs.insert_one({

    "timestamp": datetime.utcnow(),

    "pages_checked": pages_checked,

    "changes_detected": changes_detected,

    "flagged": flagged_count,

    "duration_seconds": duration

})


logger.info("Run complete in %ss", duration)