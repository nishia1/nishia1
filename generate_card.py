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
import textwrap

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
    # Use GraphQL viewer query so private data is included with the token
    query = """
    query {
      viewer {
        login
        followers { totalCount }
        repositories(ownerAffiliations: OWNER, first: 1) {
          totalCount
        }
      }
    }
    """
    try:
        data = gh_graphql(query)
        viewer = data["data"]["viewer"]
        return {
            "public_repos": viewer["repositories"]["totalCount"],
            "followers":    viewer["followers"]["totalCount"],
        }
    except Exception:
        return gh_rest(f"users/{USERNAME}")

def fetch_repos():
    # GraphQL: get ALL repos including private ones owned by the user
    repos, cursor = [], None
    query = """
    query($cursor: String) {
      viewer {
        repositories(ownerAffiliations: OWNER, first: 100, after: $cursor) {
          pageInfo { hasNextPage endCursor }
          nodes {
            name
            isFork
            stargazerCount
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

def fetch_stars(repos):
    return sum(r.get("stargazerCount", 0) for r in repos)

def fetch_top_languages(repos):
    """Aggregate bytes per language across all repos (private + public)."""
    totals = {}
    for repo in repos:
        if repo.get("isFork"):
            continue
        for edge in repo.get("languages", {}).get("edges", []):
            lang = edge["node"]["name"]
            totals[lang] = totals.get(lang, 0) + edge["size"]
    sorted_langs = sorted(totals.items(), key=lambda x: x[1], reverse=True)[:5]
    total_bytes = sum(b for _, b in sorted_langs) or 1
    return [(lang, round(bytes_ / total_bytes * 100, 1)) for lang, bytes_ in sorted_langs]

def fetch_commits_alltime():
    # Sum contributionCalendar.totalContributions across every year
    # from account creation to now — matches your profile graph total.
    query_joined = """
    query { viewer { createdAt } }
    """
    try:
        joined_year = int(gh_graphql(query_joined)["data"]["viewer"]["createdAt"][:4])
    except Exception:
        joined_year = 2020

    current_year = datetime.datetime.now(datetime.timezone.utc).year
    query = """
    query($from: DateTime!, $to: DateTime!) {
      viewer {
        contributionsCollection(from: $from, to: $to) {
          contributionCalendar { totalContributions }
        }
      }
    }
    """
    total = 0
    for year in range(joined_year, current_year + 1):
        try:
            data = gh_graphql(query, {
                "from": f"{year}-01-01T00:00:00Z",
                "to":   f"{year}-12-31T23:59:59Z",
            })
            total += data["data"]["viewer"]["contributionsCollection"]["contributionCalendar"]["totalContributions"]
        except Exception:
            pass
    return total

def fetch_streak_and_contributed():
    """
    Uses viewer (token-auth) so private contributions are included.
    Returns (current_streak, longest_streak, contributed_repos).
    - current_streak: consecutive days up to today with contributions
    - longest_streak: longest ever run in the past year
    - contributed_repos: total repos contributed to
    """
    query = """
    query {
      viewer {
        repositoriesContributedTo(
          first: 1
          includeUserRepositories: true
          contributionTypes: [COMMIT, ISSUE, PULL_REQUEST, REPOSITORY]
        ) {
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
        data = gh_graphql(query)
        viewer = data["data"]["viewer"]
        contributed = viewer["repositoriesContributedTo"]["totalCount"]

        # Collect days in chronological order with dates
        days = []
        for week in viewer["contributionsCollection"]["contributionCalendar"]["weeks"]:
            for day in week["contributionDays"]:
                days.append((day["date"], day["contributionCount"]))
        days.sort(key=lambda x: x[0])

        # Current streak: walk backwards from today, stop at first zero
        today = datetime.datetime.now(datetime.timezone.utc).date().isoformat()
        current = 0
        for date, count in reversed(days):
            if date > today:
                continue
            if count > 0:
                current += 1
            else:
                break

        # Longest streak: scan forwards through all days
        longest = best = 0
        for _, count in days:
            if count > 0:
                longest += 1
                best = max(best, longest)
            else:
                longest = 0

        return current, best, contributed
    except Exception:
        return 0, 0, 0


def fetch_committed_today_and_streak_info():
    """Returns (committed_today, days_since_last_commit) using last 30 days of calendar."""
    today = datetime.datetime.now(datetime.timezone.utc).date()
    thirty_days_ago = today - datetime.timedelta(days=30)
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
    variables = {
        "from": f"{thirty_days_ago.isoformat()}T00:00:00Z",
        "to":   f"{today.isoformat()}T23:59:59Z",
    }
    try:
        data = gh_graphql(query, variables)
        weeks = data["data"]["viewer"]["contributionsCollection"]["contributionCalendar"]["weeks"]
        days = []
        for week in weeks:
            for day in week["contributionDays"]:
                days.append((day["date"], day["contributionCount"]))
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
        return committed_today, days_since
    except Exception:
        return False, 0

# ── uptime ────────────────────────────────────────────────────────────────────

def calc_uptime():
    today = datetime.date.today()
    years  = today.year - BIRTH_YEAR - (today.month < BIRTH_MONTH)
    months = (today.month - BIRTH_MONTH) % 12
    return f"{years} years, {months} months"

# ── render ────────────────────────────────────────────────────────────────────

DOG_HAPPY    = '''                                                              
                                                              
                                                              
                                                              
                                                              
                                                              
                                                              
                                                              
                                                              
                                                              
                                                              
                                                              
                                                              
                                                              
                                                              
                             $$$$$$$$$                        
$$$                      t$$$$$$$$$$$$$$$|                    
WMC                     $$$$$$$$$$$$$$$$$$$$                  
                      r$$$$$$$$$$$$$$$B;$$$$$                 
$$$$$$$#$w            $$$  W$$$$$$$$$$   \\$$$$                
$$$$$$$$$$$$$$$$L%U   $$$$$$$$$$$$$$$*! |xYY*$$               
$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$M$M!dm$b              
$$$$$$$$$$$$$$$$b$$$$X$$$$$$$$$$$$$$$$$$$$nY$$!               
$$$$$$$$$$$$$$$$ $$$$$$$$$$$$$$$$$$$$$$$dp Y$X                
$$$$$$$$$$$$$$$L$$$$@$$$$$$$hz #$$$$$$$$$ $$                  
$$$$$*$$$$$$&amp;$B$$$$!/$$$$$$       . Ckx$%                     
$$$$$$$$$$$$$xW$$$$/p$$$$$ob$$$@Q    U8%$                     
$$$$$$$$$.$$$.$$$$$JU$$$$$o  %$$B    $@CZ$$                   
$$$$$$$$$$X$$W$$$$$w$$$$$$$$$      $$$B` @$$|                 
$$$$$$$$$$$w$$$$$$$$m$$$$$$$$$$$$$$$`B  J%:t$b                
$$$$$$$$$$$$$$$$$ $$&amp;$$$$$$$z$$$$$  x$$$$  #$$$               
    d$$$$$$$$$$$$$p$$W$$$$$$X $$$$$$$$$$   $$$$$              
          /$$$$$$$$$$ $$$$$$$$#  $$$$$      d$$$$%            
               $$$k$$$$$$$$$$$$$$8$           $$$$$           
               t$$$$M$$$$$$$$$ m               d@Q$$$         
                $$$$$&amp;$$$$$                     z$$$$$$$k     
                $$$$$$$$L$                        $$$$$$$$$   
                $$$$$$$$$                           W$$$$$$$  
                 $$$$8$$                               kbLz@$ 
                  $$$$$u                                      
                  $$$$$$:                                     
                   $$$$$k:                                    '''
DOG_EXCITED  = '''    $$$$$p                                                    
    $$$$$$$                                                   
    $$bY$$$$#                                                 
      t*$$$$$                                                 
          \\ $$                                                
          $$$$x    $$$$$$/Y                                   
          $$$$$$$$$$$$$$$$$$$                                 
          $$$$$$$$$$$$$$$$$$$$$$                              
           $$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$                    
           $$$$$$Q @$$u  $$$$$$$$$$$$$$$$$$$                  
           $$0$$$$$$U   u$$$$$$$&amp;$k$$$$$$$$$                  
            $$QX  $$$$$$$$$$$%$hL8f$$$$$$$$$$$$               
             fBLk   $$$$$$$p  u$$YY$8$$$$$$$$$$$$$            
              w$$$$J      Xmb    tm$$$$$$$$$$$$$$$            
               $$$$$$$$$w$$#    $Bm$$$$z$hq/Q$$$$             
                !$$$$$$$$$$$  $$@%C#$$$$0:w$$$$$              
                  $$$$$$$$$B 8MJ$$$$$$Wx.t|; $;               
                  $$$z$$$$$$kQJ$ozpw$Ld$$n $$$                
                  $$$w\\$$$$$$*d$@$$*$$Bkn $$$$                
                  :$$$$YQ  k$q \\WU       $$$$$                
                    $$$$$Zh              $$$$                 
                     $$$$$$C $$        $$$$$$                 
                      $$$ r$$$$/      /$$$$$C                 
                       n$kC$$$$$$h *$$$$q$$$d                 
                        $$ d$$*h$$&amp;d$$z   $$z                 
                        $$t$$$$@@$   o .$$$$%                 
                        $d$$$$$$$$z !q$$$$$$$$                
                        CY$$   $$$$\'p$$$   $$$$               
                          $%   $$$$$$$X     $$                
                          $$$$$$#$$$$$M$$$$$$$$               
                     $$$h$$$$$$$Y$$\\kM$$$$$$$$$               
                   $$$$$$$$$$$$$ m$$/X$$$X$$$$$$              
                 $$$$$$$$$$$$$$  $$$$$p$x m$$$$$              
                $$$$$$$J$$$$$$*  $x$$*$$ !fp$$$$$             
                $$$$$$$$$$$$p m*$$$$@0$   $$$$$$$$            
               B$$$$$$$W$$$m  J%Z8$x 0$$qx$$$$$$$$            
               $$$$$$$$$$MCu$       h. :U #  $$$$$\'           
               $$$$#q$$$$$$$$           ! $$ $$k@$$           
                $$$$$$p$Yd k*     |Z;/! z$$$$@xU$8k           
                J$$$$&amp;$$$$\'.                                  
                 t$$$$$$$$$:                                  
                   $$$$$$$$                                   
                      o\'$o                                    
                                                              
                                                              '''
DOG_SLEEPING = '''                                                  
                                                  
                                                  
                                                  
                                                  
                                                  
                                                  
                                                  
                           $$:                    
                     fw $$$$$$$$$$  $             
              x|.       $$$$$$$$$$$$$$$$$ ;$hL    
          $$$$$$$$$$$$M`$$$$$$$$$$$$$$$$$$p$\@$$$$
        $$$$$$$$$$$$$$$  ; Y\'$$$$$$$$$$k$$$$     X
    $$#$$$$$$$$$    $$    $$$$$ Y$$$$$$$W$$$  /$0 
   $$$$$$X\$$$$$$  %$$  $$$$$$$    $$$$$$$$d $$$$$
  $$$/ u\  $$$$$$$$$$$:$$$$$$$$$$$$$$ \'$$$$$$$$$$$
   $$$$q$$$$$$$$$$$$$r $$mZ$$$$$$$$$k   Z$$$$/    
   $$$$$$$$$  ;!$$$$$p  $o     $$$$\' %$$%$$       
      :   U     k$$$$       ;  &amp;$$$$$$$$$$$$$$u   
                f           .fB%pQh$$$$$|   . ;#  
                          `b`    o0z$$$$    $$$:&amp;h
                                    X         %$$%
                                                  
                                                  
                                                  
                                                  
                                                  
                                                  '''
DOG_SAD      = '''                                   m$$$$$$$$$$                
                        w$$J  ;$$$$$$$$$$$$$$$$$              
                        $$$$$$$$$$$$$#|box$$$$$$$$X           
                      $$$$\' $$$$$$n  /$C   $$w$$$$$$          
                     $$.   $$z$$$QQC0C*x    ;   q$$$$         
                     $    $$:$0           Y       $$$$        
                    f     $  w         \\ 8$h;/      C$$       
                   ;k!    $U$$$X      w$$$$$$$$L$   #$$$      
                  o%      $$$ xY    U$$$$$$$$$$$$$$! $h$      
                  bz      |0 XBx  m$$$$$$$$$$$$$$$$$$$Y$      
                 oC      &amp;  %$Bz$$$$$$$$$$$$$$$$$$$$$$$       
                 :J         @$#$Q$$$%dmz  r8$$$$$$$$$$$       
                  r         BMuX:$$$$mn/owzU#$$$q%$$$$$$      
                   X      |$$%*#$$bwqnm*bbwX.  d$ $$$$$$      
                  C$\'    \'$$Qoo@$| 0kqUzn!        |$$$$$      
                   Y     ;$&amp;  XQ.  u   \\!            $        
                      $pt$$$$$to  f  /Yf              k       
                      $\' u W$$/ .x|\\rt;;!           $$0       
                     /$      $L         \'f|      r$$$$        
                     \\$\\      /!:    :    /r\' z$$$$$$         
                      $x        ;q\'  d$$    r@$$$$$$$         
                      0M;      . Q@Y   $d    $$$$$$$$         
                       LMo:   \'t  !#$p      $$$$$$$$b         
                        Z$pu   /u   tb$$$$$$$ ! %$$$          
                         z/|XY`:o\\!     L;w   ;Yk$$&amp;          
                          z.:romzLpfnUfr  t   J| $$           
                           Y/!\\$J:bk$$&amp;#L    .z $$W           
                           Y.td$        |&amp;z!:  Y$$            
                           !. #$          $z: f$$             
                            z U$$         WL  !$$             
                           po n$$         qU\'\\$$              '''

STREAK_EXCITED = 7  # days to trigger excited state

def build_dog_html(committed_today, current_streak, days_since_commit):
    if current_streak >= STREAK_EXCITED and committed_today:
        dog, color, label = DOG_EXCITED, "#ffa657", f"\u26a1 {current_streak} day streak!"
    elif committed_today:
        dog, color, label = DOG_HAPPY,   "#7ee787", "committed today :)"
    elif days_since_commit >= 2:
        dog, color, label = DOG_SLEEPING, "#8b949e", "zzz... no commits in 2+ days"
    else:
        dog, color, label = DOG_SAD,      "#f78166", "no commits today..."

    dog = textwrap.dedent(dog)

    return ('<div class="dog-wrap">'
            f'<div class="dog-label" style="color:{color};font-size:9px;margin-bottom:3px">{label}</div>'
            f'<pre class="dog-art" style="color:{color}">{dog}</pre>'
            '</div>')

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

    streak_pct = min(100, round(data["longest_streak"] / max(data["longest_streak"], 60) * 100))

    for key, val in [
        ("{{UPTIME}}",      data["uptime"]),
        ("{{REPOS}}",       str(data["repos"])),
        ("{{CONTRIBUTED}}", str(data["contributed"])),
        ("{{STARS}}",       str(data["stars"])),
        ("{{COMMITS}}",     f"{data['commits']:,}"),
        ("{{FOLLOWERS}}",   str(data["followers"])),
        ("{{STREAK}}",      str(data["longest_streak"])),
        ("{{STREAK_PCT}}",  str(streak_pct)),
        ("{{LANG_BARS}}",   data["lang_bars"]),
        ("{{DOG}}",         data["dog"]),
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
    commits    = fetch_commits_alltime()
    current_streak, longest_streak, contributed = fetch_streak_and_contributed()
    committed_today, days_since_commit = fetch_committed_today_and_streak_info()
    top_langs  = fetch_top_languages(repos)

    data = {
        "uptime":         calc_uptime(),
        "repos":          profile.get("public_repos", len(repos)),
        "contributed":    contributed,
        "stars":          stars,
        "commits":        commits,
        "followers":      profile.get("followers", 0),
        "longest_streak": longest_streak,   # used for bar display in card
        "lang_bars":      build_lang_bars(top_langs),
        "dog":            build_dog_html(committed_today, current_streak, days_since_commit),
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
