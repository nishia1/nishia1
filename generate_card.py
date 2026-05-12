"""
generate_card.py
Fetches live GitHub data for nishia1 and renders github_card_dark.jpg + github_card_light.jpg
Usage:
  python generate_card.py --theme dark
  python generate_card.py --theme light
"""

import os
import argparse
import datetime
import subprocess
import requests

# ── config ────────────────────────────────────────────────────────────────────
USERNAME = "nishia1"
TOKEN    = os.environ.get("GH_TOKEN", "")
TEMPLATE = "card_template.html"

HEADERS = {"Authorization": f"Bearer {TOKEN}"} if TOKEN else {}

LANG_COLORS = {
    "Java":       "#ffa657",
    "Python":     "#79c0ff",
    "C++":        "#d2a8ff",
    "C":          "#7ee787",
    "JavaScript": "#e3b341",
    "TypeScript": "#58a6ff",
}
DEFAULT_COLOR = "#8b949e"

# ── GraphQL helper ────────────────────────────────────────────────────────────

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

def fetch_contribution_years():
    """Fetch all years the user has made contributions."""
    query = """
    query {
      viewer {
        contributionsCollection {
          contributionYears
        }
      }
    }
    """
    data = gh_graphql(query)
    return data["data"]["viewer"]["contributionsCollection"]["contributionYears"]


def fetch_profile():
    """Fetch repo count, followers, and contributed-to repo count."""
    query = """
    query {
      viewer {
        followers { totalCount }
        repositories(ownerAffiliations: OWNER, first: 1) {
          totalCount
        }
        repositoriesContributedTo(
          contributionTypes: [COMMIT, PULL_REQUEST, REPOSITORY],
          first: 1
        ) {
          totalCount
        }
      }
    }
    """
    data = gh_graphql(query)["data"]["viewer"]
    return {
        "repos":       data["repositories"]["totalCount"],
        "followers":   data["followers"]["totalCount"],
        "contributed": data["repositoriesContributedTo"]["totalCount"],
    }


def fetch_repos():
    """Fetch all owned repos with language breakdown."""
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
    """Compute top 5 languages by bytes across non-fork repos."""
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


def fetch_total_commits(years):
    """Sum all commit contributions across every contribution year."""
    query = """
    query($from: DateTime!, $to: DateTime!) {
      viewer {
        contributionsCollection(from: $from, to: $to) {
          totalCommitContributions
        }
      }
    }
    """
    total = 0
    for year in years:
        data = gh_graphql(query, {
            "from": f"{year}-01-01T00:00:00Z",
            "to":   f"{year}-12-31T23:59:59Z",
        })
        total += data["data"]["viewer"]["contributionsCollection"]["totalCommitContributions"]
    return total


def fetch_all_contribution_days(years):
    """Fetch every contribution day across all years, sorted ascending."""
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
    all_days = []
    for year in years:
        data = gh_graphql(query, {
            "from": f"{year}-01-01T00:00:00Z",
            "to":   f"{year}-12-31T23:59:59Z",
        })
        weeks = data["data"]["viewer"]["contributionsCollection"]["contributionCalendar"]["weeks"]
        for w in weeks:
            for d in w["contributionDays"]:
                all_days.append((d["date"], d["contributionCount"]))

    all_days.sort(key=lambda x: x[0])
    return all_days

# ── compute stats ─────────────────────────────────────────────────────────────

def compute_streak(all_days):
    """Return (longest_streak_days, streak_pct) across all contribution history."""
    longest = 0
    current = 0
    for _, count in all_days:
        if count > 0:
            current += 1
            longest = max(longest, current)
        else:
            current = 0

    max_possible = 365
    pct = min(round(longest / max_possible * 100, 1), 100)
    return longest, pct


def compute_energy(days):
    """Return (bar_string, state_label) based on commits in the last 30 days."""
    commits    = sum(c for _, c in days)
    max_commits = 40
    pct   = min(commits / max_commits, 1.0)
    level = int(round(pct * 10))
    bar   = "█" * level + "░" * (10 - level)

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

# ── dog states ────────────────────────────────────────────────────────────────

DOG_HAPPY    = "(•ᴗ•)"
DOG_EXCITED  = "(ᕗ⚆益⚆)ᕗ"
DOG_SLEEPING = "(－_－) zzZ"
DOG_SAD      = "(╥﹏╥)"

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
    parser = argparse.ArgumentParser()
    parser.add_argument("--theme", choices=["dark", "light"], default="dark")
    args = parser.parse_args()

    print(f"── Fetching GitHub data ({args.theme} theme) ──")

    # fetch everything — share years across calls to avoid duplicate queries
    years    = fetch_contribution_years()
    profile  = fetch_profile()
    repos    = fetch_repos()
    langs    = fetch_top_languages(repos)
    all_days = fetch_all_contribution_days(years)
    total_commits          = fetch_total_commits(years)
    longest_streak, streak_pct = compute_streak(all_days)

    # last 30 days only for energy bar
    cutoff = (
        datetime.datetime.now(datetime.timezone.utc).date()
        - datetime.timedelta(days=30)
    ).isoformat()
    recent_days = [(d, c) for d, c in all_days if d >= cutoff]

    energy_bar, energy_state = compute_energy(recent_days)
    dog, dog_label           = build_dog(energy_state)

    # load + patch template
    with open(TEMPLATE, "r") as f:
        html = f.read()

    # inject theme class for light mode (dark is the :root default)
    if args.theme == "light":
        html = html.replace("<body>", '<body class="light">')

    replacements = {
        "{{REPOS}}":        str(profile["repos"]),
        "{{CONTRIBUTED}}":  str(profile["contributed"]),
        "{{COMMITS}}":      str(total_commits),
        "{{FOLLOWERS}}":    str(profile["followers"]),
        "{{STREAK}}":       str(longest_streak),
        "{{STREAK_PCT}}":   str(streak_pct),
        "{{LANG_BARS}}":    build_lang_bars(langs),
        "{{ENERGY_BAR}}":   energy_bar,
        "{{ENERGY_STATE}}": energy_state,
        "{{DOG}}":          f"<div>{dog} {dog_label}</div>",
    }

    for k, v in replacements.items():
        html = html.replace(k, v)

    rendered_html = f"card_rendered_{args.theme}.html"
    output_jpg    = f"github_card_{args.theme}.jpg"

    with open(rendered_html, "w") as f:
        f.write(html)

    subprocess.run([
        "wkhtmltoimage", "--width", "940",
        rendered_html, output_jpg
    ], check=True)

    print(f"✔ {output_jpg} generated!")


if __name__ == "__main__":
    main()
