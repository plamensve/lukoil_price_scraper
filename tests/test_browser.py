"""Regression tests for browser thread state, without launching Chrome."""
from contextvars import Context
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from lukoil_scraper.browser import BrowserWorker


class BrowserWorkerTests(unittest.TestCase):
    def test_thread_context_does_not_mask_playwright_browser_context(self):
        worker = BrowserWorker()
        # This reproduces the reserved attribute collision that caused
        # "'_contextvars.Context' object has no attribute 'pages'".
        worker._context = Context()
        fake_page = MagicMock()
        fake_page.is_closed.return_value = False
        fake_context = MagicMock()
        fake_context.pages = [fake_page]

        fake_playwright = MagicMock()
        fake_playwright.chromium.launch_persistent_context.return_value = fake_context
        worker._playwright = fake_playwright

        with tempfile.TemporaryDirectory() as folder:
            with patch("lukoil_scraper.browser.profile_directory", return_value=Path(folder)):
                page = worker._ensure_browser()
                self.assertIs(page, fake_page)
                self.assertIs(worker._browser_context, fake_context)
                # Calling again must reuse the real Playwright browser context
                self.assertIs(worker._ensure_browser(), fake_page)
                fake_playwright.chromium.launch_persistent_context.assert_called_once()
                self.assertIsInstance(worker._context, Context)


if __name__ == "__main__":
    unittest.main()
