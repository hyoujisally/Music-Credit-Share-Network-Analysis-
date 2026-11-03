import ast
import re
from itertools import combinations

import pandas as pd
import networkx as nx

# load data and convert text back into real dates and lists
clean = pd.read_csv('clean_data.csv', parse_dates=['date'])

to_list = lambda x: ast.literal_eval(x) if isinstance(x, str) and x.startswith('[') else []
clean['producers'] = clean['producers'].apply(to_list)
clean['writers'] = clean['writers'].apply(to_list)


def split_performers(artist):
    """'Zach Bryan Featuring Lana Del Rey' -> ['Zach Bryan', 'Lana Del Rey']"""
    parts = re.split(r" featuring | with | & | x |, ", str(artist), flags=re.I)
    return [p.strip() for p in parts if p.strip()]


historical_data = []

# one network per year
for year, year_data in clean.groupby(clean['date'].dt.year):

    creator_graph = nx.Graph()
    group_cols = ['song', 'artist'] if 'artist' in year_data.columns else ['song']

    # grouping by song means each song counts once, no matter how many weeks it charted
    for track_keys, song_group in year_data.groupby(group_cols):
        producers = list({p for lst in song_group['producers'] for p in lst})
        writers = list({w for lst in song_group['writers'] for w in lst})
        performers = split_performers(song_group['artist'].iloc[0]) if 'artist' in song_group.columns else []

        all_creators = list(set(producers + writers + performers))
        for creator in all_creators:
            if not creator_graph.has_node(creator):
                creator_graph.add_node(creator, is_producer=False, is_writer=False, is_performer=False)

            if creator in producers:
                creator_graph.nodes[creator]['is_producer'] = True
            if creator in writers:
                creator_graph.nodes[creator]['is_writer'] = True
            if creator in performers:
                creator_graph.nodes[creator]['is_performer'] = True

        for creator1, creator2 in combinations(all_creators, 2):
            creator1_prod = creator1 in producers
            creator2_prod = creator2 in producers
            creator1_writer = creator1 in writers
            creator2_writer = creator2 in writers

            if (creator1_prod and creator2_prod) and (creator1_writer and creator2_writer):
                edge_role = "all_collab"
            elif creator1_prod and creator2_prod:
                edge_role = "producer_collab"
            elif creator1_writer and creator2_writer:
                edge_role = "writer_collab"
            elif (creator1_prod or creator1_writer) and (creator2_prod or creator2_writer):
                edge_role = "producer_writer_collab"
            else:
                edge_role = "performer_creator_collab"   # at least one side only performed

            if creator_graph.has_edge(creator1, creator2):
                creator_graph[creator1][creator2]['weight'] += 1
            else:
                creator_graph.add_edge(creator1, creator2, weight=1, collab_type=edge_role)

    if len(creator_graph) > 2:
        # concentration of influence
        btw = nx.betweenness_centrality(creator_graph)
        n = len(creator_graph)
        centralization = sum(max(btw.values()) - c for c in btw.values()) / (n - 1)

        density = nx.density(creator_graph)
        edge_types = nx.get_edge_attributes(creator_graph, 'collab_type')
        bridge_count = sum(1 for t in edge_types.values() if t == "producer_writer_collab")

        # role blurring: people holding two or more roles this year
        hybrids = [
            c for c, d in creator_graph.nodes(data=True)
            if d['is_producer'] + d['is_writer'] + d['is_performer'] >= 2
        ]
        top10 = sorted(btw, key=btw.get, reverse=True)[:10]

        for c, d in creator_graph.nodes(data=True):
            roles = d['is_producer'] + d['is_writer'] + d['is_performer']
            d['role_type'] = 'hybrid' if roles >= 2 else 'producer' if d['is_producer'] else 'writer' if d['is_writer'] else 'performer'
        nx.set_node_attributes(creator_graph, btw, 'betweenness')
        nx.write_gexf(creator_graph, f'network_{year}.gexf')

        historical_data.append({
            'Year': year,
            'Total_Creators': n,
            'Network_Density': round(density, 4),
            'Producer_Writer_Bridges': bridge_count,
            'Betweenness_Centralization': round(centralization, 4),
            'Hybrid_Share': round(len(hybrids) / n, 4),
            'Hybrid_Share_Top10': sum(c in hybrids for c in top10) / 10,
        })

timeline_df = pd.DataFrame(historical_data)
print(timeline_df)
timeline_df.to_csv('timeline_metrics.csv', index=False)

