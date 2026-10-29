#!/usr/bin/env python3
"""Generate self-hosted SVG stat cards for the GitHub profile README.

Data source: GitHub GraphQL API (token from GITHUB_TOKEN / GH_TOKEN env).
Outputs: assets/stats.svg, assets/langs.svg, assets/activity.svg
"""

from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request
from datetime import date, datetime, timedelta
from pathlib import Path

LOGIN = os.environ.get("PROFILE_LOGIN", "Yarfer800")
OUT = Path(__file__).resolve().parent.parent / "assets"

BG = "#0b1120"
BORDER = "#22314c"
TITLE = "#22d3ee"
TEXT = "#c3cede"
MUTED = "#6b7c96"
ACCENT = "#a78bfa"
PINK = "#f472b6"
MONO = "ui-monospace,SFMono-Regular,Menlo,Consolas,monospace"

QUERY = """
query($login: String!) {
  user(login: $login) {
    login
    name
    followers { totalCount }
    repositories(privacy: PUBLIC, ownerAffiliations: OWNER, isFork: false, first: 100) {
      totalCount
      nodes {
        name
        stargazerCount
        primaryLanguage { name color }
      }
    }
    contributionsCollection {
      totalCommitContributions
      totalPullRequestContributions
      totalIssueContributions
      totalRepositoriesWithContributedCommits
      contributionCalendar {
        totalContributions
        weeks { contributionDays { date contributionCount } }
      }
    }
  }
}
"""


def gql(token: str, query: str, variables: dict) -> dict:
    req = urllib.request.Request(
        "https://api.github.com/graphql",
        data=json.dumps({"query": query, "variables": variables}).encode(),
        headers={
            "Authorization": f"bearer {token}",
            "Content-Type": "application/json",
            "User-Agent": "profile-assets-generator",
        },
    )
    with urllib.request.urlopen(req, timeout=45) as resp:
        payload = json.load(resp)
    if "errors" in payload:
        raise SystemExit(f"GraphQL errors: {payload['errors']}")
    return payload["data"]["user"]


def esc(value: object) -> str:
    return (
        str(value)
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
    )


def head(width: int, height: int, label: str, title: str) -> str:
    return f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}" width="100%" role="img" aria-label="{esc(label)}">
  <defs>
    <linearGradient id="cardbg" x1="0" y1="0" x2="1" y2="1">
      <stop offset="0" stop-color="#080d18"/>
      <stop offset="60%" stop-color="#0b1120"/>
      <stop offset="1" stop-color="#111a2e"/>
    </linearGradient>
    <linearGradient id="accent" x1="0" y1="0" x2="1" y2="0">
      <stop offset="0" stop-color="{TITLE}"/>
      <stop offset="0.55" stop-color="{ACCENT}"/>
      <stop offset="1" stop-color="{PINK}"/>
    </linearGradient>
    <filter id="glow" x="-50%" y="-50%" width="200%" height="200%">
      <feGaussianBlur stdDeviation="42"/>
    </filter>
  </defs>
  <rect width="{width}" height="{height}" rx="16" fill="url(#cardbg)"/>
  <circle cx="{width - 40}" cy="{height - 20}" r="120" fill="{ACCENT}" opacity="0.10" filter="url(#glow)"/>
  <rect x="0.5" y="0.5" width="{width - 1}" height="{height - 1}" rx="16" fill="none" stroke="{BORDER}"/>
  <text x="28" y="36" font-family="{MONO}" font-size="13" fill="{MUTED}">{esc(title)}</text>
  <rect x="28" y="48" width="168" height="2" rx="1" fill="url(#accent)"/>
"""


def tail() -> str:
    return "</svg>\n"


def streaks(days: list[tuple[date, int]]) -> tuple[int, int]:
    """Return (current, longest) streak in days."""
    days = sorted(days)
    longest = run = 0
    for _, count in days:
        run = run + 1 if count > 0 else 0
        longest = max(longest, run)

    by_day = dict(days)
    today = date.today()
    cursor = today if by_day.get(today, 0) > 0 else today - timedelta(days=1)
    current = 0
    while by_day.get(cursor, 0) > 0:
        current += 1
        cursor -= timedelta(days=1)
    return current, longest


def num(value: int) -> str:
    if value >= 1000:
        return f"{value / 1000:.1f}k".replace(".0k", "k")
    return str(value)


def brighten(hex_color: str, floor: float = 0.45) -> str:
    """Lift dark language colors so bars stay visible on the dark card."""
    value = (hex_color or "").lstrip("#")
    if len(value) != 6:
        return ACCENT
    try:
        r, g, b = (int(value[i : i + 2], 16) for i in (0, 2, 4))
    except ValueError:
        return ACCENT
    luminance = (0.299 * r + 0.587 * g + 0.114 * b) / 255
    if luminance >= floor:
        return f"#{value.lower()}"
    boosted = [round(channel + (255 - channel) * (floor - luminance)) for channel in (r, g, b)]
    return "#{:02x}{:02x}{:02x}".format(*boosted)


def stats_card(user: dict) -> str:
    repos = user["repositories"]["nodes"]
    stars = sum(repo["stargazerCount"] for repo in repos)
    cal = user["contributionsCollection"]["contributionCalendar"]
    days = [
        (datetime.strptime(day["date"], "%Y-%m-%d").date(), day["contributionCount"])
        for week in cal["weeks"]
        for day in week["contributionDays"]
    ]
    current, longest = streaks(days)
    contribs = cal["totalContributions"]
    followers = user["followers"]["totalCount"]

    rows = [
        ("contributions", num(contribs), "past year"),
        ("repositories", str(user["repositories"]["totalCount"]), "public, owned"),
        ("stars earned", num(stars), "across projects"),
        ("followers", str(followers), "and counting"),
    ]

    parts = [head(560, 272, "GitHub stats", "gh stats --user")]
    y = 84
    for label, value, note in rows:
        parts.append(
            f'  <text x="28" y="{y}" font-family="{MONO}" font-size="13" fill="{TEXT}">{esc(label)}</text>\n'
            f'  <text x="532" y="{y}" text-anchor="end" font-family="{MONO}" font-size="14" font-weight="700" fill="url(#accent)">{esc(value)}</text>\n'
            f'  <text x="532" y="{y + 15}" text-anchor="end" font-family="{MONO}" font-size="10" fill="{MUTED}">{esc(note)}</text>\n'
        )
        y += 40

    parts.append(
        f'  <rect x="28" y="240" width="504" height="1" fill="{BORDER}"/>\n'
        f'  <text x="28" y="264" font-family="{MONO}" font-size="11" fill="{MUTED}">streak: '
        f'<tspan fill="{TITLE}">{current}d</tspan> current &amp; <tspan fill="{PINK}">{longest}d</tspan> best</text>\n'
    )
    parts.append(tail())
    return "".join(parts)


def langs_card(user: dict) -> str:
    repos = user["repositories"]["nodes"]
    tally: dict[str, int] = {}
    colors: dict[str, str] = {}
    for repo in repos:
        lang = repo.get("primaryLanguage")
        if not lang:
            continue
        name = lang["name"]
        tally[name] = tally.get(name, 0) + 1
        colors[name] = brighten(lang.get("color") or ACCENT)

    top = sorted(tally.items(), key=lambda item: (-item[1], item[0]))[:5]
    total = sum(tally.values()) or 1

    parts = [head(560, 272, "Top languages", "gh langs --top")]
    y = 100
    for name, count in top:
        share = count / total
        width = max(round(504 * share), 8)
        parts.append(
            f'  <text x="28" y="{y}" font-family="{MONO}" font-size="13" fill="{TEXT}">{esc(name)}</text>\n'
            f'  <text x="532" y="{y}" text-anchor="end" font-family="{MONO}" font-size="12" fill="{MUTED}">'
            f'{count} repo{"s" if count != 1 else ""} · {share * 100:.0f}%</text>\n'
            f'  <rect x="28" y="{y + 9}" width="504" height="8" rx="4" fill="#131c2e"/>\n'
            f'  <rect x="28" y="{y + 9}" width="{width}" height="8" rx="4" fill="{colors[name]}"/>\n'
        )
        y += 44

    parts.append(
        f'  <rect x="28" y="240" width="504" height="1" fill="{BORDER}"/>\n'
        f'  <text x="28" y="264" font-family="{MONO}" font-size="11" fill="{MUTED}">'
        f"primary language of {total} public repositories</text>\n"
    )
    parts.append(tail())
    return "".join(parts)


def activity_card(user: dict) -> str:
    cal = user["contributionsCollection"]["contributionCalendar"]
    weeks = [week["contributionDays"] for week in cal["weeks"]][-26:]
    counts = [day["contributionCount"] for week in weeks for day in week]
    peak = max(counts) if counts else 0
    shades = ["#131c2e", "#134e4a", "#0e7490", TITLE]

    cell, gap, left, top = 12, 4, 28, 80
    width, height = 1180, 226
    parts = [head(width, height, "Contribution activity", "git log --graph --all")]

    last_month = None
    for index, week in enumerate(weeks):
        first = week[0]["date"] if week else None
        if not first:
            continue
        month = datetime.strptime(first, "%Y-%m-%d").strftime("%b")
        if month != last_month:
            parts.append(
                f'  <text x="{left + index * (cell + gap)}" y="{top - 12}" font-family="{MONO}" '
                f'font-size="10" fill="{MUTED}">{esc(month)}</text>\n'
            )
            last_month = month

    for col, week in enumerate(weeks):
        for row, day in enumerate(week):
            count = day["contributionCount"]
            level = 0 if count == 0 else 1 if count <= 2 else 2 if count <= 5 else 3
            parts.append(
                f'  <rect x="{left + col * (cell + gap)}" y="{top + row * (cell + gap)}" '
                f'width="{cell}" height="{cell}" rx="3" fill="{shades[level]}">'
                f'<title>{esc(day["date"])}: {count}</title></rect>\n'
            )

    stats = [
        ("commits", num(user["contributionsCollection"]["totalCommitContributions"])),
        ("pull requests", num(user["contributionsCollection"]["totalPullRequestContributions"])),
        ("issues", num(user["contributionsCollection"]["totalIssueContributions"])),
        ("repos touched", num(user["contributionsCollection"]["totalRepositoriesWithContributedCommits"])),
    ]

    parts.append(
        f'  <rect x="500" y="72" width="1" height="112" fill="{BORDER}"/>\n'
    )
    for index, (label, value) in enumerate(stats):
        x = 548 + index * 158
        parts.append(
            f'  <text x="{x}" y="122" font-family="{MONO}" font-size="28" font-weight="700" fill="url(#accent)">{esc(value)}</text>\n'
            f'  <text x="{x}" y="146" font-family="{MONO}" font-size="11" fill="{MUTED}">{esc(label)}</text>\n'
        )

    total = cal["totalContributions"]
    parts.append(
        f'  <text x="28" y="{height - 12}" font-family="{MONO}" font-size="10" fill="{MUTED}">'
        f'last 26 weeks · <tspan fill="{TEXT}">{total}</tspan> contributions in 12m · peak '
        f'<tspan fill="{PINK}">{peak}</tspan>/day</text>\n'
    )

    legend_x = width - 28 - 4 * 18
    parts.append(
        f'  <text x="{legend_x - 42}" y="{height - 12}" font-family="{MONO}" font-size="10" fill="{MUTED}">less</text>\n'
    )
    for index, fill in enumerate(shades):
        parts.append(
            f'  <rect x="{legend_x + index * 18}" y="{height - 22}" width="12" height="12" rx="3" fill="{fill}"/>\n'
        )
    parts.append(
        f'  <text x="{width - 28}" y="{height - 12}" text-anchor="end" font-family="{MONO}" font-size="10" fill="{MUTED}">more</text>\n'
    )
    parts.append(tail())
    return "".join(parts)


def main() -> int:
    token = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
    if not token:
        print("GITHUB_TOKEN or GH_TOKEN is required", file=sys.stderr)
        return 1

    user = gql(token, QUERY, {"login": LOGIN})
    OUT.mkdir(parents=True, exist_ok=True)
    for name, svg in (
        ("stats.svg", stats_card(user)),
        ("langs.svg", langs_card(user)),
        ("activity.svg", activity_card(user)),
    ):
        (OUT / name).write_text(svg, encoding="utf-8")
        print(f"wrote {OUT / name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
