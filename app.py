import os
import time
import threading
import requests
from bs4 import BeautifulSoup
from flask import Flask

app = Flask(__name__)

# Your overlays.uno API endpoint
UNO_API_URL = "https://app.overlays.uno/apiv2/controlapps/3faAKlnUjVC21DaVd2bvYY/api"
# Your live CricHeroes match URL
CRICHEROES_MATCH_URL = "https://cricheroes.com/scorecard/28364240/individual/test-vs-test2/live"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}

last_state = None

@app.route("/")
def home():
    return "CricHeroes Overlay Bridge is Running!"

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

        # Extract Batters from the live scorecard table
        batter_rows = soup.select(".styles-module-scss-module__Cdoeoq__table tbody tr")
        batter1_name, batter1_runs, batter1_balls = "Batter 1", "0", "0"
        batter2_name, batter2_runs, batter2_balls = "Batter 2", "0", "0"

        if len(batter_rows) >= 1:
            cols1 = batter_rows[0].select("td")
            if len(cols1) >= 3:
                batter1_name = cols1[0].get_text(strip=True)
                # CricHeroes uses canvas for runs, but balls is plain text in col 2
                batter1_balls = cols1[2].get_text(strip=True)

        if len(batter_rows) >= 2:
            cols2 = batter_rows[1].select("td")
            if len(cols2) >= 3:
                batter2_name = cols2[0].get_text(strip=True)
                batter2_balls = cols2[2].get_text(strip=True)

        # Extract Bowler info from the second table
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

        return {
            "Team1Name": team1_name,
            "Team1Score": f"Score {team1_overs}",
            "Team2Name": team2_name,
            "Team2Score": f"Score {team2_overs}",
            "StrikerName": batter1_name,
            "StrikerScore": f"B: {batter1_balls}",
            "NonStrikerName": batter2_name,
            "NonStrikerScore": f"B: {batter2_balls}",
            "BowlerName": bowler_name,
            "BowlerFigures": bowler_figures
        }
    except Exception as e:
        print(f"Parsing Error: {e}", flush=True)
        return None

def update_uno_overlay(data):
    payload = {"command": "SetOverlayContent", "content": data}
    try:
        response = requests.put(UNO_API_URL, json=payload, timeout=5)
        print(f"Overlay Update Response Status: {response.status_code}", flush=True)
    except Exception as e:
        print(f"API Request Error: {e}", flush=True)

def background_scraper():
    global last_state
    print("Background scraper thread started successfully.", flush=True)
    while True:
        try:
            print(f"Fetching CricHeroes URL: {CRICHEROES_MATCH_URL}", flush=True)
            resp = requests.get(CRICHEROES_MATCH_URL, headers=HEADERS, timeout=10)
            print(f"CricHeroes Response Status: {resp.status_code}", flush=True)
            
            if resp.status_code == 200:
                current_state = parse_cricheroes_scorecard(resp.text)
                print(f"Parsed State: {current_state}", flush=True)
                
                if current_state and current_state != last_state:
                    update_uno_overlay(current_state)
                    last_state = current_state
        except Exception as e:
            print(f"CRITICAL SCRAPER ERROR: {e}", flush=True)
        time.sleep(5)

if __name__ == "__main__":
    t = threading.Thread(target=background_scraper)
    t.daemon = True
    t.start()
    
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
