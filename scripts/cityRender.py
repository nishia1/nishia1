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
    print("API Response:", response_json)  # ← must be FIRST
    weeks = response_json["data"]["user"]["contributionsCollection"]["contributionCalendar"]["weeks"]
    return [[day["contributionCount"] for day in week["contributionDays"]] for week in weeks]

# --- Building landmark shapes (isometric SVG paths) ---
# Each landmark is a function that returns SVG path data given (x, y, height)
# x, y are isometric screen coords, height scales with contributions

LANDMARKS = {
    "empire_state": {
        "city": "NYC",
        "color": "#a0b4c8",
        "accent": "#d4e4f0",
        "shape": "stepped",   # wide base, stepped tiers, antenna
    },
    "chrysler": {
        "city": "NYC",
        "color": "#b8c8d8",
        "accent": "#e8f0f8",
        "shape": "tapered",   # art deco taper, eagle gargoyles implied
    },
    "flatiron": {
        "city": "NYC",
        "color": "#c8b89c",
        "accent": "#e8d8c0",
        "shape": "wedge",     # triangular footprint
    },
    "transamerica": {
        "city": "SF",
        "color": "#e8e0d0",
        "accent": "#f8f4ec",
        "shape": "pyramid",   # pure pyramid
    },
    "salesforce": {
        "city": "SF",
        "color": "#90b0d0",
        "accent": "#c0d8f0",
        "shape": "tall_rect", # tall rectangular with rounded top
    },
    "bofa_plaza": {
        "city": "ATL",
        "color": "#c04040",
        "accent": "#e06060",
        "shape": "notched",   # distinctive red granite notched top
    },
    "westin_peachtree": {
        "city": "ATL",
        "color": "#808898",
        "accent": "#b0b8c8",
        "shape": "cylinder",  # cylindrical tower
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
        # top face
        top = f"""<polygon points="
            {tx},{ty}
            {tx+w},{ty+h2}
            {tx},{ty+scale}
            {tx-w},{ty+h2}" fill="{color_top}"/>"""
        # left face
        left = f"""<polygon points="
            {tx-w},{ty+h2}
            {tx},{ty+scale}
            {tx},{ty+scale*2}
            {tx-w},{ty+h2+scale}" fill="{color_left}"/>"""
        # right face
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
    colors = [("#a0b4c8","#708898","#8098b0"),
              ("#b0c4d8","#8098a8","#90a8c0"),
              ("#c0d4e8","#90a8b8","#a0b8d0")]
    widths = [3, 2, 1]
    heights = [base_h, max(1, base_h//2), max(1, base_h//4)]
    offsets = [0, 1, 2]
    for tier, (w, h, off, col) in enumerate(zip(widths, heights, offsets, colors)):
        for dx in range(w):
            for dy in range(w):
                svg.append(draw_building_block(cx+off+dx, cy+off+dy, h, *col, scale=scale))
    # antenna — single tall thin block
    svg.append(draw_building_block(cx+2, cy+2, base_h + base_h//2, "#d0e0f0","#a0b0c0","#b0c0d0", scale=scale//2))
    return "\n".join(svg)

def landmark_transamerica(cx, cy, base_h, scale=20):
    """Transamerica: pyramid that narrows each floor."""
    svg = []
    color = ("#e8e0d0","#b8b0a0","#c8c0b0")
    for z in range(base_h):
        inset = z * 0.4
        tx, ty = iso_project(cx, cy, z, scale=scale)
        w = max(2, scale - int(inset*2))
        svg.append(f'<polygon points="{tx},{ty} {tx+w},{ty+w*0.5} {tx},{ty+w} {tx-w},{ty+w*0.5}" fill="{color[0]}"/>')
        svg.append(f'<polygon points="{tx-w},{ty+w*0.5} {tx},{ty+w} {tx},{ty+w*2} {tx-w},{ty+w*0.5+w}" fill="{color[1]}"/>')
        svg.append(f'<polygon points="{tx+w},{ty+w*0.5} {tx},{ty+w} {tx},{ty+w*2} {tx+w},{ty+w*0.5+w}" fill="{color[2]}"/>')
    return "\n".join(svg)

def landmark_bofa(cx, cy, base_h, scale=20):
    """BofA Plaza ATL: red granite, notched crown."""
    svg = []
    for z in range(base_h):
        notch = z > base_h - 3
        col = ("#c04040","#902020","#a03030") if not notch else ("#d06060","#a04040","#b05050")
        svg.append(draw_building_block(cx, cy, 1, *col, scale=scale))
    return "\n".join(svg)

# --- Main render ---
def render_city(weeks):
    svg_parts = []
    svg_parts.append("""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1200 500"
        style="background: linear-gradient(180deg, #1a0530 0%, #6b1a3a 30%, #c4542a 65%, #f0a040 100%)"
    
    # Ground grid
    SCALE = 12
    MAX_HEIGHT = 8
    
    # Assign landmark positions — sprinkled across the contribution grid
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
                # Generic city blocks with city-tinted colors
                city_zone = week_i % 3
                if city_zone == 0:
                    cols = ("#ffffff","#cccccc","#e0e0e0")   # white
                elif city_zone == 1:
                    cols = ("#ff69b4","#c0306a","#e04d90")   # pink
                else:
                    cols = ("#222222","#111111","#1a1a1a")   # black
                svg_parts.append(draw_building_block(week_i, day_i, h, *cols, scale=SCALE))

    # City label overlays
    svg_parts.append('<text x="120" y="460" fill="#a0b4c8" font-family="monospace" font-size="11" opacity="0.7">NEW YORK CITY</text>')
    svg_parts.append('<text x="380" y="460" fill="#c09080" font-family="monospace" font-size="11" opacity="0.7">ATLANTA</text>')
    svg_parts.append('<text x="700" y="460" fill="#90b0d0" font-family="monospace" font-size="11" opacity="0.7">SAN FRANCISCO</text>')
    svg_parts.append("</svg>")
    
    return "\n".join(svg_parts)

if __name__ == "__main__":
    weeks = fetch_contributions()
    svg = render_city(weeks)
    with open("city-contributions.svg", "w") as f:
        f.write(svg)
    print("Generated city-contributions.svg")
