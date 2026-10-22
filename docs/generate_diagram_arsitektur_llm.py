"""
Generator diagram arsitektur integrasi LLM pada pipeline rekomendasi Cofind.

Satu definisi koordinat dipakai untuk dua keluaran supaya keduanya identik:
SVG (pratinjau/cetak) dan draw.io XML (bisa diedit ulang).

Jalankan:  python docs/generate_diagram_arsitektur_llm.py
"""

from __future__ import annotations

import html
import os
from xml.sax.saxutils import escape as xml_escape

CANVAS_W, CANVAS_H = 1240, 740
FONT = 'Helvetica, Arial, sans-serif'
STROKE = '#1f1f1f'
FILL = '#ffffff'
MUTED = '#6b6b6b'
ACCENT = '#1f1f1f'
LINE_H = 14
FS_TITLE = 12
FS_BODY = 10.5
FS_EDGE = 10
FS_CAPTION = 10


def wrap(text: str, width_px: float, font_size: float) -> list[str]:
    max_chars = max(8, int(width_px / (font_size * 0.53)))
    lines: list[str] = []
    for paragraph in text.split('\n'):
        current = ''
        for word in paragraph.split():
            candidate = f'{current} {word}'.strip()
            if len(candidate) <= max_chars:
                current = candidate
            else:
                if current:
                    lines.append(current)
                current = word
        lines.append(current)
    return lines or ['']


# --- Definisi node --------------------------------------------------------

BOXES = [
    {
        'id': 'query', 'x': 210, 'y': 90, 'w': 215, 'h': 92,
        'title': 'Query Building',
        'body': 'PILL_MAPPING → token BM25\n+ kalimat intent dense',
        'badge': 'TANPA LLM',
    },
    {
        'id': 'fase1', 'x': 485, 'y': 90, 'w': 230, 'h': 92,
        'title': 'Fase 1 — Hard Filter',
        'body': 'Validasi pill, eksklusi feedback\nnegatif, susun profil kandidat',
    },
    {
        'id': 'fase2', 'x': 775, 'y': 90, 'w': 255, 'h': 92,
        'title': 'Fase 2 — Hybrid Retrieval',
        'body': 'BM25 + Dense (MiniLM), gerbang\naktivitas, fusi berbobot → TOP 7',
    },
    {
        'id': 'fase3', 'x': 775, 'y': 460, 'w': 255, 'h': 92,
        'title': 'Fase 3 — Re-rank',
        'body': 'Llama 3.1 8B + grounding check\nskor = 0,6 × LLM + 0,4 × hybrid',
        'badge': 'LLM',
    },
    {
        'id': 'seleksi', 'x': 485, 'y': 460, 'w': 230, 'h': 92,
        'title': 'Seleksi TOP 3 + Evidence',
        'body': 'fit_score ≥ 5,0, kutipan\npendukung & caveat terpilih',
        'icon_left': 'podium',
    },
    {
        'id': 'ringkasan', 'x': 210, 'y': 460, 'w': 215, 'h': 92,
        'title': 'Ringkasan Naratif',
        'body': '1 panggilan LLM per toko,\nwajib mengutip review',
        'badge': 'LLM',
    },
    {
        'id': 'vcache', 'x': 775, 'y': 262, 'w': 175, 'h': 62,
        'title': 'Vector Cache',
        'body': 'memori → Redis → file',
        'muted': True,
    },
    {
        'id': 'taste', 'x': 775, 'y': 610, 'w': 255, 'h': 62,
        'title': 'Profil Selera Pengguna',
        'body': 'review sendiri, favorit, vote',
        'muted': True,
    },
]

GROUP = {
    'id': 'sumber', 'x': 455, 'y': 250, 'w': 290, 'h': 140,
    'title': 'Sumber Data',
    'items': [
        {'id': 'db', 'icon': 'database', 'cx': 512, 'caption': 'Review Pengguna\n(Supabase)'},
        {'id': 'json', 'icon': 'json', 'cx': 600, 'caption': 'facilities.json'},
        {'id': 'votes', 'icon': 'list', 'cx': 690, 'caption': 'shop_votes\n& pros-cons'},
    ],
}

USER = {'id': 'user', 'cx': 96, 'cy': 136, 'caption': 'Pengguna'}


# --- Helper SVG -----------------------------------------------------------

def txt(cx, top, lines, size, weight='normal', color=STROKE, anchor='middle'):
    spans = ''.join(
        f'<tspan x="{cx:.1f}" dy="{0 if i == 0 else LINE_H}">{html.escape(l)}</tspan>'
        for i, l in enumerate(lines)
    )
    return (f'<text x="{cx:.1f}" y="{top + size:.1f}" font-family="{FONT}" '
            f'font-size="{size}" font-weight="{weight}" fill="{color}" '
            f'text-anchor="{anchor}">{spans}</text>')


def icon_user(cx, cy):
    return (
        f'<circle cx="{cx}" cy="{cy - 20}" r="14" fill="{FILL}" stroke="{STROKE}" stroke-width="2"/>'
        f'<path d="M {cx - 24} {cy + 24} a 24 26 0 0 1 48 0 z" fill="{FILL}" '
        f'stroke="{STROKE}" stroke-width="2"/>'
    )


def icon_database(cx, cy):
    w, h = 46, 40
    x, y = cx - w / 2, cy - h / 2
    body = [f'<path d="M {x} {y + 7} v {h - 14} a {w / 2} 7 0 0 0 {w} 0 v -{h - 14} z" '
            f'fill="{FILL}" stroke="{STROKE}" stroke-width="1.8"/>']
    for offset in (7, 20, 33):
        body.append(f'<ellipse cx="{cx}" cy="{y + offset}" rx="{w / 2}" ry="7" '
                    f'fill="{FILL}" stroke="{STROKE}" stroke-width="1.8"/>')
    return ''.join(body)


def icon_json(cx, cy):
    w, h, fold = 40, 46, 12
    x, y = cx - w / 2, cy - h / 2
    return (
        f'<path d="M {x} {y} h {w - fold} l {fold} {fold} v {h - fold} h -{w} z" '
        f'fill="{FILL}" stroke="{STROKE}" stroke-width="1.8"/>'
        f'<path d="M {x + w - fold} {y} v {fold} h {fold}" fill="none" '
        f'stroke="{STROKE}" stroke-width="1.8"/>'
        f'<text x="{cx}" y="{y + h - 13}" font-family="{FONT}" font-size="10" '
        f'font-weight="bold" fill="{STROKE}" text-anchor="middle">JSON</text>'
    )


def icon_list(cx, cy):
    w, h = 42, 44
    x, y = cx - w / 2, cy - h / 2
    rows = ''.join(
        f'<line x1="{x + 9}" y1="{y + 12 + i * 10}" x2="{x + w - 9}" '
        f'y2="{y + 12 + i * 10}" stroke="{STROKE}" stroke-width="1.8"/>'
        for i in range(3)
    )
    return (f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="4" fill="{FILL}" '
            f'stroke="{STROKE}" stroke-width="1.8"/>{rows}')


def icon_podium(cx, cy):
    bars = [(-30, 14, 22, '2'), (-9, 30, 18, '1'), (12, 10, 18, '3')]
    out = []
    for dx, bh, bw, label in bars:
        x, y = cx + dx, cy + 16 - bh
        out.append(f'<rect x="{x}" y="{y}" width="{bw}" height="{bh}" fill="{FILL}" '
                   f'stroke="{STROKE}" stroke-width="1.6"/>')
        out.append(f'<text x="{x + bw / 2}" y="{y + bh - 4}" font-family="{FONT}" '
                   f'font-size="9" fill="{STROKE}" text-anchor="middle">{label}</text>')
    return ''.join(out)


ICONS = {'database': icon_database, 'json': icon_json,
         'list': icon_list, 'podium': icon_podium}


def arrow(x1, y1, x2, y2, dashed=False, label=None, label_dx=0, label_dy=-6):
    dash = ' stroke-dasharray="6 4"' if dashed else ''
    out = [f'<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" stroke="{STROKE}" '
           f'stroke-width="1.6"{dash} marker-end="url(#arrow)"/>']
    if label:
        mx, my = (x1 + x2) / 2 + label_dx, (y1 + y2) / 2 + label_dy
        out.append(txt(mx, my - FS_EDGE, [label], FS_EDGE, color=MUTED))
    return ''.join(out)


def elbow(points, dashed=False, label=None, label_at=None):
    dash = ' stroke-dasharray="6 4"' if dashed else ''
    path = ' '.join(
        ('M' if i == 0 else 'L') + f' {x} {y}' for i, (x, y) in enumerate(points))
    out = [f'<path d="{path}" fill="none" stroke="{STROKE}" stroke-width="1.6"'
           f'{dash} marker-end="url(#arrow)"/>']
    if label and label_at:
        out.append(txt(label_at[0], label_at[1], [label], FS_EDGE, color=MUTED))
    return ''.join(out)


# --- Render SVG -----------------------------------------------------------

def render_svg() -> str:
    p = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{CANVAS_W}" '
        f'height="{CANVAS_H}" viewBox="0 0 {CANVAS_W} {CANVAS_H}">',
        '<defs><marker id="arrow" viewBox="0 0 10 10" refX="9" refY="5" '
        'markerWidth="7" markerHeight="7" orient="auto-start-reverse">'
        f'<path d="M 0 0 L 10 5 L 0 10 z" fill="{STROKE}"/></marker></defs>',
        f'<rect width="{CANVAS_W}" height="{CANVAS_H}" fill="#ffffff"/>',
    ]

    # Grup sumber data
    g = GROUP
    p.append(f'<rect x="{g["x"]}" y="{g["y"]}" width="{g["w"]}" height="{g["h"]}" '
             f'rx="10" fill="{FILL}" stroke="{MUTED}" stroke-width="1.2" '
             'stroke-dasharray="5 4"/>')
    p.append(txt(g['x'] + g['w'] / 2, g['y'] + 8, [g['title']], FS_CAPTION,
                 'bold', MUTED))
    for item in g['items']:
        p.append(ICONS[item['icon']](item['cx'], g['y'] + 58))
        caption = item['caption'].split('\n')
        p.append(txt(item['cx'], g['y'] + 86, caption, 8.5, color=MUTED))

    # Kotak proses
    for box in BOXES:
        x, y, w, h = box['x'], box['y'], box['w'], box['h']
        stroke_w = 1.2 if box.get('muted') else 1.8
        color = MUTED if box.get('muted') else STROKE
        dash = ' stroke-dasharray="5 4"' if box.get('muted') else ''
        p.append(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="6" '
                 f'fill="{FILL}" stroke="{color}" stroke-width="{stroke_w}"{dash}/>')

        text_x, text_w = x, w
        if box.get('icon_left'):
            p.append(ICONS[box['icon_left']](x + 40, y + h / 2))
            text_x, text_w = x + 72, w - 72

        body_lines = wrap(box['body'], text_w - 18, FS_BODY)
        total = LINE_H + len(body_lines) * LINE_H
        top = y + (h - total) / 2 - 2
        cx = text_x + text_w / 2
        p.append(txt(cx, top, [box['title']], FS_TITLE, 'bold', color))
        p.append(txt(cx, top + LINE_H + 3, body_lines, FS_BODY, color=color))

        if box.get('badge'):
            label = box['badge']
            bw = 12 + len(label) * 5.6
            bx, by = x + w - bw - 8, y + 7
            fill = '#1f1f1f' if label == 'LLM' else '#ffffff'
            fg = '#ffffff' if label == 'LLM' else MUTED
            p.append(f'<rect x="{bx:.1f}" y="{by}" width="{bw:.1f}" height="15" '
                     f'rx="7.5" fill="{fill}" stroke="{MUTED}" stroke-width="1"/>')
            p.append(txt(bx + bw / 2, by + 1.5, [label], 9, 'bold', fg))

    # Pengguna
    p.append(icon_user(USER['cx'], USER['cy']))
    p.append(txt(USER['cx'], USER['cy'] + 34, [USER['caption']], FS_CAPTION, 'bold'))

    # Alur utama
    p.append(arrow(146, 136, 205, 136))
    p.append(txt(176, 100, ['Pill', 'Selected'], FS_EDGE, color=MUTED))
    p.append(arrow(425, 136, 480, 136))
    p.append(arrow(715, 136, 770, 136))
    p.append(arrow(600, 250, 600, 187))
    p.append(arrow(862, 262, 862, 187))
    p.append(arrow(990, 182, 990, 455))
    p.append(txt(1055, 290, ['TOP 7 kandidat', '+ kutipan bernomor'],
                 FS_EDGE, color=MUTED, anchor='start'))
    p.append(arrow(902, 610, 902, 557))
    p.append(arrow(770, 506, 720, 506))
    p.append(arrow(480, 506, 430, 506))
    p.append(elbow([(205, 506), (96, 506), (96, 187)],
                   label='Output (Modal)', label_at=(150, 480)))

    # Umpan balik lewat sisi atas
    p.append(elbow([(96, 90), (96, 34), (600, 34), (600, 85)], dashed=True,
                   label='Feedback helpful / not helpful → eksklusi kandidat',
                   label_at=(348, 16)))

    p.append('</svg>')
    return '\n'.join(p)


# --- Render draw.io -------------------------------------------------------

def render_drawio() -> str:
    base = ('html=1;whiteSpace=wrap;fillColor=#ffffff;strokeColor=#1f1f1f;'
            'fontFamily=Helvetica;fontColor=#1f1f1f;')
    cells = ['<mxCell id="0"/>', '<mxCell id="1" parent="0"/>']

    def vertex(cid, value, style, x, y, w, h, parent='1'):
        cells.append(
            f'<mxCell id="{cid}" value="{value}" style="{style}" vertex="1" '
            f'parent="{parent}"><mxGeometry x="{x:.0f}" y="{y:.0f}" '
            f'width="{w:.0f}" height="{h:.0f}" as="geometry"/></mxCell>')

    def label(text, title=None):
        if title:
            return (f'&lt;b&gt;{xml_escape(title)}&lt;/b&gt;&lt;br&gt;'
                    + xml_escape(text).replace('\n', '&lt;br&gt;'))
        return xml_escape(text).replace('\n', '&lt;br&gt;')

    vertex('user', 'Pengguna', base + 'shape=actor;verticalLabelPosition=bottom;'
           'verticalAlign=top;fontSize=11;fontStyle=1;', 66, 96, 60, 72)

    vertex('sumber', 'Sumber Data', base + 'rounded=1;arcSize=8;dashed=1;'
           'strokeColor=#6b6b6b;fontColor=#6b6b6b;verticalAlign=top;fontSize=10;'
           'fontStyle=1;container=1;collapsible=0;',
           GROUP['x'], GROUP['y'], GROUP['w'], GROUP['h'])
    shapes = {'database': 'shape=cylinder3;boundedLbl=1;backgroundOutline=1;size=8;',
              'json': 'shape=note;size=12;',
              'list': 'shape=process;size=0.1;'}
    for item in GROUP['items']:
        vertex(item['id'], label(item['caption']),
               base + shapes[item['icon']] + 'verticalLabelPosition=bottom;'
               'verticalAlign=top;fontSize=8;fontColor=#6b6b6b;',
               item['cx'] - GROUP['x'] - 22, 34, 44, 44, parent='sumber')

    for box in BOXES:
        style = base + 'rounded=1;arcSize=6;fontSize=10;'
        if box.get('muted'):
            style += 'dashed=1;strokeColor=#6b6b6b;fontColor=#6b6b6b;'
        if box.get('badge') == 'LLM':
            style += 'strokeWidth=2;'
        value = label(box['body'], box['title'])
        if box.get('badge'):
            value += f'&lt;br&gt;&lt;i&gt;[{box["badge"]}]&lt;/i&gt;'
        vertex(box['id'], value, style, box['x'], box['y'], box['w'], box['h'])

    edge = ('edgeStyle=orthogonalEdgeStyle;rounded=0;html=1;strokeColor=#1f1f1f;'
            'endArrow=block;endFill=1;fontSize=9;fontColor=#6b6b6b;')
    links = [
        ('user', 'query', 'Pill Selected', ''),
        ('query', 'fase1', '', ''),
        ('fase1', 'fase2', '', ''),
        ('sumber', 'fase1', '', 'exitX=0.5;exitY=0;entryX=0.5;entryY=1;'),
        ('vcache', 'fase2', '', 'exitX=0.5;exitY=0;entryX=0.5;entryY=1;'),
        ('fase2', 'fase3', 'TOP 7', 'exitX=0.85;exitY=1;entryX=0.85;entryY=0;'),
        ('taste', 'fase3', '', 'exitX=0.5;exitY=0;entryX=0.5;entryY=1;'),
        ('fase3', 'seleksi', '', ''),
        ('seleksi', 'ringkasan', '', ''),
        ('ringkasan', 'user', 'Output (Modal)', 'exitX=0;exitY=0.5;entryX=0.5;entryY=1;'),
        ('user', 'fase1', 'Feedback helpful / not helpful',
         'dashed=1;exitX=0.5;exitY=0;entryX=0.5;entryY=0;'),
    ]
    for index, (src, dst, text, extra) in enumerate(links):
        cells.append(
            f'<mxCell id="l{index}" value="{xml_escape(text)}" '
            f'style="{edge}{extra}" edge="1" parent="1" source="{src}" '
            f'target="{dst}"><mxGeometry relative="1" as="geometry"/></mxCell>')

    body = '\n        '.join(cells)
    return (
        '<mxfile host="app.diagrams.net">\n'
        '  <diagram name="Arsitektur Integrasi LLM">\n'
        f'    <mxGraphModel dx="{CANVAS_W}" dy="{CANVAS_H}" grid="0" gridSize="10" '
        'guides="1" tooltips="1" connect="1" arrows="1" fold="1" page="1" '
        f'pageScale="1" pageWidth="{CANVAS_W}" pageHeight="{CANVAS_H}" math="0" '
        f'shadow="0">\n      <root>\n        {body}\n      </root>\n'
        '    </mxGraphModel>\n  </diagram>\n</mxfile>\n'
    )


def main() -> None:
    out_dir = os.path.dirname(os.path.abspath(__file__))
    targets = {
        'diagram-arsitektur-llm.svg': render_svg(),
        'diagram-arsitektur-llm.drawio': render_drawio(),
    }
    for name, content in targets.items():
        path = os.path.join(out_dir, name)
        with open(path, 'w', encoding='utf-8') as handle:
            handle.write(content)
        print(f'wrote {path}')
    print(f'canvas: {CANVAS_W}x{CANVAS_H}')


if __name__ == '__main__':
    main()
