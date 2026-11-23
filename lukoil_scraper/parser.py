"""Parse the authenticated Lukoil wholesale price table."""
from __future__ import annotations

from dataclasses import dataclass
import re

from bs4 import BeautifulSoup
from bs4.element import Tag


TARGET_URL = "https://wholesale.lukoil.bg/orders/CeniTermList01072022"

TERMINALS = (
    "ЛУКОЙЛ Нефтохим",
    "ПСБ АСПАРУХОВО",
    "ПСБ ИЛИЯНЦИ",
    "ПСБ КАРНОБАТ",
    "ПСБ ПЛОВДИВ",
    "ПСБ РУСЕ",
    "ПСБ СТАРА ЗАГОРА",
)


class ScrapeError(ValueError):
    """The requested price table could not be parsed."""


@dataclass(frozen=True)
class PriceRow:
    terminal: str
    product_code: str
    product: str
    unit: str
    net_price: str
    tax_base: str
    vat: str
    gross_price: str
    advance_discount: str
    discount_15_days: str
    discount_30_days: str


@dataclass(frozen=True)
class PriceList:
    title: str
    effective_date: str
    rows: tuple[PriceRow, ...]

    @property
    def terminals(self) -> tuple[str, ...]:
        return tuple(dict.fromkeys(row.terminal for row in self.rows))


def _text(element: Tag) -> str:
    return " ".join(element.get_text(" ", strip=True).split())


def _is_hidden(element: Tag) -> bool:
    if element.has_attr("hidden") or element.get("aria-hidden") == "true":
        return True
    style = re.sub(r"\s+", "", element.get("style", "")).lower()
    return "display:none" in style


def _table_cells(tr: Tag) -> tuple[list[Tag], list[Tag]]:
    cells = tr.find_all(["td", "th"], recursive=False)
    return ([cell for cell in cells if not _is_hidden(cell)],
            [cell for cell in cells if _is_hidden(cell)])


def _page_title(soup: BeautifulSoup) -> str:
    caption = soup.find(id=re.compile(r"lblCaption$", re.I))
    if isinstance(caption, Tag):
        return _text(caption)
    for span in soup.find_all("span"):
        value = _text(span)
        if value.startswith("Ценова листа") and "в сила от" in value:
            return value
    return ""


def _terminal_header(section: Tag) -> str | None:
    """Find terminal headings, not column headings, within a thead."""
    for tr in section.find_all("tr", recursive=False):
        if "info" not in (tr.get("class") or []):
            continue
        visible, _ = _table_cells(tr)
        if not visible:
            continue
        candidate = _text(visible[0])
        if candidate.startswith(("ЛУКОЙЛ", "ПСБ")):
            return candidate
    return None


def parse_prices(html: str) -> PriceList:
    """Read repeated THEAD/TBODY blocks into complete price records.

    This page is not a conventional single-header HTML table. Each terminal
    has its own heading, column heading and tbody within the same table.
    """
    soup = BeautifulSoup(html, "html.parser")
    title = _page_title(soup)
    match = re.search(r"\b(\d{2}\.\d{2}\.\d{4})\b", title)
    effective_date = match.group(1) if match else ""
    rows: list[PriceRow] = []

    for table in soup.select("table.table-bordered"):
        terminal: str | None = None
        for section in table.find_all(["thead", "tbody"], recursive=False):
            if section.name == "thead":
                new_terminal = _terminal_header(section)
                if new_terminal:
                    terminal = new_terminal
                continue

            if not terminal:
                continue

            for tr in section.find_all("tr", recursive=False):
                visible, hidden = _table_cells(tr)
                # 9 visible columns: fuel, unit, 4 prices, and 3 discounts.
                if len(visible) != 9:
                    continue

                values = [_text(cell) for cell in visible]
                if not values[0] or values[0] in {"Вид гориво", "Общо"}:
                    continue

                product_code = _text(hidden[0]) if hidden else ""
                rows.append(
                    PriceRow(
                        terminal=terminal,
                        product_code=product_code,
                        product=values[0],
                        unit=values[1],
                        net_price=values[2],
                        tax_base=values[3],
                        vat=values[4],
                        gross_price=values[5],
                        advance_discount=values[6],
                        discount_15_days=values[7],
                        discount_30_days=values[8],
                    )
                )

    if not rows:
        body_text = soup.get_text(" ", strip=True)
        if "Въведете потребителско име и парола" in body_text or "Въведете кода от картинката" in body_text:
            raise ScrapeError("Няма активен вход. Влезте в браузъра и попълнете CAPTCHA.")
        raise ScrapeError(
            "Не са намерени ценови редове. Проверете входа или дали HTML структурата е променена."
        )

    return PriceList(title=title, effective_date=effective_date, rows=tuple(rows))


def filter_prices(price_list: PriceList, terminals: tuple[str, ...]) -> PriceList:
    if not terminals:
        raise ScrapeError("Изберете поне един терминал.")
    allowed = {" ".join(name.upper().split()) for name in terminals}
    selected = tuple(
        row for row in price_list.rows
        if " ".join(row.terminal.upper().split()) in allowed
    )
    if not selected:
        available = ", ".join(price_list.terminals)
        raise ScrapeError(f"Няма данни за избраните терминали. Налични: {available}")
    return PriceList(
        title=price_list.title,
        effective_date=price_list.effective_date,
        rows=selected,
    )
