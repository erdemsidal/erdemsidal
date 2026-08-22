"""Generate self-hosted SVG stat cards for the profile README.

Runs in GitHub Actions (see .github/workflows/cards.yml); writes light/dark
variants into assets/ so the README never depends on third-party services.
"""
import datetime
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
              "border": "#d0d7de", "track": "#eaeef2"},
    "dark":  {"title": "#a371f7", "text": "#8b949e", "value": "#c9d1d9",
              "border": "#30363d", "track": "#21262d"},
}
FONT = "'Segoe UI', Ubuntu, Helvetica, Arial, sans-serif"


def api(path):
    req = urllib.request.Request("https://api.github.com" + path)
    req.add_header("Accept", "application/vnd.github+json")
    if TOKEN:
        req.add_header("Authorization", "Bearer " + TOKEN)
    with urllib.request.urlopen(req) as resp:
        return json.load(resp)


def collect():
    user = api(f"/users/{USER}")
    repos = [r for r in api(f"/users/{USER}/repos?per_page=100&type=owner")
             if not r["fork"]]
    stars = sum(r["stargazers_count"] for r in repos)
    year = datetime.date.today().year
    try:
        commits = api(f"/search/commits?q=author:{USER}"
                      f"+author-date:%3E%3D{year}-01-01")["total_count"]
        commits_all = api(f"/search/commits?q=author:{USER}")["total_count"]
    except Exception:
        commits = commits_all = 0

    langs = {}
    for r in repos:
        if r["name"] in EXCLUDE_REPOS:
            continue
        for lang, size in api(f"/repos/{USER}/{r['name']}/languages").items():
            if lang not in EXCLUDE_LANGS:
                langs[lang] = langs.get(lang, 0) + size
    total = sum(langs.values()) or 1
    top = sorted(langs.items(), key=lambda kv: -kv[1])[:6]
    return {
        "stats": [
            ("Total Commits", commits_all),
            (f"Commits ({year})", commits),
            ("Total Stars", stars),
            ("Public Repos", user["public_repos"]),
        ],
        "langs": [(name, size / total * 100) for name, size in top],
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


def main():
    data = collect()
    os.makedirs("assets", exist_ok=True)
    for theme in THEMES:
        with open(f"assets/stats-{theme}.svg", "w", encoding="utf-8") as f:
            f.write(stats_svg(data["stats"], theme))
        with open(f"assets/langs-{theme}.svg", "w", encoding="utf-8") as f:
            f.write(langs_svg(data["langs"], theme))
    print("stats:", data["stats"])
    print("langs:", [(n, round(p, 1)) for n, p in data["langs"]])


if __name__ == "__main__":
    main()
