"""Original Brag crest, drawn without fonts or external art.

Run `py companion/brag_icon.py` from any directory to regenerate the shipped
512px master, Windows ICO and WoW texture. Pillow is the only dependency.
The same geometry renders the tray in its current status color, so source and
PyInstaller builds need no runtime asset lookup or platform font fallback.
"""
from pathlib import Path
from PIL import Image, ImageDraw

GOLD = (232, 185, 84)
INK = (30, 22, 16)
ICO_SIZES = (16, 20, 24, 32, 40, 48, 64, 128, 256)


def make_icon(color=GOLD, size=64):
    """A square RGBA crest with transparent corners, supersampled for small UI."""
    scale = size * 4 / 256
    image = Image.new("RGBA", (size * 4, size * 4))
    draw = ImageDraw.Draw(image)

    def polygon(points, fill):
        draw.polygon([(round(x * scale), round(y * scale)) for x, y in points], fill=fill)

    # Broad shoulders and a pointed base give it a recognisable shield silhouette.
    polygon([(12, 12), (244, 12), (236, 151), (214, 197),
             (128, 248), (42, 197), (20, 151)], INK)
    polygon([(24, 24), (232, 24), (224, 149), (205, 189),
             (128, 234), (51, 189), (32, 149)], color)
    polygon([(40, 40), (216, 40), (209, 145), (192, 178),
             (128, 216), (64, 178), (47, 145)], INK)
    # Hand-drawn, chamfered B: no font dependency. Large counters stay open at 16px.
    polygon([(80, 56), (145, 56), (178, 72), (178, 104),
             (162, 119), (184, 132), (184, 156), (151, 176),
             (80, 176), (80, 156), (84, 156), (84, 76), (80, 76)], color)
    polygon([(108, 79), (139, 79), (154, 87), (154, 100),
             (140, 109), (108, 109)], INK)
    polygon([(108, 130), (144, 130), (160, 139), (160, 145),
             (144, 155), (108, 155)], INK)
    image = image.resize((size, size), Image.Resampling.LANCZOS)
    # Remove almost invisible filter ringing outside the silhouette.
    image.putalpha(image.getchannel("A").point(lambda a: 0 if a < 4 else a))
    return image


def write_ico(path):
    make_icon(GOLD, 256).save(path, format="ICO", sizes=[(s, s) for s in ICO_SIZES])


if __name__ == "__main__":
    here = Path(__file__).resolve().parent
    make_icon(GOLD, 512).save(here / "assets" / "brag-icon.png")
    write_ico(here / "assets" / "brag.ico")
    # Pillow defaults to uncompressed true-color TGA; explicitly disable RLE.
    make_icon(GOLD, 64).save(here.parent / "Brag" / "icon.tga", compression=None)
