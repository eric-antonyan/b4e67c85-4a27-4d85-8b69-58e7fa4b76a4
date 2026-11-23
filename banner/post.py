#!/usr/bin/env python3
"""
Build a full HAYTSEGHAKRON carousel post (page 1 + page 2) in one command.

Page 1 -> newscard  (photo + headline)       -> <out-dir>/p1.png
Page 2 -> textpage  (heading + body text)    -> <out-dir>/p2.png

Both pages share the same --image and --heading.

Example
-------
python post.py --image photo.jpg \
    --heading "ՆՈՅԵՄԲԵՐԻ 16. ՌՈԲԵՐՏ ԱԲԱՋՅԱՆ՝ ..." \
    --body-file article.txt \
    --out-dir out/post

Defaults match the channel look: page 1 is color with solid white marks;
page 2 is color but heavily darkened so the text reads. Flags below tune each.
"""
from __future__ import annotations

import argparse
import os

from newscard import CardSpec, generate_card, hex_to_rgb
from textpage import TextPageSpec, generate_textpage, parse_body


def main():
    ap = argparse.ArgumentParser(description="Generate a 2-page news post (p1 + p2).")
    ap.add_argument("--image", required=True, help="Background photo (shared by both pages)")
    ap.add_argument("--heading", required=True, help="Title (page 1 headline + page 2 heading)")
    src = ap.add_mutually_exclusive_group(required=True)
    src.add_argument("--body", help="Page 2 body; paragraphs split on blank lines")
    src.add_argument("--body-file", help="File with the page 2 body text")

    ap.add_argument("--out-dir", default="out/post", help="Output folder (default out/post)")
    ap.add_argument("--size", default="1080x1350", help="WxH, default 1080x1350 (4:5)")
    ap.add_argument("--color", default="#ffffff", help="Brand/text tint")

    # page 1
    ap.add_argument("--p1-darken", type=float, default=0.22, help="Page 1 photo darken 0..1")
    ap.add_argument("--p1-grayscale", action="store_true", help="Make page 1 grayscale")
    ap.add_argument("--p1-overlay", action="store_true",
                    help="Blend top wordmark/mark into the photo on page 1")
    ap.add_argument("--no-p1-watermark", action="store_true")

    # page 2
    ap.add_argument("--p2-darken", type=float, default=0.72, help="Page 2 photo darken 0..1")
    ap.add_argument("--p2-grayscale", action="store_true", help="Make page 2 grayscale")
    ap.add_argument("--p2-justify", action="store_true", help="Justify page 2 body")

    args = ap.parse_args()

    w, h = (int(x) for x in args.size.lower().split("x"))
    color = hex_to_rgb(args.color)
    os.makedirs(args.out_dir, exist_ok=True)

    body = args.body
    if args.body_file:
        with open(args.body_file, encoding="utf-8") as f:
            body = f.read()

    # ---- page 1 -----------------------------------------------------------
    p1 = generate_card(CardSpec(
        image=args.image, headline=args.heading, size=(w, h),
        grayscale=args.p1_grayscale, darken=args.p1_darken, color=color,
        watermark=not args.no_p1_watermark, overlay_assets=args.p1_overlay,
    ))
    p1_path = os.path.join(args.out_dir, "p1.png")
    p1.save(p1_path, quality=95)

    # ---- page 2 -----------------------------------------------------------
    p2 = generate_textpage(TextPageSpec(
        image=args.image, heading=args.heading, paragraphs=parse_body(body),
        size=(w, h), grayscale=args.p2_grayscale, darken=args.p2_darken,
        color=color, justify=args.p2_justify,
    ))
    p2_path = os.path.join(args.out_dir, "p2.png")
    p2.save(p2_path, quality=95)

    print(f"saved {p1_path}")
    print(f"saved {p2_path}")


if __name__ == "__main__":
    main()
