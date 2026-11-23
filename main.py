"""CustomTkinter desktop app for authenticated Lukoil wholesale prices."""
from __future__ import annotations

from datetime import datetime
from pathlib import Path
from queue import Empty
import tkinter as tk
from tkinter import filedialog, messagebox

import customtkinter as ctk

from lukoil_scraper.browser import BrowserWorker
from lukoil_scraper.excel_export import export_excel
from lukoil_scraper.parser import TERMINALS, filter_prices, parse_prices


ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")


class LukoilApp(ctk.CTk):
    def __init__(self) -> None:
        super().__init__()
        self.title("Lukoil Price Scraper")
        self.geometry("850x760")
        self.minsize(780, 690)
        self.configure(fg_color="#0C1523")
        self._busy = False
        self._closing = False
        self.worker = BrowserWorker()
        self.imported_prices = None

        self._build_ui()
        self.worker.start()
        self.protocol("WM_DELETE_WINDOW", self._on_close)
        self.after(150, self._poll_events)

    def _build_ui(self) -> None:
        root = ctk.CTkFrame(self, fg_color="transparent")
        root.pack(fill="both", expand=True, padx=28, pady=23)

        ctk.CTkLabel(
            root, text="LUKOIL  /  PRICE SCRAPER",
            font=ctk.CTkFont(size=25, weight="bold"),
            text_color="#EAF1FA",
        ).pack(anchor="w")
        ctk.CTkLabel(
            root,
            text="Десктоп експорт на ценови листи от wholesale.lukoil.bg",
            font=ctk.CTkFont(size=13),
            text_color="#9BAFC5",
        ).pack(anchor="w", pady=(4, 20))

        status_box = ctk.CTkFrame(root, fg_color="#162438", corner_radius=12)
        status_box.pack(fill="x", pady=(0, 16))
        ctk.CTkLabel(
            status_box, text="СЪСТОЯНИЕ",
            text_color="#87A6C5", font=ctk.CTkFont(size=11, weight="bold"),
        ).pack(anchor="w", padx=18, pady=(13, 3))
        self.status = ctk.CTkLabel(
            status_box, text="●  Отвори Chrome или импортирай HTML",
            text_color="#E6BA64", font=ctk.CTkFont(size=14),
        )
        self.status.pack(anchor="w", padx=18, pady=(0, 14))

        login_title = ctk.CTkLabel(
            root, text="01   ИЗТОЧНИК НА ЦЕНИТЕ",
            text_color="#DCE7F5", font=ctk.CTkFont(size=13, weight="bold"),
        )
        login_title.pack(anchor="w", pady=(0, 10))
        login_buttons = ctk.CTkFrame(root, fg_color="transparent")
        login_buttons.pack(fill="x", pady=(0, 8))
        login_buttons.grid_columnconfigure((0, 1), weight=1)
        self.open_button = ctk.CTkButton(
            login_buttons, text="Отвори Chrome за цените",
            height=40, corner_radius=8, command=self._open_browser,
        )
        self.open_button.grid(row=0, column=0, sticky="ew", padx=(0, 6))
        self.verify_button = ctk.CTkButton(
            login_buttons, text="Прочети отворения таб",
            fg_color="#294158", hover_color="#355573",
            height=40, corner_radius=8, command=self._verify,
        )
        self.verify_button.grid(row=0, column=1, sticky="ew", padx=(6, 0))
        ctk.CTkLabel(
            root,
            text="В Chrome, стартиран от приложението, влез ръчно при нужда. Остави ценовата листа отворена.",
            text_color="#9BAFC5", font=ctk.CTkFont(size=12), wraplength=765, justify="left",
        ).pack(anchor="w", pady=(3, 10))
        self.import_button = ctk.CTkButton(
            root, text="Алтернатива: Импортирай запазена HTML страница",
            height=36, fg_color="#294158", hover_color="#355573",
            command=self._import_html,
        )
        self.import_button.pack(fill="x", pady=(0, 16))

        ctk.CTkLabel(
            root, text="02   ИЗБЕРИ ТЕРМИНАЛИ",
            text_color="#DCE7F5", font=ctk.CTkFont(size=13, weight="bold"),
        ).pack(anchor="w", pady=(0, 9))

        terminal_box = ctk.CTkFrame(root, fg_color="#162438", corner_radius=12)
        terminal_box.pack(fill="x", pady=(0, 15))
        terminal_box.grid_columnconfigure((0, 1), weight=1)
        self.terminal_vars: dict[str, tk.BooleanVar] = {}
        for index, terminal in enumerate(TERMINALS):
            variable = tk.BooleanVar(value=True)
            self.terminal_vars[terminal] = variable
            ctk.CTkCheckBox(
                terminal_box, text=terminal, variable=variable,
                text_color="#DCE7F5",
                checkbox_width=19, checkbox_height=19,
                font=ctk.CTkFont(size=12),
            ).grid(
                row=index // 2, column=index % 2,
                sticky="w", padx=(18, 8), pady=(14 if index < 2 else 7, 8),
            )
        self.all_button = ctk.CTkButton(
            terminal_box, text="Избери всички / Изчисти", width=220,
            fg_color="#294158", hover_color="#355573",
            height=30, command=self._toggle_all,
        )
        self.all_button.grid(row=4, column=0, columnspan=2, pady=(2, 15))

        ctk.CTkLabel(
            root, text="03   ЕКСПОРТ В EXCEL",
            text_color="#DCE7F5", font=ctk.CTkFont(size=13, weight="bold"),
        ).pack(anchor="w", pady=(0, 10))
        self.export_button = ctk.CTkButton(
            root, text="Извлечи отворената таблица → Excel (.xlsx)",
            font=ctk.CTkFont(size=14, weight="bold"),
            height=47, fg_color="#2B8CCB", hover_color="#2579B0",
            corner_radius=9, command=self._export,
        )
        self.export_button.pack(fill="x", pady=(0, 15))

        ctk.CTkLabel(
            root, text="ЖУРНАЛ",
            text_color="#DCE7F5", font=ctk.CTkFont(size=12, weight="bold"),
        ).pack(anchor="w", pady=(0, 7))
        self.log = ctk.CTkTextbox(
            root, height=115, corner_radius=10,
            fg_color="#162438", text_color="#CEDBE9",
            font=ctk.CTkFont(size=12),
        )
        self.log.pack(fill="both", expand=True)
        self.log.configure(state="disabled")
        self._log("Готово. HTML таблиците се четат от вече отворения таб, без нов вход.")

    def _log(self, message: str) -> None:
        self.log.configure(state="normal")
        self.log.insert("end", f"[{datetime.now():%H:%M:%S}] {message}\n")
        self.log.see("end")
        self.log.configure(state="disabled")

    def _set_status(self, message: str, color: str) -> None:
        self.status.configure(text=f"●  {message}", text_color=color)

    def _set_busy(self, busy: bool) -> None:
        self._busy = busy
        state = "disabled" if busy else "normal"
        for widget in (self.open_button, self.verify_button, self.export_button, self.all_button, self.import_button):
            widget.configure(state=state)

    def _toggle_all(self) -> None:
        select = not all(var.get() for var in self.terminal_vars.values())
        for variable in self.terminal_vars.values():
            variable.set(select)

    def _open_browser(self) -> None:
        self.imported_prices = None
        self._set_busy(True)
        self._set_status("Свързване с Chrome...", "#E6BA64")
        self._log("Свързвам Chrome с локален debugging порт. Влез ръчно само при нужда.")
        self.worker.submit("open")

    def _verify(self) -> None:
        self.imported_prices = None
        self._set_busy(True)
        self._set_status("Чета отворената страница...", "#E6BA64")
        self.worker.submit("verify")

    def _import_html(self) -> None:
        source = filedialog.askopenfilename(
            parent=self,
            title="Избери HTML файл, запазен от страницата с цените",
            filetypes=[("HTML страница", "*.html *.htm"), ("Всички файлове", "*.*")],
        )
        if not source:
            return
        try:
            path = Path(source)
            if path.stat().st_size > 15_000_000:
                raise ValueError("HTML файлът е прекалено голям (над 15 MB).")
            raw = path.read_bytes()
            try:
                html = raw.decode("utf-8-sig")
            except UnicodeDecodeError:
                html = raw.decode("cp1251")
            self.imported_prices = parse_prices(html)
            self._set_status(
                f"Зареден HTML: {len(self.imported_prices.rows)} реда от "
                f"{len(self.imported_prices.terminals)} терминала",
                "#63D1A5",
            )
            self._log(f"Импортирана HTML страница: {path.name}")
        except Exception as exc:
            self.imported_prices = None
            self._set_status("Грешка при импортиране на HTML", "#F08C87")
            messagebox.showerror("Импорт на HTML", str(exc), parent=self)

    def _export(self) -> None:
        selected = tuple(name for name, variable in self.terminal_vars.items() if variable.get())
        if not selected:
            messagebox.showwarning("Терминали", "Изберете поне един терминал.", parent=self)
            return

        destination = filedialog.asksaveasfilename(
            parent=self,
            title="Запази ценова листа",
            defaultextension=".xlsx",
            filetypes=[("Excel Workbook", "*.xlsx")],
            initialfile=f"Lukoil_Prices_{datetime.now():%Y-%m-%d}.xlsx",
            initialdir=str(Path.home() / "Documents") if (Path.home() / "Documents").is_dir() else str(Path.home()),
        )
        if not destination:
            return

        if self.imported_prices is not None:
            try:
                prices = filter_prices(self.imported_prices, selected)
                output = export_excel(prices, destination)
            except Exception as exc:
                messagebox.showerror("Excel експорт", str(exc), parent=self)
                return
            self._set_status(f"Excel записан · {len(prices.rows)} реда", "#63D1A5")
            self._log(f"Excel от импортиран HTML: {output}")
            messagebox.showinfo("Готово", f"Записани {len(prices.rows)} реда.\n\n{output}", parent=self)
            return

        self._set_busy(True)
        self._set_status("Чета текущия Chrome таб и записвам Excel...", "#E6BA64")
        self._log(f"Скрейпинг на отворена страница за {len(selected)} терминала.")
        self.worker.submit("export", (destination, selected))

    def _poll_events(self) -> None:
        if self._closing:
            return
        try:
            while True:
                kind, payload = self.worker.events.get_nowait()
                if kind == "log":
                    self._log(payload)
                elif kind == "opened":
                    self._set_status("Chrome е готов. Отвори цените и прочети таба.", "#E6BA64")
                    self._log("Влез при нужда и натисни „Прочети отворения таб“.")
                elif kind == "verified":
                    count, terminals = payload
                    self._set_status(f"Табът е прочетен · {len(terminals)} терминала · {count} реда", "#63D1A5")
                    self._log(f"Намерени {count} ценови реда в отворения таб.")
                elif kind == "exported":
                    filename, count, terminals = payload
                    self._set_status(f"Excel записан · {count} реда", "#63D1A5")
                    self._log(f"Експортът е успешен: {filename}")
                    messagebox.showinfo(
                        "Експортът е готов",
                        f"Записани {count} реда от {len(terminals)} терминала.\n\n{filename}",
                        parent=self,
                    )
                elif kind == "error":
                    self._set_status("Грешка. Виж журнала.", "#F08C87")
                    self._log("Грешка: " + payload)
                    messagebox.showerror("Lukoil Price Scraper", payload, parent=self)
                elif kind == "idle":
                    self._set_busy(False)
        except Empty:
            pass
        self.after(150, self._poll_events)

    def _on_close(self) -> None:
        if self._closing:
            return
        self._closing = True
        self.worker.submit("stop")
        self._close_when_done(0)

    def _close_when_done(self, checks: int) -> None:
        if not self.worker.is_alive() or checks > 25:
            self.destroy()
        else:
            self.after(150, lambda: self._close_when_done(checks + 1))


if __name__ == "__main__":
    ctk.set_widget_scaling(1.0)
    app = LukoilApp()
    app.mainloop()
