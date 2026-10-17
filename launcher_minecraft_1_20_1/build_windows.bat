@echo off
setlocal EnableExtensions
cd /d "%~dp0"

echo =====================================================
echo   PERISAFIO LAUNCHER - BUILD PARA WINDOWS
echo =====================================================

echo.
where py >nul 2>nul
if errorlevel 1 (
  echo [ERROR] No se encontro Python Launcher ^(py^).
  echo Instala Python 3.11 x64 desde python.org y marca "Add Python to PATH".
  pause
  exit /b 1
)

if not exist .venv (
  echo [1/6] Creando entorno virtual...
  py -3.11 -m venv .venv
  if errorlevel 1 goto :error
)
call .venv\Scripts\activate.bat

echo [2/6] Actualizando pip...
python -m pip install --upgrade pip
if errorlevel 1 goto :error

echo [3/6] Instalando dependencias...
pip install -r requirements.txt
if errorlevel 1 goto :error
pip install pyinstaller
if errorlevel 1 goto :error

if not exist assets\launcher.ico (
  echo [ERROR] Falta assets\launcher.ico
  goto :error
)
if not exist config.json (
  echo [ERROR] Falta config.json
  goto :error
)

echo [4/6] Compilando launcher...
pyinstaller --noconfirm --clean --windowed --onedir --name PirustudiosLauncher --icon assets\launcher.ico --add-data "assets;assets" --add-data "content;content" --add-data "config.json;." launcher.py
if errorlevel 1 goto :error

echo [5/6] Compilando administrador...
pyinstaller --noconfirm --clean --windowed --onedir --name PirustudiosAdmin --icon assets\launcher.ico --add-data "assets;assets" --add-data "config.json;." admin.py
if errorlevel 1 goto :error

echo [6/6] Preparando contenido del administrador...
if not exist dist\PirustudiosAdmin\content\mods mkdir dist\PirustudiosAdmin\content\mods
if not exist dist\PirustudiosAdmin\content\resourcepacks mkdir dist\PirustudiosAdmin\content\resourcepacks
xcopy /E /I /Y content dist\PirustudiosAdmin\content >nul
copy /Y manifest.json dist\PirustudiosAdmin\manifest.json >nul

echo Compilacion terminada.
echo.
echo Launcher: dist\PirustudiosLauncher\PirustudiosLauncher.exe
echo Admin:    dist\PirustudiosAdmin\PirustudiosAdmin.exe
echo.
echo Ahora instala Inno Setup 6 y ejecuta build_installer.bat
pause
exit /b 0

:error
echo.
echo [ERROR] La compilacion fallo. Lee el mensaje anterior.
pause
exit /b 1
