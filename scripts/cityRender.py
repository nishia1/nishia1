import requests
import math
import os
from datetime import datetime, timedelta

GITHUB_TOKEN = os.environ["GITHUB_TOKEN"]
GITHUB_USER = os.environ["GITHUB_USERNAME"]

# --- Fetch contributions via GraphQL ---
def fetch_contributions():
    query = """
    query($login: String!) {
      user(login: $login) {
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
    r = requests.post(
        "https://api.github.com/graphql",
        json={"query": query, "variables": {"login": GITHUB_USER}},
        headers={"Authorization": f"Bearer {GITHUB_TOKEN}"},
    )
    response_json = r.json()
    print("API Response:", response_json)
    weeks = response_json["data"]["user"]["contributionsCollection"]["contributionCalendar"]["weeks"]
    return [[day["contributionCount"] for day in week["contributionDays"]] for week in weeks]

LANDMARKS = {
    "empire_state": {
        "city": "NYC",
        "color": "#ff69b4",
        "accent": "#ffffff",
        "shape": "stepped",
    },
    "chrysler": {
        "city": "NYC",
        "color": "#ffffff",
        "accent": "#ff69b4",
        "shape": "tapered",
    },
    "flatiron": {
        "city": "NYC",
        "color": "#222222",
        "accent": "#ff69b4",
        "shape": "wedge",
    },
    "transamerica": {
        "city": "SF",
        "color": "#ffffff",
        "accent": "#eeeeee",
        "shape": "pyramid",
    },
    "salesforce": {
        "city": "SF",
        "color": "#ff69b4",
        "accent": "#ffaacc",
        "shape": "tall_rect",
    },
    "bofa_plaza": {
        "city": "ATL",
        "color": "#222222",
        "accent": "#ff69b4",
        "shape": "notched",
    },
    "westin_peachtree": {
        "city": "ATL",
        "color": "#ffffff",
        "accent": "#ff69b4",
        "shape": "cylinder",
    },
}

def iso_project(x, y, z, origin_x=300, origin_y=80, scale=20):
    """Convert 3D grid coords to 2D isometric screen coords."""
    sx = origin_x + (x - y) * scale
    sy = origin_y + (x + y) * scale * 0.5 - z * scale
    return sx, sy

def draw_building_block(x, y, h, color_top, color_left, color_right, scale=20):
    """Draw a single isometric cube at grid position x,y with height h."""
    pieces = []
    for z in range(h):
        tx, ty = iso_project(x, y, z, scale=scale)
        w = scale
        h2 = scale * 0.5
        top = f"""<polygon points="
            {tx},{ty}
            {tx+w},{ty+h2}
            {tx},{ty+scale}
            {tx-w},{ty+h2}" fill="{color_top}"/>"""
        left = f"""<polygon points="
            {tx-w},{ty+h2}
            {tx},{ty+scale}
            {tx},{ty+scale*2}
            {tx-w},{ty+h2+scale}" fill="{color_left}"/>"""
        right = f"""<polygon points="
            {tx+w},{ty+h2}
            {tx},{ty+scale}
            {tx},{ty+scale*2}
            {tx+w},{ty+h2+scale}" fill="{color_right}"/>"""
        pieces.extend([top, left, right])
    return "\n".join(pieces)

def landmark_empire_state(cx, cy, base_h, scale=20):
    """Empire State: wide base, 3 stepped tiers, thin antenna."""
    svg = []
    colors = [("#ff69b4","#c0306a","#e04d90"),
              ("#ffffff","#cccccc","#e0e0e0"),
              ("#ff69b4","#c0306a","#e04d90")]
    widths = [3, 2, 1]
    heights = [base_h, max(1, base_h//2), max(1, base_h//4)]
    offsets = [0, 1, 2]
    for tier, (w, h, off, col) in enumerate(zip(widths, heights, offsets, colors)):
        for dx in range(w):
            for dy in range(w):
                svg.append(draw_building_block(cx+off+dx, cy+off+dy, h, *col, scale=scale))
    svg.append(draw_building_block(cx+2, cy+2, base_h + base_h//2, "#ffffff","#cccccc","#e0e0e0", scale=scale//2))
    return "\n".join(svg)

def landmark_transamerica(cx, cy, base_h, scale=20):
    """Transamerica: pyramid that narrows each floor."""
    svg = []
    color = ("#ffffff","#cccccc","#e0e0e0")
    for z in range(base_h):
        inset = z * 0.4
        tx, ty = iso_project(cx, cy, z, scale=scale)
        w = max(2, scale - int(inset*2))
        svg.append(f'<polygon points="{tx},{ty} {tx+w},{ty+w*0.5} {tx},{ty+w} {tx-w},{ty+w*0.5}" fill="{color[0]}"/>')
        svg.append(f'<polygon points="{tx-w},{ty+w*0.5} {tx},{ty+w} {tx},{ty+w*2} {tx-w},{ty+w*0.5+w}" fill="{color[1]}"/>')
        svg.append(f'<polygon points="{tx+w},{ty+w*0.5} {tx},{ty+w} {tx},{ty+w*2} {tx+w},{ty+w*0.5+w}" fill="{color[2]}"/>')
    return "\n".join(svg)

def landmark_bofa(cx, cy, base_h, scale=20):
    """BofA Plaza ATL: dark with pink crown."""
    svg = []
    for z in range(base_h):
        notch = z > base_h - 3
        col = ("#222222","#111111","#1a1a1a") if not notch else ("#ff69b4","#c0306a","#e04d90")
        svg.append(draw_building_block(cx, cy, 1, *col, scale=scale))
    return "\n".join(svg)

# --- Main render ---
def render_city(weeks):
    svg_parts = []
    svg_parts.append("""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1200 500"
        style="background: linear-gradient(180deg, #1a0530 0%, #6b1a3a 30%, #c4542a 65%, #f0a040 100%)">""")

    SCALE = 12
    MAX_HEIGHT = 8

    landmark_positions = {
        (5, 3): "empire_state",
        (15, 2): "chrysler",
        (25, 4): "flatiron",
        (35, 2): "transamerica",
        (45, 3): "salesforce",
        (10, 3): "bofa_plaza",
        (30, 2): "westin_peachtree",
    }

    for week_i, week in enumerate(weeks):
        for day_i, count in enumerate(week):
            h = min(MAX_HEIGHT, max(1, count // 2)) if count > 0 else 0
            if h == 0:
                continue
            pos = (week_i, day_i)
            if pos in landmark_positions:
                name = landmark_positions[pos]
                lm = LANDMARKS[name]
                if lm["shape"] == "pyramid":
                    svg_parts.append(landmark_transamerica(week_i, day_i, h, SCALE))
                elif lm["shape"] == "stepped":
                    svg_parts.append(landmark_empire_state(week_i, day_i, h, SCALE))
                elif lm["shape"] == "notched":
                    svg_parts.append(landmark_bofa(week_i, day_i, h, SCALE))
                else:
                    svg_parts.append(draw_building_block(week_i, day_i, h,
                        lm["accent"], lm["color"], lm["color"], scale=SCALE))
            else:
                city_zone = week_i % 3
                if city_zone == 0:
                    cols = ("#ffffff", "#cccccc", "#e0e0e0")  # white
                elif city_zone == 1:
                    cols = ("#ff69b4", "#c0306a", "#e04d90")  # pink
                else:
                    cols = ("#222222", "#bbbbbb", "#666666")  # black
                svg_parts.append(draw_building_block(week_i, day_i, h, *cols, scale=SCALE))

    svg_parts.append('<text x="120" y="460" fill="#ffffff" font-family="monospace" font-size="11" opacity="0.8">NEW YORK CITY</text>')
    svg_parts.append('<text x="380" y="460" fill="#ff69b4" font-family="monospace" font-size="11" opacity="0.8">ATLANTA</text>')
    svg_parts.append('<text x="700" y="460" fill="#ffffff" font-family="monospace" font-size="11" opacity="0.8">SAN FRANCISCO</text>')
    svg_parts.append("</svg>")

    return "\n".join(svg_parts)

if __name__ == "__main__":
    weeks = fetch_contributions()
    svg = render_city(weeks)
    with open("city-contributions.svg", "w") as f:
        f.write(svg)
    print("Generated city-contributions.svg")
