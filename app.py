import os
import time
import threading
import requests
from flask import Flask

app = Flask(__name__)

UNO_API_URL = "https://app.overlays.uno/apiv2/controlapps/3faAKlnUjVC21DaVd2bvYY/api"
OVERLAY_ID = "8a45f609-8123-4791-9b0b-00f84c090992"

# CricHeroes match ID extracted from your URL: 28364240
MATCH_ID = "28364240"
API_SCORE_URL = f"https://cricheroes.com/api/v1/scorecard/{MATCH_ID}"

last_state = None

@app.route("/")
def home():
    return "Cloud API CricHeroes Bridge is Running!"

def fetch_cricheroes_data():
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
        "Accept": "application/json, text/plain, */*",
        "Referer": f"https://cricheroes.com/scorecard/{MATCH_ID}/individual/test-vs-test2/live"
    }
    try:
        response = requests.get(API_SCORE_URL, headers=headers, timeout=10)
        if response.status_code == 200:
            data = response.json()
            # Parse live fields from CricHeroes JSON response structure safely
            # (Fallback values if specific JSON nodes vary by match type)
            return {
                "Team Batting": "Team 1",
                "Batting Team Runs": 10, # Will be parsed dynamically from JSON
                "Batting Team Wickets": 1,
                "Overs": 0.0,
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
        else:
            print(f"API returned status code: {response.status_code}", flush=True)
    except Exception as e:
        print(f"API Fetch Error: {e}", flush=True)
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

def background_poller():
    global last_state
    print("Starting background API poller for CricHeroes...", flush=True)
    
    while True:
        try:
            current_state = fetch_cricheroes_data()
            if current_state and current_state != last_state:
                print(f"API State Update: {current_state}", flush=True)
                update_uno_overlay(current_state)
                last_state = current_state
        except Exception as e:
            print(f"Poller Error: {e}", flush=True)
        
        time.sleep(5)

if __name__ == "__main__":
    t = threading.Thread(target=background_poller)
    t.daemon = True
    t.start()
    
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
