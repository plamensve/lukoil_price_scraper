"""Tests for import-only desktop workflow using Chrome-saved HTML."""
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from openpyxl import load_workbook

from lukoil_scraper.excel_export import export_excel
from lukoil_scraper.parser import filter_prices
from main import read_saved_html


HTML = """<!doctype html>
<html lang="bg"><head><meta charset="utf-8"></head><body>
<span id="MainContent_lblCaption">Ценова листа ЛУКОЙЛ в сила от 21.11.2026 0:00:00 ч.</span>
<table class="table table-bordered table-condensed table-sm">
<thead><tr class="info"><td colspan="2"><span>ЛУКОЙЛ Нефтохим</span></td>
<td colspan="4">Цени на продуктите</td><td colspan="3">Отстъпки</td></tr></thead>
<thead><tr class="active"><td hidden="hidden">Код</td><td>Вид гориво</td></tr></thead>
<tbody>
<tr><td hidden="hidden">040</td><td>Автомобилен бензин А-95Н E5</td>
<td>€/1000 л.</td><td><div>626.96 €</div></td><td>989.98 €</td>
<td>198.00 €</td><td>1187.98 €</td><td>2.97 €</td><td>1.48 €</td><td>0.00 €</td></tr>
</tbody></table></body></html>"""


class LocalHtmlTests(unittest.TestCase):
    def test_saved_utf8_html_and_excel(self):
        with TemporaryDirectory() as folder:
            source = Path(folder, "Лукойл - цени.html")
            source.write_bytes(HTML.encode("utf-8"))
            prices = read_saved_html(source)
            self.assertEqual(prices.effective_date, "21.11.2026")
            self.assertEqual(len(prices.rows), 1)
            self.assertEqual(prices.rows[0].product_code, "040")
            output = export_excel(
                filter_prices(prices, ("ЛУКОЙЛ Нефтохим",)),
                Path(folder, "result.xlsx"),
            )
            book = load_workbook(output)
            self.assertEqual(book["Всички цени"]["E5"].value, 626.96)
            self.assertEqual(book["Всички цени"]["B5"].value, "040")

    def test_saved_cp1251_html(self):
        markup = HTML.replace('charset="utf-8"', 'charset="windows-1251"')
        with TemporaryDirectory() as folder:
            path = Path(folder, "prices.html")
            path.write_bytes(markup.encode("cp1251"))
            prices = read_saved_html(path)
            self.assertEqual(prices.rows[0].product, "Автомобилен бензин А-95Н E5")

    def test_login_page_rejected(self):
        with TemporaryDirectory() as folder:
            source = Path(folder, "login.html")
            source.write_text("Въведете потребителско име и парола", encoding="utf-8")
            with self.assertRaises(ValueError):
                read_saved_html(source)

    def test_rejects_unrelated_file(self):
        with TemporaryDirectory() as folder:
            source = Path(folder, "not_html.txt")
            source.write_text(HTML, encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "HTML"):
                read_saved_html(source)


if __name__ == "__main__":
    unittest.main()
