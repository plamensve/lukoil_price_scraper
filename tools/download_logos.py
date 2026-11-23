"""Fetch verified public company logos and bundle them into the Windows build.

Run:
    python tools/download_logos.py

Sources are pinned to the official GTA Petroleum site and a Wikimedia
Commons LUKOIL corporate-logo file. Downloads are build-time only.
"""
from __future__ import annotations

from io import BytesIO
from pathlib import Path
from urllib.request import Request, urlopen
import time

from PIL import Image, ImageChops

ROOT = Path(__file__).resolve().parent.parent
ASSETS = ROOT / "assets"

SOURCES = {
    "lukoil.png": (
        "https://upload.wikimedia.org/wikipedia/commons/thumb/"
        "f/ff/Lukoil_company_logo.svg/960px-Lukoil_company_logo.svg.png"
    ),
    "gta.png": (
        "https://gtapetroleum.com/wp-content/uploads/2021/03/"
        "GTA-logo-1200x800-rgb.jpg"
    ),
}


def fetch_image(url: str) -> Image.Image:
    last_error = None
    for attempt in range(3):
        try:
            request = Request(
                url,
                headers={
                    "User-Agent": "Mozilla/5.0 (compatible; GTA-LukoilPriceExport/1.0)",
                    "Accept": "image/avif,image/webp,image/png,image/jpeg,*/*;q=0.8",
                },
            )
            with urlopen(request, timeout=25) as response:
                raw = response.read(5_000_001)
            if len(raw) > 5_000_000:
                raise ValueError("Логото е прекалено голямо.")
            image = Image.open(BytesIO(raw))
            image.load()
            if image.width < 100 or image.height < 25:
                raise ValueError("Невалидна резолюция на логото.")
            return image.convert("RGBA")
        except Exception as error:
            last_error = error
            time.sleep(attempt + 1)
    raise RuntimeError(f"Не може да се изтегли официалното лого: {url}: {last_error}")


def trim_background(image: Image.Image) -> Image.Image:
    """Trim white margin, retaining the original branded pixels and colors."""
    alpha = image.getchannel("A")
    if alpha.getextrema()[0] < 250:
        bbox = alpha.point(lambda a: 255 if a > 32 else 0).getbbox()
    else:
        white = Image.new("RGB", image.size, "white")
        diff = ImageChops.difference(image.convert("RGB"), white)
        bbox = diff.convert("L").point(lambda p: 255 if p > 25 else 0).getbbox()
    return image.crop(bbox) if bbox else image


def main() -> None:
    ASSETS.mkdir(parents=True, exist_ok=True)
    for name, source in SOURCES.items():
        print(f"Downloading {name} from {source}", flush=True)
        image = trim_background(fetch_image(source))
        if image.width > 1100:
            ratio = 1100 / image.width
            image = image.resize(
                (1100, round(image.height * ratio)),
                Image.Resampling.LANCZOS,
            )
        destination = ASSETS / name
        image.save(destination, optimize=True)
        print(f"Bundled {destination.name}: {image.width}x{image.height}", flush=True)

    # Application icon from the official GTA emblem (left-hand side).
    gta = Image.open(ASSETS / "gta.png").convert("RGBA")
    # Cropped source begins with the GTA diamond, about 1:1 in aspect ratio.
    emblem_size = min(gta.height, int(gta.width * 0.31))
    emblem = gta.crop((0, 0, emblem_size, min(emblem_size, gta.height)))
    icon = Image.new("RGBA", (256, 256), "white")
    emblem.thumbnail((210, 210), Image.Resampling.LANCZOS)
    icon.alpha_composite(emblem, ((256 - emblem.width) // 2, (256 - emblem.height) // 2))
    icon.save(ASSETS / "app.ico", sizes=[(16, 16), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)])
    print("App icon bundled", flush=True)


if __name__ == "__main__":
    main()
