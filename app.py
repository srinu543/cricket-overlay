import os
import time
import threading
import requests
from bs4 import BeautifulSoup
from flask import Flask

app = Flask(__name__)

# Your overlays.uno API endpoint
UNO_API_URL = "https://app.overlays.uno/apiv2/controlapps/3faAKlnUjVC21DaVd2bvYY/api"
# Your CricBay live match URL
CRICBAY_MATCH_URL = "https://www.cricbay.com/view/31662"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}

last_state = None

@app.route("/")
def home():
    return "CricBay Overlay Bridge is Running!"

def parse_cricbay_scorecard(html_content):
    soup = BeautifulSoup(html_content, "html.parser")
    try:
        team_rows = soup.select(".px-3.py-1 > div")
        team1_name, team1_score, team1_wickets = "", "", ""
        team2_name, team2_score, team2_wickets = "", "", ""
        
        if len(team_rows) >= 1:
            r1 = team_rows[0]
            team1_name = r1.select_one(".display-6").get_text(strip=True)
            t1_score_text = r1.select_one(".display-7").get_text(strip=True)
            if "/" in t1_score_text:
                team1_score, team1_wickets = t1_score_text.split("/")
                
        if len(team_rows) >= 2:
            r2 = team_rows[1]
            team2_name = r2.select_one(".display-6").get_text(strip=True)
            t2_score_text = r2.select_one(".display-7").get_text(strip=True)
            if "/" in t2_score_text:
                team2_score, team2_wickets = t2_score_text.split("/")

        batters = soup.select(".card.p-1.mt-3 .d-flex.align-items-center.py-2")
        batter1_name, batter1_runs, batter1_balls = "", "", ""
        batter2_name, batter2_runs, batter2_balls = "", "", ""
        
        for b in batters:
            name_el = b.select_one("a.text-truncate")
            if not name_el:
                continue
            name = name_el.get_text(strip=True)
            stats = b.select(".audience-live-stat")
            if len(stats) >= 2:
                runs = stats[0].get_text(strip=True)
                balls = stats[1].get_text(strip=True)
                is_striker = b.select_one(".text-danger") is not None
                if is_striker:
                    batter1_name, batter1_runs, batter1_balls = name, runs, balls
                else:
                    batter2_name, batter2_runs, batter2_balls = name, runs, balls

        bowler_row = soup.select_one(".card.p-1.mt-2 .d-flex.align-items-center.py-2")
        bowler_name, bowler_figures = "", ""
        if bowler_row:
            b_name_el = bowler_row.select_one("a.text-truncate")
            if b_name_el:
                bowler_name = b_name_el.get_text(strip=True)
            b_stats = bowler_row.select(".audience-live-bowler-stat")
            b_wide = bowler_row.select_one(".audience-live-bowler-stat-wide")
            if len(b_stats) >= 4 and b_wide:
                overs = b_stats[0].get_text(strip=True)
                maidens = b_stats[1].get_text(strip=True)
                runs_conceded = b_stats[2].get_text(strip=True)
                wickets_taken = b_stats[3].get_text(strip=True)
                economy = b_wide.get_text(strip=True)
                bowler_figures = f"{overs}(O) - {maidens}(M) - {runs_conceded}(R) - {wickets_taken}(W) - {economy}(E)"

        return {
            "Team1Name": team1_name,
            "Team1Score": f"{team1_score}/{team1_wickets}",
            "Team2Name": team2_name,
            "Team2Score": f"{team2_score}/{team2_wickets}",
            "StrikerName": batter1_name,
            "StrikerScore": f"{batter1_runs} ({batter1_balls})",
            "NonStrikerName": batter2_name,
            "NonStrikerScore": f"{batter2_runs} ({batter2_balls})",
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
            print(f"Fetching CricBay URL: {CRICBAY_MATCH_URL}", flush=True)
            resp = requests.get(CRICBAY_MATCH_URL, headers=HEADERS, timeout=10)
            print(f"CricBay Response Status: {resp.status_code}", flush=True)
            
            if resp.status_code == 200:
                current_state = parse_cricbay_scorecard(resp.text)
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
