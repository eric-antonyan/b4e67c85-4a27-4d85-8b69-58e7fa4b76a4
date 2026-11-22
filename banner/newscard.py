#!/usr/bin/env python3
"""
HAYTSEGHAKRON-style Telegram news-card generator.

Full-bleed photo + dark bottom scrim + bold uppercase headline (Montserrat
Armenian) bottom-left + the real brand wordmark PNG top & bottom + faint
center watermark + the pixel chevron mark in the top-right corner.

Requires: Pillow
Bundled assets:
    fonts/Montserratarm-Black.otf, Montserratarm-ExtraBold.otf
    assets/wordmark-white.png   (the ‹HAYTSEGHAKR⊗N wordmark, white/transparent)
    assets/mark-white.png       (the pixel chevron mark, white/transparent)

Example
-------
python newscard.py --image photo.jpg \
    --headline "ԲԱՆՏՈՒՄ ՔԱՂԱՔԱԿԱՆ ՍՊԱՆՈՒԹՅՈՒՆ. ԱՐՍԵՆ ԳԵՎՈՐԳՅԱՆԻ ՄԱՀԸ." \
    --grayscale --out out/card.png
"""
from __future__ import annotations

import argparse
import os
from dataclasses import dataclass

from PIL import Image, ImageDraw, ImageFont, ImageOps

HERE = os.path.dirname(os.path.abspath(__file__))
FONT_DIR = os.path.join(HERE, "fonts")
ASSET_DIR = os.path.join(HERE, "assets")

# --- fonts -----------------------------------------------------------------

ARM = {  # Montserrat Armenian covers Armenian + Latin + digits + punctuation
    "black": "Montserratarm-Black.otf",
    "extrabold": "Montserratarm-ExtraBold.otf",
    "bold": "Montserratarm-Bold.otf",
    "semibold": "Montserratarm-SemiBold.otf",
}
_DEJAVU = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"


def headline_font(weight, size):
    p = os.path.join(FONT_DIR, ARM.get(weight, "Montserratarm-Black.otf"))
    return ImageFont.truetype(p if os.path.exists(p) else _DEJAVU, size)


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
                 top_frac=0.14, top_strength=0.40):
    """Black RGBA scrim: dark at bottom (headline) and a touch at top (wordmark)."""
    w, h = size
    mask = Image.new("L", size, 0)
    md = ImageDraw.Draw(mask)
    b_start = int(h * (1 - bottom_frac))
    for y in range(b_start, h):
        t = (y - b_start) / max(h - b_start - 1, 1)
        md.line([(0, y), (w, y)], fill=int(255 * bottom_strength * (t ** 1.4)))
    t_end = int(h * top_frac)
    for y in range(t_end):
        t = 1 - y / max(t_end - 1, 1)
        a = int(255 * top_strength * (t ** 1.3))
        if a > mask.getpixel((0, y)):
            md.line([(0, y), (w, y)], fill=a)
    scrim = Image.new("RGBA", size, (0, 0, 0, 0))
    scrim.putalpha(mask)
    return scrim


def load_asset(path, color=(255, 255, 255)):
    """Load a white/transparent PNG; tint it if color isn't white."""
    im = Image.open(path).convert("RGBA")
    if color != (255, 255, 255):
        r, g, b, a = im.split()
        tint = Image.new("RGBA", im.size, color + (0,))
        tint.putalpha(a)
        im = tint
    return im


def scaled_to_width(im, width):
    s = width / im.width
    return im.resize((round(width), round(im.height * s)), Image.LANCZOS)


def paste_alpha(base, overlay_img, xy):
    layer = Image.new("RGBA", base.size, (0, 0, 0, 0))
    layer.alpha_composite(overlay_img, (round(xy[0]), round(xy[1])))
    return Image.alpha_composite(base, layer)


# --- headline text (per-char fallback for anything Montserrat lacks) -------

_NOTDEF: dict = {}


def _covers(font, ch):
    if ch in "  ":
        return True
    key = (font.path, font.size)
    nd = _NOTDEF.get(key)
    if nd is None:
        m0 = font.getmask("")
        nd = (m0.size, bytes(m0))
        _NOTDEF[key] = nd
    m = font.getmask(ch)
    if m.size == (0, 0):
        return True
    return not (m.size == nd[0] and bytes(m) == nd[1])


class Glyphs:
    def __init__(self, size, weight="black"):
        self.size = size
        self.fonts = [headline_font(weight, size), ImageFont.truetype(_DEJAVU, size)]
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


def wrap_g(draw, text, g, max_w):
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


def fit_headline(draw, text, max_w, max_h, start, weight="black", min_size=26):
    size = start
    while size >= min_size:
        g = Glyphs(size, weight)
        lines = wrap_g(draw, text, g, max_w)
        lh = round(size * 1.14)
        if len(lines) * lh <= max_h and all(g.width(draw, ln) <= max_w for ln in lines):
            return g, lines, lh
        size -= 2
    g = Glyphs(min_size, weight)
    return g, wrap_g(draw, text, g, max_w), round(min_size * 1.14)


# --- spec & render ---------------------------------------------------------

@dataclass
class CardSpec:
    image: str
    headline: str
    size: tuple = (1080, 1350)
    grayscale: bool = False
    darken: float = 0.0
    color: tuple = (255, 255, 255)
    watermark: bool = True
    wordmark_path: str = os.path.join(ASSET_DIR, "wordmark-white.png")
    mark_path: str = os.path.join(ASSET_DIR, "mark-white.png")
    weight: str = "black"


def generate_card(spec: CardSpec) -> Image.Image:
    w, h = spec.size
    margin = round(w * 0.055)

    photo = cover_fit(Image.open(spec.image).convert("RGB"), spec.size)
    if spec.grayscale:
        photo = ImageOps.grayscale(photo).convert("RGB")
    if spec.darken > 0:
        photo = Image.blend(photo, Image.new("RGB", spec.size, (0, 0, 0)), spec.darken)

    img = photo.convert("RGBA")
    img = Image.alpha_composite(img, bottom_scrim(spec.size))

    wordmark = load_asset(spec.wordmark_path, spec.color)
    mark = load_asset(spec.mark_path, spec.color)

    # top + bottom wordmark, centered
    wm = scaled_to_width(wordmark, w * 0.34)
    top_y = round(h * 0.03)
    img = paste_alpha(img, wm, ((w - wm.width) / 2, top_y))
    foot_y = h - round(h * 0.03) - wm.height
    img = paste_alpha(img, wm, ((w - wm.width) / 2, foot_y))

    # faint center watermark
    if spec.watermark:
        big = scaled_to_width(wordmark, w * 0.46)
        faded = Image.new("RGBA", big.size, (0, 0, 0, 0))
        faded = Image.blend(faded, big, 0.14)
        img = paste_alpha(img, faded, ((w - big.width) / 2, (h - big.height) / 2))

    # top-right pixel chevron mark
    cm = scaled_to_width(mark, w * 0.055)
    img = paste_alpha(img, cm, (w - margin - cm.width, round(h * 0.032)))

    # headline, bottom-left, above the footer wordmark
    overlay = Image.new("RGBA", spec.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)
    head_bottom = foot_y - round(h * 0.028)
    head_top_limit = round(h * 0.50)
    g, lines, lh = fit_headline(
        draw, spec.headline.upper(), w - 2 * margin,
        head_bottom - head_top_limit, start=round(h * 0.055), weight=spec.weight,
    )
    y = head_bottom - len(lines) * lh
    for ln in lines:
        baseline = y + g.ascent
        g.draw_line(draw, ln, margin + 2, baseline + 2, (0, 0, 0, 120))
        g.draw_line(draw, ln, margin, baseline, spec.color + (255,))
        y += lh

    img = Image.alpha_composite(img, overlay)
    return img.convert("RGB")


def main():
    ap = argparse.ArgumentParser(description="Generate HAYTSEGHAKRON-style news cards.")
    ap.add_argument("--image", required=True, help="Background photo")
    ap.add_argument("--headline", required=True, help="Bottom headline (auto-uppercased)")
    ap.add_argument("--size", default="1080x1350", help="WxH, default 1080x1350 (4:5)")
    ap.add_argument("--grayscale", action="store_true")
    ap.add_argument("--darken", type=float, default=0.0, help="Darken photo 0..1")
    ap.add_argument("--color", default="#ffffff", help="Tint for wordmark/mark/text")
    ap.add_argument("--no-watermark", action="store_true")
    ap.add_argument("--weight", default="black", choices=list(ARM))
    ap.add_argument("--wordmark", default=os.path.join(ASSET_DIR, "wordmark-white.png"))
    ap.add_argument("--mark", default=os.path.join(ASSET_DIR, "mark-white.png"))
    ap.add_argument("--out", default="out/card.png")
    args = ap.parse_args()

    w, h = (int(x) for x in args.size.lower().split("x"))
    spec = CardSpec(
        image=args.image, headline=args.headline, size=(w, h),
        grayscale=args.grayscale, darken=args.darken, color=hex_to_rgb(args.color),
        watermark=not args.no_watermark, weight=args.weight,
        wordmark_path=args.wordmark, mark_path=args.mark,
    )
    img = generate_card(spec)
    os.makedirs(os.path.dirname(args.out) or ".", exist_ok=True)
    img.save(args.out, quality=95)
    print(f"saved {args.out}  ({w}x{h})")


if __name__ == "__main__":
    main()
