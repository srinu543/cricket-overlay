import os
import time
import threading
import requests
from bs4 import BeautifulSoup
from flask import Flask
from playwright.sync_api import sync_playwright

app = Flask(__name__)

# Your overlays.uno API endpoint and Overlay ID
UNO_API_URL = "https://app.overlays.uno/apiv2/controlapps/3faAKlnUjVC21DaVd2bvYY/api"
OVERLAY_ID = "3faAKlnUjVC21DaVd2bvYY"

TARGET_MATCH_URL = "https://cricheroes.com/scorecard/28364240/individual/test-vs-test2/live"

last_state = None

@app.route("/")
def home():
    return "Cloud Playwright CricHeroes Bridge is Running!"

def parse_cricheroes_scorecard(html_content):
    soup = BeautifulSoup(html_content, "html.parser")
    try:
        # Extract Team Names
        team_name_elements = soup.select(".styles-module-scss-module__0yl5Ha__teamName")
        team1_name = team_name_elements[0].get_text(strip=True) if len(team_name_elements) > 0 else "Team A"

        # Extract Overs info for Team 1 score baby step
        over_spans = soup.select(".styles-module-scss-module__0yl5Ha__overSpan")
        team1_overs = over_spans[0].get_text(strip=True) if len(over_spans) > 0 else "(0.0 Ov)"

        # Baby step: focusing on team name and score first
        return {
            "Team1Name": team1_name,
            "Team1Score": team1_overs
        }
    except Exception as e:
        print(f"Parsing Error: {e}", flush=True)
        return None

def update_uno_overlay(data):
    # FIXED: The API schema requires "id" instead of "overlayId"
    payload = {
        "command": "SetOverlayContent",
        "id": OVERLAY_ID,
        "content": data
    }
    try:
        response = requests.put(UNO_API_URL, json=payload, timeout=5)
        print(f"Overlay Update Response Status: {response.status_code} - Response: {response.text}", flush=True)
    except Exception as e:
        print(f"API Request Error: {e}", flush=True)

def background_scraper():
    global last_state
    print("Launching cloud Playwright browser thread...", flush=True)
    
    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True,
            args=["--disable-dev-shm-usage", "--no-sandbox"]
        )
        page = browser.new_page()
        
        print(f"Navigating to Target Match: {TARGET_MATCH_URL}", flush=True)
        try:
            page.goto(TARGET_MATCH_URL, wait_until="domcontentloaded", timeout=60000)
            time.sleep(6)
            print("Target match page loaded successfully!", flush=True)
        except Exception as e:
            print(f"Navigation error: {e}", flush=True)

        while True:
            try:
                html_content = page.content()
                current_state = parse_cricheroes_scorecard(html_content)
                
                if current_state and current_state != last_state:
                    print(f"Parsed State Update: {current_state}", flush=True)
                    update_uno_overlay(current_state)
                    last_state = current_state
            except Exception as e:
                print(f"Scraper Loop Error: {e}", flush=True)
            
            time.sleep(5)

if __name__ == "__main__":
    t = threading.Thread(target=background_scraper)
    t.daemon = True
    t.start()
    
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
