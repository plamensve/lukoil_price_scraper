"""CDP price tab selection tests with mocked browser objects."""
import unittest
from unittest.mock import MagicMock

from lukoil_scraper.browser import BrowserWorker, find_price_tab, is_price_url


class BrowserTabTests(unittest.TestCase):
    def test_only_lukoil_price_list_allowed(self):
        self.assertTrue(is_price_url("https://wholesale.lukoil.bg/orders/CeniTermList01072022"))
        self.assertFalse(is_price_url("https://wholesale.lukoil.bg/orders/Login.aspx"))
        self.assertFalse(is_price_url("https://evil.example/orders/CeniTermList01072022"))
        self.assertFalse(is_price_url("http://wholesale.lukoil.bg/orders/CeniTermList01072022"))

    def test_uses_latest_open_price_tab(self):
        context = MagicMock()
        other = MagicMock()
        other.url = "https://example.com"
        other.is_closed.return_value = False
        price = MagicMock()
        price.url = "https://wholesale.lukoil.bg/orders/CeniTermList01072022"
        price.is_closed.return_value = False
        context.pages = [other, price]
        self.assertIs(find_price_tab(context), price)

    def test_reads_existing_page_without_navigation(self):
        worker = BrowserWorker()
        context = MagicMock()
        price = MagicMock()
        price.url = "https://wholesale.lukoil.bg/orders/CeniTermList01072022"
        price.is_closed.return_value = False
        price.locator.return_value.count.return_value = 1
        price.content.return_value = "<html>read without navigating</html>"
        context.pages = [price]
        worker._browser_context = context
        worker._browser = MagicMock()
        worker._browser.is_connected.return_value = True
        self.assertIs(worker._connect(), context)
        with self.assertRaisesRegex(ValueError, "ценови редове"):
            worker._read_prices()
        price.goto.assert_not_called()
        price.reload.assert_not_called()
        price.content.assert_called_once()


if __name__ == "__main__":
    unittest.main()
