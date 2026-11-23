"""Create Windows .ico from the selected Lukoil/GTA/Excel application artwork.

The source assets/selected_icon.webp is the user-selected app icon (a
desktop-size optimized rendition of the supplied image), committed to GitHub.
Builds are fully offline and never download or replace branding.
"""
from __future__ import annotations

from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
ASSETS = ROOT / "assets"
ICON_SOURCE = "selected_icon.webp"
ICON_SIZES = ((16, 16), (24, 24), (32, 32), (48, 48),
              (64, 64), (128, 128), (256, 256))


def make_icon() -> Path:
    source = ASSETS / ICON_SOURCE
    if not source.is_file():
        raise FileNotFoundError(
            f"Missing the selected desktop icon: {source}. "
            "The build must not fall back to an unrelated logo."
        )

    with Image.open(source) as artwork:
        square = artwork.convert("RGBA")
        if square.width != square.height:
            raise ValueError(
                f"App icon must be square; got {square.width}x{square.height}"
            )
        square = square.resize((256, 256), Image.Resampling.LANCZOS)

    output = ASSETS / "app.ico"
    square.save(output, format="ICO", sizes=ICON_SIZES)
    with Image.open(output) as check:
        actual = check.ico.sizes()
        if set(ICON_SIZES) - actual:
            raise RuntimeError(
                f"Windows .ico is missing expected resolutions: {set(ICON_SIZES) - actual}"
            )
    print(f"Created selected app icon: {output} ({len(ICON_SIZES)} sizes)", flush=True)
    return output


if __name__ == "__main__":
    make_icon()
