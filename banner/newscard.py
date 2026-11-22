#!/usr/bin/env python3
"""
Telegram news-card generator (HAYTSEGHAKRON-style layout).

Full-bleed photo + dark bottom scrim + bold uppercase headline bottom-left +
centered brand wordmark (with pinwheel glyph) top & bottom + faint center
watermark + pixel chevron in the top-right corner.

Requires: Pillow

Example
-------
python newscard.py \
    --image photo.jpg \
    --headline "ԲԱՆՏՈՒՄ ՔԱՂԱՔԱԿԱՆ ՍՊԱՆՈՒԹՅՈՒՆ. ԱՐՍԵՆ ԳԵՎՈՐԳՅԱՆԻ ՄԱՀԸ." \
    --brand "HAYTSEGHAKR*N" \
    --grayscale \
    --out out/card.png

In --brand and --headline a '*' is drawn as the pinwheel glyph.
"""
from __future__ import annotations

import argparse
import math
import os
from dataclasses import dataclass

from PIL import Image, ImageDraw, ImageFont, ImageOps

# --- fonts -----------------------------------------------------------------

HERE = os.path.dirname(os.path.abspath(__file__))
ARM_DIR = os.path.join(HERE, "fonts")
LATIN_DIR = "/usr/share/fonts/opentype/inter"

ARM = {  # headline / Armenian-capable
    "black": "NotoSansArmenian-Black.ttf",
    "extrabold": "NotoSansArmenian-ExtraBold.ttf",
    "bold": "NotoSansArmenian-Bold.ttf",
    "semibold": "NotoSansArmenian-SemiBold.ttf",
    "medium": "NotoSansArmenian-Medium.ttf",
    "regular": "NotoSansArmenian-Regular.ttf",
}
LATIN = {  # brand wordmark + Latin/punctuation fallback
    "black": "Inter-Black.otf",
    "extrabold": "Inter-ExtraBold.otf",
    "bold": "Inter-Bold.otf",
    "semibold": "Inter-SemiBold.otf",
    "medium": "Inter-Medium.otf",
}
_FALLBACK = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"


def _resolve(d, table, weight):
    p = os.path.join(d, table.get(weight, next(iter(table.values()))))
    return p if os.path.exists(p) else _FALLBACK


def arm_font(weight, size):
    return ImageFont.truetype(_resolve(ARM_DIR, ARM, weight), size)


def latin_font(weight, size):
    return ImageFont.truetype(_resolve(LATIN_DIR, LATIN, weight), size)


def dejavu_font(size):
    return ImageFont.truetype(_FALLBACK, size)


# --- per-character font fallback -------------------------------------------
# Noto Sans Armenian covers Armenian only (no '.', ',', '-', Latin, digits),
# so we fall back to Inter, then DejaVu, per glyph.

_NOTDEF: dict = {}


def _covers(font, ch):
    if ch in "  ":
        return True
    key = (font.path, font.size)
    nd = _NOTDEF.get(key)
    if nd is None:
        m0 = font.getmask("")  # private-use: almost always .notdef
        nd = (m0.size, bytes(m0))
        _NOTDEF[key] = nd
    m = font.getmask(ch)
    if m.size == (0, 0):
        return True
    return not (m.size == nd[0] and bytes(m) == nd[1])


class Glyphs:
    """A size+weight font stack with per-char coverage picking and a shared baseline."""

    def __init__(self, size, weight="black"):
        self.size = size
        self.fonts = [arm_font(weight, size), latin_font(weight, size), dejavu_font(size)]
        self.ascent = max(f.getmetrics()[0] for f in self.fonts)

    def pick(self, ch):
        for f in self.fonts:
            if _covers(f, ch):
                return f
        return self.fonts[0]

    def width(self, draw, text):
        return sum(draw.textlength(ch, font=self.pick(ch)) for ch in text)

    def draw_line(self, draw, text, x, baseline, fill):
        for ch in text:
            f = self.pick(ch)
            draw.text((x, baseline), ch, font=f, fill=fill, anchor="ls")
            x += draw.textlength(ch, font=f)


# --- color -----------------------------------------------------------------

def hex_to_rgb(v):
    v = v.strip().lstrip("#")
    if len(v) == 3:
        v = "".join(c * 2 for c in v)
    return tuple(int(v[i:i + 2], 16) for i in (0, 2, 4))


# --- image helpers ---------------------------------------------------------

def cover_fit(img, size):
    tw, th = size
    iw, ih = img.size
    scale = max(tw / iw, th / ih)
    nw, nh = round(iw * scale), round(ih * scale)
    img = img.resize((nw, nh), Image.LANCZOS)
    left, top = (nw - tw) // 2, (nh - th) // 2
    return img.crop((left, top, left + tw, top + th))


def bottom_scrim(size, bottom_frac=0.55, bottom_strength=0.9,
                 top_frac=0.14, top_strength=0.38):
    """Black RGBA scrim: dark at bottom (for headline), slight dark at top (for wordmark)."""
    w, h = size
    mask = Image.new("L", size, 0)
    md = ImageDraw.Draw(mask)
    b_start = int(h * (1 - bottom_frac))
    for y in range(b_start, h):
        t = (y - b_start) / max(h - b_start - 1, 1)
        a = int(255 * bottom_strength * (t ** 1.4))  # ease-in toward bottom
        md.line([(0, y), (w, y)], fill=a)
    t_end = int(h * top_frac)
    for y in range(0, t_end):
        t = 1 - y / max(t_end - 1, 1)
        a = int(255 * top_strength * (t ** 1.3))
        # keep whichever is darker
        cur = mask.getpixel((0, y))
        if a > cur:
            md.line([(0, y), (w, y)], fill=a)
    scrim = Image.new("RGBA", size, (0, 0, 0, 0))
    scrim.putalpha(mask)
    return scrim


# --- glyph tiles (supersampled, smooth) ------------------------------------

def pinwheel_tile(px, color, blades=6, ss=4):
    """A small pinwheel/spiral brand glyph as an RGBA tile of side `px`."""
    s = px * ss
    tile = Image.new("RGBA", (s, s), (0, 0, 0, 0))
    d = ImageDraw.Draw(tile)
    c = s / 2
    R = s * 0.47
    inner = R * 0.14
    span = math.radians(360 / blades * 0.62)  # swept fan blade
    fill = color + (255,)

    def polar(ang, r):
        return (c + r * math.cos(ang), c + r * math.sin(ang))

    for i in range(blades):
        a = math.radians(i * 360 / blades)
        # a swept quadrilateral: narrow at the hub, wide and offset at the rim
        pts = [polar(a, inner), polar(a, R), polar(a + span, R), polar(a + span * 0.45, inner)]
        d.polygon(pts, fill=fill)
    hub = R * 0.16
    d.ellipse((c - hub, c - hub, c + hub, c + hub), fill=fill)
    return tile.resize((px, px), Image.LANCZOS)


def pixel_chevron_tile(px, color, ss=4):
    """A chunky pixelated left-pointing chevron as an RGBA tile of side `px`."""
    # 7x7 grid, 1 = filled block; a staircase '<'
    grid = [
        "0000110",
        "0011000",
        "1100000",
        "1100000",
        "0011000",
        "0000110",
        "0000011",
    ]
    rows = len(grid)
    cols = len(grid[0])
    cell = (px * ss) // cols
    s_w, s_h = cell * cols, cell * rows
    tile = Image.new("RGBA", (s_w, s_h), (0, 0, 0, 0))
    d = ImageDraw.Draw(tile)
    for r, line in enumerate(grid):
        for cc, ch in enumerate(line):
            if ch == "1":
                x0, y0 = cc * cell, r * cell
                d.rectangle((x0, y0, x0 + cell - 1, y0 + cell - 1), fill=color + (255,))
    out_w = px
    out_h = round(px * rows / cols)
    return tile.resize((out_w, out_h), Image.LANCZOS)


# --- tracked (letter-spaced) wordmark --------------------------------------

def tracked_width(draw, text, font, tracking, pin_w):
    w = 0
    for ch in text:
        w += pin_w if ch == "*" else draw.textlength(ch, font=font)
        w += tracking
    return w - tracking if text else 0


def draw_tracked(overlay, draw, text, font, x, y, fill, tracking, pin_w):
    """Draw letter-spaced text; '*' becomes the pinwheel glyph. Returns end x."""
    asc = font.getmetrics()[0]
    for ch in text:
        if ch == "*":
            tile = pinwheel_tile(pin_w, fill)
            overlay.alpha_composite(tile, (round(x), round(y + asc - pin_w)))
            x += pin_w + tracking
        else:
            draw.text((x, y), ch, font=font, fill=fill + (255,))
            x += draw.textlength(ch, font=font) + tracking
    return x


def wrap_g(draw, text, g: "Glyphs", max_w):
    lines, cur = [], ""
    for word in text.split():
        trial = f"{cur} {word}".strip()
        if g.width(draw, trial) <= max_w or not cur:
            cur = trial
        else:
            lines.append(cur)
            cur = word
    if cur:
        lines.append(cur)
    return lines


def fit_headline(draw, text, max_w, max_h, start, weight="black", min_size=28):
    size = start
    while size >= min_size:
        g = Glyphs(size, weight)
        lines = wrap_g(draw, text, g, max_w)
        lh = round(size * 1.12)
        if len(lines) * lh <= max_h and all(g.width(draw, ln) <= max_w for ln in lines):
            return g, lines, lh
        size -= 2
    g = Glyphs(min_size, weight)
    return g, wrap_g(draw, text, g, max_w), round(min_size * 1.12)


# --- spec & render ---------------------------------------------------------

@dataclass
class CardSpec:
    image: str
    headline: str
    brand: str = "HAYTSEGHAKR*N"
    size: tuple = (1080, 1350)
    grayscale: bool = False
    darken: float = 0.0        # 0..1 overall darkening of the photo
    color: tuple = (255, 255, 255)
    watermark: bool = True


def generate_card(spec: CardSpec) -> Image.Image:
    w, h = spec.size
    margin = round(w * 0.055)

    photo = Image.open(spec.image).convert("RGB")
    photo = cover_fit(photo, spec.size)
    if spec.grayscale:
        photo = ImageOps.grayscale(photo).convert("RGB")
    if spec.darken > 0:
        photo = Image.blend(photo, Image.new("RGB", spec.size, (0, 0, 0)), spec.darken)

    img = photo.convert("RGBA")
    img.alpha_composite(bottom_scrim(spec.size))

    overlay = Image.new("RGBA", spec.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)
    col = spec.color

    # top-center brand wordmark
    bw = round(w * 0.024)
    brand_font = latin_font("bold", bw)
    track = round(bw * 0.42)
    pin_w = round(bw * 1.05)
    total = tracked_width(draw, spec.brand, brand_font, track, pin_w)
    top_y = round(h * 0.028)
    draw_tracked(overlay, draw, spec.brand, brand_font,
                 (w - total) / 2, top_y, col, track, pin_w)

    # center watermark
    if spec.watermark:
        wm_overlay = Image.new("RGBA", spec.size, (0, 0, 0, 0))
        wm_draw = ImageDraw.Draw(wm_overlay)
        wbw = round(w * 0.028)
        wm_font = latin_font("semibold", wbw)
        wtrack = round(wbw * 0.45)
        wpin = round(wbw * 1.05)
        wtotal = tracked_width(wm_draw, spec.brand, wm_font, wtrack, wpin)
        draw_tracked(wm_overlay, wm_draw, spec.brand, wm_font,
                     (w - wtotal) / 2, h * 0.5 - wbw, col, wtrack, wpin)
        overlay.alpha_composite(Image.blend(
            Image.new("RGBA", spec.size, (0, 0, 0, 0)), wm_overlay, 0.22))

    # bottom-center brand wordmark (footer)
    foot_y = h - round(h * 0.028) - bw
    draw_tracked(overlay, draw, spec.brand, brand_font,
                 (w - total) / 2, foot_y, col, track, pin_w)

    # headline, bottom-left, above the footer
    head_bottom = foot_y - round(h * 0.03)
    head_top_limit = round(h * 0.52)
    g, lines, lh = fit_headline(
        draw, spec.headline.upper(), w - 2 * margin,
        head_bottom - head_top_limit, start=round(h * 0.052),
    )
    block_h = len(lines) * lh
    y = head_bottom - block_h
    for ln in lines:
        baseline = y + g.ascent
        g.draw_line(draw, ln, margin + 2, baseline + 2, (0, 0, 0, 130))
        g.draw_line(draw, ln, margin, baseline, col + (255,))
        y += lh

    # top-right pixel chevron
    ch_px = round(w * 0.045)
    chev = pixel_chevron_tile(ch_px, col)
    overlay.alpha_composite(chev, (w - margin - chev.width, round(h * 0.03)))

    img = Image.alpha_composite(img, overlay)
    return img.convert("RGB")


def main():
    ap = argparse.ArgumentParser(description="Generate HAYTSEGHAKRON-style news cards.")
    ap.add_argument("--image", required=True, help="Background photo")
    ap.add_argument("--headline", required=True, help="Bottom headline (auto-uppercased)")
    ap.add_argument("--brand", default="HAYTSEGHAKR*N", help="Wordmark; '*' = pinwheel")
    ap.add_argument("--size", default="1080x1350", help="WxH, default 1080x1350 (4:5)")
    ap.add_argument("--grayscale", action="store_true")
    ap.add_argument("--darken", type=float, default=0.0, help="Darken photo 0..1")
    ap.add_argument("--color", default="#ffffff")
    ap.add_argument("--no-watermark", action="store_true")
    ap.add_argument("--out", default="out/card.png")
    args = ap.parse_args()

    w, h = (int(x) for x in args.size.lower().split("x"))
    spec = CardSpec(
        image=args.image, headline=args.headline, brand=args.brand,
        size=(w, h), grayscale=args.grayscale, darken=args.darken,
        color=hex_to_rgb(args.color), watermark=not args.no_watermark,
    )
    img = generate_card(spec)
    os.makedirs(os.path.dirname(args.out) or ".", exist_ok=True)
    img.save(args.out, quality=95)
    print(f"saved {args.out}  ({w}x{h})")


if __name__ == "__main__":
    main()
