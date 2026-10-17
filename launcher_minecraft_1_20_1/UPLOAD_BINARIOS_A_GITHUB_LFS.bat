@echo off
setlocal
cd /d "%~dp0\.."
echo =========================================================
echo   SUBIR ARCHIVOS BINARIOS DE PERISAFIO CON GIT LFS
echo =========================================================
where git >nul 2>nul
if errorlevel 1 (
 echo ERROR: Instala Git for Windows desde https://git-scm.com/download/win
 pause
 exit /b 1
)
git lfs version >nul 2>nul
if errorlevel 1 (
 echo ERROR: Git LFS no esta instalado.
 echo Instala Git LFS desde https://git-lfs.com/ y vuelve a abrir CMD.
 pause
 exit /b 1
)
git lfs install
git lfs track "*.jar" "*.zip" "*.jpg" "*.jpeg" "*.png" "*.ico" "*.mp3" "*.ogg" "*.wav"
git add .gitattributes
git add launcher_minecraft_1_20_1/assets launcher_minecraft_1_20_1/content
git add launcher_minecraft_1_20_1/admin.py launcher_minecraft_1_20_1/build_installer.bat launcher_minecraft_1_20_1/update_server.py launcher_minecraft_1_20_1/installer/PirustudiosLauncher.iss
echo.
echo Revisa los archivos que Git va a subir:
git status --short
echo.
echo IMPORTANTE: verifica que el resource pack grande aparezca listado.
echo Si Git dice que el archivo supera el limite, confirma que Git LFS lo esta rastreando.
echo.
set /p OK=Escribe SUBIR para confirmar el envio al repositorio remoto:
if /I not "%OK%"=="SUBIR" (
 echo Cancelado; no se hizo commit ni push.
 pause
 exit /b 0
)
git commit -m "Add launcher assets and content via Git LFS"
if errorlevel 1 (
 echo No se creo commit. Revisa git status; puede que no haya archivos nuevos.
 pause
 exit /b 1
)
git push origin main
if errorlevel 1 (
 echo ERROR al subir. Revisa acceso al repositorio y cuota de Git LFS.
 pause
 exit /b 1
)
echo.
echo Subida terminada. Comprueba los archivos en GitHub.
pause
