
'''Loading in BillBoard Data and pulling credits from Genius.'''

import subprocess
import sys
subprocess.check_call([sys.executable, "-m", "pip", "install", "requests", "lyricsgenius", "pandas"])


import token
import pandas as pd, requests
import os, re, json, time
import lyricsgenius

url = "https://raw.githubusercontent.com/mhollingshead/billboard-hot-100/main/all.json"
weeks = requests.get(url).json()
rows = [{"date": w["date"], **e} for w in weeks for e in w["data"] if w["date"] >= "2010-01-01"]
charts = pd.DataFrame(rows)
charts.to_csv("hot100_weekly_2010_present.csv", index=False)
songs = charts.groupby(["song", "artist"], as_index=False).agg(peak=("peak_position", "min"), weeks=("weeks_on_chart", "max"), first_week=("date", "min"))
songs.to_csv("hot100_unique_songs.csv", index=False)
"""
Pull producer/writer/performer credits from Genius for every song in
hot100_unique_songs.csv

"""

SONGS_FILE = "hot100_unique_songs.csv"
OUT_FILE = "credits.jsonl"      
FAIL_FILE = "failed.jsonl"
PAUSE = 0.5                     

genius = lyricsgenius.Genius("bcI2sit3Y3f5r2_3FJWeh7MFOr6VgVxbovXjNaInOPWtlXp-30SYY405taxu3vTf", timeout=15, retries=3, verbose=False)


def norm(text):
    """Lowercase and strip punctuation/brackets so titles compare cleanly."""
    text = re.sub(r"\(.*?\)|\[.*?\]", "", str(text).lower())
    return re.sub(r"[^a-z0-9 ]", "", text).strip()


def main_artist(artist):
    return re.split(r" featuring | with | & | x | and |, ", artist, flags=re.I)[0].strip()


def names(people):
    return [p["name"] for p in (people or [])]


def find_song(title, artist):
    """Search Genius and return (song_id, confident_match) or (None, False)."""
    hits = genius.search_songs(f"{title} {main_artist(artist)}")["hits"]
    results = [h["result"] for h in hits if h.get("type") == "song"]
    for r in results:
        if norm(r["title"]) == norm(title) and norm(main_artist(artist)) in norm(r["primary_artist"]["name"]):
            return r["id"], True
    return (results[0]["id"], False) if results else (None, False)


def load_done():
    done = set()
    for path in (OUT_FILE, FAIL_FILE):
        if os.path.exists(path):
            with open(path) as f:
                for line in f:
                    rec = json.loads(line)
                    done.add((rec["chart_song"], rec["chart_artist"]))
    return done


def main():
    songs = pd.read_csv(SONGS_FILE)
    done = load_done()
    todo = [r for r in songs.itertuples() if (r.song, r.artist) not in done]
    print(f"{len(done)} already done, {len(todo)} to go")

    for i, row in enumerate(todo, 1):
        try:
            song_id, confident = find_song(row.song, row.artist)
            if song_id is None:
                raise ValueError("no search results")
            s = genius.song(song_id)["song"]
            record = {
                "chart_song": row.song,
                "chart_artist": row.artist,
                "genius_id": song_id,
                "genius_title": s["title"],
                "confident_match": confident,
                "primary_artist": s["primary_artist"]["name"],
                "featured_artists": names(s.get("featured_artists")),
                "producers": names(s.get("producer_artists")),
                "writers": names(s.get("writer_artists")),
                "release_date": s.get("release_date"),
            }
            with open(OUT_FILE, "a") as f:
                f.write(json.dumps(record) + "\n")
        except Exception as e:
            with open(FAIL_FILE, "a") as f:
                f.write(json.dumps({"chart_song": row.song, "chart_artist": row.artist, "error": str(e)}) + "\n")

        if i % 25 == 0:
            print(f"{i}/{len(todo)} processed")
        time.sleep(PAUSE)

    print("Finished. Check failed.jsonl and any records with confident_match = false.")


if __name__ == "__main__":
    main()