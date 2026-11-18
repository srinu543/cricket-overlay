import os
import time
import threading
import requests
from flask import Flask
from playwright.sync_api import sync_playwright

app = Flask(__name__)

UNO_API_URL = "https://app.overlays.uno/apiv2/controlapps/3faAKlnUjVC21DaVd2bvYY/api"
OVERLAY_ID = "8a45f609-8123-4791-9b0b-00f84c090992"
TARGET_MATCH_URL = "https://cricheroes.com/scorecard/28364240/individual/test-vs-test2/live"

last_state = None

@app.route("/")
def home():
    return "Cloud Playwright CricHeroes Bridge is Running!"

def parse_cricheroes_scorecard(page):
    try:
        body_text = page.inner_text("body")
        
        # DEBUG: Print a chunk of the page text to Render logs to inspect formatting
        print(f"--- PAGE TEXT SAMPLE ---\n{body_text[:400]}\n------------------------", flush=True)

        runs = 0
        wickets = 0
        overs = 0.0
        team_name = "Team 1"

        return {
            "Team Batting": team_name,
            "Batting Team Runs": runs,
            "Batting Team Wickets": wickets,
            "Overs": overs,
            "Bastman 1": "Batter 1",
            "Batsman 1 Score": 0,
            "Batsman 2": "Batter 2",
            "Batsman 2 Score": 0,
            "Bowler Name": "Bowler",
            "Bowler Overs": 0.0,
            "Bowler Runs": 0,
            "Bowler Wickets": "0",
            "Show Bowler Stats": True
        }
    except Exception as e:
        print(f"Parsing Error: {e}", flush=True)
        return None

def update_uno_overlay(data):
    payload = {
        "command": "SetOverlayContent",
        "id": OVERLAY_ID,
        "content": data
    }
    try:
        response = requests.put(UNO_API_URL, json=payload, timeout=5)
        print(f"Overlay Update Response Status: {response.status_code}", flush=True)
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
            page.goto(TARGET_MATCH_URL, wait_until="networkidle", timeout=60000)
            time.sleep(5)
            print("Target match page loaded successfully!", flush=True)
        except Exception as e:
            print(f"Navigation error: {e}", flush=True)

        while Time.sleep(5) or True:
            try:
                page.reload(wait_until="networkidle", timeout=30000)
                time.sleep(3)
                
                current_state = parse_cricheroes_scorecard(page)
                
                if current_state and current_state != last_state:
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
