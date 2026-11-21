#!/usr/bin/env python3
"""Draw contributions.svg: the repositories you don't own where you have opened pull requests.

Usage: python3 contributions.py <github-user> <output.svg>
Reads GITHUB_TOKEN from the environment (the workflow's token is enough). Standard library only.
"""
import base64
import json
import math
import os
import sys
import urllib.parse
import urllib.request
from html import escape

MAX_REPOS = 6
TILE_W, TILE_H, GAP = 410, 76, 16

# GitHub Octicons (MIT): star, git-merge, git-pull-request.
STAR = "M8 .25a.75.75 0 01.673.418l1.882 3.815 4.21.612a.75.75 0 01.416 1.279l-3.046 2.97.719 4.192a.75.75 0 01-1.088.791L8 12.347l-3.766 1.98a.75.75 0 01-1.088-.79l.72-4.194L.818 6.374a.75.75 0 01.416-1.28l4.21-.611L7.327.668A.75.75 0 018 .25zm0 2.445L6.615 5.5a.75.75 0 01-.564.41l-3.097.45 2.24 2.184a.75.75 0 01.216.664l-.528 3.084 2.769-1.456a.75.75 0 01.698 0l2.77 1.456-.53-3.084a.75.75 0 01.216-.664l2.24-2.183-3.096-.45a.75.75 0 01-.564-.41L8 2.694v.001z"
MERGE = "M5.45 5.154A4.25 4.25 0 0 0 9.25 7.5h1.378a2.251 2.251 0 1 1 0 1.5H9.25A5.734 5.734 0 0 1 5 7.123v3.505a2.25 2.25 0 1 1-1.5 0V5.372a2.25 2.25 0 1 1 1.95-.218ZM4.25 13.5a.75.75 0 1 0 0-1.5.75.75 0 0 0 0 1.5Zm8.5-4.5a.75.75 0 1 0 0-1.5.75.75 0 0 0 0 1.5ZM5 3.25a.75.75 0 1 0 0 .005V3.25Z"
PR = "M7.177 3.073L9.573.677A.25.25 0 0110 .854v4.792a.25.25 0 01-.427.177L7.177 3.427a.25.25 0 010-.354zM3.75 2.5a.75.75 0 100 1.5.75.75 0 000-1.5zm-2.25.75a2.25 2.25 0 113 2.122v5.256a2.251 2.251 0 11-1.5 0V5.372A2.25 2.25 0 011.5 3.25zM11 2.5h-1V4h1a1 1 0 011 1v5.628a2.251 2.251 0 101.5 0V5A2.5 2.5 0 0011 2.5zm1 10.25a.75.75 0 111.5 0 .75.75 0 01-1.5 0zM3.75 12a.75.75 0 100 1.5.75.75 0 000-1.5z"

# Colours that read on both GitHub's light and dark themes.
BLUE, MUTED, PURPLE, GREEN = "#2f81f7", "#8b949e", "#a371f7", "#3fb950"
BORDER = "rgba(139,148,158,0.35)"


def fetch(url, api=True):
    headers = {"User-Agent": "profile-cards"}
    if api:
        headers["Accept"] = "application/vnd.github+json"
        if os.environ.get("GITHUB_TOKEN"):
            headers["Authorization"] = "Bearer " + os.environ["GITHUB_TOKEN"]
    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req, timeout=30) as resp:
        body = resp.read()
        return (json.loads(body) if api else body), resp.headers.get("Content-Type", "")


def count_prs(user, extra):
    counts, page = {}, 1
    while True:
        query = urllib.parse.quote(f"is:pr author:{user} -user:{user} {extra}")
        data, _ = fetch(f"https://api.github.com/search/issues?q={query}&per_page=100&page={page}")
        for item in data["items"]:
            repo = item["repository_url"].split("/repos/", 1)[1]
            counts[repo] = counts.get(repo, 0) + 1
        if len(data["items"]) < 100 or page * 100 >= min(data["total_count"], 1000):
            return counts
        page += 1


def short(n):
    if n >= 1000:
        value = f"{n / 1000:.1f}".rstrip("0").rstrip(".")
        return value + "k"
    return str(n)


def icon(path, x, y, color):
    return f'<svg x="{x}" y="{y}" width="14" height="14" viewBox="0 0 16 16"><path fill="{color}" fill-rule="evenodd" d="{path}"/></svg>'


def tile(i, x, y, repo):
    owner, name = repo["full_name"].split("/", 1)
    if len(repo["full_name"]) > 34:
        name = name[: max(4, 33 - len(owner))] + "…"
    parts = [
        f'<a href="https://github.com/{escape(repo["full_name"])}">',
        f'<rect x="{x + 0.5}" y="{y + 0.5}" width="{TILE_W - 1}" height="{TILE_H - 1}" rx="10" fill="rgba(139,148,158,0.06)" stroke="{BORDER}"/>',
        f'<clipPath id="a{i}"><circle cx="{x + 38}" cy="{y + 38}" r="22"/></clipPath>',
        f'<image href="{repo["avatar"]}" x="{x + 16}" y="{y + 16}" width="44" height="44" clip-path="url(#a{i})"/>',
        f'<text x="{x + 74}" y="{y + 33}" class="name"><tspan fill="{MUTED}">{escape(owner)}/</tspan><tspan font-weight="700">{escape(name)}</tspan></text>',
    ]
    cx, cy = x + 74, y + 45
    meta = [(STAR, MUTED, short(repo["stars"]))]
    if repo["merged"]:
        meta.append((MERGE, PURPLE, f'{repo["merged"]} PR{"s" if repo["merged"] != 1 else ""} merged'))
    if repo["open"]:
        meta.append((PR, GREEN, f'{repo["open"]} in review'))
    for path, color, label in meta:
        parts.append(icon(path, cx, cy, color))
        parts.append(f'<text x="{cx + 19}" y="{cy + 11.5}" class="meta">{escape(label)}</text>')
        cx += 19 + int(len(label) * 7.2) + 18
    parts.append("</a>")
    return "".join(parts)


def main():
    user, out = sys.argv[1], sys.argv[2]
    merged = count_prs(user, "is:merged")
    opened = count_prs(user, "is:open")
    repos = []
    for full_name in set(merged) | set(opened):
        info, _ = fetch(f"https://api.github.com/repos/{full_name}")
        avatar, ctype = fetch(info["owner"]["avatar_url"] + "&s=88", api=False)
        repos.append({
            "full_name": info["full_name"],
            "stars": info["stargazers_count"],
            "merged": merged.get(full_name, 0),
            "open": opened.get(full_name, 0),
            "avatar": f"data:{ctype.split(';')[0] or 'image/png'};base64,{base64.b64encode(avatar).decode()}",
        })
    repos.sort(key=lambda r: (-r["merged"], -r["stars"], r["full_name"].lower()))
    repos = repos[:MAX_REPOS]

    cols = 1 if len(repos) <= 1 else 2
    rows = max(1, math.ceil(len(repos) / cols))
    width = cols * TILE_W + (cols - 1) * GAP
    height = rows * TILE_H + (rows - 1) * GAP
    tiles = [
        tile(i, (i % cols) * (TILE_W + GAP), (i // cols) * (TILE_H + GAP), r)
        for i, r in enumerate(repos)
    ]
    if not repos:
        tiles = [f'<text x="16" y="44" class="meta">No pull requests to other repositories yet.</text>']

    svg = f'''<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}" role="img">
<title>Open source contributions by {escape(user)}</title>
<style>
.name {{ font: 400 15px -apple-system, BlinkMacSystemFont, "Segoe UI", "Noto Sans", Helvetica, Arial, sans-serif; fill: {BLUE}; }}
.meta {{ font: 400 12.5px -apple-system, BlinkMacSystemFont, "Segoe UI", "Noto Sans", Helvetica, Arial, sans-serif; fill: {MUTED}; }}
</style>
{"".join(tiles)}
</svg>
'''
    os.makedirs(os.path.dirname(out) or ".", exist_ok=True)
    with open(out, "w", encoding="utf-8") as f:
        f.write(svg)
    print(f"{out}: {len(repos)} repositories")


if __name__ == "__main__":
    main()
