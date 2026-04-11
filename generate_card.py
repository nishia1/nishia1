"""
generate_card.py
Fetches live GitHub data for nishia1 and renders github_card.jpg
"""

import os
import json
import datetime
import subprocess
import requests
import textwrap

# ── config ────────────────────────────────────────────────────────────────────
USERNAME   = "nishia1"
BIRTH_YEAR  = 2007
BIRTH_MONTH = 3
TOKEN      = os.environ.get("GH_TOKEN", "")
TEMPLATE   = "card_template.html"

HEADERS = {"Authorization": f"Bearer {TOKEN}"} if TOKEN else {}

LANG_COLORS = {
    "Java": "#ffa657",
    "Python": "#79c0ff",
    "C++": "#d2a8ff",
    "C": "#7ee787",
    "JavaScript": "#e3b341",
    "TypeScript": "#58a6ff",
}
DEFAULT_COLOR = "#8b949e"

# ── helpers ───────────────────────────────────────────────────────────────────

def gh_graphql(query, variables=None):
    r = requests.post(
        "https://api.github.com/graphql",
        headers={**HEADERS, "Content-Type": "application/json"},
        json={"query": query, "variables": variables or {}},
        timeout=20,
    )
    r.raise_for_status()
    return r.json()

# ── data fetch ────────────────────────────────────────────────────────────────

def fetch_profile():
    query = """
    query {
      viewer {
        followers { totalCount }
        repositories(ownerAffiliations: OWNER, first: 1) {
          totalCount
        }
      }
    }
    """
    data = gh_graphql(query)["data"]["viewer"]
    return {
        "repos": data["repositories"]["totalCount"],
        "followers": data["followers"]["totalCount"],
    }

def fetch_repos():
    repos, cursor = [], None
    query = """
    query($cursor: String) {
      viewer {
        repositories(ownerAffiliations: OWNER, first: 100, after: $cursor) {
          pageInfo { hasNextPage endCursor }
          nodes {
            isFork
            languages(first: 10, orderBy: {field: SIZE, direction: DESC}) {
              edges { size node { name } }
            }
          }
        }
      }
    }
    """
    while True:
        data = gh_graphql(query, {"cursor": cursor})
        page = data["data"]["viewer"]["repositories"]
        repos.extend(page["nodes"])
        if not page["pageInfo"]["hasNextPage"]:
            break
        cursor = page["pageInfo"]["endCursor"]
    return repos

def fetch_top_languages(repos):
    totals = {}
    for repo in repos:
        if repo["isFork"]:
            continue
        for edge in repo["languages"]["edges"]:
            lang = edge["node"]["name"]
            totals[lang] = totals.get(lang, 0) + edge["size"]

    sorted_langs = sorted(totals.items(), key=lambda x: x[1], reverse=True)[:5]
    total = sum(v for _, v in sorted_langs) or 1

    return [(k, round(v / total * 100, 1)) for k, v in sorted_langs]

# ── ENERGY SYSTEM ─────────────────────────────────────────────────────────────

def fetch_recent_activity():
    today = datetime.datetime.now(datetime.timezone.utc).date()
    start = today - datetime.timedelta(days=30)

    query = """
    query($from: DateTime!, $to: DateTime!) {
      viewer {
        contributionsCollection(from: $from, to: $to) {
          contributionCalendar {
            weeks {
              contributionDays { date contributionCount }
            }
          }
        }
      }
    }
    """

    data = gh_graphql(query, {
        "from": f"{start}T00:00:00Z",
        "to": f"{today}T23:59:59Z"
    })

    weeks = data["data"]["viewer"]["contributionsCollection"]["contributionCalendar"]["weeks"]

    days = []
    for w in weeks:
        for d in w["contributionDays"]:
            days.append((d["date"], d["contributionCount"]))

    days.sort(key=lambda x: x[0])

    today_str = today.isoformat()
    committed_today = any(d == today_str and c > 0 for d, c in days)

    days_since = 0
    for d, c in reversed(days):
        if d == today_str:
            continue
        if c > 0:
            break
        days_since += 1

    return committed_today, days_since, days

def compute_energy(days):
    commits = sum(c for _, c in days)
    max_commits = 40

    pct = min(commits / max_commits, 1.0)
    level = int(round(pct * 10))

    bar = "█" * level + "░" * (10 - level)

    if level == 0:
        state = "asleep"
    elif level <= 3:
        state = "idle"
    elif level <= 6:
        state = "active"
    elif level <= 8:
        state = "high"
    else:
        state = "overdrive"

    return bar, state

# ── DOG STATES ────────────────────────────────────────────────────────────────

DOG_HAPPY = "(•ᴗ•)"
DOG_EXCITED = "(ᕗ⚆益⚆)ᕗ"
DOG_SLEEPING = "(－_－) zzZ"
DOG_SAD = "(╥﹏╥)"

def build_dog(energy_state):
    if energy_state == "overdrive":
        return DOG_EXCITED, "zoomies ⚡"
    elif energy_state in ["high", "active"]:
        return DOG_HAPPY, "active :)"
    elif energy_state == "idle":
        return DOG_SAD, "waiting..."
    else:
        return DOG_SLEEPING, "zzz..."

# ── render helpers ────────────────────────────────────────────────────────────

def build_lang_bars(langs):
    rows = []
    for lang, pct in langs:
        color = LANG_COLORS.get(lang, DEFAULT_COLOR)
        rows.append(
            f'<div class="lang-row">'
            f'<span class="lang-name">{lang}</span>'
            f'<div class="lang-bar-bg"><div class="lang-bar-fill" style="width:{pct}%;background:{color}"></div></div>'
            f'<span class="lang-pct">{pct}%</span>'
            f'</div>'
        )
    return "\n".join(rows)

# ── main ──────────────────────────────────────────────────────────────────────

def main():
    profile = fetch_profile()
    repos = fetch_repos()
    langs = fetch_top_languages(repos)

    committed_today, days_since, days = fetch_recent_activity()
    energy_bar, energy_state = compute_energy(days)
    dog, dog_label = build_dog(energy_state)

    with open(TEMPLATE, "r") as f:
        html = f.read()

    replacements = {
        "{{REPOS}}": str(profile["repos"]),
        "{{FOLLOWERS}}": str(profile["followers"]),
        "{{LANG_BARS}}": build_lang_bars(langs),
        "{{ENERGY_BAR}}": energy_bar,
        "{{ENERGY_STATE}}": energy_state,
        "{{DOG}}": f"<div>{dog} {dog_label}</div>",
    }

    for k, v in replacements.items():
        html = html.replace(k, v)

    with open("card_rendered.html", "w") as f:
        f.write(html)

    subprocess.run([
        "wkhtmltoimage", "--width", "940",
        "card_rendered.html", "github_card.jpg"
    ])

    print("✔ Card generated!")

if __name__ == "__main__":
    main()
