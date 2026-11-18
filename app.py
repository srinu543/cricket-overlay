import os
import time
import threading
import requests
from bs4 import BeautifulSoup
from flask import Flask
from playwright.sync_api import sync_playwright

app = Flask(__name__)

# Your overlays.uno API endpoint
UNO_API_URL = "https://app.overlays.uno/apiv2/controlapps/3faAKlnUjVC21DaVd2bvYY/api"
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
        team2_name = team_name_elements[1].get_text(strip=True) if len(team_name_elements) > 1 else "Team B"

        # Extract Overs info
        over_spans = soup.select(".styles-module-scss-module__0yl5Ha__overSpan")
        team1_overs = over_spans[0].get_text(strip=True) if len(over_spans) > 0 else "(0.0 Ov)"
        team2_overs = over_spans[1].get_text(strip=True) if len(over_spans) > 1 else "(0.0 Ov)"

        # Extract Batters
        batter_rows = soup.select(".styles-module-scss-module__Cdoeoq__table tbody tr")
        batter1_name, batter1_balls = "Batter 1", "0"
        batter2_name, batter2_balls = "Batter 2", "0"

        if len(batter_rows) >= 1:
            cols1 = batter_rows[0].select("td")
            if len(cols1) >= 3:
                batter1_name = cols1[0].get_text(strip=True)
                batter1_balls = cols1[2].get_text(strip=True)

        if len(batter_rows) >= 2:
            cols2 = batter_rows[1].select("td")
            if len(cols2) >= 3:
                batter2_name = cols2[0].get_text(strip=True)
                batter2_balls = cols2[2].get_text(strip=True)

        # Extract Bowler info
        bowler_rows = soup.select(".styles-module-scss-module__hqYHwW__wrapper tbody tr")
        bowler_name, bowler_overs = "Bowler", "0.0"
        bowler_runs, bowler_wickets, bowler_econ = "0", "0", "0.0"

        if len(bowler_rows) >= 1:
            b_cols = bowler_rows[0].select("td")
            if len(b_cols) >= 6:
                bowler_name = b_cols[0].get_text(strip=True)
                bowler_overs = b_cols[1].get_text(strip=True)
                bowler_runs = b_cols[3].get_text(strip=True)
                bowler_wickets = b_cols[4].get_text(strip=True)
                bowler_econ = b_cols[5].get_text(strip=True)

        bowler_figures = f"{bowler_overs} Ov - {bowler_runs} R - {bowler_wickets} W (Eco: {bowler_econ})"

        # Standard payload formatting matching typical overlays.uno schemas
        return {
            "Team1Name": team1_name,
            "Team1Score": team1_overs,
            "Team2Name": team2_name,
            "Team2Score": team2_overs,
            "StrikerName": f"{batter1_name} ({batter1_balls})",
            "NonStrikerName": f"{batter2_name} ({batter2_balls})",
            "BowlerName": f"{bowler_name} | {bowler_figures}"
        }
    except Exception as e:
        print(f"Parsing Error: {e}", flush=True)
        return None

def update_uno_overlay(data):
    # Depending on your overlays.uno template, content keys can be sent directly or nested
    payload = {"command": "SetOverlayContent", "content": data}
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
            
            # Wait until the dynamic team name element actually appears in the DOM
            page.wait_for_selector(".styles-module-scss-module__0yl5Ha__teamName", timeout=15000)
            print("Target match elements successfully loaded!", flush=True)
        except Exception as e:
            print(f"Navigation or selector wait error: {e}", flush=True)

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
