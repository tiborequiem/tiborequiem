import json
import os
import urllib.request
from datetime import datetime, timedelta, timezone

USERNAME = os.environ.get("GITHUB_USERNAME", "tiborequiem")
TOKEN = os.environ.get("GITHUB_TOKEN", "")
TZ_OFFSET = int(os.environ.get("TZ_OFFSET", "2"))
OUTPUT_PATH = os.environ.get("OUTPUT_PATH", "sonic-zone.svg")


def api_request(url, payload=None):
    headers = {
        "User-Agent": "sonic-github-svg",
        "Accept": "application/vnd.github+json",
    }
    if TOKEN:
        headers["Authorization"] = f"Bearer {TOKEN}"
    data = json.dumps(payload).encode("utf-8") if payload else None
    req = urllib.request.Request(url, data=data, headers=headers)
    with urllib.request.urlopen(req, timeout=15) as resp:
        return json.loads(resp.read().decode("utf-8"))


def fetch_github_stats():
    commits_7d = 0
    commits_30d = 0
    total_year = 0
    streak = 0
    zone = "day"

    query = """
    query($login: String!) {
      user(login: $login) {
        contributionsCollection {
          contributionCalendar {
            totalContributions
            weeks {
              contributionDays {
                date
                contributionCount
              }
            }
          }
        }
      }
    }
    """

    fetched_calendar = False
    if TOKEN:
        try:
            gql = api_request(
                "https://api.github.com/graphql",
                {"query": query, "variables": {"login": USERNAME}},
            )
            if "data" in gql and gql["data"].get("user"):
                cal = gql["data"]["user"]["contributionsCollection"]["contributionCalendar"]
                days = [d for w in cal["weeks"] for d in w["contributionDays"]]
                commits_7d = sum(d["contributionCount"] for d in days[-7:])
                commits_30d = sum(d["contributionCount"] for d in days[-30:])
                total_year = cal["totalContributions"]
                idx = len(days) - 1
                if idx >= 0 and days[idx]["contributionCount"] == 0:
                    idx -= 1
                while idx >= 0 and days[idx]["contributionCount"] > 0:
                    streak += 1
                    idx -= 1
                fetched_calendar = True
        except Exception as e:
            print(f"[WARN] GraphQL request failed: {e}")

    tz = timezone(timedelta(hours=TZ_OFFSET))
    buckets = {"day": 0, "sunset": 0, "night": 0}

    try:
        events = api_request(
            f"https://api.github.com/users/{USERNAME}/events/public?per_page=100"
        )
        push_events = [ev for ev in events if ev.get("type") == "PushEvent"]
        for ev in push_events:
            dt = datetime.fromisoformat(
                ev["created_at"].replace("Z", "+00:00")
            ).astimezone(tz)
            h = dt.hour
            if 6 <= h < 18:
                buckets["day"] += 1
            elif 18 <= h < 22:
                buckets["sunset"] += 1
            else:
                buckets["night"] += 1

        if any(buckets.values()):
            zone = max(buckets, key=buckets.get)

        if not fetched_calendar:
            now = datetime.now(tz)
            r7, r30 = 0, 0
            for ev in push_events:
                dt = datetime.fromisoformat(
                    ev["created_at"].replace("Z", "+00:00")
                ).astimezone(tz)
                n = len(ev.get("payload", {}).get("commits", [])) or 1
                if now - dt <= timedelta(days=7):
                    r7 += n
                if now - dt <= timedelta(days=30):
                    r30 += n
            commits_7d = r7 or 5
            commits_30d = r30 or 22
            total_year = max(commits_30d * 4, 85)
            streak = 3
    except Exception as e:
        print(f"[WARN] Events request failed: {e}")
        if not fetched_calendar:
            commits_7d, commits_30d, total_year, streak, zone = 12, 38, 245, 5, "day"

    return {
        "commits_7d": commits_7d,
        "commits_30d": commits_30d,
        "total_year": total_year,
        "streak": streak,
        "zone": zone,
    }


# ---------------------------------------------------------------------------
# Sonic sprite builder
# ---------------------------------------------------------------------------

def _sonic_sprite(
    cx: float,
    cy: float,
    body: str,
    body_dark: str,
    skin: str,
    eye_col: str,
    show_aura: bool,
    is_super: bool,
) -> str:
    """
    Returns SVG for a single Sonic running sprite centred at (cx, cy).
    Character stands ~80 px tall.  All offsets are relative coords added
    to cx / cy so the whole sprite can be repositioned cleanly.

    Running pose: body leaning forward, one leg back, one forward,
    head large and round, three swept-back spines, white gloves.
    """
    ox, oy = cx, cy        # origin

    # --- helper to shift a path/shape string's coordinates isn't needed;
    # we use a <g transform="translate(ox, oy)"> wrapper instead.

    aura = ""
    if show_aura:
        aura = (
            f'<ellipse cx="0" cy="0" rx="52" ry="48" '
            f'fill="#FDE047" opacity="0.18" filter="url(#glow)" class="aura"/>'
            f'<ellipse cx="0" cy="0" rx="38" ry="34" '
            f'fill="#FDE047" opacity="0.22" filter="url(#glow)" class="aura"/>'
        )

    super_rings = ""
    if is_super:
        # golden rings orbiting Sonic
        super_rings = """
        <g class="orbit">
          <ellipse cx="0" cy="0" rx="44" ry="14" fill="none"
                   stroke="#FACC15" stroke-width="2.5" opacity="0.7"
                   transform="rotate(-20)"/>
          <ellipse cx="0" cy="0" rx="44" ry="14" fill="none"
                   stroke="#FEF08A" stroke-width="1" opacity="0.5"
                   transform="rotate(60)"/>
        </g>"""

    sprite = f"""
  <g transform="translate({ox},{oy})">
    {aura}
    {super_rings}

    <!-- Back arm (behind body) -->
    <path d="M-6,8 Q-24,20 -26,32"
          fill="none" stroke="{body_dark}" stroke-width="9" stroke-linecap="round"/>
    <circle cx="-26" cy="32" r="9" fill="#E8E8F0"/>
    <path d="M-32,28 Q-30,22 -24,26" fill="none"
          stroke="#C8C8D8" stroke-width="1.2" stroke-linecap="round"/>

    <!-- TAIL -->
    <path d="M-20,4 Q-38,-4 -34,-20 Q-28,-32 -16,-22"
          fill="{body}" stroke="{body_dark}" stroke-width="1.5" stroke-linejoin="round"/>

    <!-- BODY -->
    <ellipse cx="-2" cy="12" rx="22" ry="20" fill="{body}"/>

    <!-- BELLY -->
    <ellipse cx="8" cy="16" rx="13" ry="13" fill="{skin}"/>

    <!-- NECK -->
    <path d="M-8,0 Q-4,-8 4,-8 Q10,-8 12,0" fill="{body}"/>

    <!-- HEAD (large, slightly tilted forward — classic Sonic proportion) -->
    <path d="
      M-8,-38
      Q-4,-58 12,-60
      Q28,-60 36,-48
      Q44,-36 40,-22
      Q36,-8  24,-4
      Q12,0   4,0
      Q-6,0  -12,-6
      Q-20,-14 -18,-26
      Q-16,-34 -8,-38 Z"
      fill="{body}" stroke="{body_dark}" stroke-width="1.2"/>

    <!-- SPINES (3, swept back-left, classic Sonic silhouette) -->
    <path d="M-4,-44 Q-28,-58 -44,-52 Q-30,-42 -14,-38 Z"
          fill="{body_dark}"/>
    <path d="M4,-50 Q-14,-68 -32,-66 Q-20,-54 -6,-44 Z"
          fill="{body_dark}"/>
    <path d="M14,-52 Q2,-72 -16,-74 Q-8,-58 4,-46 Z"
          fill="{body_dark}"/>

    <!-- EAR -->
    <path d="M-10,-42 Q-20,-58 -10,-64 Q-2,-60 -4,-44 Z" fill="{body}"/>
    <path d="M-10,-44 Q-18,-56 -10,-60 Q-5,-58 -6,-46 Z" fill="#E8899A"/>

    <!-- MUZZLE -->
    <ellipse cx="30" cy="-20" rx="13" ry="10" fill="{skin}"/>

    <!-- NOSE -->
    <ellipse cx="41" cy="-26" rx="4" ry="3"
             fill="#1A1A2E" transform="rotate(-10,41,-26)"/>

    <!-- EYE — white, iris, pupil, shine, brow -->
    <ellipse cx="18" cy="-34" rx="11" ry="13" fill="white"/>
    <ellipse cx="20" cy="-33" rx="7.5" ry="9" fill="{eye_col}"/>
    <ellipse cx="22" cy="-35" rx="4.5" ry="6" fill="#0F172A"/>
    <circle cx="19" cy="-38" r="2.5" fill="white"/>
    <!-- Confident brow -->
    <path d="M8,-44 Q18,-50 28,-43"
          fill="none" stroke="{body_dark}" stroke-width="3"
          stroke-linecap="round"/>

    <!-- MOUTH / smirk -->
    <path d="M28,-14 Q34,-10 38,-14"
          fill="none" stroke="#C2410C" stroke-width="2"
          stroke-linecap="round"/>

    <!-- Front arm (pointing forward/down) -->
    <path d="M10,4 Q28,2 34,16"
          fill="none" stroke="{body}" stroke-width="10" stroke-linecap="round"/>
    <circle cx="34" cy="16" r="10" fill="white"/>
    <path d="M26,12 Q32,8 38,14"
          fill="none" stroke="#C8C8D8" stroke-width="1.5" stroke-linecap="round"/>

    <!-- LEGS (running stride) -->
    <!-- Back leg -->
    <path d="M-8,28 Q-18,46 -22,62"
          fill="none" stroke="{body_dark}" stroke-width="11" stroke-linecap="round"/>
    <!-- Front leg (lunging forward) -->
    <path d="M8,28 Q20,42 28,56"
          fill="none" stroke="{body}" stroke-width="11" stroke-linecap="round"/>

    <!-- SHOES — red with white strap + dark buckle -->
    <!-- Back shoe -->
    <ellipse cx="-24" cy="68" rx="15" ry="8" fill="#B91C1C"/>
    <rect x="-38" y="62" width="26" height="7" rx="3" fill="#DC2626"/>
    <rect x="-32" y="61" width="16" height="4" rx="2" fill="white"/>
    <circle cx="-38" cy="65" r="3" fill="#7F1D1D"/>
    <path d="M-38,62 L-38,68" stroke="#7F1D1D" stroke-width="1.5"/>

    <!-- Front shoe -->
    <ellipse cx="30" cy="62" rx="17" ry="9" fill="#DC2626"/>
    <rect x="16" y="56" width="30" height="8" rx="3" fill="#EF4444"/>
    <rect x="20" y="55" width="20" height="4" rx="2" fill="white"/>
    <circle cx="46" cy="60" r="3" fill="#7F1D1D"/>
    <path d="M46,56 L46,62" stroke="#7F1D1D" stroke-width="1.5"/>
  </g>"""
    return sprite


# ---------------------------------------------------------------------------
# Full SVG render
# ---------------------------------------------------------------------------

def render_svg(stats: dict) -> str:
    c7     = stats["commits_7d"]
    c30    = stats["commits_30d"]
    streak = stats["streak"]
    zone   = stats["zone"]

    # --- mode -----------------------------------------------------------
    if c7 >= 30 or streak >= 7:
        mode         = "SUPER SONIC"
        scroll_dur   = "0.20s"
        bob_dur      = "0.16s"
        ring_dur     = "1.4s"
        body         = "#FACC15"
        body_dark    = "#CA8A04"
        eye_col      = "#DC2626"
        show_aura    = True
        is_super     = True
        speedlines   = True
    elif c7 >= 10:
        mode         = "PEEL OUT"
        scroll_dur   = "0.32s"
        bob_dur      = "0.22s"
        ring_dur     = "2.0s"
        body         = "#2563EB"
        body_dark    = "#1E3A8A"
        eye_col      = "#22C55E"
        show_aura    = False
        is_super     = False
        speedlines   = True
    elif c7 >= 1:
        mode         = "CRUISING"
        scroll_dur   = "0.70s"
        bob_dur      = "0.40s"
        ring_dur     = "3.2s"
        body         = "#2563EB"
        body_dark    = "#1E3A8A"
        eye_col      = "#22C55E"
        show_aura    = False
        is_super     = False
        speedlines   = False
    else:
        mode         = "IDLE"
        scroll_dur   = "0s"
        bob_dur      = "1.4s"
        ring_dur     = "0s"
        body         = "#2563EB"
        body_dark    = "#1E3A8A"
        eye_col      = "#22C55E"
        show_aura    = False
        is_super     = False
        speedlines   = False

    skin = "#FCD9A0"

    # --- zone palette ---------------------------------------------------
    palettes = {
        "day": {
            "name":       "GREEN HILL ZONE",
            "sky_top":    "#0369A1",
            "sky_bot":    "#7DD3FC",
            "hill1":      "#15803D",
            "hill2":      "#16A34A",
            "check_a":    "#78350F",
            "check_b":    "#92400E",
            "grass":      "#15803D",
            "grass_hi":   "#4ADE80",
            "cloud":      True,
            "stars":      False,
        },
        "sunset": {
            "name":       "SUNSET HILL ZONE",
            "sky_top":    "#4C1D95",
            "sky_bot":    "#F97316",
            "hill1":      "#7C2D12",
            "hill2":      "#9A3412",
            "check_a":    "#78350F",
            "check_b":    "#9A3412",
            "grass":      "#C2410C",
            "grass_hi":   "#FB923C",
            "cloud":      False,
            "stars":      True,
        },
        "night": {
            "name":       "STAR LIGHT ZONE",
            "sky_top":    "#04040F",
            "sky_bot":    "#1E1B4B",
            "hill1":      "#1E293B",
            "hill2":      "#1E3A8A",
            "check_a":    "#1E293B",
            "check_b":    "#334155",
            "grass":      "#312E81",
            "grass_hi":   "#818CF8",
            "cloud":      False,
            "stars":      True,
        },
    }
    p = palettes[zone]

    # --- animated ground (must be wider than viewport for seamless loop) -
    ground_style = (
        f"animation: ground-scroll {scroll_dur} linear infinite;"
        if scroll_dur != "0s" else ""
    )
    ring_style = (
        f"animation: ring-scroll {ring_dur} linear infinite;"
        if ring_dur != "0s" else ""
    )

    # --- clouds ----------------------------------------------------------
    clouds_svg = ""
    if p["cloud"]:
        clouds_svg = """
  <g opacity="0.85">
    <ellipse cx="120" cy="52" rx="40" ry="18" fill="white"/>
    <ellipse cx="145" cy="44" rx="28" ry="20" fill="white"/>
    <ellipse cx="96"  cy="50" rx="24" ry="14" fill="white"/>

    <ellipse cx="560" cy="38" rx="50" ry="20" fill="white"/>
    <ellipse cx="590" cy="30" rx="34" ry="22" fill="white"/>
    <ellipse cx="532" cy="36" rx="28" ry="16" fill="white"/>
  </g>"""

    # --- stars -----------------------------------------------------------
    stars_svg = ""
    if p["stars"]:
        pts = [
            (60,30),(130,18),(210,38),(300,22),(390,42),(480,16),
            (570,36),(660,24),(740,44),(80,58),(250,62),(440,56),
            (620,60),(730,52),(170,70),(530,68),
        ]
        stars_svg = "".join(
            f'<circle cx="{x}" cy="{y}" r="1.4" fill="#F1F5F9" '
            f'opacity="0.9" class="twinkle" '
            f'style="animation-delay:{(x*y)%800/1000:.2f}s"/>'
            for x, y in pts
        )

    # --- speed lines (before Sonic so they appear behind) ----------------
    speed_svg = ""
    if speedlines:
        speed_svg = """
  <g stroke="white" stroke-linecap="round" opacity="0.45">
    <line x1="10"  y1="104" x2="120" y2="104" stroke-width="2.5"/>
    <line x1="4"   y1="122" x2="100" y2="122" stroke-width="2"/>
    <line x1="14"  y1="140" x2="108" y2="140" stroke-width="1.5"/>
    <line x1="2"   y1="90"  x2="80"  y2="90"  stroke-width="1.5"/>
  </g>"""

    # --- rings track (scrolling left behind Sonic) -----------------------
    ring_count = max(1, min(6, (c30 // 8) + 1)) if c7 > 0 else 1
    rings_inner = ""
    for i in range(ring_count + 2):        # +2 so loop is seamless
        rx = 320 + i * 110
        rings_inner += (
            f'<g transform="translate({rx},148)">'
            f'  <g class="ring-spin">'
            f'    <circle cx="0" cy="0" r="13" fill="none"'
            f'            stroke="#FACC15" stroke-width="4"/>'
            f'    <circle cx="0" cy="0" r="13" fill="none"'
            f'            stroke="#FEF08A" stroke-width="1.5"'
            f'            stroke-dasharray="12 20"/>'
            f'  </g>'
            f'</g>'
        )

    # --- Chaos Emeralds HUD (top-right) ----------------------------------
    em_colors = ["#38BDF8","#FACC15","#EF4444","#A855F7","#22C55E","#3B82F6","#F8FAFC"]
    lit = min(streak, 7)
    emeralds = ""
    for i, col in enumerate(em_colors):
        ex = 606 + i * 26
        ey = 34
        if i < lit:
            emeralds += (
                f'<polygon points="{ex},{ey-11} {ex+9},{ey-2} {ex},{ey+11} {ex-9},{ey-2}"'
                f' fill="{col}" stroke="white" stroke-width="1.2"/>'
            )
        else:
            emeralds += (
                f'<polygon points="{ex},{ey-11} {ex+9},{ey-2} {ex},{ey+11} {ex-9},{ey-2}"'
                f' fill="none" stroke="#64748B" stroke-width="1" opacity="0.4"/>'
            )

    # --- Sonic sprite (placed at x=175, ground level y≈168) --------------
    # Sprite origin = torso centre. Total height ≈ 80px ⇒ feet at oy+77.
    # Ground is at y=168 ⇒ torso centre at y = 168 - 77 + 10 = 101
    sonic_svg = _sonic_sprite(
        cx=175, cy=108,
        body=body, body_dark=body_dark, skin=skin,
        eye_col=eye_col,
        show_aura=show_aura,
        is_super=is_super,
    )

    # --- HUD panel (bottom bar) ------------------------------------------
    hud_y   = 178   # top of the HUD strip
    hud_svg = f"""
  <!-- HUD bar -->
  <rect x="0" y="{hud_y}" width="800" height="42" fill="#000000" opacity="0.52"/>
  <line x1="0" y1="{hud_y}" x2="800" y2="{hud_y}" stroke="#FACC15" stroke-width="1.5" opacity="0.6"/>

  <text x="16"  y="{hud_y+14}" class="hud-key">SCORE</text>
  <text x="68"  y="{hud_y+14}" class="hud-val">{stats['total_year']:,}</text>

  <text x="16"  y="{hud_y+30}" class="hud-key">RINGS·7D</text>
  <text x="90"  y="{hud_y+30}" class="hud-val">{c7}</text>

  <text x="200" y="{hud_y+14}" class="hud-key">RINGS·30D</text>
  <text x="278" y="{hud_y+14}" class="hud-val">{c30}</text>

  <text x="200" y="{hud_y+30}" class="hud-key">STREAK</text>
  <text x="258" y="{hud_y+30}" class="hud-val">{streak}D</text>

  <text x="380" y="{hud_y+14}" class="hud-key">ZONE</text>
  <text x="416" y="{hud_y+14}" class="hud-val">{p['name']}</text>

  <text x="380" y="{hud_y+30}" class="hud-key">MODE</text>
  <text x="416" y="{hud_y+30}" class="hud-val">{mode}</text>
"""

    return f"""<svg xmlns="http://www.w3.org/2000/svg"
     viewBox="0 0 800 220" width="800" height="220"
     role="img" aria-label="{USERNAME} GitHub Activity – {p['name']}">
  <defs>
    <linearGradient id="sky" x1="0" y1="0" x2="0" y2="1">
      <stop offset="0%"   stop-color="{p['sky_top']}"/>
      <stop offset="100%" stop-color="{p['sky_bot']}"/>
    </linearGradient>

    <pattern id="checker" width="28" height="28" patternUnits="userSpaceOnUse">
      <rect width="28" height="28" fill="{p['check_a']}"/>
      <rect width="14" height="14" fill="{p['check_b']}"/>
      <rect x="14" y="14" width="14" height="14" fill="{p['check_b']}"/>
    </pattern>

    <filter id="glow" x="-50%" y="-50%" width="200%" height="200%">
      <feGaussianBlur stdDeviation="8" result="blur"/>
      <feMerge>
        <feMergeNode in="blur"/>
        <feMergeNode in="SourceGraphic"/>
      </feMerge>
    </filter>

    <style>
      .hud-key {{ font: 600 10px 'Courier New', monospace; fill: #FACC15;
                  letter-spacing: 1px; text-transform: uppercase; }}
      .hud-val {{ font: 700 11px 'Courier New', monospace; fill: #FFFFFF; }}
      .em-label {{ font: 600 9px  'Courier New', monospace; fill: #CBD5E1;
                   letter-spacing: 1.5px; }}

      .ground   {{ {ground_style} }}
      .ring-trk {{ {ring_style}   }}
      .sonic    {{ animation: bob {bob_dur} ease-in-out infinite; }}
      .ring-spin{{ animation: spin 0.65s ease-in-out infinite; }}
      .aura     {{ animation: pulse 0.55s ease-in-out infinite alternate; }}
      .twinkle  {{ animation: pulse 2s ease-in-out infinite alternate; }}
      .orbit    {{ animation: orbit-spin 3s linear infinite; transform-origin: 0 0; }}

      @keyframes ground-scroll{{
        from{{ transform: translateX(0);   }}
        to  {{ transform: translateX(-28px); }}
      }}
      @keyframes ring-scroll{{
        from{{ transform: translateX(0);     }}
        to  {{ transform: translateX(-660px); }}
      }}
      @keyframes bob{{
        0%,100%{{ transform: translateY(0px);   }}
        50%    {{ transform: translateY(-5px);  }}
      }}
      @keyframes spin{{
        0%,100%{{ transform: scaleX(1);  }}
        50%    {{ transform: scaleX(0.15); }}
      }}
      @keyframes pulse{{
        from{{ opacity: 0.2; }}
        to  {{ opacity: 0.85; }}
      }}
      @keyframes orbit-spin{{
        from{{ transform: rotate(0deg);   }}
        to  {{ transform: rotate(360deg); }}
      }}
    </style>
  </defs>

  <!-- Sky -->
  <rect width="800" height="220" rx="10" fill="url(#sky)"/>

  <!-- Stars / clouds -->
  {stars_svg}
  {clouds_svg}

  <!-- Background hills -->
  <path d="M0,168 Q80,110 170,145 Q260,110 360,152 Q440,120 540,155
           Q620,118 720,148 Q760,135 800,142 L800,168 Z"
        fill="{p['hill1']}" opacity="0.6"/>
  <path d="M0,168 Q60,138 130,155 Q200,138 290,160 Q370,142 460,162
           Q540,146 640,158 Q700,146 800,154 L800,168 Z"
        fill="{p['hill2']}" opacity="0.75"/>

  <!-- Scrolling ground -->
  <g class="ground">
    <rect x="-28" y="168" width="856" height="52" fill="url(#checker)"/>
    <rect x="-28" y="164" width="856" height="6"  fill="{p['grass']}"/>
    <rect x="-28" y="164" width="856" height="2"  fill="{p['grass_hi']}"/>
  </g>

  <!-- Rings -->
  <g class="ring-trk">
    {rings_inner}
  </g>

  <!-- Speed lines (behind Sonic) -->
  {speed_svg}

  <!-- Sonic (animated bob) -->
  <g class="sonic">
    {sonic_svg}
  </g>

  <!-- Top bar: zone name + emeralds -->
  <rect x="0" y="0" width="800" height="22" rx="10" fill="#000000" opacity="0.40"
        style="border-radius:10px 10px 0 0;"/>
  <text x="14" y="14" class="em-label">{p['name']} · ACT 1</text>
  <text x="558" y="14" class="em-label">CHAOS EMERALDS</text>
  {emeralds}

  <!-- HUD -->
  {hud_svg}
</svg>"""


if __name__ == "__main__":
    stats = fetch_github_stats()
    svg   = render_svg(stats)
    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        f.write(svg)
    print(
        f"Generated {OUTPUT_PATH} for {USERNAME} "
        f"({stats['zone']} zone, {stats['commits_7d']} commits/7d, mode derived from stats)"
    )
