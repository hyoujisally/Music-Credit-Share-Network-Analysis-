"""
  performer-creator : performed AND wrote or produced   (the role blurring you're testing)
  producer-writer   : produced and wrote, didn't perform (standard producer credit)
  producer / writer / performer : one role only

"""
import ast
import re
from itertools import combinations

import networkx as nx
import pandas as pd

TOP_N = 25   # size of the "center" group (top N people by betweenness)

clean = pd.read_csv('clean_data.csv', parse_dates=['date'])
to_list = lambda x: ast.literal_eval(x) if isinstance(x, str) and x.startswith('[') else []
clean['producers'] = clean['producers'].apply(to_list)
clean['writers'] = clean['writers'].apply(to_list)


def split_performers(artist):
    parts = re.split(r" featuring | with | & | x |, ", str(artist), flags=re.I)
    return [p.strip() for p in parts if p.strip()]


def role_type(r):
    if 'performer' in r and ('producer' in r or 'writer' in r):
        return 'performer-creator'
    if 'producer' in r and 'writer' in r:
        return 'producer-writer'
    return next(iter(r))


rows = []
seen_before = set()

for year, year_data in clean.groupby(clean['date'].dt.year):
    year_data = year_data.drop_duplicates(subset=['song', 'artist'])
    G = nx.Graph()
    roles = {}

    self_produced = 0


    for row in year_data.itertuples():
        people = {}
        for name in split_performers(row.artist):
            people.setdefault(name, set()).add('performer')
        for name in row.producers:
            people.setdefault(name, set()).add('producer')
        for name in row.writers:
            people.setdefault(name, set()).add('writer')
        if set(split_performers(row.artist)) & set(row.producers):
            self_produced += 1
        for name, r in people.items():
            roles.setdefault(name, set()).update(r)
            G.add_node(name)
        G.add_edges_from(combinations(people, 2))

    n = G.number_of_nodes()
    if n < 3:
        continue

    btw = nx.betweenness_centrality(G)
    centralization = sum(max(btw.values()) - c for c in btw.values()) / (n - 1)
    types = {p: role_type(r) for p, r in roles.items()}
    top = sorted(btw, key=btw.get, reverse=True)[:TOP_N]

    performers = [p for p, r in roles.items() if 'performer' in r]
    newcomers = set(roles) - seen_before
    seen_before |= set(roles)

    share = lambda group, t: sum(types[p] == t for p in group) / len(group)

    rows.append({
        'year': year,
        'songs': len(year_data),
        'people': n,
        'betweenness_centralization': round(centralization, 4),
        'performer_creator_share': round(share(types, 'performer-creator'), 4),
        'producer_writer_share': round(share(types, 'producer-writer'), 4),
        f'performer_creator_share_top{TOP_N}': round(share(top, 'performer-creator'), 4),
        f'producer_writer_share_top{TOP_N}': round(share(top, 'producer-writer'), 4),
        'performers_who_also_create': round(
            sum(types[p] == 'performer-creator' for p in performers) / len(performers), 4)
            if performers else 0,
        'producers_who_also_perform': round(sum('performer' in roles[p] for p in roles if 'producer' in roles[p]) / max(1, sum('producer' in r for r in roles.values())), 4),
        'self_produced_song_share': round(self_produced / len(year_data), 4),
        'avg_writers_per_song': round(year_data['writers'].apply(len).mean(), 2),
        'newcomer_rate': round(len(newcomers) / n, 4) if year != clean['date'].dt.year.min() else None,
    })
    print(f'{year} done')

metrics = pd.DataFrame(rows)
metrics.to_csv('role_metrics.csv', index=False)
print(metrics.to_string(index=False))