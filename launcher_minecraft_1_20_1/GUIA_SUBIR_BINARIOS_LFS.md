# Subir los binarios del launcher a Git LFS (Windows)

Este proceso sube los mods, resource packs, imágenes y otros binarios del ZIP a la rama `main` de este repositorio usando Git LFS.

## Necesitas

- Git for Windows: https://git-scm.com/download/win
- Git LFS: https://git-lfs.com/
- El archivo `PeriSafio_Launcher_ACTUALIZAR_CORREGIDO.zip` que contiene los archivos originales.
- Permisos de escritura en `loboxy03/PeriSafio` y sesión/autenticación de GitHub configurada para Git.

## Pasos

1. Descarga el ZIP original y guarda dónde puedas localizarlo.
2. Descarga estos dos scripts desde el repositorio: `SUBIR_A_GIT_LFS.ps1` y `SUBIR_A_GIT_LFS.bat`.
3. Abre una terminal en la carpeta donde guardaste los scripts.
4. Ejecuta `SUBIR_A_GIT_LFS.bat`. Cuando lo pida, pega la ruta completa del ZIP.
5. Revisa el resumen y responde `S` para confirmar el commit y el push.
6. Comprueba el repositorio: https://github.com/loboxy03/PeriSafio/tree/main/launcher_minecraft_1_20_1/content

También puedes pasar la ruta del ZIP como argumento:
```bat
SUBIR_A_GIT_LFS.bat "C:\Users\TU_USUARIO\Downloads\PeriSafio_Launcher_ACTUALIZAR_CORREGIDO.zip"
```

El script crea un clon en `%USERPROFILE%\PeriSafio-GitLFS` si todavía no existe, copia solo las carpetas `assets` y `content` desde el ZIP, prepara LFS y pide confirmación antes de subir.

## Importante

- El script no publica ni almacena contraseñas; Git gestiona la autenticación.
- La subida puede fallar si la cuota de Git LFS está agotada o si la cuenta no tiene permisos.
- No se considera completado hasta que el comando `git push` termina sin error. Este script no se ha ejecutado en tu PC, así que los binarios no se han subido todavía.
