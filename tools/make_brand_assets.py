"""Render brand bitmaps from assets/logo/hermisim-mark.svg (PNG sizes, .ico, wordmark,
README banner, Inno Setup wizard images). Requires cairosvg + Pillow.

    python tools/make_brand_assets.py
"""
from pathlib import Path

import cairosvg
from PIL import Image, ImageDraw, ImageFilter, ImageFont

ROOT = Path(__file__).resolve().parents[1]
LOGO = ROOT / "assets" / "logo"
INST = ROOT / "installer" / "windows" / "assets"
INST.mkdir(parents=True, exist_ok=True)
SVG = LOGO / "hermisim-mark.svg"


STANDARD = (32, 48, 64, 128, 256, 512, 1024)


def mark(n: int) -> Image.Image:
    import io
    data = cairosvg.svg2png(url=str(SVG), output_width=n, output_height=n)
    if n in STANDARD:
        (LOGO / f"hermisim-mark-{n}.png").write_bytes(data)
    return Image.open(io.BytesIO(data)).convert("RGBA")


def font(names, size):
    for n in names:
        for d in ("/usr/share/fonts/opentype/inter", "/usr/share/fonts/truetype/dejavu", "C:/Windows/Fonts"):
            f = Path(d) / n
            if f.exists():
                return ImageFont.truetype(str(f), size)
    return ImageFont.load_default()


BOLD = ["Inter-ExtraBold.otf", "Inter-Bold.otf", "DejaVuSans-Bold.ttf", "segoeuib.ttf"]
MONO = ["DejaVuSansMono.ttf", "consola.ttf"]


def gradient_text(img, xy, text, f, c0=(127, 243, 255), c1=(177, 77, 255)):
    d = ImageDraw.Draw(img)
    x0, y0, x1, y1 = d.textbbox(xy, text, font=f)
    mask = Image.new("L", img.size, 0)
    ImageDraw.Draw(mask).text(xy, text, font=f, fill=255)
    grad = Image.new("RGBA", img.size)
    gd = ImageDraw.Draw(grad)
    for x in range(x0, x1 + 1):
        t = (x - x0) / max(1, x1 - x0)
        gd.line([(x, y0), (x, y1)], fill=tuple(int(c0[i] + (c1[i] - c0[i]) * t) for i in range(3)) + (255,))
    img.paste(grad, (0, 0), mask)
    return x1, y1


def backdrop(w, h):
    img = Image.new("RGBA", (w, h), (5, 7, 12, 255))
    d = ImageDraw.Draw(img)
    for y in range(h):
        t = y / h
        d.line([(0, y), (w, y)], fill=(int(7 + 6 * (1 - t)), int(10 + 10 * (1 - t)), int(18 + 22 * (1 - t)), 255))
    grid = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    gd = ImageDraw.Draw(grid)
    hz = int(h * 0.62)
    for k in range(1, 14):
        y = hz + int((h - hz) * (k / 13) ** 1.8)
        gd.line([(0, y), (w, y)], fill=(0, 229, 255, 40), width=1)
    for k in range(-12, 13):
        gd.line([(w / 2, hz), (w / 2 + k * w / 6, h)], fill=(0, 229, 255, 34), width=1)
    img.alpha_composite(grid)
    return img


def main():
    for n in STANDARD:
        mark(n)
    m256 = Image.open(LOGO / "hermisim-mark-256.png")
    m256.save(LOGO / "hermisim.ico", sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)])
    m256.save(INST / "hermisim.ico", sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)])

    # wordmark
    wm = Image.new("RGBA", (1400, 400), (0, 0, 0, 0))
    wm.alpha_composite(mark(360), (20, 20))
    x1, _ = gradient_text(wm, (420, 90), "HERMISIM", font(BOLD, 150))
    ImageDraw.Draw(wm).rectangle([426, 262, x1, 266], fill=(74, 140, 255, 220))
    ImageDraw.Draw(wm).text((426, 282), "TULPALANG · SIMULATION SUITE", font=font(MONO, 34), fill=(125, 142, 163, 255))
    wm.save(LOGO / "hermisim-wordmark.png")

    # README banner
    bn = backdrop(1600, 420)
    glow = Image.new("RGBA", bn.size, (0, 0, 0, 0))
    ImageDraw.Draw(glow).ellipse([60, 40, 420, 400], fill=(0, 170, 255, 70))
    bn.alpha_composite(glow.filter(ImageFilter.GaussianBlur(40)))
    bn.alpha_composite(mark(340), (70, 40))
    x1, _ = gradient_text(bn, (470, 110), "HERMISIM", font(BOLD, 140))
    d = ImageDraw.Draw(bn)
    d.rectangle([476, 272, x1, 275], fill=(74, 140, 255, 230))
    d.text((476, 292), "Simulation suite & IDE for TulpaLang", font=font(BOLD[1:], 38), fill=(215, 227, 240, 255))
    d.text((478, 346), "MuJoCo co-simulation · RTL waveforms · nn / rl / eda libraries", font=font(MONO, 24), fill=(125, 142, 163, 255))
    bn.convert("RGB").save(LOGO / "hermisim-banner.png")

    # Inno Setup wizard images (2× of 164×314 and 55×58 for HiDPI)
    for scale in (1, 2):
        w, h = 164 * scale, 314 * scale
        wi = backdrop(w, h)
        g = Image.new("RGBA", wi.size, (0, 0, 0, 0))
        ImageDraw.Draw(g).ellipse([int(w * 0.05), int(h * 0.08), int(w * 0.95), int(h * 0.5)], fill=(0, 170, 255, 60))
        wi.alpha_composite(g.filter(ImageFilter.GaussianBlur(18 * scale)))
        ms = int(w * 0.82)
        wi.alpha_composite(mark(ms), ((w - ms) // 2, int(h * 0.09)))
        f = font(BOLD, 21 * scale)
        tw = ImageDraw.Draw(wi).textlength("HERMISIM", font=f)
        gradient_text(wi, (int((w - tw) / 2), int(h * 0.56)), "HERMISIM", f)
        f2 = font(MONO, 8 * scale)
        sub = "TULPALANG SUITE"
        ImageDraw.Draw(wi).text((int((w - ImageDraw.Draw(wi).textlength(sub, font=f2)) / 2), int(h * 0.56) + 30 * scale), sub, font=f2, fill=(0, 229, 255, 200))
        wi.convert("RGB").save(INST / f"wizard-large{'@2x' if scale == 2 else ''}.bmp")
        sm = Image.new("RGBA", (55 * scale, 58 * scale), (12, 16, 22, 255))
        s = 52 * scale
        sm.alpha_composite(mark(s), ((55 * scale - s) // 2, (58 * scale - s) // 2))
        sm.convert("RGB").save(INST / f"wizard-small{'@2x' if scale == 2 else ''}.bmp")
    print("brand assets written to", LOGO, "and", INST)


if __name__ == "__main__":
    main()
