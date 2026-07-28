@echo off
REM ===========================================================================
REM  ACTUALIZAR LA APP
REM  Doble click aca para traer las ultimas correcciones y dejar todo listo.
REM  No toca tus credenciales ni tus registros: solo actualiza el codigo.
REM ===========================================================================
cd /d "%~dp0"
title Actualizar bot de trading

echo.
echo  ================================================
echo   ACTUALIZANDO LA APP
echo  ================================================
echo.

REM --- avisar si la app esta abierta (hay que cerrarla antes) ---
tasklist /FI "IMAGENAME eq pythonw.exe" 2>NUL | find /I "pythonw.exe" >NUL
if not errorlevel 1 (
    echo  [ATENCION] Parece que la app esta ABIERTA.
    echo  Cerrala antes de actualizar y volve a ejecutar este archivo.
    echo.
    pause
    exit /b 1
)

echo  1) Trayendo los ultimos cambios...
git pull
if errorlevel 1 (
    echo.
    echo  [ERROR] No se pudo actualizar.
    echo  Causas tipicas: sin internet, o se modificaron archivos a mano en esta PC.
    echo  Mandale esta pantalla al asistente.
    echo.
    pause
    exit /b 1
)

echo.
echo  2) Revisando que no falte ninguna libreria...
python -m pip install -q -r requirements.txt
if errorlevel 1 (
    echo.
    echo  [ERROR] Fallo la instalacion de librerias. Mandale esta pantalla al asistente.
    echo.
    pause
    exit /b 1
)

echo.
echo  3) Version que quedo instalada:
git log -1 --pretty=format:"     %%h  -  %%s  (%%ad)" --date=format:"%%d/%%m/%%Y %%H:%%M"
echo.
echo.
echo  ================================================
echo   LISTO. Ya podes abrir la app.
echo  ================================================
echo.
pause
