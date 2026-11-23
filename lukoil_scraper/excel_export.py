"""Generate structured XLSX reports from Lukoil price rows."""
from __future__ import annotations

from collections import defaultdict
from datetime import datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path
import re

from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter

from .parser import PriceList, PriceRow


HEADERS = (
    "Терминал", "Код", "Вид гориво", "Мерна единица",
    "Нетна цена", "Данъчна основа", "ДДС", "Цена с ДДС",
    "Отстъпка аванс", "Отстъпка 15 дни", "Отстъпка 30 дни",
)
NUMERIC_COLUMNS = range(5, 12)
WIDTHS = (25, 12, 58, 16, 18, 20, 16, 18, 22, 22, 22)


def _amount(value: str) -> float | str:
    normalized = re.sub(r"[\s\u00a0€]", "", value.strip())
    if not re.fullmatch(r"-?\d+(?:[.,]\d+)?", normalized):
        return value
    try:
        return float(Decimal(normalized.replace(",", ".")))
    except InvalidOperation:
        return value


def _safe_string(value: str) -> str:
    # Excel should never interpret scraped product names as formulas.
    return value


def _sheet_name(name: str, existing: set[str]) -> str:
    base = re.sub(r"[:\\/*?\[\]]", "_", name).strip("' ")[:31] or "Терминал"
    candidate = base
    counter = 2
    while candidate.lower() in existing:
        suffix = f"_{counter}"
        candidate = base[:31 - len(suffix)] + suffix
        counter += 1
    existing.add(candidate.lower())
    return candidate


def _add_sheet(ws, price_list: PriceList, rows: list[PriceRow]) -> None:
    ws.sheet_view.showGridLines = False
    ws.merge_cells(start_row=1, start_column=1, end_row=1, end_column=len(HEADERS))
    ws["A1"] = price_list.title or "Ценова листа ЛУКОЙЛ"
    ws["A1"].font = Font(size=15, bold=True, color="FFFFFF")
    ws["A1"].fill = PatternFill("solid", fgColor="17324D")
    ws["A1"].alignment = Alignment(vertical="center")
    ws.row_dimensions[1].height = 30

    date_text = price_list.effective_date or "не е посочена"
    ws["A2"] = f"В сила от: {date_text} | Експорт: {datetime.now():%d.%m.%Y %H:%M}"
    ws["A2"].font = Font(italic=True, color="56697A")
    ws.row_dimensions[2].height = 25

    for index, heading in enumerate(HEADERS, start=1):
        cell = ws.cell(4, index, heading)
        cell.fill = PatternFill("solid", fgColor="267DB8")
        cell.font = Font(bold=True, color="FFFFFF")
        cell.alignment = Alignment(wrap_text=True, vertical="center")
    ws.row_dimensions[4].height = 30

    for row_number, item in enumerate(rows, start=5):
        values = (
            item.terminal, item.product_code, item.product, item.unit,
            item.net_price, item.tax_base, item.vat, item.gross_price,
            item.advance_discount, item.discount_15_days,
            item.discount_30_days,
        )
        for column, value in enumerate(values, start=1):
            result = _amount(value) if column in NUMERIC_COLUMNS else _safe_string(value)
            cell = ws.cell(row_number, column, result)
            if isinstance(result, str):
                cell.data_type = "s"
            else:
                cell.number_format = '#,##0.00 "€"'
            cell.alignment = Alignment(vertical="center", wrap_text=column == 3)
            if row_number % 2 == 0:
                cell.fill = PatternFill("solid", fgColor="EEF5FA")

    for index, width in enumerate(WIDTHS, start=1):
        ws.column_dimensions[get_column_letter(index)].width = width
    ws.freeze_panes = "E5"
    ws.auto_filter.ref = f"A4:K{max(5, len(rows) + 4)}"
    ws.sheet_properties.pageSetUpPr.fitToPage = True


def export_excel(price_list: PriceList, output: str | Path) -> Path:
    """Export all rows and one sheet per terminal, never overwriting on parse failure."""
    if not price_list.rows:
        raise ValueError("Няма редове за запис в Excel.")
    destination = Path(output).expanduser()
    destination.parent.mkdir(parents=True, exist_ok=True)

    book = Workbook()
    summary = book.active
    summary.title = "Всички цени"
    _add_sheet(summary, price_list, list(price_list.rows))

    grouped: dict[str, list[PriceRow]] = defaultdict(list)
    for row in price_list.rows:
        grouped[row.terminal].append(row)

    names = {summary.title.lower()}
    for terminal, items in grouped.items():
        sheet = book.create_sheet(_sheet_name(terminal, names))
        _add_sheet(sheet, price_list, items)

    book.save(destination)
    return destination
