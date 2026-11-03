"""
Animate the Hot 100 creator network from 2010 to the present 
"""
import ast
import re
from itertools import combinations

import imageio.v2 as imageio
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patheffects as pe
from matplotlib.collections import LineCollection
from matplotlib.lines import Line2D
import networkx as nx
import numpy as np
import pandas as pd

# ---------------- settings you might change ----------------
DATA_FILE = "clean_data.csv"
OUTPUT = "network_animation.mp4"
MAKE_GIF = False             
INCLUDE_PERFORMERS = True    # False = song credits only (producers + writers)
TOP_PER_YEAR = 150           # people per year eligible to appear (by betweenness)
LABELS_PER_YEAR = 10         # names shown each year
HOLD_FRAMES = 18             # frames paused on each year
TWEEN_FRAMES = 18            # frames of smooth transition between years
FPS = 24
COLORS = {
    "hybrid": "#E4572E",
    "producer": "#2E86AB",
    "writer": "#8E5BAA",
    "performer": "#9AA0A6",
}
# -----------------------------------------------------------


def to_list(x):
    if isinstance(x, list):
        return x
    try:
        return ast.literal_eval(x) if isinstance(x, str) and x.startswith("[") else []
    except (ValueError, SyntaxError):
        return []


def split_performers(artist):
    parts = re.split(r" featuring | with | & | x |, ", str(artist), flags=re.I)
    return [p.strip() for p in parts if p.strip()]


def role_type(roles):
    if len(roles) >= 2:
        return "hybrid"
    return next(iter(roles))


def centralization(btw):
    n = len(btw)
    if n < 3:
        return 0.0
    top = max(btw.values())
    return sum(top - c for c in btw.values()) / (n - 1)


# --------------------
print("Loading data...")
df = pd.read_csv(DATA_FILE, parse_dates=["date"])
df["producers"] = df["producers"].apply(to_list)
df["writers"] = df["writers"].apply(to_list)
last_date = df["date"].max()

years, graphs, roles_by_year, btw_by_year, cent_by_year = [], {}, {}, {}, {}

for year, year_data in df.groupby(df["date"].dt.year):
    year_data = year_data.drop_duplicates(subset=["song", "artist"])
    G = nx.Graph()
    roles = {}
    for row in year_data.itertuples():
        people = {}
        if INCLUDE_PERFORMERS:
            for name in split_performers(row.artist):
                people.setdefault(name, set()).add("performer")
        for name in row.producers:
            people.setdefault(name, set()).add("producer")
        for name in row.writers:
            people.setdefault(name, set()).add("writer")
        for name, r in people.items():
            roles.setdefault(name, set()).update(r)
            G.add_node(name)
        for a, b in combinations(people, 2):
            if G.has_edge(a, b):
                G[a][b]["weight"] += 1
            else:
                G.add_edge(a, b, weight=1)
    if G.number_of_nodes() < 3:
        continue
    print(f"  {year}: {G.number_of_nodes()} people, computing betweenness...")
    btw = nx.betweenness_centrality(G)
    years.append(year)
    graphs[year] = G
    roles_by_year[year] = {p: role_type(r) for p, r in roles.items()}
    btw_by_year[year] = btw
    cent_by_year[year] = centralization(btw)

# ---------------------------------
visible = {}
for y in years:
    ranked = sorted(btw_by_year[y], key=btw_by_year[y].get, reverse=True)
    visible[y] = set(ranked[:TOP_PER_YEAR])
everyone = set().union(*visible.values())

union = nx.Graph()
union.add_nodes_from(everyone)
for y in years:
    for a, b, d in graphs[y].edges(data=True):
        if a in everyone and b in everyone:
            w = union[a][b]["weight"] + d["weight"] if union.has_edge(a, b) else d["weight"]
            union.add_edge(a, b, weight=w)

print(f"Computing one shared layout for {len(everyone)} people...")
pos = nx.spring_layout(union, k=1.8 / np.sqrt(len(union)), iterations=150, weight="weight", seed=42)
names = sorted(everyone)
idx = {p: i for i, p in enumerate(names)}
xy = np.array([pos[p] for p in names])

global_max = max(max(btw_by_year[y][p] for p in visible[y]) for y in years)


def year_state(y):
    sizes = np.zeros(len(names))
    colors = np.array([COLORS["performer"]] * len(names), dtype=object)
    for p in visible[y]:
        sizes[idx[p]] = 12 + 1600 * np.sqrt(btw_by_year[y][p] / global_max)
        colors[idx[p]] = COLORS[roles_by_year[y][p]]
    edges = [(xy[idx[a]], xy[idx[b]]) for a, b in graphs[y].edges()
             if a in visible[y] and b in visible[y]]
    top = sorted(visible[y], key=btw_by_year[y].get, reverse=True)[:LABELS_PER_YEAR]
    return sizes, colors, edges, top


states = {y: year_state(y) for y in years}


def year_label(y):
    if y == last_date.year and last_date.month < 12:
        return f"{y} (through {last_date.strftime('%b %d')})"
    return str(y)


# --------------------
fig = plt.figure(figsize=(12, 9), dpi=100, facecolor="white")
ax = fig.add_axes([0.02, 0.2, 0.96, 0.78])
chart = fig.add_axes([0.08, 0.05, 0.62, 0.11])
pad = 0.08
xmin, ymin = xy.min(axis=0) - pad
xmax, ymax = xy.max(axis=0) + pad

legend_items = [Line2D([0], [0], marker="o", color="w", markerfacecolor=c, markersize=9, label=r)
                for r, c in COLORS.items() if INCLUDE_PERFORMERS or r != "performer"]
cent_values = [cent_by_year[y] for y in years]


def draw(frac_year, a_year, b_year, t):
    """t = 0 shows a_year, t = 1 shows b_year, values in between blend them."""
    ax.clear()
    ax.set_xlim(xmin, xmax)
    ax.set_ylim(ymin, ymax)
    ax.axis("off")

    sa, ca, ea, topa = states[a_year]
    sb, cb, eb, topb = states[b_year]

    if ea and t < 1:
        ax.add_collection(LineCollection(ea, colors="#555555", linewidths=0.4, alpha=0.12 * (1 - t)))
    if eb and t > 0 and b_year != a_year:
        ax.add_collection(LineCollection(eb, colors="#555555", linewidths=0.4, alpha=0.12 * t))

    sizes = sa * (1 - t) + sb * t
    colors = cb if t >= 0.5 else ca
    show = sizes > 1
    ax.scatter(xy[show, 0], xy[show, 1], s=sizes[show], c=list(colors[show]),
               edgecolors="white", linewidths=0.5, alpha=0.9, zorder=3)

    label_set, label_alpha = (topa, 1 - 2 * t) if t < 0.5 else (topb, 2 * t - 1)
    label_year = a_year if t < 0.5 else b_year
    for p in label_set:
        x, y = xy[idx[p]]
        ax.text(x, y + 0.02, p.replace("$", r"\$"), fontsize=9, ha="center", va="bottom", zorder=4,
                alpha=max(label_alpha, 0), color="#222222", fontweight="bold",
                path_effects=[pe.withStroke(linewidth=3, foreground="white")])

    ax.text(0.01, 0.97, year_label(label_year), transform=ax.transAxes,
            fontsize=30, fontweight="bold", color="#222222", va="top")
    ax.text(0.01, 0.89, "Billboard Hot 100 creator network  ·  node size = betweenness centrality",
            transform=ax.transAxes, fontsize=10, color="#666666", va="top")
    ax.legend(handles=legend_items, loc="upper right", frameon=False, fontsize=10)

    chart.clear()
    chart.plot(years, cent_values, color="#222222", linewidth=1.5)
    current = np.interp(frac_year, years, cent_values)
    chart.scatter([frac_year], [current], color=COLORS["hybrid"], s=40, zorder=3)
    chart.axvline(frac_year, color=COLORS["hybrid"], linewidth=0.8, alpha=0.6)
    chart.set_title("Betweenness centralization", fontsize=9, loc="left", color="#444444")
    chart.tick_params(labelsize=8)
    chart.set_xticks(years[::2])
    for side in ("top", "right"):
        chart.spines[side].set_visible(False)

    fig.canvas.draw()
    return np.asarray(fig.canvas.buffer_rgba())[:, :, :3].copy()


print("Rendering frames...")
frames = []
for i, y in enumerate(years):
    for _ in range(HOLD_FRAMES):
        frames.append(draw(y, y, y, 0))
    if i + 1 < len(years):
        nxt = years[i + 1]
        for f in range(1, TWEEN_FRAMES + 1):
            t = f / TWEEN_FRAMES
            t_smooth = t * t * (3 - 2 * t)          # transition 
            frames.append(draw(y + t, y, nxt, t_smooth))
    print(f"  {y} done")

for _ in range(HOLD_FRAMES * 2):                   
    frames.append(frames[-1])

print(f"Writing {OUTPUT} ({len(frames)} frames)...")
imageio.mimsave(OUTPUT, frames, fps=FPS, macro_block_size=1)
if MAKE_GIF:
    imageio.mimsave(OUTPUT.replace(".mp4", ".gif"), frames[::2], duration=2 / FPS)
print("Done.")