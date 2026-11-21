#!/usr/bin/env python3
"""Rewrite the auto-generated parts of README.md from your GitHub data.

Usage: python3 update_readme.py <github-user> <README.md>
Environment:
  GITHUB_TOKEN  token for the GitHub API (the workflow's token is enough)
  HIDE_REPOS    comma-separated repository names to leave out of "Projects"

Sections it fills (everything else in the README is left alone):
  <!-- lately:start --> ... <!-- lately:end -->      what you pushed to or sent pull requests to recently
  <!-- projects:start --> ... <!-- projects:end -->  your newest public repositories, with their descriptions

A repository shows up in "Projects" when it is yours, public, not a fork, not archived, has a
description and is not listed in HIDE_REPOS. The newest pushes come first.
"""
import datetime as dt
import json
import os
import re
import sys
import urllib.error
import urllib.parse
import urllib.request

MAX_PROJECTS = 4
LATELY_DAYS = 45
MIN_LANGUAGE_SHARE = 0.03


def api(path):
    headers = {"User-Agent": "profile-cards", "Accept": "application/vnd.github+json"}
    if os.environ.get("GITHUB_TOKEN"):
        headers["Authorization"] = "Bearer " + os.environ["GITHUB_TOKEN"]
    req = urllib.request.Request("https://api.github.com" + path, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.loads(resp.read())
    except urllib.error.HTTPError as err:
        if err.code == 404:
            return None
        raise


def parse_time(value):
    return dt.datetime.fromisoformat(value.replace("Z", "+00:00"))


def md_escape(text):
    return re.sub(r"([\\`*_\[\]|<>])", r"\\\1", text.strip())


def join_links(items):
    links = [f"[{name}]({url})" for name, url in items]
    if len(links) <= 1:
        return "".join(links)
    return ", ".join(links[:-1]) + " and " + links[-1]


def own_repos(user):
    repos = api(f"/users/{user}/repos?type=owner&sort=pushed&per_page=100") or []
    hidden = {h.strip().lower() for h in os.environ.get("HIDE_REPOS", "").split(",") if h.strip()}
    return [
        r for r in repos
        if not r["fork"] and not r["archived"] and not r["private"]
        and r["name"].lower() != user.lower() and r["name"].lower() not in hidden
    ]


def lately(user, repos):
    since = dt.datetime.now(dt.timezone.utc) - dt.timedelta(days=LATELY_DAYS)
    working = [(r["name"], r["html_url"]) for r in repos
               if r.get("description") and parse_time(r["pushed_at"]) >= since][:2]
    query = urllib.parse.quote(
        f"is:pr author:{user} -user:{user} updated:>={since.date().isoformat()}")
    found = api(f"/search/issues?q={query}&sort=updated&order=desc&per_page=50") or {"items": []}
    contributing = []
    for item in found["items"]:
        full_name = item["repository_url"].split("/repos/", 1)[1]
        entry = (full_name.split("/", 1)[1], "https://github.com/" + full_name)
        if entry not in contributing:
            contributing.append(entry)
    contributing = contributing[:2]

    parts = []
    if working:
        parts.append("working on " + join_links(working))
    if contributing:
        parts.append("contributing to " + join_links(contributing))
    if not parts:
        return ""
    return "Lately I've been " + " and ".join(parts) + "."


def projects(repos):
    rows = []
    for repo in [r for r in repos if r.get("description")][:MAX_PROJECTS]:
        links = []
        if api(f"/repos/{repo['full_name']}/releases/latest"):
            links.append(f"[Latest release]({repo['html_url']}/releases/latest)")
        homepage = (repo.get("homepage") or "").strip()
        if homepage:
            links.append(f"[Website]({homepage})")
        elif repo.get("has_pages"):
            owner = repo["owner"]["login"].lower()
            links.append(f"[Live demo](https://{owner}.github.io/{repo['name']}/)")

        languages = api(f"/repos/{repo['full_name']}/languages") or {}
        total = sum(languages.values()) or 1
        stack = [name for name, size in sorted(languages.items(), key=lambda kv: -kv[1])
                 if size / total >= MIN_LANGUAGE_SHARE][:4]
        stack += [t for t in repo.get("topics", []) if t not in {s.lower() for s in stack}][:4]

        name = f"[**{md_escape(repo['name'])}**]({repo['html_url']})"
        if links:
            name += "<br/><sub>" + " · ".join(links) + "</sub>"
        stack_md = " ".join(f"`{s}`" for s in stack)
        rows.append(f"| {name} | {md_escape(repo['description'])} | {stack_md} |")

    if not rows:
        return "_No public projects yet._"
    return "\n".join(["| Project | Description | Stack |", "| :--- | :--- | :--- |", *rows])


def replace_section(text, key, content):
    pattern = re.compile(rf"(<!-- {key}:start -->)(.*?)(<!-- {key}:end -->)", re.S)
    if not pattern.search(text):
        raise SystemExit(f"README is missing the <!-- {key}:start --> / <!-- {key}:end --> markers")
    body = f"\n{content}\n" if content else "\n"
    return pattern.sub(lambda m: m.group(1) + body + m.group(3), text, count=1)


def main():
    user, readme = sys.argv[1], sys.argv[2]
    repos = own_repos(user)
    with open(readme, encoding="utf-8") as f:
        text = f.read()
    new = replace_section(text, "lately", lately(user, repos))
    new = replace_section(new, "projects", projects(repos))
    if new != text:
        with open(readme, "w", encoding="utf-8", newline="\n") as f:
            f.write(new)
        print("README updated")
    else:
        print("README already up to date")


if __name__ == "__main__":
    main()
