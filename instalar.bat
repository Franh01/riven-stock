@echo off
rem Instalador de Riven Stock: doble click en este archivo.
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0tools\install.ps1" %*
echo.
pause
