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
        # Extract Team Names from scorecard header
        team_name_elements = soup.select(".styles-module-scss-module__0yl5Ha__teamName")
        team1_name = team_name_elements[0].get_text(strip=True) if len(team_name_elements) > 0 else "Team 1"

        # Extract Overs info
        over_spans = soup.select(".styles-module-scss-module__0yl5Ha__overSpan")
        overs_text = over_spans[0].get_text(strip=True) if len(over_spans) > 0 else "0.0"
        clean_overs = overs_text.replace("(", "").replace(" Ov)", "").strip()

        # Extract score elements directly from the live scorecard score container
        # CricHeroes typically renders scores in elements with run/wicket containers or score headers
        score_elements = soup.select(".styles-module-scss-module__0yl5Ha__teamScore, .score-details, span[class*='teamScore']")
        
        runs = 0
        wickets = 0

        if len(score_elements) > 0:
            score_text = score_elements[0].get_text(strip=True) # e.g., "10/1" or "3/0"
            if "/" in score_text:
                parts = score_text.split("/")
                runs = int(parts[0].strip() or 0)
                wickets = int(parts[1].strip() or 0)
            else:
                try:
                    runs = int(score_text)
                except ValueError:
                    pass

        # If specific score elements aren't caught by class, fallback to parsing active scorecard summary text
        if runs == 0:
            summary_divs = soup.select("div[class*='scoreCard'], div[class*='matchHeader']")
            for div in summary_divs:
                text = div.get_text()
                if "/" in text and ("Ov" in text or "Overs" in text):
                    # Attempt to locate score pattern like 10/1
                    words = text.split()
                    for w in words:
                        if "/" in w and w.replace("/", "").isdigit():
                            r, wkt = w.split("/")
                            runs, wickets = int(r), int(wkt)
                            break

        # Extract Batters
        batter_rows = soup.select(".styles-module-scss-module__Cdoeoq__table tbody tr")
        batter1_name, batter1_runs = "Batter 1", 0
        batter2_name, batter2_runs = "Batter 2", 0

        if len(batter_rows) >= 1:
            cols1 = batter_rows[0].select("td")
            if len(cols1) >= 3:
                batter1_name = cols1[0].get_text(strip=True).replace("*", "")
                try:
                    batter1_runs = int(cols1[1].get_text(strip=True) or 0)
                except ValueError:
                    pass

        if len(batter_rows) >= 2:
            cols2 = batter_rows[1].select("td")
            if len(cols2) >= 3:
                batter2_name = cols2[0].get_text(strip=True).replace("*", "")
                try:
                    batter2_runs = int(cols2[1].get_text(strip=True) or 0)
                except ValueError:
                    pass

        # Extract Bowler info
        bowler_rows = soup.select(".styles-module-scss-module__hqYHwW__wrapper tbody tr")
        bowler_name, bowler_overs_val, bowler_runs_val, bowler_wickets_val = "Bowler", 0.0, 0, 0

        if len(bowler_rows) >= 1:
            b_cols = bowler_rows[0].select("td")
            if len(b_cols) >= 6:
                bowler_name = b_cols[0].get_text(strip=True).replace("*", "")
                bowler_overs_val = float(b_cols[1].get_text(strip=True) or 0.0)
                bowler_runs_val = int(b_cols[3].get_text(strip=True) or 0)
                bowler_wickets_val = int(b_cols[4].get_text(strip=True) or 0)

        return {
            "Team Batting": team1_name,
            "Batting Team Runs": int(runs),
            "Batting Team Wickets": int(wickets),
            "Overs": float(clean_overs) if clean_overs else 0.0,
            "Bastman 1": batter1_name,
            "Batsman 1 Score": batter1_runs,
            "Batsman 2": batter2_name,
            "Batsman 2 Score": batter2_runs,
            "Bowler Name": bowler_name,
            "Bowler Overs": bowler_overs_val,
            "Bowler Runs": bowler_runs_val,
            "Bowler Wickets": str(bowler_wickets_val),
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
            page.goto(TARGET_MATCH_URL, wait_until="domcontentloaded", timeout=60000)
            time.sleep(6)
            print("Target match page loaded successfully!", flush=True)
        except Exception as e:
            print(f"Navigation error: {e}", flush=True)

        while True:
            try:
                page.reload(wait_until="domcontentloaded", timeout=30000)
                time.sleep(3)
                
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
