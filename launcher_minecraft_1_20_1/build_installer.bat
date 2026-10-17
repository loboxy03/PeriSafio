@echo off
setlocal
cd /d "%~dp0"
echo =====================================================
echo   CREAR INSTALADOR PIRUSTUDIOS LAUNCHER
echo =====================================================
where ISCC >nul 2>nul
if errorlevel 1 (
  echo [ERROR] No se encontro ISCC.exe.
  echo Instala Inno Setup 6 y vuelve a ejecutar este archivo.
  echo Normalmente queda en C:\Program Files (x86)\Inno Setup 6\
  pause
  exit /b 1
)
if not exist dist\PirustudiosLauncher\PirustudiosLauncher.exe (
  echo [ERROR] Primero ejecuta build_windows.bat
  pause
  exit /b 1
)
if not exist dist\PirustudiosAdmin\PirustudiosAdmin.exe (
  echo [ERROR] Primero ejecuta build_windows.bat
  pause
  exit /b 1
)
ISCC installer\PirustudiosLauncher.iss
if errorlevel 1 goto :error
echo.
echo INSTALADOR CREADO EN:
echo dist-installer\PirustudiosLauncher-Setup-1.0.0.exe
pause
exit /b 0
:error
echo.
echo [ERROR] Inno Setup no pudo crear el instalador.
pause
exit /b 1
