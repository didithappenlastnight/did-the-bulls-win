# bulls_bot.py
# Posts "Did the Chicago Bulls win last night?" using free BallDontLie + X API.
# Runs daily; figures out "yesterday" in America/Chicago.

import os
import sys
import requests
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from requests_oauthlib import OAuth1

# ---- Config ----
BULLS_ID = 6  # Chicago Bulls team_id in BallDontLie
BALLDONTLIE_URL = "https://balldontlie.io/api/v1/games"

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
    r = requests.get(BALLDONTLIE_URL, params=params, timeout=20)
    r.raise_for_status()
    data = r.json().get("data", [])
    if not data:
        return None
    # If there were multiple (e.g., summer league/preseason), take the first completed NBA game.
    # BallDontLie marks postseason with "postseason": True; regular season False.
    # We'll just pick the first with a final score recorded.
    for g in data:
        if g.get("status", "").lower() in ("final", "final/ot", "finished") or (
            g.get("home_team_score", 0) + g.get("visitor_team_score", 0) > 0
        ):
            return g
    return data[0]  # fallback

def format_tweet(game, date_obj):
    if game is None:
        # Off day / offseason: stay silent
        return None

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

    # "Nov 2, 2025" portable (avoid %-d for Windows)
    month = date_obj.strftime("%b")
    date_str = f"{month} {date_obj.day}, {date_obj.year}"

    # Opponent line with venue marker
    venue = "vs" if bulls_is_home else "@"
    opponent_line = f"{venue} {opp['full_name']}"

    score_line = f"Bulls {bulls_score} – {opp_score} {opp['name']}"

    tweet = f"{yes_no}\n{date_str}\n{opponent_line}\n{score_line}"
    # Trim just in case (280 char limit)
    return tweet[:280]

def post_to_x(status_text):
    if not all([API_KEY, API_SECRET, ACCESS_TOKEN, ACCESS_SECRET]):
        fail("Missing one or more Twitter credentials in environment variables.")

    auth = OAuth1(API_KEY, API_SECRET, ACCESS_TOKEN, ACCESS_SECRET)
    url = "https://api.twitter.com/1.1/statuses/update.json"
    r = requests.post(url, auth=auth, data={"status": status_text}, timeout=20)
    if r.status_code >= 400:
        fail(f"Twitter post failed [{r.status_code}]: {r.text}")
    print("Tweet posted:", r.json().get("id_str"))

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
