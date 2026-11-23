"""Desktop-only Chrome CDP scraping; no extension, cookies, or CAPTCHA handling.

The program launches Chrome with a dedicated persistent profile on localhost.
The user logs in directly in Chrome and leaves the price-list tab open.
We extract DOM HTML from that tab; verify/export NEVER navigates it.
"""
from __future__ import annotations

import os
from pathlib import Path
from queue import Queue
import shutil
import subprocess
from threading import Thread
import time
from typing import Any
from urllib.parse import urlsplit

from playwright.sync_api import Browser, BrowserContext, Page, Playwright, sync_playwright

from .excel_export import export_excel
from .parser import TARGET_URL, filter_prices, parse_prices


# Local-only debugging interface. Never bind the debugging port publicly.
CDP_HOST = "127.0.0.1"
CDP_PORT = 9333


def profile_directory() -> Path:
    """Separate Chrome profile so Chrome >= 136 accepts remote debugging."""
    local = os.getenv("LOCALAPPDATA")
    root = Path(local) if local else Path.home() / ".local" / "share"
    return root / "LukoilPriceScraper" / "ChromeProfile"


def find_chrome() -> str:
    """Find a locally installed Chromium-based browser on Windows."""
    choices = []
    for variable in ("PROGRAMFILES", "PROGRAMFILES(X86)", "LOCALAPPDATA"):
        root = os.environ.get(variable)
        if root:
            choices.extend((
                Path(root) / "Google" / "Chrome" / "Application" / "chrome.exe",
                Path(root) / "Microsoft" / "Edge" / "Application" / "msedge.exe",
            ))
    for choice in choices:
        if choice.is_file():
            return str(choice)
    for name in ("chrome", "msedge", "google-chrome", "chromium"):
        binary = shutil.which(name)
        if binary:
            return binary
    raise RuntimeError("Не е намерен Google Chrome или Microsoft Edge на компютъра.")


def is_price_url(url: str) -> bool:
    """Only read prices from the exact allowed Lukoil host and page family."""
    parsed = urlsplit(url)
    return (
        parsed.scheme == "https"
        and (parsed.hostname or "").lower() == "wholesale.lukoil.bg"
        and parsed.path.lower().startswith("/orders/cenitermlist")
    )


def find_price_tab(context: BrowserContext) -> Page | None:
    """Pick the newest open price-list tab. Ignore unrelated browser content."""
    pages = [page for page in context.pages if not page.is_closed()]
    return next((p for p in reversed(pages) if is_price_url(p.url)), None)


class BrowserWorker(Thread):
    """Own the Playwright sync API entirely within a dedicated worker thread."""

    def __init__(self) -> None:
        super().__init__(name="lukoil-browser", daemon=True)
        self.commands: Queue[tuple[str, Any]] = Queue()
        self.events: Queue[tuple[str, Any]] = Queue()
        self._playwright: Playwright | None = None
        self._browser: Browser | None = None
        # Avoid _context: Thread uses this attribute internally on some Python versions.
        self._browser_context: BrowserContext | None = None
        self._chrome_process: subprocess.Popen | None = None

    def submit(self, command: str, value: Any = None) -> None:
        self.commands.put((command, value))

    def _connect(self) -> BrowserContext:
        if self._browser is not None and self._browser.is_connected():
            assert self._browser_context is not None
            return self._browser_context

        if self._playwright is None:
            self._playwright = sync_playwright().start()

        endpoint = f"http://{CDP_HOST}:{CDP_PORT}"
        try:
            browser = self._playwright.chromium.connect_over_cdp(endpoint, timeout=2500)
            self.events.put(("log", "Свързах се с Chrome, стартиран с remote debugging."))
        except Exception:
            profile = profile_directory()
            profile.mkdir(parents=True, exist_ok=True)
            executable = find_chrome()
            flags = [
                executable,
                f"--remote-debugging-address={CDP_HOST}",
                f"--remote-debugging-port={CDP_PORT}",
                f"--user-data-dir={profile}",
                "--no-first-run",
                "--no-default-browser-check",
                TARGET_URL,
            ]
            # A dedicated user data dir is required by newer Chrome releases.
            self._chrome_process = subprocess.Popen(
                flags, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
            )
            browser = None
            last_error: Exception | None = None
            for _ in range(40):
                time.sleep(0.35)
                try:
                    browser = self._playwright.chromium.connect_over_cdp(
                        endpoint, timeout=1250
                    )
                    break
                except Exception as exc:
                    last_error = exc
                    if self._chrome_process.poll() is not None:
                        break
            if browser is None:
                raise RuntimeError(
                    "Не успях да се свържа с Chrome на 127.0.0.1:9333. "
                    "Проверете дали портът не е зает или Chrome не блокира "
                    "remote debugging. " + str(last_error or "")
                )
            self.events.put((
                "log",
                "Chrome е стартиран с отделен локален профил. "
                "При нужда влезте в Лукойл ръчно; CAPTCHA не се автоматизира.",
            ))

        self._browser = browser
        if not browser.contexts:
            raise RuntimeError("Chrome няма достъпен контекст за четене на табове.")
        self._browser_context = browser.contexts[0]
        return self._browser_context

    def _open_page(self) -> None:
        context = self._connect()
        price_page = find_price_tab(context)
        if price_page is not None:
            price_page.bring_to_front()
            return
        # Only an explicit button click opens the target page.
        page = context.new_page()
        page.goto(TARGET_URL, wait_until="domcontentloaded", timeout=45000)
        page.bring_to_front()

    def _read_prices(self):
        """Read the CURRENT tab DOM, without reopening or refreshing the page."""
        if self._browser_context is None or self._browser is None:
            raise RuntimeError("Първо натиснете „Отвори Chrome за цените“.")
        context = self._connect()
        page = find_price_tab(context)
        if page is None:
            raise RuntimeError(
                "Няма отворен таб с цените на Лукойл в Chrome, "
                "стартиран чрез приложението. Влезте и отворете ценовата листа."
            )
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
                        self._open_page()
                        self.events.put(("opened", None))
                    elif command == "verify":
                        prices = self._read_prices()
                        self.events.put(("verified", (len(prices.rows), prices.terminals)))
                    elif command == "export":
                        filename, terminals = payload
                        prices = filter_prices(self._read_prices(), terminals)
                        destination = export_excel(prices, filename)
                        self.events.put((
                            "exported",
                            (str(destination), len(prices.rows), prices.terminals),
                        ))
                except Exception as exc:
                    self.events.put(("error", str(exc)))
                finally:
                    self.events.put(("idle", None))
        finally:
            # Close our CDP connection. Do not forcibly close an existing user's
            # browser: any Chrome window that remains open can be reused later.
            if self._browser is not None:
                try:
                    self._browser.close()
                except Exception:
                    pass
            if self._playwright is not None:
                try:
                    self._playwright.stop()
                except Exception:
                    pass
