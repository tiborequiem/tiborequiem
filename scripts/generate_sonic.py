import json
import os
import urllib.request
from datetime import datetime, timedelta, timezone

USERNAME  = os.environ.get("GITHUB_USERNAME", "tiborequiem")
TOKEN     = os.environ.get("GITHUB_TOKEN", "")
TZ_OFFSET = int(os.environ.get("TZ_OFFSET", "2"))
OUTPUT_PATH = os.environ.get("OUTPUT_PATH", "sonic-zone.svg")

# ── API helpers ───────────────────────────────────────────────────────────────

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

    # GraphQL contribution calendar (authenticated)
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

    # Public events for zone detection (and fallback stats)
    tz = timezone(timedelta(hours=TZ_OFFSET))
    buckets = {"day": 0, "sunset": 0, "night": 0}
    try:
        events = api_request(f"https://api.github.com/users/{USERNAME}/events/public?per_page=100")
        pushes = [e for e in events if e.get("type") == "PushEvent"]
        for ev in pushes:
            dt = datetime.fromisoformat(ev["created_at"].replace("Z", "+00:00")).astimezone(tz)
            h  = dt.hour
            if   6  <= h < 18: buckets["day"]    += 1
            elif 18 <= h < 22: buckets["sunset"] += 1
            else:               buckets["night"]  += 1
        if any(buckets.values()):
            zone = max(buckets, key=buckets.get)
        if not TOKEN:                                # fallback stats from events
            now = datetime.now(tz)
            for ev in pushes:
                dt = datetime.fromisoformat(ev["created_at"].replace("Z", "+00:00")).astimezone(tz)
                n  = len(ev.get("payload", {}).get("commits", [])) or 1
                if now - dt <= timedelta(days=7):  commits_7d  += n
                if now - dt <= timedelta(days=30): commits_30d += n
            total_year = max(commits_30d * 4, 0)
            streak     = 3
    except Exception as e:
        print(f"[WARN] Events: {e}")

    return dict(commits_7d=commits_7d, commits_30d=commits_30d,
                total_year=total_year, streak=streak, zone=zone)


# ── SVG renderer ─────────────────────────────────────────────────────────────

def render_svg(stats: dict) -> str:
    c7     = stats["commits_7d"]
    c30    = stats["commits_30d"]
    streak = stats["streak"]
    zone   = stats["zone"]
    total  = stats["total_year"]

    # ── mode ─────────────────────────────────────────────────────────────────
    if   c7 >= 30 or streak >= 7: mode, accent = "SUPER SONIC", "#FACC15"
    elif c7 >= 10:                 mode, accent = "PEEL OUT",    "#60A5FA"
    elif c7 >= 1:                  mode, accent = "CRUISING",    "#34D399"
    else:                          mode, accent = "IDLE",        "#94A3B8"

    # ── zone palette ─────────────────────────────────────────────────────────
    Z = {
        "day": {
            "label":    "GREEN HILL ZONE",
            "bg":       "#0C1428",
            "neon1":    "#22C55E",   # dominant neon (rings, borders)
            "neon2":    "#4ADE80",   # secondary neon
            "sky_line": "#1A3A1A",   # horizon stripe
        },
        "sunset": {
            "label":    "SUNSET HILL ZONE",
            "bg":       "#120818",
            "neon1":    "#FB923C",
            "neon2":    "#FBBF24",
            "sky_line": "#3B1A0A",
        },
        "night": {
            "label":    "STAR LIGHT ZONE",
            "bg":       "#060614",
            "neon1":    "#818CF8",
            "neon2":    "#22D3EE",
            "sky_line": "#0F0F3A",
        },
    }
    p = Z[zone]

    neon1  = p["neon1"]
    neon2  = p["neon2"]
    bg     = p["bg"]

    # ── Chaos Emeralds ───────────────────────────────────────────────────────
    EM_COLORS = ["#38BDF8","#FACC15","#EF4444","#A855F7","#22C55E","#3B82F6","#E2E8F0"]
    lit       = min(streak, 7)

    em_svg = ""
    for i, col in enumerate(EM_COLORS):
        ex = 32 + i * 36
        if i < lit:
            em_svg += (
                f'<g filter="url(#glow-sm)">'
                f'  <polygon points="{ex},8 {ex+10},18 {ex},28 {ex-10},18"'
                f'           fill="{col}" stroke="white" stroke-width="1"/>'
                f'</g>'
            )
        else:
            em_svg += (
                f'<polygon points="{ex},8 {ex+10},18 {ex},28 {ex-10},18"'
                f' fill="none" stroke="#334155" stroke-width="1" opacity="0.5"/>'
            )

    # ── Animated rings row ───────────────────────────────────────────────────
    # Number of rings scales with 30-day commits
    ring_count = max(2, min(7, c30 // 6 + 1)) if c30 > 0 else 2
    rings_svg  = ""
    for i in range(ring_count + 3):              # extra so loop is seamless
        rx = 42 + i * 100
        rings_svg += (
            f'<g transform="translate({rx},0)" filter="url(#glow-sm)">'
            f'  <g class="ring-spin">'
            f'    <ellipse cx="0" cy="0" rx="16" ry="16"'
            f'             fill="none" stroke="{neon1}" stroke-width="4"/>'
            f'    <ellipse cx="0" cy="0" rx="16" ry="16"'
            f'             fill="none" stroke="{neon2}" stroke-width="1.5"'
            f'             stroke-dasharray="14 18"/>'
            f'  </g>'
            f'</g>'
        )

    # ── Scanline overlay ─────────────────────────────────────────────────────
    # SVG pattern of alternating semi-transparent stripes — purely decorative
    scanlines = (
        '<rect width="800" height="230" fill="url(#scanlines)" '
        'pointer-events="none" rx="12" opacity="0.18"/>'
    )

    # ── Star field (night / sunset) ──────────────────────────────────────────
    stars_svg = ""
    if zone in ("night", "sunset"):
        import hashlib
        pts = []
        for n in range(55):
            h = int(hashlib.md5(f"star{n}".encode()).hexdigest()[:8], 16)
            sx = (h >> 16) % 740 + 30
            sy = (h & 0xFFFF) % 110 + 10
            sr = 0.8 + ((h >> 8) & 0xFF) / 400
            pts.append((sx, sy, sr, n))
        stars_svg = "".join(
            f'<circle cx="{sx}" cy="{sy}" r="{sr:.1f}" fill="white" opacity="0.7"'
            f' class="twinkle" style="animation-delay:{(n*73)%2000/1000:.2f}s"/>'
            for sx, sy, sr, n in pts
        )

    # ── Stat rows ────────────────────────────────────────────────────────────
    # Each row: label (neon) + value (white) + small bar
    def stat_row(label, value, bar_pct, bar_color, row_y):
        bar_w     = int(bar_pct * 230)
        bar_w     = max(2, bar_w)
        label_len = len(label)
        return f"""
  <text x="30"  y="{row_y}"    class="stat-label">{label}</text>
  <text x="210" y="{row_y}"    class="stat-val">{value}</text>
  <rect x="30"  y="{row_y+5}"  width="230" height="4" rx="2" fill="#1E293B"/>
  <rect x="30"  y="{row_y+5}"  width="{bar_w}" height="4" rx="2"
        fill="{bar_color}" filter="url(#glow-sm)"/>"""

    rows = []

    # SCORE
    rows.append(stat_row(
        "SCORE", f"{total:,}",
        min(total / 1000, 1.0),
        neon2, 0
    ))
    # RINGS 7D
    rows.append(stat_row(
        "RINGS · 7D", str(c7),
        min(c7 / 30, 1.0),
        neon1, 32
    ))
    # RINGS 30D
    rows.append(stat_row(
        "RINGS · 30D", str(c30),
        min(c30 / 100, 1.0),
        neon1, 64
    ))
    # STREAK
    rows.append(stat_row(
        "STREAK", f"{streak} DAYS",
        min(streak / 7, 1.0),
        accent, 96
    ))

    stat_block = "\n".join(rows)

    # ── Big title / mode badge ───────────────────────────────────────────────
    # Right column: big mode text + zone label

    return f"""<svg xmlns="http://www.w3.org/2000/svg"
     viewBox="0 0 800 230" width="800" height="230"
     role="img" aria-label="{USERNAME} GitHub Activity — {p['label']}">
  <defs>
    <!-- Scanline pattern -->
    <pattern id="scanlines" width="1" height="4" patternUnits="userSpaceOnUse">
      <rect width="1" height="2" fill="black"/>
    </pattern>

    <!-- Neon glow (strong) -->
    <filter id="glow" x="-40%" y="-40%" width="180%" height="180%">
      <feGaussianBlur stdDeviation="5" result="b"/>
      <feMerge><feMergeNode in="b"/><feMergeNode in="SourceGraphic"/></feMerge>
    </filter>

    <!-- Neon glow (subtle) -->
    <filter id="glow-sm" x="-20%" y="-20%" width="140%" height="140%">
      <feGaussianBlur stdDeviation="2.5" result="b"/>
      <feMerge><feMergeNode in="b"/><feMergeNode in="SourceGraphic"/></feMerge>
    </filter>

    <!-- CRT border gradient -->
    <linearGradient id="border-grad" x1="0" y1="0" x2="1" y2="1">
      <stop offset="0%"   stop-color="{neon1}"/>
      <stop offset="50%"  stop-color="{accent}"/>
      <stop offset="100%" stop-color="{neon2}"/>
    </linearGradient>

    <!-- Animated ring scroll -->
    <style>
      @import url('https://fonts.googleapis.com/css2?family=Press+Start+2P&amp;display=swap');

      .px  {{ font-family: 'Press Start 2P', 'Courier New', monospace; }}

      .zone-label {{
        font-family: 'Press Start 2P', 'Courier New', monospace;
        font-size: 9px; fill: {neon2}; letter-spacing: 1px;
      }}
      .mode-text {{
        font-family: 'Press Start 2P', 'Courier New', monospace;
        font-size: 15px; fill: {accent};
      }}
      .username-text {{
        font-family: 'Press Start 2P', 'Courier New', monospace;
        font-size: 11px; fill: white;
      }}
      .stat-label {{
        font-family: 'Press Start 2P', 'Courier New', monospace;
        font-size: 8px; fill: {neon1}; letter-spacing: 0.5px;
      }}
      .stat-val {{
        font-family: 'Press Start 2P', 'Courier New', monospace;
        font-size: 8px; fill: white;
      }}
      .em-label {{
        font-family: 'Press Start 2P', 'Courier New', monospace;
        font-size: 7px; fill: #64748B; letter-spacing: 1px;
      }}
      .ring-row  {{ animation: ring-scroll 4s linear infinite; }}
      .ring-spin {{ animation: spin 0.7s ease-in-out infinite; }}
      .twinkle   {{ animation: twinkle 2.4s ease-in-out infinite alternate; }}
      .blink     {{ animation: blink 1.2s step-end infinite; }}

      @keyframes ring-scroll {{
        from {{ transform: translateX(0);      }}
        to   {{ transform: translateX(-100px); }}
      }}
      @keyframes spin {{
        0%,100% {{ transform: scaleX(1);    }}
        50%     {{ transform: scaleX(0.12); }}
      }}
      @keyframes twinkle {{
        from {{ opacity: 0.15; }}
        to   {{ opacity: 0.9;  }}
      }}
      @keyframes blink {{
        0%,100% {{ opacity: 1; }}
        50%     {{ opacity: 0; }}
      }}
    </style>
  </defs>

  <!-- Background -->
  <rect width="800" height="230" rx="12" fill="{bg}"/>

  <!-- Star field -->
  {stars_svg}

  <!-- Horizon glow -->
  <rect x="0" y="155" width="800" height="40" fill="{p['sky_line']}" opacity="0.4"/>
  <rect x="0" y="192" width="800" height="38" fill="{p['sky_line']}" opacity="0.6" rx="0"/>

  <!-- Neon border (gradient) -->
  <rect x="0" y="0" width="800" height="230" rx="12"
        fill="none" stroke="url(#border-grad)" stroke-width="2.5"/>
  <!-- Inner border glow -->
  <rect x="3" y="3" width="794" height="224" rx="10"
        fill="none" stroke="{neon1}" stroke-width="0.5" opacity="0.3"/>

  <!-- ════════════════════════════════════════════
       LEFT PANEL  — Chaos Emeralds + Stats
       ════════════════════════════════════════════ -->

  <!-- Emeralds header -->
  <text x="30" y="22" class="em-label">CHAOS EMERALDS  ({lit}/7)</text>

  <!-- Emerald row -->
  <g transform="translate(30, 28)">
    {em_svg}
  </g>

  <!-- Divider -->
  <line x1="30" y1="68" x2="290" y2="68" stroke="{neon1}" stroke-width="0.8" opacity="0.3"/>

  <!-- Stats block -->
  <g transform="translate(0, 82)">
    {stat_block}
  </g>

  <!-- Rings row (scrolling, below stats) -->
  <g transform="translate(0, 193)">
    <clipPath id="ring-clip">
      <rect x="30" y="-20" width="260" height="40"/>
    </clipPath>
    <g clip-path="url(#ring-clip)">
      <g class="ring-row" transform="translate(30, 0)">
        {rings_svg}
      </g>
    </g>
  </g>

  <!-- ════════════════════════════════════════════
       VERTICAL DIVIDER
       ════════════════════════════════════════════ -->
  <line x1="320" y1="16" x2="320" y2="214"
        stroke="{neon1}" stroke-width="1" opacity="0.25"/>

  <!-- ════════════════════════════════════════════
       RIGHT PANEL  — Username, Zone, Mode, Grid
       ════════════════════════════════════════════ -->

  <!-- Username -->
  <text x="344" y="38" class="username-text">@{USERNAME}</text>

  <!-- Zone label -->
  <text x="344" y="60" class="zone-label">{p['label']}</text>

  <!-- Thin accent line under labels -->
  <line x1="344" y1="68" x2="762" y2="68"
        stroke="{accent}" stroke-width="1.5" opacity="0.4" filter="url(#glow-sm)"/>

  <!-- MODE badge -->
  <rect x="344" y="78" width="210" height="36" rx="4"
        fill="{accent}" fill-opacity="0.1" stroke="{accent}" stroke-width="1" stroke-opacity="0.5"/>
  <text x="354" y="102" class="mode-text">{mode}</text>

  <!-- Contribution grid (mini pixel heatmap, decorative) -->
  <!-- 15 cols × 7 rows = last ~15 weeks of activity feel -->
  <text x="344" y="136" class="em-label">CONTRIBUTION GRID</text>
  <g transform="translate(344, 143)">
{''.join(
    f'<rect x="{col*26}" y="{row*12}" width="20" height="8" rx="2" '
    f'fill="{neon1}" opacity="{0.08 + (hash((col*7+row)) % 10) * 0.09:.2f}"/>'
    for row in range(7)
    for col in range(16)
)}
  </g>

  <!-- Bottom right: blinking cursor -->
  <text x="724" y="216" class="em-label" style="animation: blink 1.2s step-end infinite; fill:{neon1}">▮</text>
  <text x="344" y="216" class="em-label">INSERT COIN TO CONTINUE</text>

  <!-- Scanlines overlay -->
  {scanlines}

</svg>"""


if __name__ == "__main__":
    stats = fetch_github_stats()
    svg   = render_svg(stats)
    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        f.write(svg)
    print(
        f"Generated {OUTPUT_PATH} for {USERNAME} "
        f"({stats['zone']} zone, mode based on {stats['commits_7d']} commits/7d)"
    )
