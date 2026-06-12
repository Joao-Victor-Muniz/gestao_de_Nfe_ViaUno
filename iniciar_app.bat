@echo off
:: Verifica se está rodando como Administrador
net session >nul 2>&1
if %errorLevel% == 0 (
    goto :iniciar_app
) else (
    echo Solicitando privilegios de Administrador...
    echo Set UAC = CreateObject^("Shell.Application"^) > "%temp%\getadmin.vbs"
    echo UAC.ShellExecute "%~s0", "", "", "runas", 1 >> "%temp%\getadmin.vbs"
    "%temp%\getadmin.vbs"
    del "%temp%\getadmin.vbs"
    exit /B
)

:iniciar_app
:: Define o título da janela
title NF_APP_ViaUno

:: Muda para a pasta onde o .bat está localizado
cd /d "%~dp0"

:: Inicia o servidor Python
echo Iniciando o servidor NF_APP_ViaUno...
python app.py
pause
