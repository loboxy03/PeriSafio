@echo off
setlocal
title PeriSafio - Subir binarios a Git LFS
echo ==========================================================
echo  PeriSafio Launcher - Subida de mods y resourcepacks a LFS
echo ==========================================================
echo.
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0SUBIR_A_GIT_LFS.ps1" %*
if errorlevel 1 (
  echo.
  echo ERROR: No se completo la subida. Lee el mensaje anterior.
  pause
  exit /b 1
)
echo.
pause
