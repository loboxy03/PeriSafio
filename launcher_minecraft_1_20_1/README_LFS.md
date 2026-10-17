# Subir los binarios grandes del launcher

El repositorio ya contiene reglas `.gitattributes` para rastrear JAR, ZIP, imágenes e iconos con Git LFS. El manifiesto de Git LFS no contiene el archivo original: el binario se debe transferir con un cliente Git LFS.

## Pasos para subir los archivos originales

1. Instala [Git for Windows](https://git-scm.com/download/win) y [Git LFS](https://git-lfs.com/).
2. Descarga el repositorio actualizado y extrae el paquete fuente completo del launcher.
3. Copia los archivos binarios originales dentro de `launcher_minecraft_1_20_1/assets/` y `launcher_minecraft_1_20_1/content/`. No uses archivos vacíos ni sustitutos.
4. Abre la carpeta raíz del repositorio en CMD y ejecuta `git pull origin main`.
5. Ejecuta `launcher_minecraft_1_20_1/UPLOAD_BINARIOS_A_GITHUB_LFS.bat` y escribe `SUBIR` cuando verifiques la lista.
6. Comprueba en GitHub que los JAR/ZIP muestran su tamaño y que al descargar el resource pack se obtiene un ZIP real, no un archivo de texto con un puntero LFS.

## Límites y advertencias

GitHub bloquea archivos normales mayores de 100 MB. Git LFS puede alojarlos, pero tiene límites de almacenamiento y transferencia según la cuota de la cuenta. Si se agota la cuota, el push puede fallar. No se han subido los binarios originales en este commit; esta configuración prepara el repositorio para la transferencia auténtica.
