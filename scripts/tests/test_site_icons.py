"""The committed site icons are the ones scripts/generate/site_icons.py draws."""

from PIL import Image, ImageChops

from scripts.generate import site_icons


def test_every_icon_is_committed_at_its_size():
    for name, (_, size) in site_icons.ICONS.items():
        with Image.open(site_icons.PUBLIC / name) as image:
            assert image.size == (size, size), name


def test_committed_icons_match_the_drawing():
    # Pixel comparison rather than bytes, so a Pillow upgrade that encodes
    # differently doesn't fail it; a changed mark or a stale icon does.
    for name, (shape, size) in site_icons.ICONS.items():
        with Image.open(site_icons.PUBLIC / name) as committed:
            diff = ImageChops.difference(committed.convert("RGBA"), shape(size))
            assert max(high for _, high in diff.getextrema()) <= 2, name


def test_full_bleed_icons_have_no_transparent_corner():
    # iOS and Android launchers fill transparency with black.
    for name in ("apple-touch-icon.png", "maskable-512x512.png"):
        with Image.open(site_icons.PUBLIC / name) as image:
            assert image.convert("RGBA").getpixel((0, 0))[3] == 255, name


def test_svg_favicon_draws_the_same_disc():
    svg = (site_icons.PUBLIC.parent / "public" / "favicon.svg").read_text()
    cx, cy = site_icons.DISC_CENTRE
    assert f'cx="{cx}" cy="{cy}" r="{site_icons.DISC_RADIUS}"' in svg
    assert "#335145" in svg
