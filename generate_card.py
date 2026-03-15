#!/usr/bin/env python3
"""
generate_card.py
Fetches live GitHub data for nishia1 and renders github_card.jpg
Requires: requests, wkhtmltoimage (apt install wkhtmltopdf)
"""

import os
import re
import json
import math
import datetime
import subprocess
import requests

# ── config ────────────────────────────────────────────────────────────────────
USERNAME   = "nishia1"
BIRTH_YEAR  = 2007
BIRTH_MONTH = 3
TOKEN      = os.environ.get("GH_TOKEN", "")   # set as repo secret GH_TOKEN
TEMPLATE   = "card_template.html"
OUTPUT_HTML= "card_rendered.html"
OUTPUT_IMG = "github_card.jpg"

HEADERS = {"Authorization": f"Bearer {TOKEN}"} if TOKEN else {}

LANG_COLORS = {
    "Java":       "#ffa657",
    "Python":     "#79c0ff",
    "C++":        "#d2a8ff",
    "C":          "#7ee787",
    "JavaScript": "#e3b341",
    "TypeScript": "#58a6ff",
    "Rust":       "#f78166",
    "Go":         "#79c0ff",
    "Shell":      "#8b949e",
    "HTML":       "#f78166",
    "CSS":        "#7ee787",
}
DEFAULT_COLOR = "#8b949e"

# ── helpers ───────────────────────────────────────────────────────────────────

def gh_rest(path):
    url = f"https://api.github.com/{path}"
    r = requests.get(url, headers=HEADERS, timeout=15)
    r.raise_for_status()
    return r.json()

def gh_graphql(query, variables=None):
    r = requests.post(
        "https://api.github.com/graphql",
        headers={**HEADERS, "Content-Type": "application/json"},
        json={"query": query, "variables": variables or {}},
        timeout=20,
    )
    r.raise_for_status()
    return r.json()

# ── fetch data ────────────────────────────────────────────────────────────────

def fetch_profile():
    return gh_rest(f"users/{USERNAME}")

def fetch_repos():
    repos, page = [], 1
    while True:
        batch = gh_rest(f"users/{USERNAME}/repos?per_page=100&page={page}&type=owner")
        repos.extend(batch)
        if len(batch) < 100:
            break
        page += 1
    return repos

def fetch_stars(repos):
    return sum(r["stargazers_count"] for r in repos)

def fetch_top_languages(repos):
    """Aggregate bytes per language across all repos."""
    totals = {}
    for repo in repos:
        if repo.get("fork"):
            continue
        try:
            langs = gh_rest(f"repos/{USERNAME}/{repo['name']}/languages")
            for lang, bytes_ in langs.items():
                totals[lang] = totals.get(lang, 0) + bytes_
        except Exception:
            pass
    # sort and take top 5
    sorted_langs = sorted(totals.items(), key=lambda x: x[1], reverse=True)[:5]
    total_bytes = sum(b for _, b in sorted_langs) or 1
    return [(lang, round(bytes_ / total_bytes * 100, 1)) for lang, bytes_ in sorted_langs]

def fetch_commits_this_year():
    year = datetime.datetime.utcnow().year
    query = """
    query($login: String!, $from: DateTime!, $to: DateTime!) {
      user(login: $login) {
        contributionsCollection(from: $from, to: $to) {
          totalCommitContributions
          restrictedContributionsCount
        }
      }
    }
    """
    variables = {
        "login": USERNAME,
        "from": f"{year}-01-01T00:00:00Z",
        "to":   f"{year}-12-31T23:59:59Z",
    }
    try:
        data = gh_graphql(query, variables)
        cc = data["data"]["user"]["contributionsCollection"]
        return cc["totalCommitContributions"] + cc["restrictedContributionsCount"]
    except Exception:
        return 0

def fetch_streak_and_contributed():
    """
    Uses contributionCalendar to calculate longest streak
    and total contributed repos.
    """
    query = """
    query($login: String!) {
      user(login: $login) {
        repositoriesContributedTo(first: 1, contributionTypes: [COMMIT, ISSUE, PULL_REQUEST, REPOSITORY]) {
          totalCount
        }
        contributionsCollection {
          contributionCalendar {
            weeks {
              contributionDays {
                contributionCount
                date
              }
            }
          }
        }
      }
    }
    """
    try:
        data = gh_graphql(query, {"login": USERNAME})
        user = data["data"]["user"]
        contributed = user["repositoriesContributedTo"]["totalCount"]

        days = []
        for week in user["contributionsCollection"]["contributionCalendar"]["weeks"]:
            for day in week["contributionDays"]:
                days.append(day["contributionCount"])

        longest = cur = 0
        for count in days:
            if count > 0:
                cur += 1
                longest = max(longest, cur)
            else:
                cur = 0

        return longest, contributed
    except Exception:
        return 0, 0

# ── uptime ────────────────────────────────────────────────────────────────────

def calc_uptime():
    today = datetime.date.today()
    years  = today.year - BIRTH_YEAR - (today.month < BIRTH_MONTH)
    months = (today.month - BIRTH_MONTH) % 12
    return f"{years} years, {months} months"

# ── render ────────────────────────────────────────────────────────────────────

def build_lang_bars(top_langs):
    bars = []
    for lang, pct in top_langs:
        color = LANG_COLORS.get(lang, DEFAULT_COLOR)
        bar = (
            f'<div class="lang-row">'
            f'  <span class="lang-name">{lang}</span>'
            f'  <div class="lang-bar-bg">'
            f'    <div class="lang-bar-fill" style="width:{pct}%;background:{color}"></div>'
            f'  </div>'
            f'  <span class="lang-pct">{pct}%</span>'
            f'</div>'
        )
        bars.append(bar)
    return "\n".join(bars)

LIGHT_OVERRIDE = """
  :root {
    --bg:           #ffffff !important;
    --card-bg:      #f6f8fa !important;
    --border:       #d0d7de !important;
    --text-primary: #1f2328 !important;
    --text-muted:   #57606a !important;
    --text-dim:     #d0d7de !important;
    --ascii-color:  #0969da !important;
    --ascii-glow:   rgba(9,105,218,0.15) !important;
    --scanline:     rgba(0,0,0,0.015) !important;
    --bar-bg:       #d0d7de !important;
    --green:  #1a7f37 !important;
    --blue:   #0969da !important;
    --purple: #8250df !important;
    --orange: #bc4c00 !important;
    --yellow: #9a6700 !important;
    --red:    #cf222e !important;
  }
"""

def render_html(data):
    with open(TEMPLATE, "r", encoding="utf-8") as f:
        base = f.read()

    streak_pct = min(100, round(data["streak"] / max(data["streak"], 60) * 100))

    for key, val in [
        ("{{UPTIME}}",      data["uptime"]),
        ("{{REPOS}}",       str(data["repos"])),
        ("{{CONTRIBUTED}}", str(data["contributed"])),
        ("{{STARS}}",       str(data["stars"])),
        ("{{COMMITS}}",     f"{data['commits']:,}"),
        ("{{FOLLOWERS}}",   str(data["followers"])),
        ("{{STREAK}}",      str(data["streak"])),
        ("{{STREAK_PCT}}",  str(streak_pct)),
        ("{{LANG_BARS}}",   data["lang_bars"]),
    ]:
        base = base.replace(key, val)

    with open("card_dark.html", "w", encoding="utf-8") as f:
        f.write(base)
    light_html = base.replace("</style>", LIGHT_OVERRIDE + "\n</style>")
    with open("card_light.html", "w", encoding="utf-8") as f:
        f.write(light_html)
    print("✔ Wrote card_dark.html + card_light.html")

def render_image():
    for html_file, img_file in [("card_dark.html", "github_card_dark.jpg"), ("card_light.html", "github_card_light.jpg")]:
        abs_path = os.path.abspath(html_file)
        cmd = ["wkhtmltoimage", "--width", "940", "--quality", "95", "--zoom", "1.5",
               f"file://{abs_path}", img_file]
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode not in (0, 1):
            raise RuntimeError(f"wkhtmltoimage failed for {html_file}:\n{result.stderr}")
        print(f"✔ Rendered {img_file}")

# ── main ──────────────────────────────────────────────────────────────────────

def main():
    print("Fetching GitHub data…")
    profile    = fetch_profile()
    repos      = fetch_repos()
    stars      = fetch_stars(repos)
    commits    = fetch_commits_this_year()
    streak, contributed = fetch_streak_and_contributed()
    top_langs  = fetch_top_languages(repos)

    data = {
        "uptime":      calc_uptime(),
        "repos":       profile.get("public_repos", len(repos)),
        "contributed": contributed,
        "stars":       stars,
        "commits":     commits,
        "followers":   profile.get("followers", 0),
        "streak":      streak,
        "lang_bars":   build_lang_bars(top_langs),
    }

    print(json.dumps({k: v for k, v in data.items() if k != "lang_bars"}, indent=2))

    render_html(data)
    render_image()
    print("Done! Add to README.md:")
    print('\n<picture>')
    print('  <source media="(prefers-color-scheme: dark)" srcset="github_card_dark.jpg">')
    print('  <source media="(prefers-color-scheme: light)" srcset="github_card_light.jpg">')
    print('  <img src="github_card_dark.jpg" alt="nishi@nishia1">')
    print('</picture>')

if __name__ == "__main__":
    main()
