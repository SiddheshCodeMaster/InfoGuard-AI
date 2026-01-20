import requests 
from datetime import datetime
import os
import re
import mwparserfromhell as mwpf

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

def extract_text(data):
    pages = data["query"]["pages"]
    page = next(iter(pages.values()))
    return page.get("extract", "")

def clean_wiki_text_nlp(text):
    wikicode = mwpf.parse(text)

    # Remove templates (Infobox, Use Indian English, etc.)
    for template in wikicode.filter_templates():
        wikicode.remove(template)

    # Remove files / images
    for link in wikicode.filter_wikilinks():
        if link.title.lower().startswith(("file:", "image:")):
            wikicode.remove(link)

    # Remove HTML-like tags (refs, etc.)
    for tag in wikicode.filter_tags():
        wikicode.remove(tag)

    # Convert to plain text
    clean_text = wikicode.strip_code()

    # Light NLP-friendly cleanup
    clean_text = re.sub(r"\n{2,}", "\n", clean_text)
    clean_text = re.sub(r"\s+", " ", clean_text)

    return clean_text.strip()

def save_to_file(title, text, raw_or_clean ,save_path="revisions_files"):
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    if raw_or_clean == "raw":
        filename = f"{title.replace(' ', '_')}_{raw_or_clean}_{timestamp}.txt"
        save_path = save_path + "/raw"
    
        # Ensure directory exists
        os.makedirs(save_path, exist_ok=True)
        
        full_path = os.path.join(save_path, filename)
        
        with open(full_path, "w", encoding="utf-8") as f:
            f.write(text)
    else:
        filename = f"{title.replace(' ', '_')}_{raw_or_clean}_{timestamp}.txt"
        save_path = save_path + "/clean"

        # Ensure directory exists
        os.makedirs(save_path, exist_ok=True)
        
        full_path = os.path.join(save_path, filename)
        
        with open(full_path, "w", encoding="utf-8") as f:
            f.write(text)

    print(f"Saved: {full_path}")

# Run
data = fetch_page("Jaipur")

# Correct extraction
text = extract_text(data)

# Save RAW
save_to_file("Jaipur", text, 'raw')

# Clean using NLP parser
clean_text = clean_wiki_text_nlp(text)

# Save CLEAN
save_to_file("Jaipur", clean_text, 'clean')
