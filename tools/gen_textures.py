#!/usr/bin/env python3
"""Draw the window's shape textures (rounded corners, focus ring, badges).

Kodi skins can't draw rounded rectangles, so these are small white PNGs
that the window XML tints with colordiffuse and stretches with 9-slice
borders. Needs Pillow; re-run after changing a size here:

    python tools/gen_textures.py
"""

from pathlib import Path

from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / 'resources' / 'skins' / 'Default' / 'media'
# Draw large and downsample, so the curves are anti-aliased.
SS = 4


def rounded(size, radius, stroke=0, fill=True):
    w, h = size
    img = Image.new('RGBA', (w * SS, h * SS), (255, 255, 255, 0))
    draw = ImageDraw.Draw(img)
    box = (0, 0, w * SS - 1, h * SS - 1)
    if fill:
        draw.rounded_rectangle(box, radius * SS, fill=(255, 255, 255, 255))
    else:
        draw.rounded_rectangle(box, radius * SS, outline=(255, 255, 255, 255),
                               width=stroke * SS)
    return img.resize(size, Image.LANCZOS)


ICON = 96          # icon canvas; shown at 32 px, so strokes stay crisp
STROKE = 7
WHITE = (255, 255, 255, 255)


def icon(draw_glyph):
    """A white line icon on a transparent ICON x ICON canvas."""
    def make():
        n = ICON * SS
        img = Image.new('RGBA', (n, n), (255, 255, 255, 0))
        draw_glyph(ImageDraw.Draw(img), n / ICON, STROKE * SS)
        return img.resize((ICON, ICON), Image.LANCZOS)
    return make


def g_search(d, u, w):
    d.ellipse((16 * u, 14 * u, 62 * u, 60 * u), outline=WHITE, width=w)
    d.line((55 * u, 53 * u, 80 * u, 78 * u), fill=WHITE, width=int(w * 1.3))


def g_home(d, u, w):
    d.line((14 * u, 46 * u, 48 * u, 16 * u, 82 * u, 46 * u), fill=WHITE,
           width=w, joint='curve')
    d.line((24 * u, 40 * u, 24 * u, 80 * u, 72 * u, 80 * u, 72 * u, 40 * u),
           fill=WHITE, width=w, joint='curve')
    d.rectangle((41 * u, 56 * u, 55 * u, 80 * u), outline=WHITE, width=w)


def g_subscriptions(d, u, w):
    d.line((26 * u, 14 * u, 70 * u, 14 * u), fill=WHITE, width=w)
    d.line((20 * u, 26 * u, 76 * u, 26 * u), fill=WHITE, width=w)
    d.rounded_rectangle((12 * u, 38 * u, 84 * u, 82 * u), 8 * u,
                        outline=WHITE, width=w)
    d.polygon([(42 * u, 49 * u), (42 * u, 71 * u), (60 * u, 60 * u)],
              fill=WHITE)


def g_library(d, u, w):
    for y in (22, 40, 58):
        d.line((14 * u, y * u, 56 * u, y * u), fill=WHITE, width=w)
    d.line((14 * u, 76 * u, 40 * u, 76 * u), fill=WHITE, width=w)
    d.polygon([(58 * u, 50 * u), (58 * u, 82 * u), (84 * u, 66 * u)],
              fill=WHITE)


def g_account(d, u, w):
    d.ellipse((32 * u, 14 * u, 64 * u, 46 * u), outline=WHITE, width=w)
    d.arc((16 * u, 54 * u, 80 * u, 112 * u), 180, 360, fill=WHITE, width=w)


def g_settings(d, u, w):
    import math
    cx = cy = 48 * u
    points = []
    # Eight flat teeth: two outer points, then two inner ones.
    for i in range(32):
        angle = math.pi * 2 * (i - 0.5) / 32
        radius = (39 if i % 4 in (0, 1) else 30) * u
        points.append((cx + radius * math.cos(angle),
                       cy + radius * math.sin(angle)))
    d.polygon(points, outline=WHITE, width=w)
    d.ellipse((cx - 11 * u, cy - 11 * u, cx + 11 * u, cy + 11 * u),
              outline=WHITE, width=w)


def g_mic(d, u, w):
    d.rounded_rectangle((36 * u, 10 * u, 60 * u, 56 * u), 12 * u, fill=WHITE)
    d.arc((24 * u, 28 * u, 72 * u, 70 * u), 0, 180, fill=WHITE, width=w)
    d.line((48 * u, 70 * u, 48 * u, 84 * u), fill=WHITE, width=w)


def g_backspace(d, u, w):
    d.line((34 * u, 22 * u, 84 * u, 22 * u, 84 * u, 74 * u, 34 * u, 74 * u,
            10 * u, 48 * u, 34 * u, 22 * u), fill=WHITE, width=w,
           joint='curve')
    d.line((46 * u, 36 * u, 68 * u, 60 * u), fill=WHITE, width=w)
    d.line((68 * u, 36 * u, 46 * u, 60 * u), fill=WHITE, width=w)


def g_history(d, u, w):
    d.arc((14 * u, 14 * u, 82 * u, 82 * u), 200, 520, fill=WHITE, width=w)
    d.polygon([(8 * u, 30 * u), (30 * u, 30 * u), (14 * u, 50 * u)],
              fill=WHITE)
    d.line((48 * u, 30 * u, 48 * u, 50 * u, 62 * u, 60 * u), fill=WHITE,
           width=w, joint='curve')


def glow():
    """Soft horizontal glow under a focused tab's underline."""
    from PIL import ImageFilter
    w, h = 128, 32
    img = Image.new('L', (w, h), 0)
    ImageDraw.Draw(img).rounded_rectangle((16, 13, w - 17, 18), 3, fill=255)
    img = img.filter(ImageFilter.GaussianBlur(5))
    white = Image.new('RGBA', (w, h), (255, 255, 255, 0))
    white.putalpha(img)
    return white


TEXTURES = {
    'glow.png': glow,
    'icon_backspace.png': icon(g_backspace),
    'icon_history.png': icon(g_history),
    'icon_search.png': icon(g_search),
    'icon_home.png': icon(g_home),
    'icon_subscriptions.png': icon(g_subscriptions),
    'icon_library.png': icon(g_library),
    'icon_account.png': icon(g_account),
    'icon_settings.png': icon(g_settings),
    'icon_mic.png': icon(g_mic),
    # Thumbnail corner masks (used as <texture diffuse=...>), one per tile size
    # so the radius doesn't stretch.
    'mask_tile.png': lambda: rounded((528, 297), 12),
    'mask_tile_large.png': lambda: rounded((720, 405), 14),
    'mask_tile_grid.png': lambda: rounded((405, 228), 10),
    # 9-slice shapes: tinted and stretched in the XML.
    'focus_ring.png': lambda: rounded((64, 64), 20, stroke=6, fill=False),
    'round8.png': lambda: rounded((32, 32), 8),
    'round12.png': lambda: rounded((48, 48), 12),
    # Pills: one per height, sliced at exactly half the height in the XML,
    # or the 9-slice cuts the curve and the ends come out pointy.
    'pill50.png': lambda: rounded((50, 50), 25),
    'pill58.png': lambda: rounded((58, 58), 29),
    'pill64.png': lambda: rounded((64, 64), 32),
    'pill70.png': lambda: rounded((70, 70), 35),
    'circle.png': lambda: rounded((96, 96), 48),
}


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    for name, make in TEXTURES.items():
        make().save(OUT / name, optimize=True)
        print('Wrote', (OUT / name).relative_to(ROOT))


if __name__ == '__main__':
    main()
