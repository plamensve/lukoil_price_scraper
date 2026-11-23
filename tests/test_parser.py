"""Deterministic parser/export tests using synthetic, non-secret HTML."""
import tempfile
import unittest
from pathlib import Path

from openpyxl import load_workbook

from lukoil_scraper.excel_export import export_excel
from lukoil_scraper.parser import ScrapeError, filter_prices, parse_prices


HTML = """
<span id="MainContent_lblCaption">Ценова листа ЛУКОЙЛ БЪЛГАРИЯ ЕООД в сила от 21.11.2026 0:00:00 ч.</span>
<table class="table table-bordered table-condensed table-sm">
  <thead><tr class="info"><td colspan="2"><span>ЛУКОЙЛ Нефтохим</span></td>
    <td colspan="4">Цени на продуктите</td><td colspan="3">Отстъпки</td></tr></thead>
  <thead><tr class="active"><td hidden="hidden">Код</td><td>Вид гориво</td></tr></thead>
  <tbody><tr><td hidden="hidden"><span>040</span></td>
    <td><span>Автомобилен бензин А-95Н E5</span></td><td class="text-centre">€/1000 л.</td>
    <td><div>626.96 €</div></td><td><div>989.98 €</div></td>
    <td>198.00 €</td><td>1187.98 €</td><td>2.97 €</td><td>1.48 €</td><td>0.00 €</td>
  </tr></tbody>
  <thead><tr class="info"><td colspan="2">ПСБ РУСЕ</td><td colspan="4">Цени</td></tr></thead>
  <thead><tr class="active"><td>Вид гориво</td></tr></thead>
  <tbody><tr><td hidden="hidden">041</td><td>Дизел E5</td><td>€/1000 л.</td>
    <td>969.89 €</td><td>1300.18 €</td><td>260.04 €</td>
    <td>1560.22 €</td><td>3.90 €</td><td>1.95 €</td><td>0.00 €</td>
  </tr></tbody>
</table>
"""


class ParserTests(unittest.TestCase):
    def test_repeated_sections_and_hidden_code(self):
        result = parse_prices(HTML)
        self.assertEqual(result.effective_date, "21.11.2026")
        self.assertEqual(len(result.rows), 2)
        self.assertEqual(result.terminals, ("ЛУКОЙЛ Нефтохим", "ПСБ РУСЕ"))
        self.assertEqual(result.rows[0].product_code, "040")
        self.assertEqual(result.rows[0].net_price, "626.96 €")
        self.assertEqual(result.rows[1].gross_price, "1560.22 €")

    def test_filter_by_terminal(self):
        result = filter_prices(parse_prices(HTML), ("ПСБ РУСЕ",))
        self.assertEqual(len(result.rows), 1)
        self.assertEqual(result.rows[0].product_code, "041")

    def test_missing_or_login_page_is_not_exported(self):
        with self.assertRaises(ScrapeError):
            parse_prices("<html><body>Въведете потребителско име и парола</body></html>")

    def test_excel_numeric_columns(self):
        with tempfile.TemporaryDirectory() as folder:
            output = export_excel(parse_prices(HTML), Path(folder) / "prices.xlsx")
            workbook = load_workbook(output)
            self.assertEqual(len(workbook.sheetnames), 3)
            self.assertEqual(workbook["Всички цени"]["B5"].value, "040")
            self.assertEqual(workbook["Всички цени"]["E5"].value, 626.96)
            self.assertEqual(workbook["Всички цени"]["H6"].value, 1560.22)
            self.assertEqual(workbook["ПСБ РУСЕ"]["C5"].value, "Дизел E5")


if __name__ == "__main__":
    unittest.main()
