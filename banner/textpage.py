#!/usr/bin/env python3
"""
HAYTSEGHAKRON-style text page (carousel "page 2").

Same brand frame as newscard.py (wordmark top & bottom, corner chevron) over
a heavily darkened photo, with a bold uppercase heading and flowing body
paragraphs. A paragraph prefixed with "> " is rendered as a bold uppercase
emphasis block (the closing line in the reference).

Requires: Pillow  +  the assets/fonts bundled next to newscard.py

Example
-------
python textpage.py --image photo.jpg \
    --heading "ՆՈՅԵՄԲԵՐԻ 16. ՌՈԲԵՐՏ ԱԲԱՋՅԱՆ՝ ..." \
    --body-file article.txt --out out/page2.png

article.txt: paragraphs separated by blank lines; prefix a paragraph with
"> " to make it the bold uppercase emphasis block.
"""
from __future__ import annotations

import argparse
import os
from dataclasses import dataclass

from PIL import Image, ImageDraw, ImageOps

from newscard import (
    ASSET_DIR, Glyphs, cover_fit, hex_to_rgb, load_asset, paste_alpha,
    scaled_to_width, wrap_g,
)


def para_height(draw, paras, col_w, body_size, head_lh_ratio=1.45, gap_ratio=0.62):
    """Total height of the body block for a given body size (for auto-fit)."""
    total = 0
    for i, (style, _) in enumerate(paras):
        g = _para_glyphs(style, body_size)
        lh = round(body_size * head_lh_ratio)
        lines = wrap_g(draw, paras[i][1], g, col_w)
        total += len(lines) * lh
        if i < len(paras) - 1:
            total += round(lh * gap_ratio)
    return total


def _para_glyphs(style, size):
    return Glyphs(size, "bold" if style == "emphasis" else "medium")


@dataclass
class TextPageSpec:
    image: str
    heading: str
    paragraphs: list          # list of (style, text); style in {"body","emphasis"}
    size: tuple = (1080, 1350)
    grayscale: bool = True
    darken: float = 0.70
    color: tuple = (255, 255, 255)
    body_color: tuple = (232, 232, 234)
    justify: bool = True
    wordmark_path: str = os.path.join(ASSET_DIR, "wordmark-white.png")
    mark_path: str = os.path.join(ASSET_DIR, "mark-white.png")


def _draw_para(draw, g, text, x, top, col_w, lh, fill, justify):
    lines = wrap_g(draw, text, g, col_w)
    y = top
    for i, ln in enumerate(lines):
        baseline = y + g.ascent
        extra = 0.0
        spaces = ln.count(" ")
        if justify and i < len(lines) - 1 and spaces:
            natural = g.width(draw, ln)
            if natural >= col_w * 0.5:
                extra = (col_w - natural) / spaces
        g.draw_line(draw, ln, x, baseline, fill, extra)
        y += lh
    return y


def generate_textpage(spec: TextPageSpec) -> Image.Image:
    w, h = spec.size
    margin = round(w * 0.055)
    col_w = w - 2 * margin

    # background: heavily darkened (grayscale) photo
    photo = cover_fit(Image.open(spec.image).convert("RGB"), spec.size)
    if spec.grayscale:
        photo = ImageOps.grayscale(photo).convert("RGB")
    photo = Image.blend(photo, Image.new("RGB", spec.size, (0, 0, 0)), spec.darken)
    img = photo.convert("RGBA")

    # brand frame (same as the card)
    wordmark = load_asset(spec.wordmark_path, spec.color)
    mark = load_asset(spec.mark_path, spec.color)
    wm = scaled_to_width(wordmark, w * 0.22)
    gap = round(h * 0.02)
    img = paste_alpha(img, wm, ((w - wm.width) / 2, gap))
    bot_wm_top = h - gap - wm.height
    img = paste_alpha(img, wm, ((w - wm.width) / 2, bot_wm_top))
    cm = scaled_to_width(mark, w * 0.055)
    img = paste_alpha(img, cm, (round(w * 0.969) - cm.width, round(h * 0.03)))

    overlay = Image.new("RGBA", spec.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)

    # heading, left-aligned, fixed size
    head_size = round(w * 0.037)
    hg = Glyphs(head_size, "black")
    head_lh = round(head_size * 1.14)
    y = round(h * 0.085)
    for ln in wrap_g(draw, spec.heading.upper(), hg, col_w):
        base = y + hg.ascent
        hg.draw_line(draw, ln, margin, base, spec.color + (255,))
        y += head_lh
    body_top = y + round(h * 0.028)

    # auto-fit body size so the whole block fits above the bottom wordmark
    avail = (bot_wm_top - round(h * 0.03)) - body_top
    body_size = round(w * 0.0228)
    while body_size >= 14:
        if para_height(draw, spec.paragraphs, col_w, body_size) <= avail:
            break
        body_size -= 1

    # render paragraphs
    y = body_top
    for i, (style, text) in enumerate(spec.paragraphs):
        g = _para_glyphs(style, body_size)
        lh = round(body_size * 1.45)
        if style == "emphasis":
            fill = spec.color + (255,)
            text = text.upper()
        else:
            fill = spec.body_color + (255,)
        y = _draw_para(draw, g, text, margin, y, col_w, lh, fill, spec.justify)
        if i < len(spec.paragraphs) - 1:
            y += round(lh * 0.62)

    return Image.alpha_composite(img, overlay).convert("RGB")


def parse_body(text):
    """Split into (style, text) paragraphs; '> ' prefix marks emphasis."""
    paras = []
    for block in text.replace("\r\n", "\n").split("\n\n"):
        block = " ".join(block.split())
        if not block:
            continue
        if block.startswith("> "):
            paras.append(("emphasis", block[2:].strip()))
        else:
            paras.append(("body", block))
    return paras


def main():
    ap = argparse.ArgumentParser(description="Generate HAYTSEGHAKRON-style text pages.")
    ap.add_argument("--image", required=True)
    ap.add_argument("--heading", required=True)
    src = ap.add_mutually_exclusive_group(required=True)
    src.add_argument("--body", help="Body text; paragraphs split on blank lines")
    src.add_argument("--body-file", help="File with the body text")
    ap.add_argument("--size", default="1080x1350")
    ap.add_argument("--darken", type=float, default=0.70)
    ap.add_argument("--no-grayscale", action="store_true")
    ap.add_argument("--no-justify", action="store_true")
    ap.add_argument("--color", default="#ffffff")
    ap.add_argument("--out", default="out/textpage.png")
    args = ap.parse_args()

    body = args.body
    if args.body_file:
        with open(args.body_file, encoding="utf-8") as f:
            body = f.read()

    w, h = (int(x) for x in args.size.lower().split("x"))
    spec = TextPageSpec(
        image=args.image, heading=args.heading, paragraphs=parse_body(body),
        size=(w, h), grayscale=not args.no_grayscale, darken=args.darken,
        color=hex_to_rgb(args.color), justify=not args.no_justify,
    )
    img = generate_textpage(spec)
    os.makedirs(os.path.dirname(args.out) or ".", exist_ok=True)
    img.save(args.out, quality=95)
    print(f"saved {args.out}  ({w}x{h})")


if __name__ == "__main__":
    main()
