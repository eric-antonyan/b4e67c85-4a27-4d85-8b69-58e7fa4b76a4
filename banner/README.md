# HAYTSEGHAKRON post generator

Python tools that turn a photo + text into HAYTSEGHAKRON-style Telegram/Instagram
cards (4:5). There are three scripts:

| Script | Makes | Use |
|--------|-------|-----|
| `post.py` | **both** carousel pages at once | the main entry point |
| `newscard.py` | **page 1** – photo + headline | a single image card |
| `textpage.py` | **page 2** – heading + body article | a single text card |

Plus `banner.py`, a general-purpose gradient banner generator (unrelated to the
channel template).

---

## Setup

Only [Pillow](https://pypi.org/project/Pillow/) is required (NumPy is used for the
overlay blend if you enable it):

```bash
pip install Pillow numpy
```

Fonts and brand assets are bundled, so nothing else to install:

```
fonts/     Montserrat Armenian (Black/ExtraBold/Bold/SemiBold/Medium/Regular)
assets/    wordmark-white.png  (the ‹HAYTSEGHAKR⊗N wordmark)
           mark-white.png      (the pixel chevron corner mark)
```

Run every command from inside the `banner/` folder.

---

## Quick start — a full post

```bash
python post.py \
  --image photo.jpg \
  --heading "ՆՈՅԵՄԲԵՐԻ 16. ՌՈԲԵՐՏ ԱԲԱՋՅԱՆ՝ ..." \
  --body-file article.txt \
  --out-dir out/post
# → out/post/p1.png   (photo + headline)
# → out/post/p2.png   (heading + article text)
```

Both pages share the same `--image` and `--heading`. Page 1 is color with solid
white marks; page 2 is darkened so the text reads.

### `article.txt` format

Paragraphs are separated by a **blank line**. Prefix a paragraph with `> ` to make
it the **bold uppercase closing line**:

```
First paragraph of the article…

Second paragraph…

> Հերոսները չեն մեռնում. նրանց կամքն ու չենքը փոխանցվում են…
```

### `post.py` options

| Flag | Default | Notes |
|------|---------|-------|
| `--image` | — | background photo (required) |
| `--heading` | — | title, used on both pages (required) |
| `--body` / `--body-file` | — | page 2 text (one required) |
| `--out-dir` | `out/post` | output folder |
| `--size` | `1440x1800` | `WxH`, 4:5 |
| `--color` | `#ffffff` | brand + text tint |
| `--p1-darken` | `0.22` | page 1 photo darkening `0..1` |
| `--p1-grayscale` | off | page 1 grayscale |
| `--p1-overlay` | off | blend page-1 top mark into the photo |
| `--no-p1-watermark` | off | drop the faint center watermark |
| `--p2-darken` | `0.72` | page 2 photo darkening `0..1` |
| `--p2-grayscale` | off | page 2 grayscale |
| `--p2-justify` | off | justify the page-2 body |

---

## Page 1 only — `newscard.py`

```bash
python newscard.py --image photo.jpg \
  --headline "ՎԵՐՆԱԳԻՐ ԱՅՍՏԵՂ." \
  --grayscale --out out/card.png
```

| Flag | Default | Notes |
|------|---------|-------|
| `--image`, `--headline` | — | required |
| `--size` | `1440x1800` | `WxH` |
| `--grayscale` | off | mono photo |
| `--darken` | `0.0` | darken the whole photo `0..1` |
| `--headline-size` | auto | fixed px; auto = `width × 0.037` |
| `--weight` | `black` | headline weight |
| `--justify` | off | full-width headline |
| `--overlay` | off | blend top wordmark + corner into the photo (bottom stays solid) |
| `--color` | `#ffffff` | brand + text tint |
| `--no-watermark` | off | drop the center watermark |
| `--wordmark`, `--mark` | bundled | override the brand PNGs |

The headline is a **fixed size** and wraps to as many lines as needed (it only
shrinks as an overflow safety), so short and long headlines look consistent.

---

## Page 2 only — `textpage.py`

```bash
python textpage.py --image photo.jpg \
  --heading "ՎԵՐՆԱԳԻՐ ԱՅՍՏԵՂ." \
  --body-file article.txt \
  --out out/page2.png
```

| Flag | Default | Notes |
|------|---------|-------|
| `--image`, `--heading` | — | required |
| `--body` / `--body-file` | — | one required (see format above) |
| `--size` | `1440x1800` | `WxH` |
| `--darken` | `0.74` | photo darkening `0..1` |
| `--no-grayscale` | grayscale on | keep the photo in color |
| `--justify` | off | justify the body |
| `--overlay` | off | blend wordmark/mark into the photo |
| `--color` | `#ffffff` | brand + text tint |

Body is **Bold**, the `> ` emphasis line is **Black**, both auto-shrink to fit
above the bottom wordmark.

---

## Tips

- **Source resolution matters most.** Output is 1440×1800 (use `--size 2160x2700`
  for 2×). A tall 4:5 card is cropped from the photo and upscaled if the source is
  small, so for the sharpest result start from a **high-resolution photo**
  (≥ 2000 px tall). A light sharpen is applied automatically on upscales.
- **Overlay vs solid.** `--overlay` looks good over dark/busy photos but washes out
  over bright skies — leave it off (solid white) for guaranteed legibility.
- **Darkening.** Bump `--p1-darken` / `--darken` if a bright photo makes the
  headline hard to read.
```
