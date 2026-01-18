import requests 

def fetch_page(title):
    url = "https://en.wikipedia.org/w/api.php"
    params = {
        "action": "query",
        "prop": "revisions",
        "rvprop": "timestamp|user|content",
        "rvslots": "main",
        "format": "json",
        "titles": title
    }

    response = requests.get(url,params)
    response.raise_for_status()
    return response.json()

data = fetch_page("Artificial Intelligence")
print(data)

def extract_text(data):
    pages = data['query']['pages']
    return pages[0]['revisions'][0]['main']['content']

text = extract_text(data)
print(text)
