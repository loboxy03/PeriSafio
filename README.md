# PeriSafio Launcher

Código fuente y documentación del launcher PeriSafio para Windows / Minecraft 1.20.1.

## Código fuente corregido

La versión corregida elimina el borrado automático de Morpher, retira el resource pack antiguo y configura la sincronización del pack `Nutria_DEDsafio2_v1.2.zip`.

**Importante:** este repositorio está en proceso de carga. El archivo ZIP completo del proyecto contiene recursos grandes y no se puede subir íntegro mediante la integración actual de GitHub. No compiles hasta que estén presentes `launcher.py`, `manifest.json`, `config.json`, `build_windows.bat` y las carpetas de recursos.

## Compilar en Windows

1. Instala Python 3.11.
2. Extrae el proyecto completo en una carpeta.
3. Ejecuta `build_windows.bat`.
4. Abre el ejecutable generado en `dist\PirustudiosLauncher\PirustudiosLauncher.exe`.
5. Pulsa **SINCRONIZAR** antes de jugar para descargar los archivos definidos en el manifiesto.

## Actualizaciones

El manifiesto de actualización del launcher está alojado en [PeriSafio-Updates](https://github.com/loboxy03/PeriSafio-Updates).

## Estado

- [x] Repositorio de código creado bajo la cuenta `loboxy03`.
- [ ] Subir el código fuente completo y los recursos.
- [ ] Verificar compilación en Windows.
- [ ] Probar sincronización y lanzamiento del juego.

No guardes contraseñas, tokens ni secretos en el repositorio.
