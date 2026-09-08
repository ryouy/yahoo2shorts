"""Generate the small, inset yc2ys application icon and platform variants."""

from pathlib import Path
from PIL import Image, ImageDraw
import shutil
import subprocess


ROOT = Path(__file__).resolve().parents[1]
BUILD = ROOT / "frontend" / "build"
MASTER = BUILD / "icon-master.png"
ICONSET = BUILD / "icon.iconset"


def line(draw, points, fill, width):
    draw.line(points, fill=fill, width=width, joint="curve")
    radius = width // 2
    for x, y in (points[0], points[-1]):
        draw.ellipse((x - radius, y - radius, x + radius, y + radius), fill=fill)


def main():
    scale = 4
    canvas = Image.new("RGBA", (1024 * scale, 1024 * scale), (0, 0, 0, 0))
    draw = ImageDraw.Draw(canvas)
    draw.rounded_rectangle((102 * scale, 102 * scale, 922 * scale, 922 * scale), radius=196 * scale, fill="#16181D")
    white, lime, stroke = "#F7F8FA", "#BEF264", 76 * scale
    line(draw, [(364 * scale, 348 * scale), (512 * scale, 526 * scale), (660 * scale, 348 * scale)], white, stroke)
    line(draw, [(512 * scale, 526 * scale), (512 * scale, 692 * scale), (442 * scale, 780 * scale)], white, stroke)
    dot = 31 * scale
    draw.ellipse((654 * scale - dot, 326 * scale - dot, 654 * scale + dot, 326 * scale + dot), fill=lime)
    image = canvas.resize((1024, 1024), Image.Resampling.LANCZOS)
    image.save(MASTER)

    if ICONSET.exists():
        shutil.rmtree(ICONSET)
    ICONSET.mkdir()
    for size in (16, 32, 128, 256, 512):
        for suffix, pixels in (("", size), ("@2x", size * 2)):
            image.resize((pixels, pixels), Image.Resampling.LANCZOS).save(ICONSET / f"icon_{size}x{size}{suffix}.png")
    icns = BUILD / "icon.icns"
    icns.unlink(missing_ok=True)
    subprocess.run(["iconutil", "-c", "icns", str(ICONSET), "-o", str(icns)], check=True)
    image.save(BUILD / "icon.ico", sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)])


if __name__ == "__main__":
    main()
