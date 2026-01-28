import requests
from time import sleep

def safe_get(url, params, headers, retries=5, timeout=20):
    for attempt in range(retries):
        try:
            response = requests.get(
                url,
                params=params,
                headers=headers,
                timeout=timeout
            )
            response.raise_for_status()
            return response.json()

        except requests.exceptions.ReadTimeout:
            print(f"Timeout (attempt {attempt+1}/{retries}) — retrying...")
        
        except requests.exceptions.RequestException as e:
            print(f"Request error: {e} — retrying...")

        sleep(2 ** attempt)   # exponential backoff

    print("API failed after retries — skipping request")
    return None