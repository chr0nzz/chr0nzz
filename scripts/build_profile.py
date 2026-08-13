import base64
import itertools
import json
import os
import re
import sys
import unicodedata
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PROFILE = ROOT / 'profile'
FONT_PATH = PROFILE / 'fonts' / 'jetbrains-mono-latin.woff2'
LOGIN = os.environ.get('GITHUB_REPOSITORY_OWNER', 'chr0nzz')
PINS = ['traefik-manager', 'traefik-manager-mobile', 'gatekeeper', 'traefik-stack']
TAGLINE = '// self-hosted. open source. no nonsense.'
ABOUT_TITLE = 'Developer & self-hosting enthusiast'
ABOUT = [
    'I build and maintain open-source tools for the self-hosted homelab community, along with the companion mobile apps that bring those services to your fingertips.',
    'I am passionate about creating seamless, highly functional software with a strong focus on clean, dark-themed, glassmorphism-inspired interfaces that make managing server environments intuitive.',
]
BUTTONS = [
    ('btn-xyzlab', 'xyzlab.dev', True),
    ('btn-kofi', 'ko-fi', False),
    ('btn-play', 'google play', False),
]
STACK = [
    ('stack', ['go', 'typescript', 'python', 'astro', 'kotlin']),
    ('infra', ['docker', 'traefik', 'cloudflare', 'tailscale', 'linux']),
]
RELEASE_COUNT = 5
LANG_COUNT = 6

THEMES = {
    'dark': {
        'accent': '#22c55e',
        'accent_dim': 'rgba(34,197,94,0.12)',
        'accent_border': 'rgba(34,197,94,0.3)',
        'warn': '#fbbf24',
        'warn_dim': 'rgba(251,191,36,0.12)',
        'warn_border': 'rgba(251,191,36,0.3)',
        'info': '#60a5fa',
        'bg2': '#111316',
        'bg3': '#181b1f',
        'text': '#e8eaed',
        'text2': '#8b9199',
        'text3': '#7d8590',
        'border': 'rgba(255,255,255,0.07)',
        'seg_ring': 'rgba(255,255,255,0.16)',
        'btn_text': '#052e16',
        'heat': [
            'rgba(34,197,94,0.08)',
            'rgba(34,197,94,0.22)',
            'rgba(34,197,94,0.45)',
            'rgba(34,197,94,0.72)',
            '#22c55e',
        ],
    },
    'light': {
        'accent': '#16a34a',
        'accent_dim': 'rgba(22,163,74,0.1)',
        'accent_border': 'rgba(22,163,74,0.3)',
        'warn': '#b45309',
        'warn_dim': 'rgba(180,83,9,0.1)',
        'warn_border': 'rgba(180,83,9,0.3)',
        'info': '#1d4ed8',
        'bg2': '#ffffff',
        'bg3': '#f1f3f5',
        'text': '#0b0d0f',
        'text2': '#4b5563',
        'text3': '#667080',
        'border': 'rgba(0,0,0,0.08)',
        'seg_ring': 'rgba(0,0,0,0.18)',
        'btn_text': '#052e16',
        'heat': [
            'rgba(22,163,74,0.07)',
            'rgba(22,163,74,0.25)',
            'rgba(22,163,74,0.45)',
            'rgba(22,163,74,0.7)',
            '#15803d',
        ],
    },
}

QUERY = '''
query($login: String!, $cursor: String) {
  user(login: $login) {
    createdAt
    followers { totalCount }
    contributionsCollection {
      totalCommitContributions
      restrictedContributionsCount
      contributionCalendar {
        totalContributions
        weeks { contributionDays { date contributionCount } }
      }
    }
    repositories(first: 100, after: $cursor, ownerAffiliations: OWNER, privacy: PUBLIC, isFork: false) {
      totalCount
      pageInfo { hasNextPage endCursor }
      nodes {
        name
        description
        url
        stargazerCount
        isArchived
        primaryLanguage { name color }
        latestRelease { tagName publishedAt url isPrerelease }
        languages(first: 10, orderBy: {field: SIZE, direction: DESC}) {
          edges { size node { name color } }
        }
      }
    }
  }
}
'''

STAR = 'M5 0.4 6.46 3.36 9.73 3.83 7.36 6.14 7.92 9.39 5 7.85 2.08 9.39 2.64 6.14 0.27 3.83 3.54 3.36Z'


def gql(query, variables, token):
    body = json.dumps({'query': query, 'variables': variables}).encode()
    req = urllib.request.Request(
        'https://api.github.com/graphql',
        data=body,
        headers={
            'Authorization': f'bearer {token}',
            'Content-Type': 'application/json',
            'User-Agent': f'{LOGIN}-profile-builder',
        },
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        payload = json.load(resp)
    if payload.get('errors'):
        raise SystemExit(f'graphql errors: {payload["errors"]}')
    return payload['data']


def fetch():
    token = os.environ.get('GH_TOKEN') or os.environ.get('GITHUB_TOKEN')
    if not token:
        raise SystemExit('GITHUB_TOKEN is not set')
    data = gql(QUERY, {'login': LOGIN, 'cursor': None}, token)
    user = data['user']
    repos = user['repositories']['nodes']
    page = user['repositories']['pageInfo']
    while page['hasNextPage']:
        more = gql(QUERY, {'login': LOGIN, 'cursor': page['endCursor']}, token)
        repos += more['user']['repositories']['nodes']
        page = more['user']['repositories']['pageInfo']
    user['repositories']['nodes'] = repos
    return user


def esc(s):
    return (
        str(s)
        .replace('&', '&amp;')
        .replace('<', '&lt;')
        .replace('>', '&gt;')
        .replace('"', '&quot;')
    )


def fmt(n):
    return f'{n:,}'


def units(text):
    total = 0
    for ch in str(text):
        if unicodedata.east_asian_width(ch) in 'WF' or ord(ch) >= 0x1F000:
            total += 2
        else:
            total += 1
    return total


def mono_w(text, size):
    return units(text) * size * 0.6


def elide(text, max_units):
    if units(text) <= max_units:
        return text
    out = ''
    for ch in text:
        if units(out + ch) > max_units - 1:
            break
        out += ch
    return out.rstrip() + '…'


def rel_time(iso, now):
    then = datetime.fromisoformat(iso.replace('Z', '+00:00'))
    days = (now - then).days
    if days <= 0:
        return 'today'
    if days < 7:
        return f'{days}d ago'
    if days < 60:
        return f'{days // 7}w ago'
    if days < 360:
        return f'{days // 30}mo ago'
    return f'{max(days // 365, 1)}y ago'


def uptime(iso, now):
    then = datetime.fromisoformat(iso.replace('Z', '+00:00'))
    months = (now.year - then.year) * 12 + now.month - then.month
    if (now.day - then.day) < 0:
        months -= 1
    years, rem = divmod(max(months, 0), 12)
    if years and rem:
        return f'{years}y {rem}m'
    if years:
        return f'{years}y'
    return f'{rem}m'


def wrap(text, limit, max_lines):
    words = []
    for w in str(text).split():
        while units(w) > limit:
            head = ''
            for ch in w:
                if units(head + ch) > limit:
                    break
                head += ch
            words.append(head)
            w = w[len(head):]
        if w:
            words.append(w)
    lines, cur = [], ''
    for w in words:
        cand = f'{cur} {w}'.strip()
        if units(cand) <= limit:
            cur = cand
        else:
            if cur:
                lines.append(cur)
            cur = w
        if len(lines) == max_lines:
            break
    if len(lines) < max_lines and cur:
        lines.append(cur)
    if words and ' '.join(lines) != ' '.join(words):
        lines[-1] = elide(lines[-1], limit - 1)
        if not lines[-1].endswith('…'):
            lines[-1] += '…'
    return lines


def hex_rgb(color):
    c = (color or '#7d8590').lstrip('#')
    if len(c) == 3:
        c = ''.join(ch * 2 for ch in c)
    return tuple(int(c[i : i + 2], 16) for i in (0, 2, 4))


def color_dist(a, b):
    r1, g1, b1 = hex_rgb(a)
    r2, g2, b2 = hex_rgb(b)
    rm = (r1 + r2) / 2
    dr, dg, db = r1 - r2, g1 - g2, b1 - b2
    return ((2 + rm / 256) * dr * dr + 4 * dg * dg + (2 + (255 - rm) / 256) * db * db) ** 0.5


def arrange_langs(langs):
    if len(langs) < 3:
        return langs
    best, best_key = langs, None
    for perm in itertools.permutations(range(len(langs))):
        min_d = min(
            color_dist(langs[perm[i]][1], langs[perm[i + 1]][1])
            for i in range(len(perm) - 1)
        )
        displacement = sum(abs(pos - idx) for pos, idx in enumerate(perm))
        key = (-min_d, displacement)
        if best_key is None or key < best_key:
            best_key = key
            best = [langs[i] for i in perm]
    return best


def font_face():
    b64 = base64.b64encode(FONT_PATH.read_bytes()).decode()
    return (
        "@font-face{font-family:'JBM';"
        f"src:url(data:font/woff2;base64,{b64}) format('woff2');"
        'font-weight:100 800;}'
    )


def svg_open(w, h, t, label):
    css = (
        font_face()
        + "text{font-family:'JBM',ui-monospace,monospace;}"
        + '.cur{animation:b 1.1s step-end infinite;}'
        + '@keyframes b{50%{opacity:0;}}'
        + '@media (prefers-reduced-motion: reduce){.cur{animation:none;}}'
    )
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" '
        f'viewBox="0 0 {w} {h}" role="img" aria-label="{esc(label)}">'
        f'<style>{css}</style>'
        f'<rect x="0.5" y="0.5" width="{w - 1}" height="{h - 1}" rx="12" '
        f'fill="{t["bg2"]}" stroke="{t["border"]}"/>'
    )


def win_bar(w, h, t, prefix, title, bar_h=32):
    return (
        f'<path d="M0.5 12.5 A12 12 0 0 1 12.5 0.5 H{w - 12.5} A12 12 0 0 1 {w - 0.5} 12.5 '
        f'V{bar_h - 0.5} H0.5 Z" fill="{t["bg3"]}"/>'
        f'<line x1="0.5" y1="{bar_h - 0.5}" x2="{w - 0.5}" y2="{bar_h - 0.5}" stroke="{t["border"]}"/>'
        f'<rect x="0.5" y="0.5" width="{w - 1}" height="{h - 1}" rx="12" fill="none" stroke="{t["border"]}"/>'
        f'<text x="12" y="{bar_h / 2 + 4}" font-size="11" letter-spacing="0.02em">'
        f'<tspan fill="{t["accent"]}" font-weight="500">{esc(prefix)}</tspan>'
        f'<tspan fill="{t["text2"]}">{esc(title)}</tspan></text>'
    )


def logo_mark(x, y, scale, t):
    bw = 6 * scale
    gap = 2 * scale
    heights = [18 * scale, 12.5 * scale, 8 * scale]
    ops = ['1', '0.5', '0.25']
    box_w = 3 * bw + 2 * gap + 8 * scale
    box_h = 22 * scale
    out = (
        f'<rect x="{x}" y="{y}" width="{box_w}" height="{box_h}" rx="{6 * scale}" '
        f'fill="{t["bg3"]}" stroke="{t["border"]}"/>'
    )
    bx = x + 4 * scale
    base = y + box_h - 2 * scale
    for h, op in zip(heights, ops):
        out += (
            f'<rect x="{bx}" y="{base - h}" width="{bw}" height="{h}" rx="1" '
            f'fill="{t["accent"]}" opacity="{op}"/>'
        )
        bx += bw + gap
    return out


def star_icon(x, y, color):
    return f'<path d="{STAR}" transform="translate({x} {y})" fill="{color}"/>'


def pill(x, y, label, t):
    w = mono_w(label, 9) + 16
    return (
        f'<rect x="{x - w}" y="{y}" width="{w}" height="17" rx="8.5" '
        f'fill="{t["accent_dim"]}" stroke="{t["accent_border"]}"/>'
        f'<text x="{x - w / 2}" y="{y + 12}" font-size="9" letter-spacing="0.1em" '
        f'font-weight="700" fill="{t["accent"]}" text-anchor="middle">{esc(label.upper())}</text>'
    ), w


def render_masthead(theme, stars):
    t = THEMES[theme]
    w, h = 830, 68
    out = svg_open(w, h, t, f'{LOGIN} · xyzlab.dev')
    out += logo_mark(18, 19, 1.35, t)
    out += (
        f'<text x="66" y="31" font-size="15" font-weight="700" fill="{t["text"]}">{esc(LOGIN)} '
        f'<tspan fill="{t["accent"]}">· xyzlab.dev</tspan></text>'
        f'<text x="66" y="50" font-size="11" fill="{t["accent"]}">{esc(TAGLINE)}</text>'
    )
    cx = 66 + mono_w(TAGLINE, 11) + 5
    out += f'<rect class="cur" x="{cx}" y="41" width="6" height="11" fill="{t["accent"]}"/>'
    p, pw = pill(w - 18, 25.5, 'os', t)
    star_txt = fmt(stars)
    sx = w - 18 - pw - 14 - mono_w(star_txt, 12)
    out += star_icon(sx - 16, 29, t['accent'])
    out += f'<text x="{sx}" y="38" font-size="12" font-weight="500" fill="{t["text2"]}">{star_txt}</text>'
    out += p
    return out + '</svg>'


def render_about(theme):
    t = THEMES[theme]
    w = 830
    paras = [wrap(p, 104, 3) for p in ABOUT]
    y = 32 + 28
    body = (
        f'<text x="16" y="{y}" font-size="12.5"><tspan fill="{t["accent"]}">$</tspan>'
        f'<tspan fill="{t["text"]}"> cat about.md</tspan></text>'
    )
    y += 28
    body += (
        f'<text x="16" y="{y}" font-size="13" font-weight="700" '
        f'fill="{t["text"]}">{esc(ABOUT_TITLE)}</text>'
    )
    y += 28
    for lines in paras:
        for line in lines:
            body += f'<text x="16" y="{y}" font-size="12" fill="{t["text2"]}">{esc(line)}</text>'
            y += 22
        y += 8
    h = y - 8 - 22 + 34
    out = svg_open(w, h, t, 'about chr0nzz')
    out += win_bar(w, h, t, '0:', 'about · readme')
    return out + body + '</svg>'


def render_button(theme, label, primary):
    t = THEMES[theme]
    w = int(mono_w(label, 11)) + 34
    h = 30
    if primary:
        fill, stroke, txt, fw = t['accent'], t['accent'], t['btn_text'], '700'
    else:
        fill, stroke, txt, fw = t['bg2'], t['border'], t['text2'], '500'
    css = font_face() + "text{font-family:'JBM',ui-monospace,monospace;}"
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" '
        f'viewBox="0 0 {w} {h}" role="img" aria-label="{esc(label)}">'
        f'<style>{css}</style>'
        f'<rect x="0.5" y="0.5" width="{w - 1}" height="{h - 1}" rx="8" '
        f'fill="{fill}" stroke="{stroke}"/>'
        f'<text x="{w / 2}" y="19" font-size="11" font-weight="{fw}" '
        f'fill="{txt}" text-anchor="middle">{esc(label)}</text>'
        '</svg>'
    )


def render_stats(theme, d):
    t = THEMES[theme]
    w, h = 830, 204
    cols = [
        (
            112,
            224,
            [
                ('uptime', d['uptime'], f' · since {d["since"]}'),
                ('stars', fmt(d['stars']), ''),
                ('commits', fmt(d['commits']), ' · last 12mo'),
            ],
        ),
        (
            470,
            582,
            [
                ('repos', f'{d["repo_count"]} public', ''),
                ('followers', fmt(d['followers']), ''),
                ('contribs', fmt(d['contribs']), ' · last 12mo'),
            ],
        ),
    ]
    out = svg_open(w, h, t, f'{LOGIN} GitHub stats')
    out += win_bar(w, h, t, '3:', f'stats · {LOGIN}@github')
    out += (
        f'<text x="16" y="60" font-size="12.5"><tspan fill="{t["accent"]}">$</tspan>'
        f'<tspan fill="{t["text"]}"> {LOGIN} --stats</tspan></text>'
    )
    box_y = 76
    out += (
        f'<rect x="16" y="{box_y}" width="70" height="88" rx="8" '
        f'fill="{t["accent_dim"]}" stroke="{t["accent_border"]}"/>'
    )
    for i, (bw, op) in enumerate([(42, '1'), (30, '0.5'), (18, '0.25')]):
        out += (
            f'<rect x="30" y="{box_y + 20 + i * 17}" width="{bw}" height="7" rx="2" '
            f'fill="{t["accent"]}" opacity="{op}"/>'
        )
    for kx, vx, rows in cols:
        y = box_y + 20
        for key, val, note in rows:
            out += (
                f'<text x="{kx}" y="{y}" font-size="12.5">'
                f'<tspan fill="{t["text3"]}">{esc(key)}</tspan></text>'
                f'<text x="{vx}" y="{y}" font-size="12.5" font-weight="500">'
                f'<tspan fill="{t["text"]}">{esc(val)}</tspan>'
                f'<tspan fill="{t["accent"]}">{esc(note)}</tspan></text>'
            )
            y += 26
    out += (
        f'<text x="16" y="188" font-size="12.5" fill="{t["accent"]}">$</text>'
        f'<rect class="cur" x="30" y="177" width="8" height="14" fill="{t["accent"]}"/>'
    )
    return out + '</svg>'


def render_pin(theme, repo):
    t = THEMES[theme]
    w, h = 404, 112
    out = svg_open(w, h, t, f'{repo["name"]} repository card')
    out += win_bar(w, h, t, '~/', f'apps/{repo["name"]}', 30)
    desc = repo.get('description') or ''
    for i, line in enumerate(wrap(desc, 52, 2)):
        out += f'<text x="14" y="{50 + i * 17}" font-size="11.5" fill="{t["text2"]}">{esc(line)}</text>'
    meta_y = 96
    x = 14
    lang = repo.get('primaryLanguage')
    if lang:
        out += f'<circle cx="{x + 4.5}" cy="{meta_y - 4}" r="4.5" fill="{lang["color"] or t["text3"]}"/>'
        x += 14
        out += f'<text x="{x}" y="{meta_y}" font-size="11" fill="{t["text2"]}">{esc(lang["name"])}</text>'
        x += mono_w(lang['name'], 11) + 14
    out += star_icon(x, meta_y - 9, t['accent'])
    star_txt = fmt(repo['stargazerCount'])
    out += (
        f'<text x="{x + 14}" y="{meta_y}" font-size="11" font-weight="500" '
        f'fill="{t["accent"]}">{star_txt}</text>'
    )
    release = repo.get('latestRelease')
    if release and release.get('tagName'):
        tag = release['tagName']
        pre = release.get('isPrerelease') or re.match(r'v?0\.', tag)
        kind = 'pre' if pre else 'stable'
        fill, brd, txt = (
            (t['warn_dim'], t['warn_border'], t['warn'])
            if pre
            else (t['accent_dim'], t['accent_border'], t['accent'])
        )
        avail = w - 14 - (x + 14 + mono_w(star_txt, 11) + 10) - 14
        max_tag = int(avail / 6) - len(kind) - 1
        if len(tag) > max_tag:
            tag = tag[: max(max_tag - 1, 4)] + '…'
        label = f'{tag} {kind}'
        bw = mono_w(label, 10) + 14
        out += (
            f'<rect x="{w - 14 - bw}" y="{meta_y - 12}" width="{bw}" height="16" rx="4" '
            f'fill="{fill}" stroke="{brd}"/>'
            f'<text x="{w - 14 - bw / 2}" y="{meta_y}" font-size="10" font-weight="500" '
            f'fill="{txt}" text-anchor="middle">{esc(label)}</text>'
        )
    return out + '</svg>'


def render_releases(theme, entries, now):
    t = THEMES[theme]
    w = 830
    rows = entries[:RELEASE_COUNT]
    h = 32 + 18 + max(len(rows), 1) * 24 + 14
    out = svg_open(w, h, t, 'latest releases')
    out += win_bar(w, h, t, '2:', 'releases · tail -f')
    y = 32 + 30
    if not rows:
        out += (
            f'<text x="16" y="{y}" font-size="12.5"><tspan fill="{t["accent"]}">$</tspan>'
            f'<tspan fill="{t["text3"]}"> no releases yet</tspan></text>'
        )
        return out + '</svg>'
    names = [elide(name, 28) for _, name, _ in rows]
    x_date = 16
    x_repo = x_date + mono_w('2026-01-01', 12.5) + 16
    name_w = max(units(n) for n in names)
    x_tag = x_repo + name_w * 12.5 * 0.6 + 16
    for (published, _, rel), name in zip(rows, names):
        when = rel_time(published, now)
        tag_budget = int((w - 16 - mono_w(when, 12.5) - 12 - x_tag) / (12.5 * 0.6))
        tag = elide(rel['tagName'], max(tag_budget, 6))
        out += (
            f'<text x="{x_date}" y="{y}" font-size="12.5" fill="{t["text3"]}">{published[:10]}</text>'
            f'<text x="{x_repo}" y="{y}" font-size="12.5" fill="{t["info"]}">{esc(name)}</text>'
            f'<text x="{x_tag}" y="{y}" font-size="12.5" font-weight="700" '
            f'fill="{t["accent"]}">{esc(tag)}</text>'
            f'<text x="{w - 16}" y="{y}" font-size="12.5" fill="{t["text3"]}" '
            f'text-anchor="end">{when}</text>'
        )
        y += 24
    return out + '</svg>'


def render_heatmap(theme, weeks):
    t = THEMES[theme]
    weeks = weeks[-52:]
    counts = sorted(
        d['contributionCount'] for wk in weeks for d in wk['contributionDays'] if d['contributionCount'] > 0
    )
    def q(p):
        if not counts:
            return 0
        return counts[min(int(len(counts) * p), len(counts) - 1)]
    q1, q2, q3 = q(0.25), q(0.5), q(0.75)
    def level(c):
        if c == 0:
            return 0
        if c <= q1:
            return 1
        if c <= q2:
            return 2
        if c <= q3:
            return 3
        return 4
    cell, gap = 11, 3
    pitch = cell + gap
    grid_w = len(weeks) * pitch - gap
    w = 830
    grid_x = (w - grid_w) / 2
    grid_y = 32 + 14
    legend_y = grid_y + 7 * pitch - gap + 16
    h = legend_y + 16
    out = svg_open(w, h, t, 'contribution activity, last 52 weeks')
    out += win_bar(w, h, t, '1:', 'activity · last 52 weeks')
    for wi, wk in enumerate(weeks):
        for di, day in enumerate(wk['contributionDays']):
            color = t['heat'][level(day['contributionCount'])]
            out += (
                f'<rect x="{grid_x + wi * pitch}" y="{grid_y + di * pitch}" '
                f'width="{cell}" height="{cell}" rx="2.5" fill="{color}"/>'
            )
    lx = w - 16 - 5 * pitch - mono_w('more', 10) - 8
    out += (
        f'<text x="{lx - mono_w("less", 10) - 8}" y="{legend_y + 9}" font-size="10" '
        f'fill="{t["text3"]}">less</text>'
    )
    for i, c in enumerate(t['heat']):
        out += f'<rect x="{lx + i * pitch}" y="{legend_y}" width="{cell}" height="{cell}" rx="2.5" fill="{c}"/>'
    out += (
        f'<text x="{lx + 5 * pitch + 4}" y="{legend_y + 9}" font-size="10" '
        f'fill="{t["text3"]}">more</text>'
    )
    return out + '</svg>'


def lang_shares(langs):
    total = sum(s for _, _, s in langs) or 1
    pcts = [round(100 * s / total) for _, _, s in langs]
    drift = 100 - sum(pcts)
    if pcts:
        pcts[pcts.index(max(pcts))] += drift
    return pcts


def render_langs(theme, langs):
    t = THEMES[theme]
    w = 830
    bar_y = 32 + 16
    legend_y = bar_y + 12 + 22
    h = legend_y + 18
    langs = list(langs)
    pcts = lang_shares(langs)
    langs = [l for l, p in zip(langs, pcts) if p > 0]
    pcts = lang_shares(langs)

    def legend_w(ls, ps):
        return sum(15 + mono_w(f'{n} {p}%', 11) + 18 for (n, _, _), p in zip(ls, ps))

    while len(langs) > 1 and legend_w(langs, pcts) > w - 32:
        smallest = min(range(len(langs)), key=lambda i: langs[i][2])
        langs.pop(smallest)
        pcts = lang_shares(langs)
    langs = arrange_langs(langs)
    pcts = lang_shares(langs)
    out = svg_open(w, h, t, 'language breakdown by repo bytes')
    out += win_bar(w, h, t, '4:', 'languages · by repo bytes')
    bar_x, bar_w, gap = 16, w - 32, 2
    avail = bar_w - gap * (len(langs) - 1)
    out += f'<clipPath id="bar"><rect x="{bar_x}" y="{bar_y}" width="{bar_w}" height="12" rx="6"/></clipPath>'
    x = bar_x
    for (name, color, _), pct in zip(langs, pcts):
        seg = avail * pct / 100
        out += (
            f'<rect x="{x:.1f}" y="{bar_y}" width="{seg:.1f}" height="12" '
            f'fill="{color}" clip-path="url(#bar)"/>'
        )
        x += seg + gap
    lx = bar_x
    for (name, color, _), pct in zip(langs, pcts):
        out += (
            f'<rect x="{lx}" y="{legend_y - 9}" width="9" height="9" rx="2" fill="{color}" '
            f'stroke="{t["seg_ring"]}"/>'
            f'<text x="{lx + 15}" y="{legend_y}" font-size="11" fill="{t["text2"]}">{esc(name)} '
            f'<tspan fill="{t["text"]}" font-weight="500">{pct}%</tspan></text>'
        )
        lx += 15 + mono_w(f'{name} {pct}%', 11) + 18
    return out + '</svg>'


def render_stack(theme):
    t = THEMES[theme]
    w, h = 830, 44
    out = svg_open(w, h, t, 'tech stack')
    parts = []
    for label, items in STACK:
        parts.append(f'<tspan fill="{t["text3"]}">{esc(label)}:</tspan> ')
        for i, item in enumerate(items):
            if i:
                parts.append(f'<tspan fill="{t["accent"]}"> · </tspan>')
            parts.append(f'<tspan fill="{t["text"]}" font-weight="500">{esc(item)}</tspan>')
        parts.append('   ')
    out += f'<text x="16" y="27" font-size="12">{"".join(parts)}</text>'
    return out + '</svg>'


def collect_langs(repos):
    sizes, colors = {}, {}
    for r in repos:
        for e in (r.get('languages') or {}).get('edges', []):
            name = e['node']['name']
            sizes[name] = sizes.get(name, 0) + e['size']
            colors[name] = e['node']['color']
    top = sorted(sizes.items(), key=lambda kv: -kv[1])[:LANG_COUNT]
    return [(name, colors.get(name) or '#7d8590', size) for name, size in top]


def collect_releases(repos):
    entries = []
    for r in repos:
        rel = r.get('latestRelease')
        if rel and rel.get('publishedAt'):
            entries.append((rel['publishedAt'], r['name'], rel))
    entries.sort(reverse=True)
    return entries


def write_if_changed(path, content):
    if path.exists() and path.read_text() == content:
        return False
    path.write_text(content)
    return True


def main():
    now = datetime.now(timezone.utc)
    if len(sys.argv) > 1 and sys.argv[1] == '--data':
        if len(sys.argv) < 3:
            raise SystemExit('--data requires a path')
        payload = json.loads(Path(sys.argv[2]).read_text())
        user = payload.get('data', payload)['user']
    else:
        user = fetch()
    repos = [r for r in user['repositories']['nodes'] if not r['isArchived']]
    contrib = user['contributionsCollection']
    created = datetime.fromisoformat(user['createdAt'].replace('Z', '+00:00'))
    d = {
        'stars': sum(r['stargazerCount'] for r in repos),
        'commits': contrib['totalCommitContributions'] + contrib['restrictedContributionsCount'],
        'followers': user['followers']['totalCount'],
        'repo_count': len(repos),
        'contribs': contrib['contributionCalendar']['totalContributions'],
        'uptime': uptime(user['createdAt'], now),
        'since': created.strftime('%b %Y').lower(),
    }
    weeks = contrib['contributionCalendar']['weeks']
    langs = collect_langs(repos)
    releases = collect_releases(repos)
    by_name = {r['name']: r for r in repos}
    changed = []
    missing = [n for n in PINS if n not in by_name]
    if missing:
        print(f'warning: pinned repos missing from fetch: {", ".join(missing)}')
    for theme in THEMES:
        changed.append(write_if_changed(PROFILE / f'masthead-{theme}.svg', render_masthead(theme, d['stars'])))
        changed.append(write_if_changed(PROFILE / f'about-{theme}.svg', render_about(theme)))
        for key, label, primary in BUTTONS:
            changed.append(write_if_changed(PROFILE / f'{key}-{theme}.svg', render_button(theme, label, primary)))
        changed.append(write_if_changed(PROFILE / f'stats-{theme}.svg', render_stats(theme, d)))
        changed.append(write_if_changed(PROFILE / f'heatmap-{theme}.svg', render_heatmap(theme, weeks)))
        changed.append(write_if_changed(PROFILE / f'releases-{theme}.svg', render_releases(theme, releases, now)))
        changed.append(write_if_changed(PROFILE / f'langs-{theme}.svg', render_langs(theme, langs)))
        changed.append(write_if_changed(PROFILE / f'stack-{theme}.svg', render_stack(theme)))
        for name in PINS:
            if name in by_name:
                changed.append(
                    write_if_changed(PROFILE / f'pin-{name}-{theme}.svg', render_pin(theme, by_name[name]))
                )
    print(f'{sum(changed)} file(s) updated')


if __name__ == '__main__':
    main()
