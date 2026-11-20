"""Render NovelForge's original book/nib mark and all macOS icon representations.

Run on macOS: uv run --with pillow python scripts/generate_macos_icon.py
Pillow is a build-time tool; the application has no new imaging dependency.
"""

import subprocess
import tempfile
from pathlib import Path

from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[1]
ICONS = ROOT / "apps/desktop/src-tauri/icons"
BLUE = "#5368F4"


def curve(points: list[tuple[float, float]], count: int = 32):
    """Sample a cubic Bezier with endpoints and two control points."""
    result = []
    for index in range(count + 1):
        t = index / count
        result.append(
            tuple(
                (1 - t) ** 3 * points[0][axis]
                + 3 * (1 - t) ** 2 * t * points[1][axis]
                + 3 * (1 - t) * t * t * points[2][axis]
                + t**3 * points[3][axis]
                for axis in (0, 1)
            )
        )
    return result


def render(size: int) -> Image.Image:
    # Supersampling preserves the simple silhouette at 16/32-pixel Finder sizes.
    scale = size * 4 / 1024
    canvas = Image.new("RGBA", (size * 4, size * 4))
    draw = ImageDraw.Draw(canvas)

    def polygon(points, fill):
        draw.polygon([(round(x * scale), round(y * scale)) for x, y in points], fill=fill)

    def line(points, fill, width):
        draw.line(
            [(round(x * scale), round(y * scale)) for x, y in points],
            fill=fill,
            width=max(1, round(width * scale)),
            joint="curve",
        )

    # The transparent outside margin follows macOS icon geometry. No text or hairlines.
    draw.rounded_rectangle(
        (64 * scale, 64 * scale, 960 * scale, 960 * scale), radius=204 * scale, fill=BLUE
    )
    left = [(240, 326)] + curve([(240, 326), (336, 306), (423, 335), (482, 392)])
    left += [(482, 734)] + curve([(482, 734), (405, 681), (332, 661), (240, 680)])
    right = [(784, 326)] + curve([(784, 326), (688, 306), (601, 335), (542, 392)])
    right += [(542, 734)] + curve([(542, 734), (619, 681), (692, 661), (784, 680)])
    polygon(left, "#FFFFFF")
    polygon(right, "#FFFFFF")
    # The gap between pages becomes a pen nib; the two pages remain readable when small.
    polygon([(512, 234), (571, 320), (541, 392), (512, 418), (483, 392), (453, 320)], "#FFFFFF")
    line([(512, 319), (512, 374)], BLUE, 15)
    if size >= 64:
        line(curve([(291, 410), (344, 407), (401, 426), (437, 452)]), BLUE, 15)
        line(curve([(291, 480), (344, 477), (401, 496), (437, 522)]), BLUE, 15)
        line(curve([(587, 452), (623, 426), (680, 407), (733, 410)]), BLUE, 15)
        line(curve([(587, 522), (623, 496), (680, 477), (733, 480)]), BLUE, 15)
    return canvas.resize((size, size), Image.Resampling.LANCZOS)


def main() -> None:
    ICONS.mkdir(parents=True, exist_ok=True)
    render(1024).save(ICONS / "icon.png")
    render(32).save(ICONS / "32x32.png")
    render(128).save(ICONS / "128x128.png")
    render(256).save(ICONS / "128x128@2x.png")
    with tempfile.TemporaryDirectory(prefix="novelforge-icon-") as directory:
        iconset = Path(directory) / "NovelForge.iconset"
        iconset.mkdir()
        for logical in (16, 32, 128, 256, 512):
            for density in (1, 2):
                suffix = "@2x" if density == 2 else ""
                render(logical * density).save(iconset / f"icon_{logical}x{logical}{suffix}.png")
        subprocess.run(
            ["iconutil", "-c", "icns", str(iconset), "-o", str(ICONS / "icon.icns")], check=True
        )
    print("Generated macOS icon with 16–1024 pixel representations:", ICONS / "icon.icns")


if __name__ == "__main__":
    main()
