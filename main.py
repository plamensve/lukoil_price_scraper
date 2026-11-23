"""GTA Petroleum · Lukoil HTML price list -> Excel desktop utility.

Fully local workflow:
    Chrome (logged in) -> Ctrl+S -> HTML file -> Import -> Excel.
No browser debugging, extension, web server, or login automation required.
"""
from __future__ import annotations

from datetime import datetime
from pathlib import Path
import sys
import tkinter as tk
from tkinter import filedialog, messagebox

import customtkinter as ctk
from PIL import Image

from lukoil_scraper.excel_export import export_excel
from lukoil_scraper.parser import PriceList, filter_prices, parse_prices


ctk.set_appearance_mode("light")
ctk.set_default_color_theme("blue")

BG = "#EEF5F2"
WHITE = "#FFFFFF"
INK = "#173C37"
MUTED = "#57766F"
BORDER = "#D5E6E1"
TEAL = "#007269"
HOVER_GREEN = "#005B54"
SOFT = "#E4F3EF"
BLUE = "#007269"


def resource_path(name: str) -> Path:
    root = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent))
    return root / "assets" / name


def read_saved_html(filename: str | Path) -> PriceList:
    """Parse a locally saved HTML page; rely on BeautifulSoup's encoding detection."""
    path = Path(filename)
    if path.suffix.lower() not in {".html", ".htm"}:
        raise ValueError("Изберете HTML файл (.html или .htm), запазен от Chrome с Ctrl+S.")
    if not path.is_file():
        raise FileNotFoundError(f"HTML файлът не е намерен: {path}")
    if path.stat().st_size > 20_000_000:
        raise ValueError("HTML файлът е над 20 MB. Запазете само страницата с цените.")
    raw = path.read_bytes()
    if not raw:
        raise ValueError("HTML файлът е празен.")
    # BeautifulSoup detects HTML meta charset and Windows encodings.
    return parse_prices(raw)


class PriceScraperApp(ctk.CTk):
    def __init__(self) -> None:
        super().__init__()
        self.title("GTA Petroleum | Lukoil Price Export")
        self.geometry("1080x840")
        self.minsize(960, 790)
        self.configure(fg_color=BG)
        self.prices: PriceList | None = None
        self.source_file: Path | None = None
        self.terminal_vars: dict[str, tk.BooleanVar] = {}
        self.logo_images: list[ctk.CTkImage] = []
        self._build_ui()
        app_icon = resource_path("app.ico")
        if app_icon.is_file():
            try:
                self.iconbitmap(default=str(app_icon))
            except tk.TclError:
                pass
        self.after(60, self._set_windows_titlebar_color)

    def _set_windows_titlebar_color(self) -> None:
        """Apply a GTA-green native Windows title bar where supported."""
        if sys.platform != "win32":
            return
        try:
            import ctypes
            from ctypes import wintypes

            self.update_idletasks()
            hwnd = ctypes.windll.user32.GetParent(self.winfo_id()) or self.winfo_id()

            def colorref(value: str) -> int:
                r, g, b = (int(value[i:i + 2], 16) for i in (1, 3, 5))
                return r | (g << 8) | (b << 16)

            caption = ctypes.c_int(colorref(TEAL))
            foreground = ctypes.c_int(colorref("#FFFFFF"))
            change = ctypes.windll.dwmapi.DwmSetWindowAttribute
            change.argtypes = [wintypes.HWND, wintypes.DWORD, ctypes.c_void_p, wintypes.DWORD]
            change.restype = ctypes.c_long
            change(hwnd, 35, ctypes.byref(caption), ctypes.sizeof(caption))
            change(hwnd, 36, ctypes.byref(foreground), ctypes.sizeof(foreground))
        except (OSError, AttributeError, ValueError, tk.TclError):
            pass  # Windows versions without caption recoloring use system theme.

    def _card(self, parent, **kwargs) -> ctk.CTkFrame:
        return ctk.CTkFrame(
            parent, fg_color=WHITE, corner_radius=13,
            border_width=1, border_color=BORDER, **kwargs,
        )

    def _brand(self, parent, image_name: str, fallback: str,
               size: tuple[int, int]) -> None:
        path = resource_path(image_name)
        if path.is_file():
            try:
                with Image.open(path) as raw:
                    image = raw.convert("RGBA")
                target_w, target_h = size
                factor = min(target_w / image.width, target_h / image.height)
                actual = (max(1, round(image.width * factor)),
                          max(1, round(image.height * factor)))
                icon = ctk.CTkImage(light_image=image, dark_image=image, size=actual)
                self.logo_images.append(icon)
                ctk.CTkLabel(parent, image=icon, text="").pack(anchor="center")
                return
            except Exception:
                pass
        ctk.CTkLabel(parent, text=fallback, text_color=INK,
                     font=ctk.CTkFont(size=12, weight="bold")).pack()

    def _heading(self, parent, number: str, title: str) -> None:
        row = ctk.CTkFrame(parent, fg_color="transparent")
        row.pack(fill="x", padx=20, pady=(16, 10))
        ctk.CTkLabel(
            row, text=number, width=28, height=28, corner_radius=6,
            fg_color=SOFT, text_color=TEAL,
            font=ctk.CTkFont(size=12, weight="bold"),
        ).pack(side="left")
        ctk.CTkLabel(
            row, text=title, font=ctk.CTkFont(size=15, weight="bold"),
            text_color=INK,
        ).pack(side="left", padx=(10, 0))

    def _build_ui(self) -> None:
        # Compact brand row; not a large banner.
        header = ctk.CTkFrame(self, fg_color=WHITE, corner_radius=0, height=66)
        header.pack(side="top", fill="x")
        header.pack_propagate(False)
        brand_left = ctk.CTkFrame(header, fg_color="transparent")
        brand_left.pack(side="left", padx=(24, 0), pady=6)
        self._brand(brand_left, "gta.png", "GTA PETROLEUM", (225, 52))
        ctk.CTkLabel(
            header, text="ЛУКОЙЛ · Експорт на ценови листи",
            text_color=MUTED, font=ctk.CTkFont(size=13, weight="bold"),
        ).pack(side="right", padx=26)

        footer = ctk.CTkFrame(
            self, fg_color="#E0EEE9", height=38, corner_radius=0
        )
        footer.pack(side="bottom", fill="x")
        footer.pack_propagate(False)
        ctk.CTkLabel(
            footer, text="Created by Plamen Svetoslavov",
            font=ctk.CTkFont(size=11, weight="bold"),
            text_color=TEAL,
        ).pack(side="right", padx=20)

        # Regular frame: no unnecessary vertical scrollbar for 7 terminals.
        body = ctk.CTkFrame(self, fg_color="transparent", corner_radius=0)
        body.pack(fill="both", expand=True, padx=22, pady=(12, 4))

        import_card = self._card(body)
        import_card.pack(fill="x", pady=(0, 12))
        self._heading(import_card, "01", "Зареди запазена HTML страница")
        actions = ctk.CTkFrame(import_card, fg_color="transparent")
        actions.pack(fill="x", padx=20, pady=(0, 10))
        self.import_button = ctk.CTkButton(
            actions, text="Избери HTML файл", height=42, width=210,
            font=ctk.CTkFont(size=13, weight="bold"),
            fg_color=TEAL, hover_color=HOVER_GREEN,
            command=self._import_file,
        )
        self.import_button.pack(side="left")
        self.file_label = ctk.CTkLabel(
            actions, text="Не е избран файл", text_color=MUTED,
            font=ctk.CTkFont(size=12), anchor="w",
        )
        self.file_label.pack(side="left", padx=15, fill="x", expand=True)

        ctk.CTkLabel(
            import_card,
            text=(
                "Инструкции:\n"
                "1. Влез в Лукойл и отвори страницата с цените.\n"
                "2. Натисни Ctrl+S и запази като „Уеб страница, само HTML“ (.htm/.html).\n"
                "3. Избери запазения файл по-горе, маркирай терминалите и натисни „Експорт в Excel“."
            ),
            font=ctk.CTkFont(size=12),
            text_color=MUTED,
            justify="left",
            anchor="w",
            wraplength=900,
        ).pack(fill="x", padx=20, pady=(0, 10))

        self.summary_label = ctk.CTkLabel(
            import_card, text="Очаква се HTML файл с ценовите таблици.",
            height=33, fg_color="#F4F7FA", corner_radius=7, text_color=MUTED,
            font=ctk.CTkFont(size=12),
        )
        self.summary_label.pack(fill="x", padx=20, pady=(0, 13))

        terminal_card = self._card(body)
        terminal_card.pack(fill="x", pady=(0, 10))
        self._heading(terminal_card, "02", "Избери терминалите за експорт")

        selection_bar = ctk.CTkFrame(terminal_card, fg_color="transparent")
        selection_bar.pack(fill="x", padx=20, pady=(0, 8))
        self.terminal_hint = ctk.CTkLabel(
            selection_bar, text="Терминалите ще се покажат след импортиране.",
            text_color=MUTED, font=ctk.CTkFont(size=12),
        )
        self.terminal_hint.pack(side="left")
        self.toggle_button = ctk.CTkButton(
            selection_bar, text="Избери / изчисти всички", width=165,
            height=29, fg_color=SOFT, hover_color="#CCE9E1",
            text_color=BLUE, command=self._toggle_all, state="disabled",
        )
        self.toggle_button.pack(side="right")
        self.terminal_grid = ctk.CTkFrame(
            terminal_card, fg_color="#F4FAF7", corner_radius=8,
        )
        self.terminal_grid.pack(fill="x", padx=20, pady=(0, 13))
        self.terminal_grid.grid_columnconfigure((0, 1), weight=1)
        ctk.CTkLabel(
            self.terminal_grid, text="Няма заредени терминали.",
            text_color=MUTED, font=ctk.CTkFont(size=12),
        ).grid(row=0, column=0, sticky="w", padx=14, pady=15)

        export_card = self._card(body)
        export_card.pack(fill="x", pady=(0, 12))
        self._heading(export_card, "03", "Създай Excel файл")
        self.export_button = ctk.CTkButton(
            export_card, text="Експорт в Excel (.xlsx)",
            height=48, fg_color=TEAL, hover_color=HOVER_GREEN,
            font=ctk.CTkFont(size=15, weight="bold"),
            command=self._export, state="disabled",
        )
        self.export_button.pack(fill="x", padx=20, pady=(0, 17))

        self.status_label = ctk.CTkLabel(
            footer, text="Готово за работа · Всички данни се обработват локално",
            text_color=MUTED, fg_color="transparent", anchor="w",
            height=38, corner_radius=0, font=ctk.CTkFont(size=11),
        )
        self.status_label.pack(side="left", fill="x", expand=True, padx=(12, 0))

    def _set_status(self, message: str, success: bool = False) -> None:
        self.status_label.configure(
            text="  " + message,
            text_color=TEAL if success else MUTED,
        )

    def _selected(self) -> tuple[str, ...]:
        return tuple(name for name, var in self.terminal_vars.items() if var.get())

    def _update_export_button(self) -> None:
        valid = self.prices is not None and bool(self._selected())
        self.export_button.configure(state="normal" if valid else "disabled")

    def _toggle_all(self) -> None:
        select = not all(var.get() for var in self.terminal_vars.values())
        for var in self.terminal_vars.values():
            var.set(select)
        self._update_export_button()

    def _render_terminals(self) -> None:
        for widget in self.terminal_grid.winfo_children():
            widget.destroy()
        self.terminal_vars.clear()
        if not self.prices:
            self.toggle_button.configure(state="disabled")
            return
        self.toggle_button.configure(state="normal")
        totals: dict[str, int] = {}
        for row in self.prices.rows:
            totals[row.terminal] = totals.get(row.terminal, 0) + 1
        for index, (name, count) in enumerate(totals.items()):
            var = tk.BooleanVar(value=True)
            self.terminal_vars[name] = var
            checkbox = ctk.CTkCheckBox(
                self.terminal_grid, text=f"{name}   ({count})",
                variable=var, text_color=INK, command=self._update_export_button,
                fg_color=TEAL, hover_color=HOVER_GREEN,
                font=ctk.CTkFont(size=12), checkbox_width=19,
                checkbox_height=19, border_width=2,
            )
            checkbox.grid(
                row=index // 2, column=index % 2, sticky="w",
                padx=15, pady=(10 if index < 2 else 5, 8),
            )
        self.terminal_hint.configure(text=f"Намерени {len(totals)} терминала")

    def _clear_data(self) -> None:
        self.prices = None
        self.source_file = None
        self.file_label.configure(text="Не е избран файл", text_color=MUTED)
        self.summary_label.configure(text="Очаква се HTML файл с ценовите таблици.")
        self._render_terminals()
        self._update_export_button()

    def _import_file(self) -> None:
        filename = filedialog.askopenfilename(
            parent=self, title="Избери HTML файл от Лукойл",
            filetypes=[
                ("HTML страници", "*.html *.htm"),
                ("Всички файлове", "*.*"),
            ],
        )
        if not filename:
            return
        # Invalidate previously loaded data even if this import fails.
        self._clear_data()
        try:
            prices = read_saved_html(filename)
        except Exception as exc:
            self._set_status("Неуспешно зареждане на HTML файла.")
            messagebox.showerror(
                "Неуспешен импорт",
                f"Не успях да разпозная ценовата листа.\n\n{exc}\n\n"
                "Увери се, че си запазил страницата с цените, а не страницата за вход.",
                parent=self,
            )
            return

        self.prices = prices
        self.source_file = Path(filename)
        self.file_label.configure(text=self.source_file.name, text_color=INK)
        date_text = prices.effective_date or "не е посочена"
        self.summary_label.configure(
            text=f"✓  {len(prices.rows)} ценови реда · "
                 f"{len(prices.terminals)} терминала · В сила от: {date_text}",
            text_color=TEAL, fg_color=SOFT,
        )
        self._render_terminals()
        self._update_export_button()
        self._set_status(f"Успешно заредена ценова листа: {self.source_file.name}", True)

    def _export(self) -> None:
        if self.prices is None:
            messagebox.showwarning("Няма данни", "Първо зареди HTML файл.", parent=self)
            return
        selected = self._selected()
        if not selected:
            messagebox.showwarning("Няма избор", "Избери поне един терминал.", parent=self)
            return
        safe_date = self.prices.effective_date.replace(".", "-") or datetime.now().strftime("%d-%m-%Y")
        target = filedialog.asksaveasfilename(
            parent=self, title="Запази ценова листа в Excel",
            defaultextension=".xlsx",
            filetypes=[("Excel Workbook", "*.xlsx")],
            initialfile=f"Lukoil_Prices_{safe_date}.xlsx",
        )
        if not target:
            return
        try:
            prices = filter_prices(self.prices, selected)
            destination = export_excel(prices, target)
        except Exception as exc:
            self._set_status("Грешка при Excel експорта.")
            messagebox.showerror("Грешка при Excel експорта", str(exc), parent=self)
            return
        self._set_status(f"Excel файлът е записан: {destination}", True)
        messagebox.showinfo(
            "Успешен експорт",
            f"Записани {len(prices.rows)} реда от {len(prices.terminals)} терминала.\n\n{destination}",
            parent=self,
        )


if __name__ == "__main__":
    app = PriceScraperApp()
    app.mainloop()
