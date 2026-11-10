"""Lectura del archivo .env (sin dependencias externas).

Formato de cada línea:  NOMBRE=valor
Se ignoran líneas vacías y comentarios (#). Las variables que ya existan en la terminal
NO se sobrescriben: lo que definas en la terminal tiene prioridad sobre el archivo.
También se tolera por error el formato de PowerShell ($env:NOMBRE='valor').
"""
import os
from pathlib import Path


def cargar_env(ruta):
    ruta = Path(ruta)
    if not ruta.is_file():
        return []
    cargadas = []
    for linea in ruta.read_text(encoding="utf-8-sig").splitlines():
        linea = linea.strip()
        if not linea or linea.startswith("#"):
            continue
        for prefijo in ("export ", "$env:"):
            if linea.startswith(prefijo):
                linea = linea[len(prefijo):].strip()
        if "=" not in linea:
            continue
        nombre, valor = linea.split("=", 1)
        nombre, valor = nombre.strip(), valor.strip()
        if len(valor) >= 2 and valor[0] == valor[-1] and valor[0] in "'\"":
            valor = valor[1:-1]
        if nombre and nombre not in os.environ:
            os.environ[nombre] = valor
            cargadas.append(nombre)
    return cargadas
