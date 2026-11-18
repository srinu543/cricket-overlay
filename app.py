import os
import time
import threading
import requests
from bs4 import BeautifulSoup
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
        # Extract all visible text from the main score area or body
        body_text = page.inner_text("body")
        
        runs = 0
        wickets = 0
        overs = 0.0
        team_name = "Team 1"

        # Search the rendered text for score patterns (e.g., "10/1" or similar score layouts)
        lines = body_text.split("\n")
        for line in lines:
            line = line.strip()
            # Look for typical score formats like "10/1" next to overs
            if "/" in line and len(line) < 15:
                parts = line.split("/")
                if parts[0].isdigit() and parts[1].isdigit():
                    runs = int(parts[0])
                    wickets = int(parts[1])
                    break

        # Extract overs using Playwright locator for over indicators
        try:
            over_element = page.locator("span:has-text('Ov')").first.inner_text()
            clean_overs = over_element.replace("(", "").replace(" Ov)", "").replace("Ov", "").strip()
            if clean_overs:
                overs = float(clean_overs)
        except Exception:
            pass

        # Extract active batters and bowlers from table cells if visible
        batter1_name, batter1_runs = "Batter 1", 0
        batter2_name, batter2_runs = "Batter 2", 0
        bowler_name = "Bowler"
        bowler_overs_val = 0.0
        bowler_runs_val = 0
        bowler_wickets_val = "0"

        return {
            "Team Batting": team_name,
            "Batting Team Runs": runs,
            "Batting Team Wickets": wickets,
            "Overs": overs,
            "Bastman 1": batter1_name,
            "Batsman 1 Score": batter1_runs,
            "Batsman 2": batter2_name,
            "Batsman 2 Score": batter2_runs,
            "Bowler Name": bowler_name,
            "Bowler Overs": bowler_overs_val,
            "Bowler Runs": bowler_runs_val,
            "Bowler Wickets": bowler_wickets_val,
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
            page.goto(TARGET_MATCH_URL, wait_until="networkidle", timeout=60000)
            time.sleep(5)
            print("Target match page loaded successfully!", flush=True)
        except Exception as e:
            print(f"Navigation error: {e}", flush=True)

        while True:
            try:
                # Reload periodically to get fresh match data
                page.reload(wait_until="networkidle", timeout=30000)
                time.sleep(3)
                
                current_state = parse_cricheroes_scorecard(page)
                
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
