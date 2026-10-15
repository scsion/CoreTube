#!/usr/bin/env python3
"""Draw the CoreTube brand: emblem, wordmark and backgrounds.

CoreTube's emblem is CoreELEC's red open ring (redrawn at any size from the
proportions of CoreELEC's own 128 px logo) holding YouTube's play badge where
CoreELEC has its power symbol. The wordmark is set like CoreELEC's: a medium "Core"
and a light "Tube" in Gotham. Gotham isn't free, so it isn't bundled: pass
the folder that holds Gotham-Medium.otf and Gotham-Light.otf (on Windows,
C:/Windows/Fonts). The PNGs this writes are committed, so only rebranding
needs the fonts. Needs Pillow:

    python tools/gen_brand.py C:/Windows/Fonts
"""

import argparse
import math
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont

ROOT = Path(__file__).resolve().parent.parent
# Not resources/media: tools/sync_upstream.py replaces that folder.
BRAND = ROOT / 'resources' / 'brand'
SKIN_MEDIA = ROOT / 'resources' / 'skins' / 'Default' / 'media'

RED = (227, 6, 19, 255)
WHITE = (255, 255, 255, 255)
BG = (15, 15, 15)

# The two logo options users pick between in the add-on settings
# (leanback.logo): YouTube's red play badge, or a white one with a red
# triangle that stands out more against the red ring when small.
VARIANTS = {
    'a': {'badge': RED, 'play': WHITE},
    'b': {'badge': WHITE, 'play': RED},
}

# Emblem geometry in CoreELEC's 128 px logo units, centre at (64, 64).
UNIT = 128
RING_R, RING_W = 54, 16           # red ring: mid radius, stroke
RING_GAP = 150                    # ring runs -150..150 deg: open on the left
BADGE_W, BADGE_H, BADGE_R = 60, 42, 12   # play badge inside the ring
PLAY_W, PLAY_H = 17, 20                  # its triangle


def _arc(draw, cx, cy, r, w, start, end, color):
    """Arc with round caps, angles clockwise from 3 o'clock."""
    draw.arc((cx - r - w / 2, cy - r - w / 2, cx + r + w / 2, cy + r + w / 2),
             start, end, fill=color, width=int(round(w)))
    for angle in (start, end):
        a = math.radians(angle)
        x, y = cx + r * math.cos(a), cy + r * math.sin(a)
        draw.ellipse((x - w / 2, y - w / 2, x + w / 2, y + w / 2), fill=color)


def emblem(size, mono=None, badge=RED, play=WHITE):
    """The emblem on a transparent square. mono draws it in one colour, with
    the play triangle cut out of the badge."""
    ss = 4
    n = size * ss
    img = Image.new('RGBA', (n, n), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    u = n / UNIT
    c = 64 * u
    _arc(d, c, c, RING_R * u, RING_W * u, -RING_GAP, RING_GAP, mono or RED)
    d.rounded_rectangle((c - BADGE_W / 2 * u, c - BADGE_H / 2 * u,
                         c + BADGE_W / 2 * u, c + BADGE_H / 2 * u),
                        BADGE_R * u, fill=mono or badge)
    # The triangle's centroid sits on the badge centre.
    left = c - PLAY_W / 3 * u
    d.polygon([(left, c - PLAY_H / 2 * u), (left, c + PLAY_H / 2 * u),
               (left + PLAY_W * u, c)],
              fill=(0, 0, 0, 0) if mono else play)
    return img.resize((size, size), Image.LANCZOS)


def wordmark(fonts, height, color=WHITE):
    """'Core' medium + 'Tube' light, tight like CoreELEC's, on transparent."""
    ss = 4
    px = height * ss
    bold = ImageFont.truetype(str(fonts / 'Gotham-Medium.otf'), px)
    light = ImageFont.truetype(str(fonts / 'Gotham-Light.otf'), px)
    parts = (('Core', bold), ('Tube', light))
    widths = [ImageDraw.Draw(Image.new('L', (1, 1))).textlength(t, font=f)
              for t, f in parts]
    w = int(sum(widths) + px * 0.1)
    img = Image.new('RGBA', (w, int(px * 1.3)), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    x = 0
    for (text, font), width in zip(parts, widths):
        d.text((x, 0), text, font=font, fill=color)
        x += width
    img = img.crop(img.getbbox())
    return img.resize((max(1, img.width // ss), max(1, img.height // ss)),
                      Image.LANCZOS)


def lockup(fonts, height, gap=0.28, variant='a'):
    """Emblem left of the wordmark, wordmark cap height ~ 0.42 emblem."""
    mark = emblem(height, **VARIANTS[variant])
    words = wordmark(fonts, int(height * 0.48))
    w = mark.width + int(height * gap) + words.width
    img = Image.new('RGBA', (w, height), (0, 0, 0, 0))
    img.alpha_composite(mark, (0, 0))
    img.alpha_composite(words, (mark.width + int(height * gap),
                                (height - words.height) // 2))
    return img


def background(fonts, size=(1920, 1080), with_logo=True, variant='a'):
    """Neutral backdrop: near-black with a soft red glow behind a centred
    lockup, quiet enough to sit behind any menu."""
    w, h = size
    img = Image.new('RGB', size, BG)
    glow = Image.new('L', size, 0)
    d = ImageDraw.Draw(glow)
    r = int(h * 0.55)
    d.ellipse((w // 2 - r, h // 2 - r, w // 2 + r, h // 2 + r), fill=70)
    glow = glow.filter(ImageFilter.GaussianBlur(h * 0.18))
    red = Image.new('RGB', size, (120, 8, 16))
    img = Image.composite(red, img, glow)
    # A faint, oversized ring watermark bleeding off the right edge.
    ring = emblem(int(h * 1.3), mono=(255, 255, 255, 14))
    img = img.convert('RGBA')
    img.alpha_composite(ring, (int(w * 0.52), int(-h * 0.15)))
    if with_logo:
        logo = lockup(fonts, int(h * 0.16), variant=variant)
        img.alpha_composite(logo, ((w - logo.width) // 2,
                                   (h - logo.height) // 2))
    return img.convert('RGB')


def main():
    parser = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    parser.add_argument('fonts', type=Path,
                        help='folder with Gotham-Medium.otf and Gotham-Light.otf')
    args = parser.parse_args()

    # Per option: the window header's lockup, and the icon and backdrop that
    # leanback/brand.py copies to resources/brand/ when the option changes
    # (the add-on icon and the Bald hub point there). Option A ships active.
    outputs = {}
    for name in VARIANTS:
        outputs[SKIN_MEDIA / 'brand_lockup_{}.png'.format(name)] = lockup(
            args.fonts, 64, variant=name)
        outputs[BRAND / name / 'icon.png'] = _icon(name)
        outputs[BRAND / name / 'fanart.jpg'] = background(args.fonts,
                                                          variant=name)
    outputs[BRAND / 'icon.png'] = _icon('a')
    outputs[BRAND / 'fanart.jpg'] = background(args.fonts, variant='a')
    for path, img in outputs.items():
        path.parent.mkdir(parents=True, exist_ok=True)
        if path.suffix == '.jpg':
            img.save(path, quality=90, optimize=True)
        else:
            img.save(path, optimize=True)
        print('Wrote', path.relative_to(ROOT))


def _icon(variant):
    """Add-on icon: the emblem on Kodi's dark tile."""
    img = Image.new('RGBA', (256, 256), BG + (255,))
    img.alpha_composite(emblem(196, **VARIANTS[variant]), (30, 30))
    return img


if __name__ == '__main__':
    main()
