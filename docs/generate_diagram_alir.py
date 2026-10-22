"""
Generator diagram alir penelitian Cofind.

Satu definisi tata letak dipakai untuk tiga keluaran supaya ketiganya selalu
identik: SVG (pratinjau), draw.io XML (bisa diedit ulang), dan Mermaid.

Jalankan:  python docs/generate_diagram_alir.py
"""

from __future__ import annotations

import html
import os
from xml.sax.saxutils import escape as xml_escape

# --- Parameter tata letak -------------------------------------------------

CANVAS_W = 980
CENTER_X = CANVAS_W // 2
MARGIN_TOP = 40
MARGIN_BOTTOM = 40

TERMINAL_W, TERMINAL_H = 180, 56
CONTAINER_W = 780
CONTAINER_PAD = 18
CONTAINER_TITLE_H = 34
CHILD_GAP = 12
CHILD_MIN_H = 48
GAP_BETWEEN_NODES = 44

FONT = 'Helvetica, Arial, sans-serif'
FS_TITLE = 13
FS_CHILD = 11
FS_TERMINAL = 13
LINE_H = 14

STROKE = '#1f1f1f'
FILL = '#ffffff'


def wrap(text: str, width_px: float, font_size: int) -> list[str]:
    """Bungkus teks berdasarkan perkiraan lebar rata-rata karakter."""
    max_chars = max(8, int(width_px / (font_size * 0.53)))
    lines: list[str] = []
    for paragraph in text.split('\n'):
        words, current = paragraph.split(), ''
        for word in words:
            candidate = f'{current} {word}'.strip()
            if len(candidate) <= max_chars:
                current = candidate
            else:
                if current:
                    lines.append(current)
                current = word
        lines.append(current)
    return lines or ['']


# --- Definisi isi diagram -------------------------------------------------

NODES = [
    {
        'kind': 'terminal',
        'id': 'start',
        'title': 'Start',
    },
    {
        'kind': 'container',
        'id': 'analisis',
        'title': 'Analisis Masalah',
        'rows': [
            ['Menentukan Latar Belakang dan Rumusan Masalah'],
        ],
    },
    {
        'kind': 'container',
        'id': 'literatur',
        'title': 'Studi Literatur',
        'rows': [
            [
                'Retrieval-Augmented Generation (RAG)',
                'Hybrid Retrieval: BM25 + Dense Embedding',
            ],
            [
                'LLM Reranking & Grounding Kutipan',
                'Evaluasi Ringkasan: ROUGE & BERTScore',
            ],
        ],
    },
    {
        'kind': 'container',
        'id': 'pengumpulan',
        'title': 'Pengumpulan Data',
        'rows': [
            [
                'Review Pengguna Cofind\n(Supabase PostgreSQL)',
                'Metadata & Rating Coffee Shop\n(salinan Google Maps, input admin)',
            ],
            [
                'Data Fasilitas per Toko\n(facilities.json)',
                'Vote Komunitas & Pros-Cons\n(shop_votes, shop_pros_cons)',
            ],
        ],
    },
    {
        'kind': 'container',
        'id': 'pemrosesan',
        'title': 'Pemrosesan Data',
        'rows': [
            [
                'Build Profile Review\n(review + vote + fasilitas per toko)',
                'Keywords Mapping\n(PILL_MAPPING: aktivitas + atribut)',
            ],
            [
                'Filtering\n(min. 1 review, eksklusi feedback not_helpful)',
                'Indeks BM25 + Embedding Kalimat\n(MiniLM multilingual) & Vector Cache',
            ],
        ],
    },
    {
        'kind': 'container',
        'id': 'implementasi',
        'title': 'Integrasi & Implementasi — Pipeline RAG 3 Fase',
        'rows': [
            ['Fase 1 — Hard Filter: validasi pill, eksklusi feedback negatif, '
             'susun profil kandidat'],
            ['Fase 2 — Hybrid Retrieval: skor BM25 (sparse) + Dense Embedding (cosine), '
             'gerbang aktivitas wajib, normalisasi min-max & fusi berbobot dengan skor '
             'kualitas toko → Top-K = 7 kandidat'],
            ['Fase 3 — Penggunaan LLM (Llama 3.1 8B Instruct via HF Router): rerank '
             'fit_score 0–10, grounding check kutipan, skor akhir = 0,6 × LLM + 0,4 × Hybrid'],
            [
                'Seleksi Top-3 Rekomendasi\n(fit_score ≥ 5,0 + bukti aktivitas)',
                'Build Evidence\n(kutipan pendukung & caveat dari review)',
            ],
            [
                'Ringkasan Naratif per Toko\n(LLM, fallback deterministik)',
                'Pembuatan User Interface Output Recommendation\n(React + progres SSE)',
            ],
        ],
    },
    {
        'kind': 'container',
        'id': 'pengujian',
        'title': 'Pengujian',
        'rows': [
            [
                'ROUGE-Score & BERT-Score\n(kualitas ringkasan naratif)',
                'Grounding Rate\n(kutipan terverifikasi ada di korpus review)',
            ],
            [
                'Feedback Pengguna\n(helpful / not helpful)',
                'Pengujian Fungsional & Latensi Pipeline',
            ],
        ],
    },
    {
        'kind': 'terminal',
        'id': 'kesimpulan',
        'title': 'Kesimpulan',
    },
]


# --- Perhitungan tata letak ----------------------------------------------

def build_layout(nodes):
    """Lengkapi setiap node dengan koordinat absolut dan ukuran akhir."""
    y = MARGIN_TOP
    for node in nodes:
        if node['kind'] == 'terminal':
            node['w'], node['h'] = TERMINAL_W, TERMINAL_H
            node['x'] = CENTER_X - TERMINAL_W // 2
            node['y'] = y
        else:
            inner_w = CONTAINER_W - 2 * CONTAINER_PAD
            child_y = CONTAINER_TITLE_H + CONTAINER_PAD
            placed = []
            for row in node['rows']:
                cols = len(row)
                child_w = (inner_w - CHILD_GAP * (cols - 1)) / cols
                row_h = CHILD_MIN_H
                wrapped_row = []
                for text in row:
                    lines = wrap(text, child_w - 20, FS_CHILD)
                    row_h = max(row_h, len(lines) * LINE_H + 22)
                    wrapped_row.append(lines)
                for index, lines in enumerate(wrapped_row):
                    placed.append({
                        'x': CONTAINER_PAD + index * (child_w + CHILD_GAP),
                        'y': child_y,
                        'w': child_w,
                        'h': row_h,
                        'lines': lines,
                        'text': row[index],
                    })
                child_y += row_h + CHILD_GAP
            node['w'] = CONTAINER_W
            node['h'] = child_y - CHILD_GAP + CONTAINER_PAD
            node['x'] = CENTER_X - CONTAINER_W // 2
            node['y'] = y
            node['children'] = placed
        y = node['y'] + node['h'] + GAP_BETWEEN_NODES
    return y - GAP_BETWEEN_NODES + MARGIN_BOTTOM


# --- Keluaran SVG ---------------------------------------------------------

def render_svg(nodes, canvas_h) -> str:
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{CANVAS_W}" '
        f'height="{canvas_h}" viewBox="0 0 {CANVAS_W} {canvas_h}">',
        '<defs><marker id="arrow" viewBox="0 0 10 10" refX="9" refY="5" '
        'markerWidth="7" markerHeight="7" orient="auto-start-reverse">'
        f'<path d="M 0 0 L 10 5 L 0 10 z" fill="{STROKE}"/></marker></defs>',
        f'<rect width="{CANVAS_W}" height="{canvas_h}" fill="#ffffff"/>',
    ]

    def text_block(cx, top, lines, font_size, weight='normal'):
        first = top + font_size
        spans = ''.join(
            f'<tspan x="{cx:.1f}" dy="{0 if i == 0 else LINE_H}">'
            f'{html.escape(line)}</tspan>'
            for i, line in enumerate(lines)
        )
        return (
            f'<text x="{cx:.1f}" y="{first:.1f}" font-family="{FONT}" '
            f'font-size="{font_size}" font-weight="{weight}" fill="{STROKE}" '
            f'text-anchor="middle">{spans}</text>'
        )

    for node in nodes:
        x, y, w, h = node['x'], node['y'], node['w'], node['h']
        cx = x + w / 2
        if node['kind'] == 'terminal':
            parts.append(
                f'<ellipse cx="{cx}" cy="{y + h / 2}" rx="{w / 2}" ry="{h / 2}" '
                f'fill="{FILL}" stroke="{STROKE}" stroke-width="1.4"/>'
            )
            parts.append(text_block(cx, y + h / 2 - FS_TERMINAL / 2 - 2,
                                    [node['title']], FS_TERMINAL, 'bold'))
        else:
            parts.append(
                f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="10" ry="10" '
                f'fill="{FILL}" stroke="{STROKE}" stroke-width="1.4"/>'
            )
            title_lines = wrap(node['title'], w - 40, FS_TITLE)
            parts.append(text_block(cx, y + 8, title_lines, FS_TITLE, 'bold'))
            for child in node['children']:
                ax, ay = x + child['x'], y + child['y']
                parts.append(
                    f'<rect x="{ax:.1f}" y="{ay:.1f}" width="{child["w"]:.1f}" '
                    f'height="{child["h"]:.1f}" rx="4" ry="4" fill="{FILL}" '
                    f'stroke="{STROKE}" stroke-width="1"/>'
                )
                block_h = len(child['lines']) * LINE_H
                parts.append(text_block(
                    ax + child['w'] / 2,
                    ay + (child['h'] - block_h) / 2 - 2,
                    child['lines'],
                    FS_CHILD,
                ))

    for upper, lower in zip(nodes, nodes[1:]):
        y1 = upper['y'] + upper['h']
        y2 = lower['y']
        parts.append(
            f'<line x1="{CENTER_X}" y1="{y1}" x2="{CENTER_X}" y2="{y2 - 2}" '
            f'stroke="{STROKE}" stroke-width="1.4" marker-end="url(#arrow)"/>'
        )

    parts.append('</svg>')
    return '\n'.join(parts)


# --- Keluaran draw.io -----------------------------------------------------

def render_drawio(nodes, canvas_h) -> str:
    cells = [
        '<mxCell id="0"/>',
        '<mxCell id="1" parent="0"/>',
    ]
    base = ('html=1;whiteSpace=wrap;fillColor=#ffffff;strokeColor=#1f1f1f;'
            'fontFamily=Helvetica;fontColor=#1f1f1f;')

    for node in nodes:
        node_id = node['id']
        if node['kind'] == 'terminal':
            style = base + f'ellipse;fontSize={FS_TERMINAL};fontStyle=1;'
            cells.append(
                f'<mxCell id="{node_id}" value="{xml_escape(node["title"])}" '
                f'style="{style}" vertex="1" parent="1">'
                f'<mxGeometry x="{node["x"]}" y="{node["y"]}" '
                f'width="{node["w"]}" height="{node["h"]}" as="geometry"/></mxCell>'
            )
        else:
            style = (base + f'rounded=1;arcSize=8;verticalAlign=top;'
                     f'fontSize={FS_TITLE};fontStyle=1;spacingTop=6;'
                     'container=1;collapsible=0;')
            cells.append(
                f'<mxCell id="{node_id}" value="{xml_escape(node["title"])}" '
                f'style="{style}" vertex="1" parent="1">'
                f'<mxGeometry x="{node["x"]}" y="{node["y"]}" '
                f'width="{node["w"]}" height="{node["h"]}" as="geometry"/></mxCell>'
            )
            child_style = base + f'rounded=0;fontSize={FS_CHILD};'
            for index, child in enumerate(node['children']):
                value = xml_escape(child['text']).replace('\n', '&#10;')
                cells.append(
                    f'<mxCell id="{node_id}-c{index}" value="{value}" '
                    f'style="{child_style}" vertex="1" parent="{node_id}">'
                    f'<mxGeometry x="{child["x"]:.0f}" y="{child["y"]:.0f}" '
                    f'width="{child["w"]:.0f}" height="{child["h"]:.0f}" '
                    'as="geometry"/></mxCell>'
                )

    edge_style = ('edgeStyle=orthogonalEdgeStyle;rounded=0;html=1;'
                  'strokeColor=#1f1f1f;endArrow=block;endFill=1;exitX=0.5;'
                  'exitY=1;entryX=0.5;entryY=0;')
    for index, (upper, lower) in enumerate(zip(nodes, nodes[1:])):
        cells.append(
            f'<mxCell id="e{index}" style="{edge_style}" edge="1" parent="1" '
            f'source="{upper["id"]}" target="{lower["id"]}">'
            '<mxGeometry relative="1" as="geometry"/></mxCell>'
        )

    body = '\n        '.join(cells)
    return (
        '<mxfile host="app.diagrams.net">\n'
        '  <diagram name="Diagram Alir Penelitian">\n'
        f'    <mxGraphModel dx="{CANVAS_W}" dy="{canvas_h}" grid="0" '
        'gridSize="10" guides="1" tooltips="1" connect="1" arrows="1" '
        f'fold="1" page="1" pageScale="1" pageWidth="{CANVAS_W}" '
        f'pageHeight="{canvas_h}" math="0" shadow="0">\n'
        f'      <root>\n        {body}\n      </root>\n'
        '    </mxGraphModel>\n'
        '  </diagram>\n'
        '</mxfile>\n'
    )


# --- Keluaran Mermaid -----------------------------------------------------

def render_mermaid(nodes) -> str:
    lines = ['flowchart TD']
    for node in nodes:
        node_id = node['id'].upper()
        if node['kind'] == 'terminal':
            lines.append(f'    {node_id}(["{node["title"]}"])')
            continue
        lines.append(f'    subgraph {node_id}["{node["title"]}"]')
        lines.append('        direction TB')
        flat = [text for row in node['rows'] for text in row]
        for index, text in enumerate(flat):
            label = text.replace('\n', '<br/>')
            lines.append(f'        {node_id}_{index}["{label}"]')
        lines.append('    end')
    for upper, lower in zip(nodes, nodes[1:]):
        lines.append(f'    {upper["id"].upper()} --> {lower["id"].upper()}')
    return '\n'.join(lines) + '\n'


def main() -> None:
    out_dir = os.path.dirname(os.path.abspath(__file__))
    canvas_h = build_layout(NODES)

    targets = {
        'diagram-alir-penelitian.svg': render_svg(NODES, canvas_h),
        'diagram-alir-penelitian.drawio': render_drawio(NODES, canvas_h),
        'diagram-alir-penelitian.mmd': render_mermaid(NODES),
    }
    for name, content in targets.items():
        path = os.path.join(out_dir, name)
        with open(path, 'w', encoding='utf-8') as handle:
            handle.write(content)
        print(f'wrote {path}')
    print(f'canvas: {CANVAS_W}x{canvas_h}')


if __name__ == '__main__':
    main()
