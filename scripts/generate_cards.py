"""Generate self-hosted SVG stat cards for the profile README.

Runs in GitHub Actions (see .github/workflows/cards.yml); writes light/dark
variants into assets/ so the README never depends on third-party services.
All activity numbers come from GitHub's own contributionsCollection so the
cards always match what the profile page itself reports.
"""
import json
import os
import urllib.request

USER = "erdemsidal"
# e-Muhasebe-Project carries ~13 MB of bundled frontend JS that would drown
# out the real language stats; material-ui is an upstream fork.
EXCLUDE_REPOS = {"e-Muhasebe-Project", "material-ui"}
EXCLUDE_LANGS = {"HTML", "CSS", "SCSS", "Dockerfile"}
TOKEN = os.environ.get("GITHUB_TOKEN", "")

LANG_COLORS = {
    "Java": "#b07219", "JavaScript": "#f1e05a", "Python": "#3572A5",
    "TypeScript": "#3178c6", "Shell": "#89e051", "Kotlin": "#A97BFF",
    "Go": "#00ADD8", "C": "#555555", "C++": "#f34b7d", "Rust": "#dea584",
}
FALLBACK_COLOR = "#8b949e"

THEMES = {
    "light": {"title": "#6f42c1", "text": "#57606a", "value": "#24292f",
              "border": "#d0d7de", "track": "#eaeef2",
              "heat": ["#ebedf0", "#d8c8f5", "#b795f0", "#8957e5", "#6f42c1"]},
    "dark":  {"title": "#a371f7", "text": "#8b949e", "value": "#c9d1d9",
              "border": "#30363d", "track": "#21262d",
              "heat": ["#21262d", "#3b2a5e", "#5b3a9e", "#7c4dcc", "#a371f7"]},
}
FONT = "'Segoe UI', Ubuntu, Helvetica, Arial, sans-serif"

MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
          "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]


def rest(path):
    req = urllib.request.Request("https://api.github.com" + path)
    req.add_header("Accept", "application/vnd.github+json")
    if TOKEN:
        req.add_header("Authorization", "Bearer " + TOKEN)
    with urllib.request.urlopen(req) as resp:
        return json.load(resp)


def graphql(query):
    req = urllib.request.Request(
        "https://api.github.com/graphql",
        data=json.dumps({"query": query}).encode(),
        headers={"Authorization": "Bearer " + TOKEN,
                 "Content-Type": "application/json"})
    with urllib.request.urlopen(req) as resp:
        payload = json.load(resp)
    if "errors" in payload:
        raise RuntimeError(payload["errors"])
    return payload["data"]


def collect():
    user = rest(f"/users/{USER}")
    repos = [r for r in rest(f"/users/{USER}/repos?per_page=100&type=owner")
             if not r["fork"]]
    stars = sum(r["stargazers_count"] for r in repos)

    contribs = graphql("""
      query {
        user(login: "%s") {
          contributionsCollection {
            totalCommitContributions
            contributionCalendar {
              totalContributions
              weeks { contributionDays { date contributionCount } }
            }
          }
        }
      }""" % USER)["user"]["contributionsCollection"]
    calendar = contribs["contributionCalendar"]

    langs = {}
    for r in repos:
        if r["name"] in EXCLUDE_REPOS:
            continue
        for lang, size in rest(f"/repos/{USER}/{r['name']}/languages").items():
            if lang not in EXCLUDE_LANGS:
                langs[lang] = langs.get(lang, 0) + size
    total = sum(langs.values()) or 1
    top = sorted(langs.items(), key=lambda kv: -kv[1])[:6]
    return {
        "stats": [
            ("Contributions (last year)", calendar["totalContributions"]),
            ("Commits (last year)", contribs["totalCommitContributions"]),
            ("Total Stars", stars),
            ("Public Repos", user["public_repos"]),
        ],
        "langs": [(name, size / total * 100) for name, size in top],
        "weeks": calendar["weeks"],
        "total_contribs": calendar["totalContributions"],
    }


def card(width, height, theme, title, body):
    c = THEMES[theme]
    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">
  <rect x="0.5" y="0.5" width="{width - 1}" height="{height - 1}" rx="6" fill="none" stroke="{c['border']}"/>
  <text x="24" y="38" font-family="{FONT}" font-size="18" font-weight="600" fill="{c['title']}">{title}</text>
{body}
</svg>
"""


def stats_svg(stats, theme):
    c = THEMES[theme]
    rows = []
    for i, (name, value) in enumerate(stats):
        y = 74 + i * 28
        rows.append(
            f'  <circle cx="30" cy="{y - 5}" r="4" fill="{c["title"]}"/>\n'
            f'  <text x="46" y="{y}" font-family="{FONT}" font-size="14" fill="{c["text"]}">{name}</text>\n'
            f'  <text x="396" y="{y}" text-anchor="end" font-family="{FONT}" font-size="14" font-weight="600" fill="{c["value"]}">{value}</text>'
        )
    return card(420, 195, theme, "Erdem Sıdal's GitHub Stats", "\n".join(rows))


def langs_svg(langs, theme):
    c = THEMES[theme]
    bar_x, bar_w, bar_y = 24, 292, 62
    body = [f'  <rect x="{bar_x}" y="{bar_y}" width="{bar_w}" height="10" rx="5" fill="{c["track"]}"/>']
    x = bar_x
    for name, pct in langs:
        w = bar_w * pct / 100
        body.append(
            f'  <rect x="{x:.1f}" y="{bar_y}" width="{max(w, 2):.1f}" height="10" rx="5" '
            f'fill="{LANG_COLORS.get(name, FALLBACK_COLOR)}"/>'
        )
        x += w
    for i, (name, pct) in enumerate(langs):
        col, row = divmod(i, 3)
        lx, ly = 24 + col * 150, 98 + row * 26
        body.append(
            f'  <circle cx="{lx + 5}" cy="{ly - 5}" r="5" fill="{LANG_COLORS.get(name, FALLBACK_COLOR)}"/>\n'
            f'  <text x="{lx + 18}" y="{ly}" font-family="{FONT}" font-size="13" fill="{c["value"]}">{name} '
            f'<tspan fill="{c["text"]}">{pct:.1f}%</tspan></text>'
        )
    return card(340, 195, theme, "Most Used Languages", "\n".join(body))


def heat_level(count):
    if count == 0:
        return 0
    if count <= 2:
        return 1
    if count <= 4:
        return 2
    if count <= 7:
        return 3
    return 4


def contribs_svg(weeks, total, theme):
    c = THEMES[theme]
    cell, gap = 10, 3
    left, top = 24, 66
    grid_w = len(weeks) * (cell + gap) - gap
    width = left * 2 + grid_w
    body = []
    prev_month = None
    for wi, week in enumerate(weeks):
        x = left + wi * (cell + gap)
        month = int(week["contributionDays"][0]["date"][5:7])
        if month != prev_month:
            if prev_month is not None and x + 28 <= left + grid_w:
                body.append(
                    f'  <text x="{x}" y="{top - 8}" font-family="{FONT}" '
                    f'font-size="11" fill="{c["text"]}">{MONTHS[month - 1]}</text>')
            prev_month = month
        for di, day in enumerate(week["contributionDays"]):
            y = top + di * (cell + gap)
            color = c["heat"][heat_level(day["contributionCount"])]
            body.append(
                f'  <rect x="{x}" y="{y}" width="{cell}" height="{cell}" rx="2" fill="{color}">'
                f'<title>{day["date"]}: {day["contributionCount"]}</title></rect>')
    footer_y = top + 7 * (cell + gap) + 18
    body.append(
        f'  <text x="{left}" y="{footer_y}" font-family="{FONT}" font-size="12" '
        f'fill="{c["text"]}">{total} contributions in the last year</text>')
    legend_x = left + grid_w - 5 * (cell + gap) - 40
    body.append(
        f'  <text x="{legend_x - 8}" y="{footer_y}" text-anchor="end" '
        f'font-family="{FONT}" font-size="12" fill="{c["text"]}">Less</text>')
    for i in range(5):
        body.append(
            f'  <rect x="{legend_x + i * (cell + gap)}" y="{footer_y - 9}" width="{cell}" '
            f'height="{cell}" rx="2" fill="{c["heat"][i]}"/>')
    body.append(
        f'  <text x="{legend_x + 5 * (cell + gap) + 5}" y="{footer_y}" '
        f'font-family="{FONT}" font-size="12" fill="{c["text"]}">More</text>')
    return card(width, footer_y + 16, theme, "Contribution Activity", "\n".join(body))


def main():
    data = collect()
    os.makedirs("assets", exist_ok=True)
    for theme in THEMES:
        with open(f"assets/stats-{theme}.svg", "w", encoding="utf-8") as f:
            f.write(stats_svg(data["stats"], theme))
        with open(f"assets/langs-{theme}.svg", "w", encoding="utf-8") as f:
            f.write(langs_svg(data["langs"], theme))
        with open(f"assets/contribs-{theme}.svg", "w", encoding="utf-8") as f:
            f.write(contribs_svg(data["weeks"], data["total_contribs"], theme))
    print("stats:", data["stats"])
    print("langs:", [(n, round(p, 1)) for n, p in data["langs"]])


if __name__ == "__main__":
    main()
