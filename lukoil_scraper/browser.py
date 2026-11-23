"""Dedicated Playwright worker; all browser calls stay on one thread."""
from __future__ import annotations

import os
from pathlib import Path
from queue import Queue
from threading import Thread
from typing import Any

from playwright.sync_api import BrowserContext, Page, Playwright, sync_playwright

from .excel_export import export_excel
from .parser import TARGET_URL, filter_prices, parse_prices


def profile_directory() -> Path:
    """Store browser state per Windows user, outside the EXE/repository."""
    local = os.getenv("LOCALAPPDATA")
    root = Path(local) if local else Path.home() / ".local" / "share"
    return root / "LukoilPriceScraper" / "BrowserProfile"


class BrowserWorker(Thread):
    """Accept simple commands and emit events; never touch Tk from this thread."""

    def __init__(self) -> None:
        super().__init__(name="lukoil-browser", daemon=True)
        self.commands: Queue[tuple[str, Any]] = Queue()
        self.events: Queue[tuple[str, Any]] = Queue()
        self._playwright: Playwright | None = None
        self._context: BrowserContext | None = None
        self._page: Page | None = None

    def submit(self, command: str, value: Any = None) -> None:
        self.commands.put((command, value))

    def _ensure_browser(self) -> Page:
        if self._context is not None:
            pages = [p for p in self._context.pages if not p.is_closed()]
            self._page = self._page if self._page in pages else None
            if self._page is None:
                self._page = pages[0] if pages else self._context.new_page()
            return self._page

        if self._playwright is None:
            self._playwright = sync_playwright().start()

        folder = profile_directory()
        folder.mkdir(parents=True, exist_ok=True)

        failures = []
        for channel in ("chrome", "msedge"):
            try:
                self._context = self._playwright.chromium.launch_persistent_context(
                    user_data_dir=str(folder),
                    channel=channel,
                    headless=False,
                    accept_downloads=False,
                    no_viewport=True,
                )
                self._page = (
                    self._context.pages[0]
                    if self._context.pages
                    else self._context.new_page()
                )
                self.events.put(("log", f"Стартиран браузър: {channel}."))
                return self._page
            except Exception as exc:
                failures.append(f"{channel}: {str(exc).splitlines()[0]}")

        raise RuntimeError(
            "Не успях да стартирам Chrome или Edge. "
            "Уверете се, че е инсталиран и че друг прозорец на приложението "
            "не използва същия профил. " + " | ".join(failures)
        )

    def _visit_price_page(self) -> Page:
        page = self._ensure_browser()
        page.goto(TARGET_URL, wait_until="domcontentloaded", timeout=45000)
        return page

    def _read_prices(self):
        page = self._visit_price_page()
        # Most responses are server-rendered. Also allow the table to load
        # asynchronously if the server later changes its implementation.
        if page.locator("table.table-bordered tbody tr").count() == 0:
            try:
                page.locator("table.table-bordered tbody tr").first.wait_for(
                    state="attached", timeout=5000
                )
            except Exception:
                pass
        return parse_prices(page.content())

    def run(self) -> None:
        try:
            while True:
                command, payload = self.commands.get()
                if command == "stop":
                    break
                try:
                    if command == "open":
                        self._visit_price_page()
                        self.events.put(("opened", None))
                    elif command == "verify":
                        prices = self._read_prices()
                        self.events.put(("verified", (len(prices.rows), prices.terminals)))
                    elif command == "export":
                        filename, terminals = payload
                        prices = filter_prices(self._read_prices(), terminals)
                        destination = export_excel(prices, filename)
                        self.events.put(("exported", (str(destination), len(prices.rows), prices.terminals)))
                except Exception as exc:
                    self.events.put(("error", str(exc)))
                finally:
                    self.events.put(("idle", None))
        finally:
            if self._context is not None:
                try:
                    self._context.close()
                except Exception:
                    pass
            if self._playwright is not None:
                try:
                    self._playwright.stop()
                except Exception:
                    pass
