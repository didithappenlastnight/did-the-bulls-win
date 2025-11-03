# bulls_bot.py
# Posts "Did the Chicago Bulls win last night?" using free BallDontLie + X API (v2).
# Runs daily; figures out "yesterday" in America/Chicago.

import os
import sys
import requests
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from requests_oauthlib import OAuth1

# ---- Config ----
BULLS_ID = 6  # Chicago Bulls team_id in BallDontLie
BALLDONTLIE_URL = "https://api.balldontlie.io/v1/games"

# X (Twitter) creds come from environment variables (we set them as GitHub Secrets)
API_KEY = os.getenv("TWITTER_API_KEY")
API_SECRET = os.getenv("TWITTER_API_SECRET")
ACCESS_TOKEN = os.getenv("TWITTER_ACCESS_TOKEN")
ACCESS_SECRET = os.getenv("TWITTER_ACCESS_SECRET")

def fail(msg, code=1):
    print(msg)
    sys.exit(code)

def chicago_yesterday_date():
    tz = ZoneInfo("America/Chicago")
    now_ct = datetime.now(tz)
    yday_ct = now_ct - timedelta(days=1)
    return yday_ct.date()

def fetch_bulls_game_for(date_obj):
    params = {
        "dates[]": date_obj.isoformat(),
        "team_ids[]": BULLS_ID,
        "per_page": 100,
    }
    headers = {"Authorization": f"Bearer {os.getenv('BDL_API_KEY')}"}
    print("DEBUG requesting:", BALLDONTLIE_URL, params)
    r = requests.get(BALLDONTLIE_URL, params=params, headers=headers, timeout=20)
    r.raise_for_status()
    data = r.json().get("data", [])
    if not data:
        return None

    for g in data:
        if g.get("status", "").lower() in ("final", "final/ot", "finished") or (
            g.get("home_team_score", 0) + g.get("visitor_team_score", 0) > 0
        ):
            return g
    return data[0]  # fallback

def format_tweet(game, date_obj):
    if game is None:
        return None  # Off day / offseason

    home = game["home_team"]
    away = game["visitor_team"]
    home_score = game["home_team_score"]
    away_score = game["visitor_team_score"]

    bulls_is_home = home["id"] == BULLS_ID
    bulls_score = home_score if bulls_is_home else away_score
    opp = away if bulls_is_home else home
    opp_score = away_score if bulls_is_home else home_score

    won = bulls_score > opp_score
    yes_no = "Yes" if won else "No"

    month = date_obj.strftime("%b")
    date_str = f"{month} {date_obj.day}, {date_obj.year}"

    venue = "vs" if bulls_is_home else "@"
    opponent_line = f"{venue} {opp['full_name']}"

    score_line = f"Bulls {bulls_score} – {opp_score} {opp['name']}"

    tweet = f"{yes_no}\n{date_str}\n{opponent_line}\n{score_line}"
    return tweet[:280]

def post_to_x(status_text):
    if not all([API_KEY, API_SECRET, ACCESS_TOKEN, ACCESS_SECRET]):
        fail("Missing one or more Twitter credentials in environment variables.")

    # X API v2 endpoint (works on free tier)
    auth = OAuth1(API_KEY, API_SECRET, ACCESS_TOKEN, ACCESS_SECRET)
    url = "https://api.twitter.com/2/tweets"
    payload = {"text": status_text}
    r = requests.post(url, auth=auth, json=payload, timeout=20)
    if r.status_code >= 400:
        fail(f"Twitter post failed [{r.status_code}]: {r.text}")
    tid = r.json().get("data", {}).get("id")
    print("Tweet posted:", tid)

def main():
    ydate = chicago_yesterday_date()
    game = fetch_bulls_game_for(ydate)
    tweet = format_tweet(game, ydate)
    if tweet is None:
        print("No Bulls game yesterday — nothing to post.")
        return
    post_to_x(tweet)

if __name__ == "__main__":
    main()
