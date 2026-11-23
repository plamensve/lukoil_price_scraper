@echo off
setlocal
cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
    py -3.12 -m venv .venv
    if errorlevel 1 goto :error
)

call ".venv\Scripts\activate.bat"
python -m pip install --upgrade pip
if errorlevel 1 goto :error
python -m pip install -r requirements.txt "pyinstaller>=6.12,<7"
if errorlevel 1 goto :error

python tools\download_logos.py
if errorlevel 1 goto :error

python -m unittest discover -s tests -v
if errorlevel 1 goto :error

python -m PyInstaller --noconfirm --clean --onefile --windowed --name LukoilPriceScraper --icon assets\app.ico --add-data "assets;assets" --collect-data customtkinter --hidden-import=PIL._tkinter_finder main.py
if errorlevel 1 goto :error

echo.
echo Build successful: dist\LukoilPriceScraper.exe
exit /b 0

:error
echo.
echo Build failed. Check the error messages above.
exit /b 1
