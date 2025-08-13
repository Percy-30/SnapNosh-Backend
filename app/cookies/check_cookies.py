import os
from pathlib import Path

cookies_path = Path("app/cookies/cookies.txt")
print("Ruta absoluta:", cookies_path.resolve())
print("¿Existe el archivo?:", cookies_path.exists())
