# cleaning column names and organizing merged data

import pandas as pd 

merged_data = pd.read_csv('merged_data.csv')

merged_data.columns = (merged_data.columns.str.strip().str.lower()
                       .str.replace(' ', '_').str.replace('(', '', regex=False).str.replace(')', '', regex=False))

merged_data['date'] = pd.to_datetime(merged_data['date'], format='%Y-%m-%d')
merged_data['year'] = merged_data['date'].dt.year

merged_data = merged_data[['date', 'year', 'song', 'artist', 'this_week', 'peak_position', 'weeks_on_chart', 'producers', 'writers']]
merged_data.to_csv('clean_data.csv', index=False)