@echo off
setlocal
title YT-DLP Studio - Build

echo ============================================
echo   YT-DLP Studio - Gerador do executavel
echo ============================================
echo.

where python >nul 2>nul
if errorlevel 1 (
    echo [ERRO] Python nao encontrado no PATH.
    echo Instale o Python 3.10+ em https://python.org e marque
    echo a opcao "Add python.exe to PATH" durante a instalacao.
    pause
    exit /b 1
)

echo [1/4] Criando ambiente virtual (.venv)...
python -m venv .venv
call .venv\Scripts\activate.bat

echo.
echo [2/4] Instalando dependencias...
python -m pip install --upgrade pip >nul
pip install -r requirements.txt
if errorlevel 1 (
    echo [ERRO] Falha ao instalar dependencias.
    pause
    exit /b 1
)

echo.
echo [3/4] Empacotando com PyInstaller (isso leva 1-3 minutos)...
pyinstaller --noconfirm --clean --onefile --windowed ^
    --name "YT-DLP Studio" ^
    --icon "assets\icon.ico" ^
    --add-data "assets;assets" ^
    src\main.py

if errorlevel 1 (
    echo [ERRO] Falha ao gerar o executavel.
    pause
    exit /b 1
)

echo.
echo [4/4] Pronto!
echo O executavel esta em: dist\YT-DLP Studio.exe
echo Voce pode mover esse arquivo .exe para qualquer pasta do seu
echo computador e executa-lo diretamente (nao precisa do Python
echo instalado na maquina que for rodar o programa).
echo.
pause
