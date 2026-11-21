@echo off
REM Đóng gói EXE bằng PyInstaller — CHƯA BUILD THỬ (G7). Chạy trên Windows 10/11 x64, Python 3.11.
chcp 65001 >nul
setlocal
if not exist .venv (
  py -3.11 -m venv .venv || goto :err
)
call .venv\Scripts\activate.bat
python -m pip install --upgrade pip
pip install -r requirements.lock pyinstaller || goto :err
python -m pytest -q || goto :err
pyinstaller --noconfirm --windowed --name CadastralValidatorPro ^
  --paths src --add-data "config;config" --add-data "scripts\microstation;scripts\microstation" ^
  main.py || goto :err
echo.
echo Xong: dist\CadastralValidatorPro\CadastralValidatorPro.exe
echo Hay kiem tra tren may Windows sach truoc khi ban giao.
goto :eof
:err
echo LOI - xem thong bao phia tren.
exit /b 1
