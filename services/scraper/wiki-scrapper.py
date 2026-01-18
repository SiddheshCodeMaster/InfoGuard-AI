import requests 
from datetime import datetime

def fetch_page(title):
    url = "https://en.wikipedia.org/w/api.php"
    
    headers = {
        "User-Agent": "InfoGuardAI/1.0 (https://github.com/SiddheshCodeMaster/InfoGuard-AI.git)"
    }
    
    params = {
        "action": "query",
        "prop": "revisions",
        "rvprop": "timestamp|user|content",
        "rvslots": "main",
        "format": "json",
        "formatversion": "2",
        "titles": title
    }

    response = requests.get(url, params=params, headers=headers)
    response.raise_for_status()
    return response.json()

def extract_text(data):
    return data["query"]["pages"][0]["revisions"][0]["slots"]["main"]["content"]

def save_to_file(title, text):
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"{title.replace(' ', '_')}_{timestamp}.txt"
    
    with open(filename, "w", encoding="utf-8") as f:
        f.write(text)
    
    print(f"Saved: {filename}")

# Run
data = fetch_page("Jaipur")
text = extract_text(data)
save_to_file("Jaipur", text)