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

def parse_cricheroes_scorecard(html_content):
    soup = BeautifulSoup(html_content, "html.parser")
    try:
        body_text = soup.get_text()
        
        # If still blocked, return defaults
        if "you have been blocked" in body_text.lower():
            print("Cloudflare block page detected!", flush=True)
            return None

        # Extract Overs info
        over_spans = soup.select(".styles-module-scss-module__0yl5Ha__overSpan")
        overs_text = over_spans[0].get_text(strip=True) if len(over_spans) > 0 else "0.0"
        clean_overs = overs_text.replace("(", "").replace(" Ov)", "").strip()

        # Extract Team Names
        team_name_elements = soup.select(".styles-module-scss-module__0yl5Ha__teamName")
        team1_name = team_name_elements[0].get_text(strip=True) if len(team_name_elements) > 0 else "Team 1"

        # Parse score elements
        score_elements = soup.select(".styles-module-scss-module__0yl5Ha__teamScore, .score-details, span[class*='teamScore']")
        runs = 0
        wickets = 0

        if len(score_elements) > 0:
            score_text = score_elements[0].get_text(strip=True)
            if "/" in score_text:
                parts = score_text.split("/")
                runs = int(parts[0].strip() or 0)
                wickets = int(parts[1].strip() or 0)

        # Fallback scan in page text if specific selectors miss
        if runs == 0:
            for line in body_text.split("\n"):
                line = line.strip()
                if "/" in line and len(line) < 10 and line.replace("/", "").isdigit():
                    parts = line.split("/")
                    runs = int(parts[0])
                    wickets = int(parts[1])
                    break

        return {
            "Team Batting": team1_name,
            "Batting Team Runs": runs,
            "Batting Team Wickets": wickets,
            "Overs": float(clean_overs) if clean_overs else 0.0,
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
        # Launch with stealth arguments to prevent Cloudflare bot detection
        browser = p.chromium.launch(
            headless=True,
            args=[
                "--disable-dev-shm-usage",
                "--no-sandbox",
                "--disable-blink-features=AutomationControlled",
                "--start-maximized"
            ]
        )
        
        # Create context with standard desktop User-Agent
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
            viewport={"width": 1920, "height": 1080}
        )
        page = context.new_page()
        
        print(f"Navigating to Target Match: {TARGET_MATCH_URL}", flush=True)
        try:
            page.goto(TARGET_MATCH_URL, wait_until="domcontentloaded", timeout=60000)
            time.sleep(8) # Allow Cloudflare challenge script to resolve naturally
            print("Target match page loaded successfully!", flush=True)
        except Exception as e:
            print(f"Navigation error: {e}", flush=True)

        while True:
            try:
                page.reload(wait_until="domcontentloaded", timeout=30000)
                time.sleep(4)
                
                html_content = page.content()
                current_state = parse_cricheroes_scorecard(html_content)
                
                if current_state and current_state != last_state:
                    print(f"Parsed State Update: {current_state}", flush=True)
                    update_uno_overlay(current_state)
                    last_state = current_state
            except Exception as e:
                print(f"Scraper Loop Error: {e}", flush=True)
            
            time.sleep(6)

if __name__ == "__main__":
    t = threading.Thread(target=background_scraper)
    t.daemon = True
    t.start()
    
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
