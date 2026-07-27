#!/usr/bin/env python3
"""
Generate the SalesMake default social image (SALESMAKE_DEFAULT_IMAGE).

A single 1080x1080 brand tile used as the fallback media for posts so that
Instagram / Pinterest (which reject imageless posts) validate. Built around the
SalesMake logo with the wordmark + descriptor + site.

Usage:
    python scripts/make_default_image.py --logo assets/logo.jpg --out assets/salesmake-default-1080.png
"""
import argparse
from PIL import Image, ImageDraw, ImageFont

WIN_FONTS = r"C:\Windows\Fonts"


def load_font(name, size):
    return ImageFont.truetype(f"{WIN_FONTS}\\{name}", size)


def sample_brand_colors(logo):
    """Pick a representative deep-navy and a bright-blue from the logo pixels."""
    im = logo.convert("RGB")
    im.thumbnail((160, 160))
    navy = (18, 42, 82)     # sensible defaults
    blue = (46, 122, 196)
    best_navy_score = best_blue_score = -1
    for r, g, b in im.getdata():
        if b < 40 and r < 40 and g < 40:
            continue  # skip near-black outlines
        if b > r and b > g:
            # navy = dark & blue-dominant
            navy_score = (b - r) + (140 - b)  # blue-dominant but dark
            if b < 130 and navy_score > best_navy_score:
                best_navy_score = navy_score
                navy = (r, g, b)
            # blue = bright & blue-dominant
            blue_score = (b - r) + b
            if b > 150 and blue_score > best_blue_score:
                best_blue_score = blue_score
                blue = (r, g, b)
    return navy, blue


def knockout_white(img, thresh=234):
    """Make near-white pixels transparent so the logo blends into the canvas.
    The logo's gray swoosh (~155) and blue bars are far below thresh, so safe."""
    img = img.convert("RGBA")
    out = []
    for r, g, b, a in img.getdata():
        out.append((r, g, b, 0) if (r >= thresh and g >= thresh and b >= thresh) else (r, g, b, a))
    img.putdata(out)
    return img


def center_text(draw, cx, y, text, font, fill):
    l, t, r, b = draw.textbbox((0, 0), text, font=font)
    draw.text((cx - (r - l) / 2 - l, y), text, font=font, fill=fill)
    return b - t


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--logo", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--wordmark", default="SalesMake")
    ap.add_argument("--descriptor", default="Outbound & GTM consultancy")
    ap.add_argument("--site", default="salesmake.agency")
    args = ap.parse_args()

    S = 1080
    logo = Image.open(args.logo).convert("RGBA")
    navy, blue = sample_brand_colors(logo)
    logo = knockout_white(logo)
    gray = (90, 100, 112)
    print("sampled navy:", navy, " blue:", blue, " logo size:", logo.size)

    # Canvas: soft vertical wash from white to a very light blue-gray for depth.
    canvas = Image.new("RGB", (S, S), "#ffffff")
    top, bot = (255, 255, 255), (241, 245, 250)
    px = canvas.load()
    for y in range(S):
        f = y / (S - 1)
        row = tuple(round(top[i] + (bot[i] - top[i]) * f) for i in range(3))
        for x in range(S):
            px[x, y] = row
    draw = ImageDraw.Draw(canvas)

    # Logo, scaled to ~460px wide, centered horizontally near the top.
    lw = 460
    lh = round(logo.height * lw / logo.width)
    logo_r = logo.resize((lw, lh), Image.LANCZOS)
    lx = (S - lw) // 2
    ly = 120
    canvas.paste(logo_r, (lx, ly), logo_r)  # RGBA paste keeps any transparency

    # Wordmark
    y = ly + lh + 24
    wf = load_font("trebucbd.ttf", 104)
    center_text(draw, S / 2, y, args.wordmark, wf, navy)

    # Descriptor
    y += 150
    df = load_font("trebuc.ttf", 42)
    center_text(draw, S / 2, y, args.descriptor, df, gray)

    # Footer band with the site
    band_h = 104
    draw.rectangle([0, S - band_h, S, S], fill=navy)
    sf = load_font("trebucbd.ttf", 46)
    l, t, r, b = draw.textbbox((0, 0), args.site, font=sf)
    draw.text((S / 2 - (r - l) / 2 - l, S - band_h + (band_h - (b - t)) / 2 - t),
              args.site, font=sf, fill=(255, 255, 255))

    canvas.save(args.out, "PNG")
    print("wrote", args.out, canvas.size)


if __name__ == "__main__":
    main()
