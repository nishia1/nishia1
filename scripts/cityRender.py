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


def draw_iso_face(tx, ty, w, h2, scale, color_top, color_left, color_right):
    """Draw a single isometric cube face-set at already-projected screen position."""
    top = (f'<polygon points="{tx},{ty} {tx+w},{ty+h2} {tx},{ty+scale} {tx-w},{ty+h2}"'
           f' fill="{color_top}"/>')
    left = (f'<polygon points="{tx-w},{ty+h2} {tx},{ty+scale} {tx},{ty+scale*2} {tx-w},{ty+h2+scale}"'
            f' fill="{color_left}"/>')
    right = (f'<polygon points="{tx+w},{ty+h2} {tx},{ty+scale} {tx},{ty+scale*2} {tx+w},{ty+h2+scale}"'
             f' fill="{color_right}"/>')
    return top + left + right


def draw_building_block(x, y, h, color_top, color_left, color_right, scale=20):
    """Draw a column of isometric cubes at grid position (x, y) with height h."""
    pieces = []
    for z in range(h):
        tx, ty = iso_project(x, y, z, scale=scale)
        pieces.append(draw_iso_face(tx, ty, scale, scale * 0.5, scale,
                                    color_top, color_left, color_right))
    return "\n".join(pieces)


def landmark_empire_state(cx, cy, base_h, scale=20):
    """
    Empire State: three stepped tiers that stack in z, plus a thin spire.
    Tier 1: 3x3 footprint, height = base_h          (pink)
    Tier 2: 1x1 footprint, height = base_h//2       (white), sits on top of tier 1
    Tier 3: 1x1 footprint, height = base_h//4       (pink),  sits on top of tier 2
    Spire:  SVG line from the top of tier 3 upward
    """
    svg = []

    tier_specs = [
        # (footprint_size, height, color_top, color_left, color_right, cx_offset, cy_offset)
        (3, base_h,        "#ff69b4", "#c0306a", "#e04d90", 0, 0),
        (1, base_h // 2,   "#ffffff", "#cccccc", "#e0e0e0", 1, 1),
        (1, base_h // 4,   "#ff69b4", "#c0306a", "#e04d90", 1, 1),
    ]

    z_cursor = 0
    for fp, h, ct, cl, cr, xoff, yoff in tier_specs:
        h = max(1, h)
        for dx in range(fp):
            for dy in range(fp):
                for z in range(h):
                    tx, ty = iso_project(cx + xoff + dx, cy + yoff + dy, z_cursor + z, scale=scale)
                    svg.append(draw_iso_face(tx, ty, scale, scale * 0.5, scale, ct, cl, cr))
        z_cursor += h

    # Spire: project the top of the central column
    spire_tx, spire_ty = iso_project(cx + 1, cy + 1, z_cursor, scale=scale)
    svg.append(f'<line x1="{spire_tx}" y1="{spire_ty}" '
               f'x2="{spire_tx}" y2="{spire_ty - scale * 2}" '
               f'stroke="#ffffff" stroke-width="1.5"/>')

    return "\n".join(svg)


def landmark_transamerica(cx, cy, base_h, scale=20):
    """
    Transamerica pyramid: each floor is one story tall, but the top-face
    polygon shrinks linearly toward the tip.  Left/right faces are redrawn
    each floor to match the shrinking width.
    """
    svg = []
    for z in range(base_h):
        # fraction 0 (bottom) -> 1 (top)
        frac = z / max(base_h - 1, 1)
        w = max(3, int(scale * (1 - frac * 0.85)))   # shrinks from scale down to ~15% of scale
        h2 = w * 0.5

        tx, ty = iso_project(cx, cy, z, scale=scale)

        # Top face (diamond)
        top = (f'<polygon points="{tx},{ty} {tx+w},{ty+h2} {tx},{ty+w} {tx-w},{ty+h2}"'
               f' fill="#ffffff" opacity="0.92"/>')
        # Left face
        left = (f'<polygon points="{tx-w},{ty+h2} {tx},{ty+w} {tx},{ty+w+scale} {tx-w},{ty+h2+scale}"'
                f' fill="#cccccc"/>')
        # Right face
        right = (f'<polygon points="{tx+w},{ty+h2} {tx},{ty+w} {tx},{ty+w+scale} {tx+w},{ty+h2+scale}"'
                 f' fill="#e0e0e0"/>')
        svg.extend([top, left, right])

    # Needle
    spire_tx, spire_ty = iso_project(cx, cy, base_h, scale=scale)
    svg.append(f'<line x1="{spire_tx}" y1="{spire_ty}" '
               f'x2="{spire_tx}" y2="{spire_ty - scale * 2.5}" '
               f'stroke="#dddddd" stroke-width="1"/>')

    return "\n".join(svg)


def landmark_chrysler(cx, cy, base_h, scale=20):
    """
    Chrysler: wide gray base, then a pink art-deco setback, then eagle-crown
    white setback, then a thin needle spire.
    """
    svg = []
    z_cursor = 0

    base = max(1, base_h)
    mid  = max(1, base_h // 2)
    crown = max(1, base_h // 4)

    # Base: grey
    for z in range(base):
        tx, ty = iso_project(cx, cy, z_cursor + z, scale=scale)
        svg.append(draw_iso_face(tx, ty, scale, scale * 0.5, scale,
                                 "#e8e8e8", "#aaaaaa", "#cccccc"))
    z_cursor += base

    # Mid setback (inset 0.5 units): pink art-deco
    for z in range(mid):
        tx, ty = iso_project(cx, cy, z_cursor + z, scale=scale)
        svg.append(draw_iso_face(tx, ty, int(scale * 0.78), scale * 0.39, scale,
                                 "#ff69b4", "#c0306a", "#e04d90"))
    z_cursor += mid

    # Crown: white eagle setbacks
    for z in range(crown):
        tx, ty = iso_project(cx, cy, z_cursor + z, scale=scale)
        svg.append(draw_iso_face(tx, ty, int(scale * 0.55), scale * 0.28, scale,
                                 "#ffffff", "#dddddd", "#eeeeee"))
    z_cursor += crown

    # Needle
    spire_tx, spire_ty = iso_project(cx, cy, z_cursor, scale=scale)
    svg.append(f'<line x1="{spire_tx}" y1="{spire_ty}" '
               f'x2="{spire_tx}" y2="{spire_ty - scale * 2}" '
               f'stroke="#cccccc" stroke-width="1.5"/>')

    return "\n".join(svg)


def landmark_flatiron(cx, cy, base_h, scale=20):
    """
    Flatiron: wedge footprint — a 3x1 base tapering to 1x1 at the top.
    Dark body with pink accent windows.
    """
    svg = []
    # Three columns at y+0, y+1, y+2 — all same height, giving a wedge silhouette
    footprints = [(cx,   cy,   base_h,       "#222222", "#111111", "#1a1a1a"),
                  (cx+1, cy,   base_h // 2,  "#ff69b4", "#c0306a", "#e04d90"),
                  (cx+2, cy,   base_h // 4,  "#222222", "#111111", "#1a1a1a")]
    for gx, gy, h, ct, cl, cr in footprints:
        h = max(1, h)
        for z in range(h):
            tx, ty = iso_project(gx, gy, z, scale=scale)
            svg.append(draw_iso_face(tx, ty, scale, scale * 0.5, scale, ct, cl, cr))
    return "\n".join(svg)


def landmark_salesforce(cx, cy, base_h, scale=20):
    """
    Salesforce Tower SF: very tall rectangle (2x2), pink glass exterior,
    with a lighter crown at the top ~15% of height.
    """
    svg = []
    crown_start = max(1, int(base_h * 0.85))

    for z in range(base_h):
        is_crown = z >= crown_start
        ct = "#ffaacc" if is_crown else "#ff69b4"
        cl = "#e04d90" if is_crown else "#c0306a"
        cr = "#ffccdd" if is_crown else "#e04d90"
        for dx in range(2):
            for dy in range(2):
                tx, ty = iso_project(cx + dx, cy + dy, z, scale=scale)
                svg.append(draw_iso_face(tx, ty, scale, scale * 0.5, scale, ct, cl, cr))

    return "\n".join(svg)


def landmark_bofa(cx, cy, base_h, scale=20):
    """
    BofA Plaza ATL: dark body with a pink glowing crown on the top 2 floors.
    Fixed: each floor now correctly drawn at its own z level.
    """
    svg = []
    crown_floors = 2

    for z in range(base_h):
        is_crown = z >= (base_h - crown_floors)
        ct = "#ff69b4" if is_crown else "#222222"
        cl = "#c0306a" if is_crown else "#111111"
        cr = "#e04d90" if is_crown else "#1a1a1a"
        tx, ty = iso_project(cx, cy, z, scale=scale)
        svg.append(draw_iso_face(tx, ty, scale, scale * 0.5, scale, ct, cl, cr))

    return "\n".join(svg)


def landmark_westin_peachtree(cx, cy, base_h, scale=20):
    """
    Westin Peachtree ATL: cylindrical tower approximated as a narrower
    rounded column — alternating white/light-gray rings, giving a curved feel.
    """
    svg = []
    for z in range(base_h):
        # Alternate ring color for banding effect
        ring = z % 3
        ct = "#ffffff" if ring == 0 else ("#eeeeee" if ring == 1 else "#ff69b4")
        cl = "#cccccc" if ring == 0 else ("#bbbbbb" if ring == 1 else "#c0306a")
        cr = "#dddddd" if ring == 0 else ("#cccccc" if ring == 1 else "#e04d90")
        # Narrower footprint to simulate cylindrical silhouette
        w = int(scale * 0.7)
        tx, ty = iso_project(cx, cy, z, scale=scale)
        svg.append(draw_iso_face(tx, ty, w, w * 0.5, scale, ct, cl, cr))

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
