"""Prepare Windows branding from locally bundled assets only.

User-supplied GTA Petroleum logo is committed in assets/gta.png. Do not
download anything during build: GitHub Actions should be reproducible
without depending on image hosts, HTTP 403/429, or external availability.
"""
from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parent.parent
ASSETS = ROOT / "assets"


def make_icon() -> Path:
    ASSETS.mkdir(parents=True, exist_ok=True)
    gta_path = ASSETS / "gta.png"
    icon = Image.new("RGBA", (256, 256), "white")
    if gta_path.is_file():
        with Image.open(gta_path) as raw:
            logo = raw.convert("RGBA")
        # Left diamond GTA symbol from the user-provided official logo.
        span = min(logo.height, round(logo.width * 0.31))
        emblem = logo.crop((0, 0, span, min(span, logo.height)))
        emblem.thumbnail((215, 215), Image.Resampling.LANCZOS)
        x = (256 - emblem.width) // 2
        y = (256 - emblem.height) // 2
        icon.alpha_composite(emblem, (x, y))
    else:
        draw = ImageDraw.Draw(icon)
        draw.rounded_rectangle((18, 18, 238, 238), 38, fill="#F4F7F9", outline="#BBCAD4", width=4)
        draw.rounded_rectangle((60, 48, 196, 208), 16, fill="#D62834")
        draw.rectangle((79, 78, 177, 183), fill="white")
        for y in (101, 127, 153):
            draw.rounded_rectangle((96, y, 165, y + 8), 3, fill="#D62834")
    output = ASSETS / "app.ico"
    icon.save(output, sizes=[(16, 16), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)])
    print("Created offline Windows icon:", output, flush=True)
    return output


if __name__ == "__main__":
    make_icon()
