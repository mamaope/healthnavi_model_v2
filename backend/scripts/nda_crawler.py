import os
import time
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin, unquote

# --- CONFIGURATION ---
BASE_URL = "https://www.nda.or.ug/"
OUTPUT_FOLDER = "nda_downloads"

# These URLs correspond to the dropdown menu items in your screenshot
TARGET_URLS = [
    "https://www.nda.or.ug/human-medicine-guidelines/",
    "https://www.nda.or.ug/veterinary-medicine-guidelines/",
    "https://www.nda.or.ug/herbal-medicine-guidelines/",
    "https://www.nda.or.ug/medical-devices-guidelines/"
]

# Headers to mimic a real browser
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
}

def download_file(url, folder):
    """Downloads a single file with a timeout safety mechanism."""
    try:
        filename = unquote(url.split("/")[-1])
        # Clean filename of query parameters if any exist
        if "?" in filename:
            filename = filename.split("?")[0]
            
        filepath = os.path.join(folder, filename)

        if os.path.exists(filepath):
            print(f"[SKIP] Already exists: {filename}")
            return

        print(f"[DOWNLOADING] {filename}...")
        
        # TIMEOUT ADDED: If server doesn't respond in 15 seconds, it throws an error
        with requests.get(url, headers=HEADERS, stream=True, timeout=15) as r:
            r.raise_for_status()
            with open(filepath, 'wb') as f:
                for chunk in r.iter_content(chunk_size=8192): 
                    f.write(chunk)
        
        print(f"[SUCCESS] Saved {filename}")
        time.sleep(0.5) # Reduced sleep slightly to be faster

    except requests.exceptions.Timeout:
        print(f"[SKIP - TIMEOUT] Server took too long to respond for: {url}")
    except requests.exceptions.ConnectionError:
        print(f"[SKIP - ERROR] Connection error for: {url}")
    except Exception as e:
        print(f"[SKIP - FAILED] {filename} failed. Reason: {e}")

def main():
    if not os.path.exists(OUTPUT_FOLDER):
        os.makedirs(OUTPUT_FOLDER)
        print(f"Created directory: {OUTPUT_FOLDER}")

    for page_url in TARGET_URLS:
        print(f"\n--- Scanning: {page_url} ---")
        try:
            # Added timeout here too for the main page load
            response = requests.get(page_url, headers=HEADERS, timeout=20)
            soup = BeautifulSoup(response.text, "html.parser")

            links = soup.find_all("a", href=True)
            doc_links = [l['href'] for l in links if l['href'].lower().endswith(('.pdf', '.doc', '.docx', '.xls', '.zip'))]

            print(f"Found {len(doc_links)} documents. Starting download...")

            for link in doc_links:
                full_url = urljoin(page_url, link)
                download_file(full_url, OUTPUT_FOLDER)

        except Exception as e:
            print(f"Failed to crawl {page_url}: {e}")

    print("\nAll tasks completed.")

if __name__ == "__main__":
    main()
    