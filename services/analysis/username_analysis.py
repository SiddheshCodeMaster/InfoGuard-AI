import re
from sentence_transformers import SentenceTransformer
from sklearn.metrics.pairwise import cosine_similarity

SUSPICIOUS_KEYWORDS = [
    "official", "admin", "moderator", "verified",
    "gov", "government", "bjp", "congress", "party",
    "election", "vote", "politics",
    "truth", "real", "exposed", "agenda",
    "media", "news", "facts",
    "brand", "store", "shop", "officialpage",
    "anti", "pro", "support", "boycott"
]

def tokenize_username(username):
    return re.findall(r"[a-zA-Z]+", username.lower())

def username_pattern_risk(username):
    u = username.lower()
    matched = [k for k in SUSPICIOUS_KEYWORDS if k in u]

    return {
        "matched_keywords": matched,
        "keyword_count": len(matched),
        "has_numbers": bool(re.search(r"\d{3,}", u)),
        "all_caps": username.isupper(),
        "length": len(username)
    }

def username_token_risk(username):
    tokens = tokenize_username(username)
    risky_tokens = [t for t in tokens if t in SUSPICIOUS_KEYWORDS]

    return {
        "tokens": tokens,
        "risky_tokens": risky_tokens,
        "token_risk_score": len(risky_tokens) / max(len(tokens), 1)
    }

def compute_username_risk(username):
    p = username_pattern_risk(username)
    t = username_token_risk(username)

    score = 0.0

    score += 0.3 if p["keyword_count"] > 0 else 0
    score += 0.2 if p["has_numbers"] else 0
    score += 0.2 if p["all_caps"] else 0
    score += min(t["token_risk_score"], 0.3)

    reasons = p["matched_keywords"] + t["risky_tokens"]
    if p["has_numbers"]:
        reasons.append("excessive_numbers")
    if p["all_caps"]:
        reasons.append("all_caps")

    return {
        "risk_score": round(min(score, 1.0), 2),
        "reasons": list(set(reasons))
    }

