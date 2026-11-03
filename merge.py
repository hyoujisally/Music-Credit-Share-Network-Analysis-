## joining billboard data with credits data based on song and artist names, then saving to a new CSV file
import pandas as pd 

billboard_data = pd.read_csv("hot100_weekly_2010_present.csv")
credits_data = pd.read_json("credits.jsonl", lines=True)

credits_data = credits_data.rename(columns={"chart_song": "song", "chart_artist": "artist"})

merged_data = pd.merge(billboard_data, credits_data, on=["song", "artist"], how="inner")
merged_data.to_csv("merged_data.csv", index=False)