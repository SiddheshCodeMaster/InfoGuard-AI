import re
from sentence_transformers import SentenceTransformer
from sklearn.metrics.pairwise import cosine_similarity

semantic_model = None

RISK_WORDS = [
    "propaganda", "agenda", "fake", "exposed",
    "corrupt", "biased", "manipulated", "truth"
]

SUSPICIOUS_KEYWORDS = [
    "official", "admin", "moderator", "verified",
    "gov", "government", "bjp", "congress", "party",
    "election", "vote", "politics",
    "truth", "real", "exposed", "agenda",
    "media", "news", "facts",
    "brand", "store", "shop", "officialpage",
    "anti", "pro", "support", "boycott"
]

def get_semantic_model():
    global semantic_model
    if semantic_model is None:
        print("-- Loading semantic model... --")
        semantic_model = SentenceTransformer("all-MiniLM-L6-v2")
    return semantic_model

def compute_semantic_similarity(old_text: str, new_text: str) -> float:
    if not old_text or not new_text:
        return 1.0  # nothing to compare

    model = get_semantic_model()

    embeddings = model.encode(
        [old_text, new_text],
        normalize_embeddings=True
    )

    similarity = cosine_similarity(
        [embeddings[0]],
        [embeddings[1]]
    )[0][0]

    return round(float(similarity), 3)

def compute_content_risk(text: str):
    text = text.lower()
    hits = [w for w in RISK_WORDS if w in text]

    return {
        "risk_words": hits,
        "risk_score": min(len(hits) * 0.2, 1.0)
    }

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

def analyze_edit(old_text, new_text, username):
    username_risk = compute_username_risk(username)
    content_risk = compute_content_risk(new_text)
    similarity = compute_semantic_similarity(old_text, new_text)

    semantic_risk = 1 - similarity

    final_risk = round(
    (semantic_risk * 0.4) +
    (content_risk["risk_score"] * 0.4) +
    (username_risk["risk_score"] * 0.2),3)

    flagged = final_risk >= 0.5
    
    return {
        "semantic_similarity": similarity,
        "username_risk": username_risk,
        "content_risk": content_risk,
        "final_risk": final_risk,
        "flagged": flagged
    }