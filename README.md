# PeriSafio Launcher

Código fuente y documentación del launcher PeriSafio para Windows / Minecraft 1.20.1.

## Qué deben recibir los jugadores

Distribuye un **ejecutable (.exe) compilado** del launcher, no solamente el ZIP del código fuente. El ZIP sirve para editar o compilar el proyecto.

## Flujo de actualizaciones

1. El jugador abre el launcher.
2. Si hay contenido nuevo, el botón **ACTUALIZAR** debe estar disponible.
3. Al pulsarlo, el launcher descarga los mods y resource packs definidos en el manifiesto.
4. Mientras se comprueba o instala una actualización, **JUGAR** debe permanecer deshabilitado.
5. Cuando termina correctamente, el botón de actualización se oculta y se puede pulsar **JUGAR**.
6. Si falla, el launcher debe mostrar una opción para reintentar y mantener **JUGAR** bloqueado.

El manifiesto remoto está alojado en [PeriSafio-Updates](https://github.com/loboxy03/PeriSafio-Updates/blob/main/manifest.json).

## Cómo publicar un mod o resource pack

1. Sube el archivo a un Release de `PeriSafio-Updates`.
2. Añade o actualiza su entrada en `manifest.json`, indicando la ruta de destino, URL de descarga y SHA-256 correcto.
3. Incrementa `content_version` para que los launchers instalados detecten la nueva versión.
4. Prueba la actualización con una copia del launcher antes de distribuir el cambio.

**Importante:** si `remove_missing` está en `true`, el launcher puede eliminar archivos administrados que ya no estén incluidos en el manifiesto. Conserva en el manifiesto todos los mods y resource packs que deban permanecer instalados.

## Compilar y distribuir

1. Usa el proyecto fuente completo que contiene `launcher.py`, `manifest.json`, `config.json`, `build_windows.bat` y los recursos.
2. En Windows, instala la versión de Python requerida por el proyecto y ejecuta `build_windows.bat`.
3. Prueba el ejecutable generado: actualizar, comprobar hashes, fallos de red, bloqueo de JUGAR y apertura normal de Minecraft.
4. Publica el nuevo ejecutable en un Release para que todos descarguen la misma versión.

## Estado del repositorio

- [x] Repositorio y enlace al manifiesto remoto documentados.
- [ ] Confirmar que el código actualizado de `launcher.py` esté publicado aquí.
- [ ] Completar el código fuente y los recursos necesarios para compilar.
- [ ] Compilar y probar el ejecutable en Windows.

No guardes contraseñas, tokens ni secretos en el repositorio.
