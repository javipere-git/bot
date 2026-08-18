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
if not errorlevel 1 goto :actualizado

REM --- Segundo intento, solo por las excluidas ---------------------------------
REM  Tus excluidas las escribe la app en esta PC, asi que pueden chocar con las
REM  que vienen del repositorio y frenar la actualizacion (paso el 18/08/2026).
REM  Antes de darse por vencido: se guarda una COPIA de las tuyas, se toma la
REM  version del repositorio y se reintenta. No se pierde nada; la copia queda
REM  en config\excluidas_respaldo.txt y la lista del broker ni se toca.
if not exist "config\excluidas.txt" goto :fallo
echo.
echo     Aviso: tus excluidas de esta PC chocan con las del repositorio.
echo     Guardo una copia en config\excluidas_respaldo.txt y reintento.
copy /Y "config\excluidas.txt" "config\excluidas_respaldo.txt" >NUL
del /Q "config\excluidas.txt" >NUL 2>&1
git checkout -- config/excluidas.txt >NUL 2>&1
git pull
if not errorlevel 1 (
    echo     Listo. Revisa config\excluidas_respaldo.txt por si tenias simbolos
    echo     que no esten en la lista que bajo del repositorio.
    goto :actualizado
)

:fallo
echo.
echo  [ERROR] No se pudo actualizar.
echo  Causas tipicas: sin internet, o se modificaron archivos a mano en esta PC.
echo  Mandale esta pantalla al asistente.
echo.
pause
exit /b 1

:actualizado

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
