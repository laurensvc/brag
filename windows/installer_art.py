"""The installer's pictures, in the look of Brag's page: dark wood, gold trim, the crest, the Cinzel title.

  py windows\\installer_art.py <folder>   writes wizard-back.png, wizard-image.png and wizard-small.png there

windows\\build.ps1 runs it; brag.iss shows them. Pillow is the only dependency (windows\\requirements.txt).
"""
import os, sys
from PIL import Image, ImageDraw, ImageFilter, ImageFont

COMPANION = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "companion")
sys.path.insert(0, COMPANION)
from brag_icon import make_icon  # noqa: E402

ASSETS = os.path.join(COMPANION, "assets")
INK = (8, 6, 4)  # the page's darkening over the wood (index.html body)
GOLD, GOLD_SOFT, MUTED = (255, 209, 0), (227, 183, 90), (185, 164, 124)  # --gold, --gold-soft, --muted
# Sizes: Inno Setup keeps these aspect ratios and recommends at least 596x432 and 202x386 (brag.iss).
BACK = (1193, 864)  # 497:360, the whole wizard
TALL = (410, 785)  # 164:314, left of the Welcome and Finish pages
SMALL = 116  # square, top right of the other pages


def wood(size, dim):
    """The page's wood texture, cropped to fill size, darkened like the page (dim 0..1)."""
    with Image.open(os.path.join(ASSETS, "accordion-content-bg.webp")) as src:
        img = src.convert("RGB")
    scale = max(size[0] / img.width, size[1] / img.height)
    img = img.resize((round(img.width * scale), round(img.height * scale)), Image.Resampling.LANCZOS)
    left, top = (img.width - size[0]) // 2, (img.height - size[1]) // 2
    img = img.crop((left, top, left + size[0], top + size[1]))
    return Image.blend(img, Image.new("RGB", size, INK), dim)


def cinzel(px, weight=900):
    font = ImageFont.truetype(os.path.join(ASSETS, "Cinzel.ttf"), px)
    try:
        font.set_variation_by_axes([weight])  # Cinzel is a variable font, 400 to 900
    except (OSError, AttributeError):  # Pillow without variable font support: the regular weight
        pass
    return font


def centered(draw, y, text, font, fill):
    w = draw.textlength(text, font=font)
    draw.text(((TALL[0] - w) / 2, y), text, font=font, fill=fill)


def glow(img, text_layer, color, radius):
    """Gold text with a warm glow behind it, like the page's title."""
    halo = Image.new("RGBA", img.size, color + (0,))
    halo.putalpha(text_layer.getchannel("A").filter(ImageFilter.GaussianBlur(radius)))
    img.alpha_composite(halo)
    img.alpha_composite(text_layer)


def tall():
    img = wood(TALL, .62).convert("RGBA")
    draw = ImageDraw.Draw(img)
    for inset, color, width in ((10, GOLD_SOFT, 3), (19, (120, 92, 40), 1)):  # gold trim, like the cards
        draw.rectangle((inset, inset, TALL[0] - 1 - inset, TALL[1] - 1 - inset), outline=color, width=width)
    crest = make_icon(size=230)
    shadow = Image.new("RGBA", img.size)
    shadow.paste((0, 0, 0, 200), (90, 190), crest.getchannel("A"))
    img.alpha_composite(shadow.filter(ImageFilter.GaussianBlur(10)))
    img.alpha_composite(crest, ((TALL[0] - 230) // 2, 170))
    title = Image.new("RGBA", img.size)
    t = ImageDraw.Draw(title)
    font = cinzel(92)
    w = t.textlength("BRAG", font=font)
    t.text(((TALL[0] - w) / 2, 430), "BRAG", font=font, fill=GOLD)
    glow(img, title, (255, 170, 0), 9)
    draw = ImageDraw.Draw(img)
    draw.line((95, 560, TALL[0] - 95, 560), fill=GOLD_SOFT, width=2)
    for i, line in enumerate(("Your big moments,", "posted to Discord")):
        centered(draw, 585 + i * 40, line, cinzel(27, 700), MUTED)
    return img.convert("RGB")


def write(folder):
    os.makedirs(folder, exist_ok=True)
    wood(BACK, .80).save(os.path.join(folder, "wizard-back.png"))
    tall().save(os.path.join(folder, "wizard-image.png"))
    make_icon(size=SMALL).save(os.path.join(folder, "wizard-small.png"))


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    write(sys.argv[1])
