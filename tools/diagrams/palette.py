"""Shared visual language for the project diagrams.

One colour per architecture layer, used identically in every diagram, so a
reader who learns the legend once can read all of them. Fills are light and
text is dark, and every canvas paints its own background — that way the SVGs
stay legible whether GitHub renders them on a light or a dark page.

Hues are spaced for colour-vision deficiency: purple / blue / teal / amber /
grey are distinguishable in deuteranopia and protanopia, and red is reserved
for the safety veto so it never competes with a layer colour.
"""

INK = '#1f2328'
MUTED = '#57606a'
CANVAS = '#ffffff'
PANEL = '#f6f8fa'
LINE = '#8c959f'

LAYERS = {
    'L5': {'name': 'L5 业务任务层',   'fill': '#efe6fb', 'stroke': '#6750a4', 'text': '#3d2a66'},
    'L4': {'name': 'L4 感知与规划层', 'fill': '#e3eefc', 'stroke': '#1a73e8', 'text': '#10396e'},
    'L3': {'name': 'L3 通信与接口层', 'fill': '#ddf1ee', 'stroke': '#00897b', 'text': '#08453d'},
    'L2': {'name': 'L2 实时控制与安全层', 'fill': '#fdeddc', 'stroke': '#e8710a', 'text': '#6b3405'},
    'L1': {'name': 'L1 驱动与执行层', 'fill': '#eceff1', 'stroke': '#5f6368', 'text': '#2f3133'},
}

SAFETY = {'fill': '#fce8e6', 'stroke': '#c5221f', 'text': '#7a1512'}
NEW = '#1a7f37'      # things this update added
PENDING = '#9a6700'  # things still waiting on hardware

FONT = ("-apple-system, BlinkMacSystemFont, 'Segoe UI', 'Noto Sans CJK SC', "
        "'Source Han Sans SC', 'Microsoft YaHei', Helvetica, Arial, sans-serif")
MONO = "ui-monospace, SFMono-Regular, 'SF Mono', Menlo, Consolas, monospace"


def esc(text):
    """Diagram labels carry <, > and & freely (\'<10 rpm\', \'A & B\'); SVG does not."""
    return (str(text).replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;'))


def header(width, height, title, subtitle=''):
    out = [
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}" '
        f'width="{width}" height="{height}" font-family="{FONT}" role="img">',
        f'<rect width="{width}" height="{height}" rx="10" fill="{CANVAS}"/>',
        f'<text x="32" y="44" font-size="23" font-weight="700" fill="{INK}">{esc(title)}</text>',
    ]
    if subtitle:
        out.append(f'<text x="32" y="70" font-size="13.5" fill="{MUTED}">{esc(subtitle)}</text>')
    return out


def arrow_defs(colors):
    """One marker per colour; SVG markers cannot inherit the path stroke."""
    parts = ['<defs>']
    for i, c in enumerate(colors):
        parts.append(
            f'<marker id="a{i}" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="6.5" '
            f'markerHeight="6.5" orient="auto-start-reverse">'
            f'<path d="M0,0.8 L10,5 L0,9.2 z" fill="{c}"/></marker>')
    parts.append('</defs>')
    return parts, {c: f'a{i}' for i, c in enumerate(colors)}


def wrap_text(x, y, lines, size, fill, line_height=None, weight='400', anchor='middle',
              family=None):
    lh = line_height or size * 1.35
    fam = f' font-family="{family}"' if family else ''
    out = []
    for i, line in enumerate(lines):
        out.append(f'<text x="{x}" y="{y + i * lh:.1f}" font-size="{size}" font-weight="{weight}" '
                   f'text-anchor="{anchor}" fill="{fill}"{fam}>{esc(line)}</text>')
    return out


def box(x, y, w, h, fill, stroke, radius=8, width=1.6, dash=None):
    d = f' stroke-dasharray="{dash}"' if dash else ''
    return (f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{radius}" fill="{fill}" '
            f'stroke="{stroke}" stroke-width="{width}"{d}/>')
