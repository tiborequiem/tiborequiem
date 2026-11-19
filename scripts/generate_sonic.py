import hashlib
import json
import os
import urllib.request
from datetime import datetime, timedelta, timezone

USERNAME    = os.environ.get("GITHUB_USERNAME", "tiborequiem")
TOKEN       = os.environ.get("GITHUB_TOKEN", "")
TZ_OFFSET   = int(os.environ.get("TZ_OFFSET", "2"))
OUTPUT_PATH = os.environ.get("OUTPUT_PATH", "sonic-zone.svg")


# ── API ───────────────────────────────────────────────────────────────────────

def api_request(url, payload=None):
    headers = {"User-Agent": "sonic-github-svg", "Accept": "application/vnd.github+json"}
    if TOKEN:
        headers["Authorization"] = f"Bearer {TOKEN}"
    data = json.dumps(payload).encode() if payload else None
    req  = urllib.request.Request(url, data=data, headers=headers)
    with urllib.request.urlopen(req, timeout=15) as r:
        return json.loads(r.read().decode())


def fetch_github_stats():
    commits_7d = commits_30d = total_year = streak = 0
    zone = "day"

    if TOKEN:
        try:
            gql = api_request(
                "https://api.github.com/graphql",
                {"query": """query($l:String!){user(login:$l){contributionsCollection{
                 contributionCalendar{totalContributions weeks{contributionDays{
                 date contributionCount}}}}}}""",
                 "variables": {"l": USERNAME}},
            )
            if "data" in gql and gql["data"].get("user"):
                cal  = gql["data"]["user"]["contributionsCollection"]["contributionCalendar"]
                days = [d for w in cal["weeks"] for d in w["contributionDays"]]
                commits_7d  = sum(d["contributionCount"] for d in days[-7:])
                commits_30d = sum(d["contributionCount"] for d in days[-30:])
                total_year  = cal["totalContributions"]
                i = len(days) - 1
                if i >= 0 and days[i]["contributionCount"] == 0:
                    i -= 1
                while i >= 0 and days[i]["contributionCount"] > 0:
                    streak += 1; i -= 1
        except Exception as e:
            print(f"[WARN] GraphQL: {e}")

    tz = timezone(timedelta(hours=TZ_OFFSET))
    buckets = {"day": 0, "sunset": 0, "night": 0}
    try:
        events = api_request(
            f"https://api.github.com/users/{USERNAME}/events/public?per_page=100"
        )
        pushes = [e for e in events if e.get("type") == "PushEvent"]
        for ev in pushes:
            dt = datetime.fromisoformat(ev["created_at"].replace("Z","+00:00")).astimezone(tz)
            h  = dt.hour
            if   6  <= h < 18: buckets["day"]    += 1
            elif 18 <= h < 22: buckets["sunset"] += 1
            else:               buckets["night"]  += 1
        if any(buckets.values()):
            zone = max(buckets, key=buckets.get)
        if not TOKEN:
            now = datetime.now(tz)
            for ev in pushes:
                dt = datetime.fromisoformat(ev["created_at"].replace("Z","+00:00")).astimezone(tz)
                n  = len(ev.get("payload", {}).get("commits", [])) or 1
                if now - dt <= timedelta(days=7):  commits_7d  += n
                if now - dt <= timedelta(days=30): commits_30d += n
            total_year = max(commits_30d * 4, 0)
            streak = 3
    except Exception as e:
        print(f"[WARN] Events: {e}")

    return dict(commits_7d=commits_7d, commits_30d=commits_30d,
                total_year=total_year, streak=streak, zone=zone)


# ── Render ────────────────────────────────────────────────────────────────────

def render_svg(stats: dict) -> str:
    c7     = stats["commits_7d"]
    c30    = stats["commits_30d"]
    streak = stats["streak"]
    zone   = stats["zone"]
    total  = stats["total_year"]

    # ── Mode ─────────────────────────────────────────────────────────────────
    if   c7 >= 30 or streak >= 7: mode, accent = "SUPER SONIC ★", "#F9C200"
    elif c7 >= 10:                 mode, accent = "PEEL OUT",       "#60A5FA"
    elif c7 >= 1:                  mode, accent = "CRUISING",       "#4ADE80"
    else:                          mode, accent = "IDLE",           "#94A3B8"

    scroll_spd = {"SUPER SONIC ★":"0.26s","PEEL OUT":"0.44s",
                  "CRUISING":"0.85s","IDLE":"8s"}[mode]

    # ── Zone palettes — game accurate ────────────────────────────────────────
    P = {
        "day": dict(
            name        = "GREEN HILL ZONE",
            sky_top     = "#5BB8F5",   # classic GHZ sky
            sky_bot     = "#9DD8F9",
            hill_back   = "#2DB447",   # back hill — bright green
            hill_back_s = "#1A8A2E",   # stroke / shadow
            hill_fore   = "#208A38",   # front hill — slightly darker
            hill_fore_s = "#135E22",
            checker_a   = "#6B3800",   # classic Sonic ground checker
            checker_b   = "#9A5200",
            grass       = "#29C242",
            grass_hi    = "#52E870",
            clouds      = True,
            stars       = False,
        ),
        "sunset": dict(
            name        = "SUNSET HILL ZONE",
            sky_top     = "#1C0836",
            sky_bot     = "#C84A18",
            hill_back   = "#7A2C10",
            hill_back_s = "#521C08",
            hill_fore   = "#902E10",
            hill_fore_s = "#62200A",
            checker_a   = "#3C1800",
            checker_b   = "#5E2800",
            grass       = "#A03418",
            grass_hi    = "#C85030",
            clouds      = False,
            stars       = True,
        ),
        "night": dict(
            name        = "STAR LIGHT ZONE",
            sky_top     = "#02020E",
            sky_bot     = "#0C0B30",
            hill_back   = "#0E1842",
            hill_back_s = "#080E26",
            hill_fore   = "#141E5A",
            hill_fore_s = "#0C1438",
            checker_a   = "#080826",
            checker_b   = "#10103A",
            grass       = "#1A1C60",
            grass_hi    = "#4040B8",
            clouds      = False,
            stars       = True,
        ),
    }
    p = P[zone]

    # ── Clouds (day only) ─────────────────────────────────────────────────────
    clouds_svg = ""
    if p["clouds"]:
        def cloud(cx, cy, s=1.0):
            # classic cartoon cloud: 3 overlapping ellipses
            return (
                f'<ellipse cx="{cx}" cy="{cy}" rx="{int(30*s)}" ry="{int(16*s)}" fill="white"/>'
                f'<ellipse cx="{cx+int(24*s)}" cy="{cy-int(7*s)}" rx="{int(20*s)}" ry="{int(14*s)}" fill="white"/>'
                f'<ellipse cx="{cx-int(22*s)}" cy="{cy-int(5*s)}" rx="{int(18*s)}" ry="{int(12*s)}" fill="white"/>'
            )
        clouds_svg = (
            f'<g opacity="0.95">'
            f'{cloud(118, 72, 1.0)}'
            f'{cloud(390, 62, 0.75)}'
            f'{cloud(636, 70, 1.1)}'
            f'</g>'
        )

    # ── Stars (night / sunset) ────────────────────────────────────────────────
    stars_svg = ""
    if p["stars"]:
        pts = []
        for n in range(52):
            h  = int(hashlib.md5(f"star{n}".encode()).hexdigest()[:8], 16)
            sx = (h >> 16) % 740 + 30
            sy = (h & 0xFFFF) % 95 + 48    # stay in scene band
            sr = 0.6 + ((h >> 8) & 0xFF) / 420
            pts.append((sx, sy, sr, n))
        stars_svg = "".join(
            f'<circle cx="{sx}" cy="{sy}" r="{sr:.1f}" fill="white" opacity="0.85"'
            f' style="animation:twinkle {1.6+(n%5)*0.4:.1f}s ease-in-out {(n*83%2000)/1000:.2f}s infinite alternate"/>'
            for sx, sy, sr, n in pts
        )

    # ── Hills (Green Hill Zone silhouette) ────────────────────────────────────
    # Two round humps for the back layer, three for the front.
    # All paths land at y=147 (the grass line) on both ends.
    hill_back = (
        f'<path d="M0,147 C40,147 70,88 155,88 C240,88 270,147 360,147'
        f'          C450,147 480,84 565,84 C650,84 680,147 800,147 Z"'
        f' fill="{p["hill_back"]}" stroke="{p["hill_back_s"]}" stroke-width="1.5"/>'
    )
    hill_fore = (
        f'<path d="M0,147 C30,147 55,116 115,116 C175,116 200,147 270,147'
        f'          C340,147 365,112 435,112 C505,112 530,147 610,147'
        f'          C680,147 710,118 775,118 C800,118 800,138 800,147 Z"'
        f' fill="{p["hill_fore"]}" stroke="{p["hill_fore_s"]}" stroke-width="1"/>'
    )

    # ── Rings ─────────────────────────────────────────────────────────────────
    ring_count = max(2, min(8, (c30 // 7) + 2)) if c7 > 0 else 2
    ring_xs    = [int(210 + i * (380 / max(ring_count - 1, 1)))
                  for i in range(ring_count)]
    rings_svg  = "".join(
        f'<g transform="translate({rx},130)">'
        f'  <g class="ring-spin">'
        f'    <circle cx="0" cy="0" r="11" fill="none" stroke="#F9C200" stroke-width="4.5"/>'
        f'    <circle cx="0" cy="0" r="11" fill="none" stroke="#FFF5A0" stroke-width="1.5"'
        f'            stroke-dasharray="8 14" stroke-linecap="round"/>'
        f'  </g>'
        f'</g>'
        for rx in ring_xs
    )

    # ── Chaos Emeralds ────────────────────────────────────────────────────────
    EM = ["#38BDF8","#F9C200","#EF4444","#A855F7","#22C55E","#3B82F6","#E2E8F0"]
    lit = min(streak, 7)
    em_svg = ""
    for i, col in enumerate(EM):
        ex = 574 + i * 30
        if i < lit:
            em_svg += (
                f'<polygon points="{ex},163 {ex+9},175 {ex},187 {ex-9},175"'
                f' fill="{col}" stroke="rgba(255,255,255,0.6)" stroke-width="0.8"/>'
            )
        else:
            em_svg += (
                f'<polygon points="{ex},163 {ex+9},175 {ex},187 {ex-9},175"'
                f' fill="none" stroke="#2D3748" stroke-width="1"/>'
            )

    return f"""<svg xmlns="http://www.w3.org/2000/svg"
     viewBox="0 0 800 200" width="800" height="200"
     role="img" aria-label="{USERNAME} GitHub — {p['name']} · ACT 1">
  <defs>
    <clipPath id="card"><rect width="800" height="200" rx="12"/></clipPath>

    <linearGradient id="sky" x1="0" y1="0" x2="0" y2="1">
      <stop offset="0%"   stop-color="{p['sky_top']}"/>
      <stop offset="100%" stop-color="{p['sky_bot']}"/>
    </linearGradient>

    <!-- Classic Sonic 1 checkerboard ground -->
    <pattern id="checker" width="32" height="32" patternUnits="userSpaceOnUse">
      <rect width="32" height="32" fill="{p['checker_a']}"/>
      <rect x="0"  y="0"  width="16" height="16" fill="{p['checker_b']}"/>
      <rect x="16" y="16" width="16" height="16" fill="{p['checker_b']}"/>
    </pattern>

    <style>
      /* HUD font — monospace approximates the Sonic bitmap font */
      .hud-lbl {{
        font: 600 9px 'Courier New', Courier, monospace;
        fill: #94A3B8; letter-spacing: 1.5px;
        text-transform: uppercase;
      }}
      .hud-val {{
        font: 700 16px 'Courier New', Courier, monospace;
        fill: #FFFFFF;
      }}
      .zone-name {{
        font: 700 10px 'Courier New', Courier, monospace;
        fill: {accent}; letter-spacing: 1px;
      }}
      .mode-val {{
        font: 700 13px 'Courier New', Courier, monospace;
        fill: {accent}; letter-spacing: 1px;
      }}
      .em-lbl {{
        font: 600 8px 'Courier New', Courier, monospace;
        fill: #4B5563; letter-spacing: 1.5px;
      }}

      /* Ground scroll */
      .ground {{ animation: gscroll {scroll_spd} linear infinite; }}

      /* Ring squish — transform-box keeps origin centred on each ring */
      .ring-spin {{
        transform-box: fill-box;
        transform-origin: center;
        animation: rspin 0.65s ease-in-out infinite;
      }}

      @keyframes gscroll {{
        from {{ transform: translateX(0);    }}
        to   {{ transform: translateX(-32px); }}
      }}
      @keyframes rspin {{
        0%,100% {{ transform: scaleX(1);   }}
        50%     {{ transform: scaleX(0.08); }}
      }}
      @keyframes twinkle {{
        from {{ opacity: 0.1; }}
        to   {{ opacity: 0.9; }}
      }}
    </style>
  </defs>

  <g clip-path="url(#card)">

    <!-- ░░ SKY ░░ -->
    <rect width="800" height="200" fill="url(#sky)"/>

    <!-- Stars / clouds -->
    {stars_svg}
    {clouds_svg}

    <!-- ░░ HILLS ░░ -->
    {hill_back}
    {hill_fore}

    <!-- ░░ GROUND ░░ -->
    <g class="ground">
      <rect x="-32" y="147" width="864" height="53" fill="url(#checker)"/>
      <!-- Grass strip -->
      <rect x="-32" y="143" width="864" height="6" fill="{p['grass']}"/>
      <!-- Specular highlight on grass -->
      <rect x="-32" y="143" width="864" height="2" fill="{p['grass_hi']}" opacity="0.7"/>
    </g>

    <!-- ░░ RINGS ░░ -->
    {rings_svg}

    <!-- ══════════════════════════════════════════
         TOP HUD BAR  (Sonic 1-style: SCORE / RINGS / TIME / STREAK)
         ══════════════════════════════════════════ -->
    <rect width="800" height="46" fill="#000000" opacity="0.72"/>
    <!-- Zone-coloured bottom edge of bar -->
    <rect y="45" width="800" height="1.5" fill="{accent}" opacity="0.55"/>

    <!-- SCORE -->
    <text x="24"  y="17" class="hud-lbl">SCORE</text>
    <text x="24"  y="37" class="hud-val">{total:,}</text>

    <!-- RINGS / 7D -->
    <text x="196" y="17" class="hud-lbl">RINGS · 7D</text>
    <text x="196" y="37" class="hud-val">{c7}</text>

    <!-- RINGS / 30D -->
    <text x="348" y="17" class="hud-lbl">RINGS · 30D</text>
    <text x="348" y="37" class="hud-val">{c30}</text>

    <!-- STREAK -->
    <text x="500" y="17" class="hud-lbl">STREAK</text>
    <text x="500" y="37" class="hud-val">{streak} DAYS</text>

    <!-- Zone name — right aligned -->
    <text x="778" y="22" class="zone-name" text-anchor="end">{p['name']}</text>
    <text x="778" y="38" class="zone-name" text-anchor="end" style="fill:#64748B">ACT 1</text>

    <!-- ══════════════════════════════════════════
         BOTTOM HUD BAR  (MODE + CHAOS EMERALDS)
         ══════════════════════════════════════════ -->
    <rect y="154" width="800" height="46" fill="#000000" opacity="0.72"/>
    <!-- Zone-coloured top edge of bar -->
    <rect y="154" width="800" height="1.5" fill="{accent}" opacity="0.55"/>

    <!-- Mode -->
    <text x="24"  y="171" class="em-lbl">MODE</text>
    <text x="24"  y="188" class="mode-val">{mode}</text>

    <!-- Chaos Emeralds -->
    <text x="574" y="161" class="em-lbl">CHAOS EMERALDS  ({lit}/7)</text>
    {em_svg}

  </g>

  <!-- Card border -->
  <rect width="800" height="200" rx="12" fill="none"
        stroke="{accent}" stroke-width="1.5" opacity="0.35"/>
</svg>"""


if __name__ == "__main__":
    stats = fetch_github_stats()
    svg   = render_svg(stats)
    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        f.write(svg)
    print(f"Generated {OUTPUT_PATH} — {USERNAME} · {stats['zone']} zone · {stats['commits_7d']} commits/7d")
