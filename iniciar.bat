@echo off
chcp 65001 >nul
cd /d "%~dp0"
.venv\Scripts\python.exe -c "import cv2, numpy, tkinter" 2>nul && goto rodar
echo Instalando as bibliotecas...
python -m venv .venv
.venv\Scripts\python.exe -m pip install --quiet --disable-pip-version-check -r requirements.txt || goto erro
:rodar
if "%~1"=="" (
    start "" ".venv\Scripts\pythonw.exe" interface.py
    exit /b
)
.venv\Scripts\python.exe bot_loja_secreta.py %*
pause
exit /b
:erro
echo Nao consegui instalar as bibliotecas.
echo Instale o Python em python.org, marque "Add python.exe to PATH" e abra de novo.
pause
