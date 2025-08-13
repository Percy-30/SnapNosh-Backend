# app/cookies/check_cookies.py
from pathlib import Path

COOKIES_PATH = Path("app/cookies/cookies.txt")

def cookies_are_valid() -> bool:
    """
    Verifica si el archivo de cookies existe y contiene datos.
    """
    print("Ruta absoluta:", COOKIES_PATH.resolve())
    print("¿Existe el archivo?:", COOKIES_PATH.exists())

    if not COOKIES_PATH.exists():
        return False
    
    contenido = COOKIES_PATH.read_text(encoding="utf-8").strip()
    return bool(contenido)
