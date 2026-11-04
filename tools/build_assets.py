#!/usr/bin/env python3
"""Rebuild the profile artwork in ../assets.

Fonts cannot load inside an SVG shown through <img>, so all text is converted
to outlines here. To change a project row, edit tools/bom.json and run:

    pip install fonttools
    python tools/build_assets.py

Project links live in README.md, so changing a link needs no rebuild.
"""
import json
import re
from pathlib import Path

from fontTools.pens.svgPathPen import SVGPathPen
from fontTools.pens.transformPen import TransformPen
from fontTools.ttLib import TTFont

TOOLS = Path(__file__).resolve().parent
ASSETS = TOOLS.parent / "assets"
BG, LINE, SOFT = "#0a0e13", "#2c3847", "#1a222d"
TEXT, MUTED, FAINT, CYAN = "#e7edf3", "#8996a6", "#6b7786", "#4dd9e8"
LIVE_STATUSES = {"IN PROGRESS", "CONCEPT"}


class Face:
    def __init__(self, filename):
        self.font = TTFont(TOOLS / "fonts" / filename)
        self.glyphs = self.font.getGlyphSet()
        self.cmap = self.font.getBestCmap()
        self.upem = self.font["head"].unitsPerEm

    def width(self, text, size, spacing=0):
        total = 0
        for ch in text:
            name = self.cmap.get(ord(ch), ".notdef")
            total += self.glyphs[name].width * size / self.upem + spacing
        return total

    def path(self, text, x, y, size, spacing=0, anchor="start"):
        if anchor == "end":
            x -= self.width(text, size, spacing)
        elif anchor == "middle":
            x -= self.width(text, size, spacing) / 2
        scale = size / self.upem
        pen = SVGPathPen(self.glyphs, ntos=lambda v: f"{v:.2f}".rstrip("0").rstrip("."))
        for ch in text:
            name = self.cmap.get(ord(ch), ".notdef")
            self.glyphs[name].draw(TransformPen(pen, (scale, 0, 0, -scale, x, y)))
            x += self.glyphs[name].width * scale + spacing
        return pen.getCommands()


MONO = Face("ibm-plex-mono-latin-400-normal.woff")
MONO_BOLD = Face("ibm-plex-mono-latin-600-normal.woff")
SANS = Face("manrope-latin-800-normal.woff")

TEXT_STYLES = {
    "name": (SANS, 38, -0.5, TEXT),
    "tag": (MONO, 14, 0, CYAN),
    "lab": (MONO_BOLD, 11, 0.4, TEXT),
    "sub": (MONO, 10.5, 0, MUTED),
    "tick": (MONO, 9, 0, FAINT),
    "tb": (MONO, 9, 0.5, MUTED),
    "tv": (MONO, 11.5, 0, TEXT),
    "tvc": (MONO, 11.5, 0, CYAN),
    "vio": (MONO, 10, 0, "#8393f2"),
    "cap": (MONO, 10.5, 0, MUTED),
    "capb": (MONO_BOLD, 10.5, 0.4, TEXT),
    "sn": (MONO, 10, 0, "#c4d0dc"),
}
TEXT_RE = re.compile(r'<text x="([\d.]+)" y="([\d.]+)" class="(\w+)"(?: style="text-anchor: (\w+)")?>(.*?)</text>')


def outline(match):
    x, y, cls, anchor, text = match.groups()
    face, size, spacing, fill = TEXT_STYLES[cls]
    return f'<path fill="{fill}" d="{face.path(text, float(x), float(y), size, spacing, anchor or "start")}"/>'


def css():
    rules = (TOOLS / "src" / "style.css").read_text().splitlines()
    return "<style>" + "".join(r for r in rules if "font-family" not in r) + "</style>"


def build_source(name, out):
    svg = (TOOLS / "src" / f"{name}.src.svg").read_text()
    svg = TEXT_RE.sub(outline, svg)
    if "<text" in svg:
        raise SystemExit(f"unconverted text left in {name}")
    w, h = re.search(r'viewBox="0 0 (\d+) (\d+)"', svg).groups()
    if ' width="' not in svg.split(">", 1)[0]:
        svg = svg.replace("<svg ", f'<svg width="{w}" height="{h}" ', 1)
    plate = f'<rect width="{w}" height="{h}" rx="6" fill="{BG}"/>'
    svg = re.sub(r"(<svg [^>]*>)", lambda m: m.group(1) + css() + plate, svg, count=1)
    (ASSETS / out).write_text(svg)


def mobile_banner():
    src = (TOOLS / "src" / "banner.src.svg").read_text()
    start = src.index('<path d="M300 392h170"')
    end = src.index('<path d="M44 178h206')
    arm = TEXT_RE.sub("", src[start:end])
    w, h = 400, 372
    head = (
        f'<path fill="{TEXT}" d="{SANS.path("Thabang Molise", 24, 58, 34, -0.4)}"/>'
        f'<path fill="{CYAN}" d="{MONO.path("Software for machines that move.", 24, 84, 13)}"/>'
        f'<path fill="{MUTED}" d="{MONO.path("Robotics, ML and backends", 24, 104, 12)}"/>'
    )
    (ASSETS / "banner-mobile.svg").write_text(
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w} {h}" width="{w}" height="{h}" '
        f'role="img" aria-label="Thabang Molise. Software for machines that move.">{css()}'
        f'<rect width="{w}" height="{h}" fill="{BG}"/>'
        f'<rect x="8" y="8" width="{w - 16}" height="{h - 16}" class="frame"/>{head}'
        f'<g transform="translate(-244 26) scale(.86)">{arm}</g></svg>'
    )


def wrap(face, text, size, width):
    lines, line = [], ""
    for word in text.split():
        trial = f"{line} {word}".strip()
        if face.width(trial, size) <= width or not line:
            line = trial
        else:
            lines.append(line)
            line = word
    return lines + [line]


def panel(w, h, first, last):
    """A row of the BOM card; rows stack to read as one panel."""
    r = 6
    top = f"M.5 {r}Q.5 .5 {r} .5H{w - r}Q{w - .5} .5 {w - .5} {r}" if first else f"M.5 0V0M{w - .5} 0"
    if first and last:
        edge = f"{top}V{h - r}Q{w - .5} {h - .5} {w - r} {h - .5}H{r}Q.5 {h - .5} .5 {h - r}Z"
    elif first:
        edge = f"M.5 {h}V{r}Q.5 .5 {r} .5H{w - r}Q{w - .5} .5 {w - .5} {r}V{h}"
    elif last:
        edge = f"M.5 0V{h - r}Q.5 {h - .5} {r} {h - .5}H{w - r}Q{w - .5} {h - .5} {w - .5} {h - r}V0"
    else:
        edge = f"M.5 0V{h}M{w - .5} 0V{h}"
    fill = f'<rect width="{w}" height="{h}" rx="{r if first and last else 0}" fill="{BG}"/>'
    if first:
        fill = f'<path fill="{BG}" d="M0 {h}V{r}Q0 0 {r} 0H{w - r}Q{w} 0 {w} {r}V{h}Z"/>'
    if last:
        fill = f'<path fill="{BG}" d="M0 0V{h - r}Q0 {h} {r} {h}H{w - r}Q{w} {h} {w} {h - r}V0Z"/>'
    rule = "" if last else f'<path stroke="{SOFT}" d="M1 {h - .5}H{w - 1}"/>'
    return fill + rule + f'<path fill="none" stroke="{LINE}" d="{edge}"/>'


def text(face, value, x, y, size, fill, spacing=0, anchor="start"):
    return f'<path fill="{fill}" d="{face.path(value, x, y, size, spacing, anchor)}"/>'


def svg(path, w, h, label, body):
    (ASSETS / path).write_text(
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w} {h}" width="{w}" height="{h}" '
        f'role="img" aria-label="{label}">{body}</svg>'
    )


DESK = {"item": 14, "part": 62, "function": 290, "materials": 536, "status": 734}
DESK_W = {"function": 230, "materials": 186}


def bom_header():
    w, h = 846, 38
    labels = {"item": "ITEM", "part": "PART", "function": "FUNCTION", "materials": "MATERIALS", "status": "STATUS"}
    body = panel(w, h, True, False).replace(SOFT, LINE)
    for key, label in labels.items():
        body += text(MONO, label, DESK[key], 24, 11, MUTED, 0.5)
    svg("bom-header.svg", w, h, "Bill of materials", body)
    w, h = 400, 34
    body = panel(w, h, True, False).replace(SOFT, LINE)
    body += text(MONO, "PART", 16, 22, 11, MUTED, 0.5) + text(MONO, "STATUS", w - 16, 22, 11, MUTED, 0.5, "end")
    svg("bom-header-mobile.svg", w, h, "Bill of materials", body)


def bom_rows(rows):
    for i, row in enumerate(rows):
        last = i == len(rows) - 1
        status_fill = CYAN if row["status"] in LIVE_STATUSES else MUTED
        label = f'{row["part"]}: {row["function"]}. {row["materials"]}. {row["status"].title()}.'.replace("..", ".")

        size, lead = 12.5, 18
        fn = wrap(MONO, row["function"], size, DESK_W["function"])
        mat = wrap(MONO, row["materials"], size, DESK_W["materials"])
        h = 18 + lead * max(len(fn), len(mat)) + 2
        w = 846
        body = panel(w, h, False, last)
        y = 24
        body += text(MONO, row["item"], DESK["item"], y, size, FAINT)
        body += text(MONO_BOLD, row["part"], DESK["part"], y, size, TEXT)
        body += text(MONO, row["status"], DESK["status"], y, size, status_fill)
        for n, line in enumerate(fn):
            body += text(MONO, line, DESK["function"], y + n * lead, size, MUTED)
        for n, line in enumerate(mat):
            body += text(MONO, line, DESK["materials"], y + n * lead, size, MUTED)
        svg(f'bom-{row["item"]}.svg', w, h, label, body)

        w = 400
        size, lead = 14, 20
        fn = wrap(MONO, row["function"], size, w - 32)
        h = 42 + lead * len(fn) + 12
        body = panel(w, h, False, last)
        body += text(MONO_BOLD, row["part"], 16, 28, 15, TEXT)
        if MONO_BOLD.width(row["part"], 15) + MONO.width(row["status"], 12) + 44 <= w:
            body += text(MONO, row["status"], w - 16, 28, 12, status_fill, 0, "end")
            start = 50
        else:
            h += lead
            body = panel(w, h, False, last) + text(MONO_BOLD, row["part"], 16, 28, 15, TEXT)
            body += text(MONO, row["status"], 16, 48, 12, status_fill)
            start = 70
        for n, line in enumerate(fn):
            body += text(MONO, line, 16, start + n * lead, size, MUTED)
        svg(f'bom-{row["item"]}-mobile.svg', w, h, label, body)


def main():
    ASSETS.mkdir(exist_ok=True)
    build_source("banner", "banner.svg")
    build_source("detail-pisces", "detail-pisces.svg")
    build_source("detail-piano", "detail-piano.svg")
    mobile_banner()
    rows = json.loads((TOOLS / "bom.json").read_text())
    bom_header()
    bom_rows(rows)
    print(f"Built {len(list(ASSETS.glob('*.svg')))} files in {ASSETS}")


if __name__ == "__main__":
    main()
