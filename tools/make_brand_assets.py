""".RAV IDE brand bitmaps, rendered from the master logo ``assets/logo/ravide-logo.jpg``
(1408×768 neon circuit-raven with the ``.RAV IDE`` lettering). Requires Pillow only.

Writes:
  assets/logo/ravide-mark-{32..1024}.png   square app mark (whole logo, raven + lettering)
  assets/logo/ravide-head-{16,24,32,48}.png  raven head only — legible at tiny sizes
  assets/logo/ravide.ico                     Windows icon (head at ≤32 px, full mark above)
  assets/logo/ravide-banner.jpg              README banner
  installer/windows/assets/ravide.ico, wizard-{large,small}[@2x].bmp   Inno Setup art

    python tools/make_brand_assets.py
"""
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont

ROOT = Path(__file__).resolve().parents[1]
LOGO = ROOT / "assets" / "logo"
INST = ROOT / "installer" / "windows" / "assets"
INST.mkdir(parents=True, exist_ok=True)
MASTER = LOGO / "ravide-logo.jpg"

# Crop boxes in master-logo pixels (1408×768).
MARK_BOX = (340, 40, 1068, 768)   # square: whole raven + ".RAV IDE"
HEAD_BOX = (540, 78, 868, 406)    # square: raven head above the lettering

STANDARD = (32, 48, 64, 128, 256, 512, 1024)
SMALL = (16, 24, 32, 48)
BG = (8, 10, 22)                  # logo backdrop navy


def _master() -> Image.Image:
    im = Image.open(MASTER).convert("RGB")
    sx, sy = im.width / 1408, im.height / 768   # tolerate a re-exported master at another size
    im.box = lambda b: tuple(int(v * (sx if i % 2 == 0 else sy)) for i, v in enumerate(b))  # type: ignore[attr-defined]
    return im


def _rounded(img: Image.Image, radius_frac: float = 0.18) -> Image.Image:
    """Square → rounded-square tile with transparent corners."""
    n = img.width
    mask = Image.new("L", (n * 4, n * 4), 0)
    ImageDraw.Draw(mask).rounded_rectangle([0, 0, n * 4 - 1, n * 4 - 1], radius=int(n * 4 * radius_frac), fill=255)
    out = img.convert("RGBA")
    out.putalpha(mask.resize((n, n), Image.LANCZOS))
    return out


def mark(im: Image.Image, n: int, *, head: bool = False, rounded: bool = True) -> Image.Image:
    src = im.crop(im.box(HEAD_BOX if head else MARK_BOX))
    if n < src.width // 3:  # sharpen a touch after heavy downscales so the neon lines survive
        out = src.resize((n, n), Image.LANCZOS).filter(ImageFilter.UnsharpMask(radius=0.6, percent=60, threshold=1))
    else:
        out = src.resize((n, n), Image.LANCZOS)
    return _rounded(out) if rounded else out.convert("RGBA")


def font(names, size):
    for n in names:
        for d in ("/usr/share/fonts/opentype/inter", "/usr/share/fonts/truetype/dejavu", "C:/Windows/Fonts"):
            f = Path(d) / n
            if f.exists():
                return ImageFont.truetype(str(f), size)
    return ImageFont.load_default()


MONO = ["DejaVuSansMono.ttf", "consola.ttf"]
GREEN = (80, 255, 140)


def main():
    im = _master()
    for n in STANDARD:
        mark(im, n).save(LOGO / f"ravide-mark-{n}.png")
    for n in SMALL:
        mark(im, n, head=True).save(LOGO / f"ravide-head-{n}.png")

    # .ico: Pillow picks, for each requested size, the appended image of exactly that size.
    frames = [mark(im, n, head=True) for n in (16, 24, 32)] + [mark(im, n) for n in (48, 64, 128, 256)]
    for dst in (LOGO / "ravide.ico", INST / "ravide.ico"):
        frames[-1].save(dst, format="ICO", sizes=[f.size for f in frames], append_images=frames[:-1])

    # README banner: the master logo, trimmed of some empty top/bottom margin.
    im.crop(im.box((0, 24, 1408, 752))).save(LOGO / "ravide-banner.jpg", quality=90, optimize=True)

    # Inno Setup wizard images (1× and 2× of 164×314 and 55×58).
    for scale in (1, 2):
        w, h = 164 * scale, 314 * scale
        wi = Image.new("RGBA", (w, h), BG + (255,))
        ms = int(w * 0.94)
        tile = mark(im, ms, rounded=False)
        fade = Image.new("L", tile.size, 0)  # feather the crop edge into the backdrop
        ImageDraw.Draw(fade).rectangle([6 * scale, 6 * scale, ms - 6 * scale, ms - 6 * scale], fill=255)
        tile.putalpha(fade.filter(ImageFilter.GaussianBlur(5 * scale)))
        wi.alpha_composite(tile, ((w - ms) // 2, int(h * 0.12)))
        f = font(MONO, 9 * scale)
        d = ImageDraw.Draw(wi)
        for i, line in enumerate(("TULPALANG", "SIMULATION SUITE & IDE")):
            tw = d.textlength(line, font=f)
            d.text(((w - tw) / 2, int(h * 0.12) + ms + (14 + 14 * i) * scale), line, font=f, fill=GREEN + (230,))
        wi.convert("RGB").save(INST / f"wizard-large{'@2x' if scale == 2 else ''}.bmp")

        sm = Image.new("RGBA", (55 * scale, 58 * scale), BG + (255,))
        s = 52 * scale
        sm.alpha_composite(mark(im, s, head=True), ((55 * scale - s) // 2, (58 * scale - s) // 2))
        sm.convert("RGB").save(INST / f"wizard-small{'@2x' if scale == 2 else ''}.bmp")
    print("brand assets written to", LOGO, "and", INST)


if __name__ == "__main__":
    main()
