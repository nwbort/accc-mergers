"""Draw the site's icons: favicons, app icons and the Apple touch icon.

The mark is the Android app's launcher icon (nwbort/accc-mergers-app,
``app/src/main/res/drawable/ic_launcher_foreground.xml``): two parties joining
into one, white on the site's primary green. Its geometry is copied here in the
app's own 108-unit viewport, so the site and the app draw the same mark; change
it there and here together. ``frontend/public/favicon.svg`` is the same drawing
as vector, for browsers that take an SVG favicon.

Two shapes, from the same mark:

- **Round** (favicons, the manifest's ``any`` icons, the logo in the homepage's
  Organization JSON-LD): a green disc cropped close around the mark, so it
  stays legible at 16px.
- **Full-bleed** (``apple-touch-icon.png``, the manifest's ``maskable`` icon):
  a green square with the mark at the app's own proportions, inside the
  adaptive-icon safe zone, because iOS and Android launchers cut their own
  shape from the square and a transparent corner would show as black.

Drawn at 16x and downsampled, so edges are antialiased without a vector
renderer. Run from the repo root::

    python -m scripts.generate.site_icons
"""

from pathlib import Path

from PIL import Image, ImageDraw

from scripts.paths import REPO_ROOT

PUBLIC = REPO_ROOT / "frontend" / "public"

GREEN = (0x33, 0x51, 0x45, 255)
WHITE = (255, 255, 255, 255)

# The app's mark, in its 108x108 viewport: strokes from each upper node down
# to the join, then down to the lower node; a filled node at each end.
STROKE_WIDTH = 5
STROKES = [((37, 40), (54, 58)), ((71, 40), (54, 58)), ((54, 58), (54, 72))]
NODES = [(37, 40), (71, 40), (54, 72)]
NODE_RADIUS = 8

# The round icon's disc, in the same viewport: centred on the mark (its extent
# is x 29-79, y 32-80) with room around it, so the mark fills ~60% of the disc.
DISC_CENTRE = (54, 56)
DISC_RADIUS = 42

SUPERSAMPLE = 16


def _draw_mark(draw: ImageDraw.ImageDraw, scale: float, origin: tuple[float, float]) -> None:
    """Draw the mark, mapping viewport (x, y) to ``origin + (x, y) * scale``."""
    ox, oy = origin

    def at(x: float, y: float) -> tuple[float, float]:
        return ox + x * scale, oy + y * scale

    half = STROKE_WIDTH * scale / 2
    for start, end in STROKES:
        draw.line([at(*start), at(*end)], fill=WHITE, width=round(STROKE_WIDTH * scale))
        # Round caps and joins, as the vector's strokeLineCap/LineJoin.
        for x, y in (start, end):
            cx, cy = at(x, y)
            draw.ellipse([cx - half, cy - half, cx + half, cy + half], fill=WHITE)
    r = NODE_RADIUS * scale
    for x, y in NODES:
        cx, cy = at(x, y)
        draw.ellipse([cx - r, cy - r, cx + r, cy + r], fill=WHITE)


def round_icon(size: int) -> Image.Image:
    """The mark on a green disc that fills the square, transparent outside it."""
    big = size * SUPERSAMPLE
    image = Image.new("RGBA", (big, big), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    draw.ellipse([0, 0, big - 1, big - 1], fill=GREEN)
    scale = big / (2 * DISC_RADIUS)
    origin = (big / 2 - DISC_CENTRE[0] * scale, big / 2 - DISC_CENTRE[1] * scale)
    _draw_mark(draw, scale, origin)
    return image.resize((size, size), Image.LANCZOS)


def full_bleed_icon(size: int) -> Image.Image:
    """The mark at the app's proportions on a green square (no transparency)."""
    big = size * SUPERSAMPLE
    image = Image.new("RGBA", (big, big), GREEN)
    _draw_mark(ImageDraw.Draw(image), big / 108, (0, 0))
    return image.resize((size, size), Image.LANCZOS)


# Every icon the site serves: filename -> (shape, size).
ICONS = {
    "favicon-16x16.png": (round_icon, 16),
    "favicon-32x32.png": (round_icon, 32),
    "android-chrome-192x192.png": (round_icon, 192),
    "android-chrome-512x512.png": (round_icon, 512),
    "maskable-512x512.png": (full_bleed_icon, 512),
    "apple-touch-icon.png": (full_bleed_icon, 180),
}


def write_icons(public: Path = PUBLIC) -> list[Path]:
    """Write every icon in ICONS, plus favicon.ico (16, 32 and 48px)."""
    written = []
    for name, (shape, size) in ICONS.items():
        path = public / name
        shape(size).save(path, optimize=True)
        written.append(path)
    ico = public / "favicon.ico"
    round_icon(48).save(ico, sizes=[(16, 16), (32, 32), (48, 48)])
    written.append(ico)
    return written


if __name__ == "__main__":
    for path in write_icons():
        print(f"wrote {path.relative_to(REPO_ROOT)}")
