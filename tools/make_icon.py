"""Genera assets/icon.png y assets/icon.ico: un cristal violeta partido por una grieta,
inspirado en los rivens de Warframe (sin usar arte original)."""

from pathlib import Path

from PIL import Image, ImageChops, ImageDraw, ImageFilter

S = 1024
OUT = Path(__file__).resolve().parent.parent / "assets"

RHOMBUS = [(512, 120), (790, 512), (512, 904), (234, 512)]
# Grieta en zigzag que parte el cristal de arriba a abajo.
CRACK = [(512, 60), (486, 300), (548, 450), (470, 600), (534, 760), (512, 964)]


def vertical_gradient(stops):
    """stops: [(y_fraction, (r, g, b)), ...]"""
    img = Image.new("RGB", (1, S))
    for y in range(S):
        t = y / (S - 1)
        for (t0, c0), (t1, c1) in zip(stops, stops[1:]):
            if t0 <= t <= t1:
                k = (t - t0) / (t1 - t0)
                img.putpixel((0, y), tuple(round(a + (b - a) * k) for a, b in zip(c0, c1)))
                break
    return img.resize((S, S))


def radial_background():
    bg = Image.new("RGB", (S, S), (12, 5, 24))
    glow = Image.new("L", (S, S), 0)
    ImageDraw.Draw(glow).ellipse((150, 150, 874, 874), fill=255)
    glow = glow.filter(ImageFilter.GaussianBlur(170))
    return Image.composite(Image.new("RGB", (S, S), (58, 24, 108)), bg, glow)


def polygon_mask(points):
    m = Image.new("L", (S, S), 0)
    ImageDraw.Draw(m).polygon(points, fill=255)
    return m


def main():
    OUT.mkdir(exist_ok=True)
    icon = radial_background().convert("RGBA")

    # Halo violeta detrás del cristal.
    halo = polygon_mask(RHOMBUS).filter(ImageFilter.GaussianBlur(60))
    icon.paste((170, 90, 255, 255), (0, 0), halo.point(lambda v: v * 0.75))

    crystal = vertical_gradient([(0, (238, 214, 255)), (0.45, (160, 92, 246)), (1, (66, 22, 150))])
    rhombus = polygon_mask(RHOMBUS)
    left_side = polygon_mask(CRACK + [(0, S), (0, 0)])
    halves = [
        (ImageChops.multiply(rhombus, left_side), (-24, 8)),
        (ImageChops.subtract(rhombus, left_side), (24, -8)),
    ]

    # Luz que sale por la grieta.
    crack_glow = Image.new("L", (S, S), 0)
    ImageDraw.Draw(crack_glow).line(CRACK[1:-1], fill=255, width=38, joint="curve")
    icon.paste((236, 210, 255, 255), (0, 0), crack_glow.filter(ImageFilter.GaussianBlur(16)))

    for mask, (dx, dy) in halves:
        shifted = ImageChops.offset(mask, dx, dy)
        icon.paste(ImageChops.offset(crystal, dx, dy), (0, 0), shifted)
        # Borde fino más claro en cada mitad.
        edge = ImageChops.subtract(shifted, shifted.filter(ImageFilter.MinFilter(9)))
        icon.paste((245, 232, 255, 255), (0, 0), edge.point(lambda v: v * 0.7))

    # Faceta interior que da volumen.
    facet = polygon_mask([(512, 250), (680, 512), (512, 774), (344, 512)])
    facet = ImageChops.multiply(facet, ImageChops.invert(crack_glow.filter(ImageFilter.MaxFilter(31))))
    icon.paste((255, 255, 255, 255), (0, 0), facet.point(lambda v: v * 0.12))

    # Esquinas redondeadas.
    corners = Image.new("L", (S, S), 0)
    ImageDraw.Draw(corners).rounded_rectangle((0, 0, S - 1, S - 1), radius=200, fill=255)
    icon.putalpha(corners)

    icon.save(OUT / "icon.png")
    icon.save(OUT / "icon.ico", sizes=[(n, n) for n in (16, 24, 32, 48, 64, 128, 256)])
    print("ok:", OUT / "icon.ico")


if __name__ == "__main__":
    main()
