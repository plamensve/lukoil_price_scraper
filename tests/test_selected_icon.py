"""Confirm that the Windows EXE uses the selected artwork, not a fallback."""
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch
import shutil
import unittest

from PIL import Image
from tools import build_assets


class SelectedIconTests(unittest.TestCase):
    def test_windows_icon_contains_256_and_smaller_sizes(self):
        selected = build_assets.ROOT / "assets" / "selected_icon.webp"
        self.assertTrue(selected.is_file(), "Selected icon not committed")
        with TemporaryDirectory() as folder:
            assets = Path(folder)
            shutil.copyfile(selected, assets / "selected_icon.webp")
            with patch.object(build_assets, "ASSETS", assets):
                result = build_assets.make_icon()
            self.assertEqual(result, assets / "app.ico")
            with Image.open(result) as icon:
                self.assertTrue(set(build_assets.ICON_SIZES).issubset(icon.ico.sizes()))
                self.assertEqual(icon.ico.getimage((256, 256)).size, (256, 256))

    def test_no_fallback_to_unrelated_logo(self):
        with TemporaryDirectory() as folder:
            with patch.object(build_assets, "ASSETS", Path(folder)):
                with self.assertRaises(FileNotFoundError):
                    build_assets.make_icon()


if __name__ == "__main__":
    unittest.main()
