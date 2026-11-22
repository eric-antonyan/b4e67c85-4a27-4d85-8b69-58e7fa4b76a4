#!/usr/bin/env python3
"""
Telegram banner / poster generator.

Generates clean promo images for Telegram channels and posts: gradient or
solid or image backgrounds, auto-fitted title + subtitle, an optional tag
pill and footer handle.

Requires: Pillow  (pip install Pillow)

Examples
--------
# Simple gradient banner for a post (1280x720)
python banner.py --title "Новый дроп" --subtitle "Забирай пока дают" \
    --tag "NEWS" --handle "@mychannel" --out out/drop.png

# Square post with a custom color scheme
python banner.py --preset square --title "Запуск 2.0" \
    --bg "#0f2027,#2c5364" --accent "#38bdf8" --out out/launch.png

# Use a photo as the background (auto-darkened for readable text)
python banner.py --preset story --bg-image photo.jpg \
    --title "Прямой эфир" --subtitle "Сегодня в 20:00" --out out/live.png

Call generate_banner(...) directly to use it as a library.
"""
from __future__ import annotations

import argparse
import os
from dataclasses import dataclass, field

from PIL import Image, ImageDraw, ImageFont, ImageFilter

# --- fonts -----------------------------------------------------------------

FONT_DIR = "/usr/share/fonts/opentype/inter"
FONT_WEIGHTS = {
    "thin": "Inter-Thin.otf",
    "light": "Inter-Light.otf",
    "regular": "Inter-Regular.otf",
    "medium": "Inter-Medium.otf",
    "semibold": "Inter-SemiBold.otf",
    "bold": "Inter-Bold.otf",
    "extrabold": "Inter-ExtraBold.otf",
    "black": "Inter-Black.otf",
}
# Fallback chain if Inter isn't installed on the host.
_FALLBACKS = [
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
]

# --- presets (width, height) ----------------------------------------------

PRESETS = {
    "post": (1280, 720),     # 16:9 link-preview / post image
    "wide": (1200, 600),     # 2:1 channel-style banner
    "square": (1080, 1080),  # square feed post
    "story": (1080, 1920),   # 9:16 story / vertical
    "small": (800, 450),     # lightweight 16:9
}


def _font_path(weight: str) -> str:
    p = os.path.join(FONT_DIR, FONT_WEIGHTS.get(weight, "Inter-Bold.otf"))
    if os.path.exists(p):
        return p
    for f in _FALLBACKS:
        if os.path.exists(f):
            return f
    raise FileNotFoundError("No usable font found (Inter or DejaVu).")


def load_font(weight: str, size: int) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(_font_path(weight), size)


# --- color helpers ---------------------------------------------------------

def hex_to_rgb(value: str) -> tuple[int, int, int]:
    value = value.strip().lstrip("#")
    if len(value) == 3:
        value = "".join(c * 2 for c in value)
    if len(value) != 6:
        raise ValueError(f"Bad hex color: {value!r}")
    return tuple(int(value[i:i + 2], 16) for i in (0, 2, 4))  # type: ignore


def lerp(a: int, b: int, t: float) -> int:
    return round(a + (b - a) * t)


def gradient(size: tuple[int, int], c1, c2, angle: str = "diag") -> Image.Image:
    """Two-stop linear gradient. angle in {'vert','horiz','diag'}."""
    w, h = size
    base = Image.new("RGB", size, c1)
    draw = ImageDraw.Draw(base)
    if angle == "horiz":
        for x in range(w):
            t = x / max(w - 1, 1)
            draw.line([(x, 0), (x, h)], fill=tuple(lerp(c1[i], c2[i], t) for i in range(3)))
    elif angle == "diag":
        steps = w + h
        for s in range(steps):
            t = s / max(steps - 1, 1)
            draw.line([(s, 0), (0, s)], fill=tuple(lerp(c1[i], c2[i], t) for i in range(3)))
    else:  # vert
        for y in range(h):
            t = y / max(h - 1, 1)
            draw.line([(0, y), (w, y)], fill=tuple(lerp(c1[i], c2[i], t) for i in range(3)))
    return base


def cover_fit(img: Image.Image, size: tuple[int, int]) -> Image.Image:
    """Resize + center-crop an image to exactly fill `size` (CSS object-fit: cover)."""
    tw, th = size
    iw, ih = img.size
    scale = max(tw / iw, th / ih)
    nw, nh = round(iw * scale), round(ih * scale)
    img = img.resize((nw, nh), Image.LANCZOS)
    left, top = (nw - tw) // 2, (nh - th) // 2
    return img.crop((left, top, left + tw, top + th))


# --- text layout -----------------------------------------------------------

def wrap_text(draw, text, font, max_width) -> list[str]:
    lines, cur = [], ""
    for word in text.split():
        trial = f"{cur} {word}".strip()
        if draw.textlength(trial, font=font) <= max_width or not cur:
            cur = trial
        else:
            lines.append(cur)
            cur = word
    if cur:
        lines.append(cur)
    return lines


def fit_block(draw, text, weight, max_width, max_height, start_size, min_size=18):
    """Largest font size at which wrapped `text` fits the box in BOTH axes."""
    size = start_size
    while size >= min_size:
        font = load_font(weight, size)
        lines = wrap_text(draw, text, font, max_width)
        line_h = round(size * 1.18)
        fits_h = len(lines) * line_h <= max_height
        # a long single word can still exceed max_width after wrapping
        fits_w = all(draw.textlength(ln, font=font) <= max_width for ln in lines)
        if fits_h and fits_w:
            return font, lines, line_h
        size -= 2
    font = load_font(weight, min_size)
    return font, wrap_text(draw, text, font, max_width), round(min_size * 1.18)


def draw_lines(draw, lines, font, line_h, x, y, fill, shadow=True):
    for ln in lines:
        if shadow:
            draw.text((x + 2, y + 3), ln, font=font, fill=(0, 0, 0, 160))
        draw.text((x, y), ln, font=font, fill=fill)
        y += line_h
    return y


def rounded_pill(draw, xy, radius, fill):
    draw.rounded_rectangle(xy, radius=radius, fill=fill)


# --- main --------------------------------------------------------------------

@dataclass
class BannerSpec:
    title: str
    subtitle: str = ""
    tag: str = ""
    handle: str = ""
    size: tuple[int, int] = PRESETS["post"]
    bg: tuple = field(default_factory=lambda: (hex_to_rgb("#0f2027"), hex_to_rgb("#2c5364")))
    bg_angle: str = "diag"
    bg_image: str | None = None
    accent: tuple = field(default_factory=lambda: hex_to_rgb("#38bdf8"))
    text_color: tuple = (255, 255, 255)
    overlay: float = 0.45  # darkening applied over bg images (0..1)


def generate_banner(spec: BannerSpec) -> Image.Image:
    w, h = spec.size
    margin = round(min(w, h) * 0.075)

    # 1. background
    if spec.bg_image:
        bg = cover_fit(Image.open(spec.bg_image).convert("RGB"), spec.size)
        if spec.overlay > 0:
            shade = Image.new("RGB", spec.size, (0, 0, 0))
            bg = Image.blend(bg, shade, spec.overlay)
    else:
        bg = gradient(spec.size, spec.bg[0], spec.bg[1], spec.bg_angle)

    img = bg.convert("RGBA")
    overlay_layer = Image.new("RGBA", spec.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay_layer)

    content_w = w - 2 * margin
    y = margin

    # 2. tag pill (top-left)
    if spec.tag:
        tag_font = load_font("bold", round(min(w, h) * 0.028))
        tw = draw.textlength(spec.tag.upper(), font=tag_font)
        pad_x, pad_y = round(tag_font.size * 0.7), round(tag_font.size * 0.42)
        pill_h = tag_font.size + 2 * pad_y
        rounded_pill(draw, (margin, y, margin + tw + 2 * pad_x, y + pill_h),
                     radius=pill_h // 2, fill=spec.accent + (255,))
        # contrast text color on the pill
        lum = 0.299 * spec.accent[0] + 0.587 * spec.accent[1] + 0.114 * spec.accent[2]
        tag_fg = (0, 0, 0) if lum > 150 else (255, 255, 255)
        draw.text((margin + pad_x, y + pad_y), spec.tag.upper(), font=tag_font, fill=tag_fg)
        y += pill_h + round(margin * 0.5)

    # 3. reserve footer space for the handle
    footer_h = round(min(w, h) * 0.05) if spec.handle else 0
    block_bottom = h - margin - footer_h

    # 4. title (auto-fit, takes up to ~60% of remaining height)
    avail_h = block_bottom - y
    title_font, title_lines, title_lh = fit_block(
        draw, spec.title, "black", content_w,
        round(avail_h * (0.6 if spec.subtitle else 0.85)),
        start_size=round(h * 0.16),
    )
    title_total = len(title_lines) * title_lh

    # 5. subtitle
    sub_lines, sub_font, sub_lh = [], None, 0
    if spec.subtitle:
        sub_font, sub_lines, sub_lh = fit_block(
            draw, spec.subtitle, "medium", content_w,
            round(avail_h * 0.3), start_size=round(h * 0.055),
        )
    sub_total = len(sub_lines) * sub_lh

    gap = round(margin * 0.5) if sub_lines else 0
    block_total = title_total + gap + sub_total
    # vertically center the text block in the available area
    ty = y + max(0, (avail_h - block_total) // 2)

    # accent bar to the left of the title
    bar_w = round(w * 0.008)
    draw.rounded_rectangle(
        (margin, ty + round(title_lh * 0.12), margin + bar_w, ty + title_total - round(title_lh * 0.12)),
        radius=bar_w, fill=spec.accent + (255,),
    )
    text_x = margin + bar_w + round(margin * 0.5)

    ny = draw_lines(draw, title_lines, title_font, title_lh, text_x, ty, spec.text_color + (255,))
    if sub_lines:
        ny += gap
        draw_lines(draw, sub_lines, sub_font, sub_lh, text_x, ny,
                   (230, 230, 235, 235), shadow=True)

    # 6. footer handle (bottom-left)
    if spec.handle:
        hf = load_font("semibold", footer_h)
        draw.text((margin, h - margin - footer_h), spec.handle,
                  font=hf, fill=spec.accent + (255,))

    # soften shadows a touch
    img = Image.alpha_composite(img, overlay_layer)
    return img.convert("RGB")


def _parse_bg(s: str):
    parts = [p for p in s.split(",") if p.strip()]
    if len(parts) == 1:
        c = hex_to_rgb(parts[0])
        return (c, c)
    return (hex_to_rgb(parts[0]), hex_to_rgb(parts[1]))


def main():
    ap = argparse.ArgumentParser(description="Generate Telegram banners/posters.")
    ap.add_argument("--title", required=True)
    ap.add_argument("--subtitle", default="")
    ap.add_argument("--tag", default="", help="Small uppercase pill label, e.g. NEWS")
    ap.add_argument("--handle", default="", help="Footer text, e.g. @mychannel")
    ap.add_argument("--preset", choices=PRESETS, default="post")
    ap.add_argument("--size", help="Custom WxH, e.g. 1280x720 (overrides preset)")
    ap.add_argument("--bg", default="#0f2027,#2c5364",
                    help="Solid '#hex' or 2-stop gradient '#a,#b'")
    ap.add_argument("--bg-angle", choices=["vert", "horiz", "diag"], default="diag")
    ap.add_argument("--bg-image", help="Background photo (auto cover-fit + darkened)")
    ap.add_argument("--overlay", type=float, default=0.45, help="Darken bg image 0..1")
    ap.add_argument("--accent", default="#38bdf8")
    ap.add_argument("--text", default="#ffffff")
    ap.add_argument("--out", default="out/banner.png")
    args = ap.parse_args()

    size = PRESETS[args.preset]
    if args.size:
        w, h = args.size.lower().split("x")
        size = (int(w), int(h))

    spec = BannerSpec(
        title=args.title, subtitle=args.subtitle, tag=args.tag, handle=args.handle,
        size=size, bg=_parse_bg(args.bg), bg_angle=args.bg_angle,
        bg_image=args.bg_image, overlay=args.overlay,
        accent=hex_to_rgb(args.accent), text_color=hex_to_rgb(args.text),
    )
    img = generate_banner(spec)
    os.makedirs(os.path.dirname(args.out) or ".", exist_ok=True)
    img.save(args.out, quality=95)
    print(f"saved {args.out}  ({size[0]}x{size[1]})")


if __name__ == "__main__":
    main()
