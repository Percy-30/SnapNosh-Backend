from dotenv import load_dotenv
import os

load_dotenv()

from app.services.youtube_cookie_updater import login_youtube_and_save_cookies

EMAIL = os.getenv("YOUTUBE_EMAIL")
PASSWORD = os.getenv("YOUTUBE_PASSWORD")
OUTPUT_PATH = os.getenv("YOUTUBE_COOKIES_PATH", "cookies.txt")

if not EMAIL or not PASSWORD:
    print("❌ Falta configurar variables de entorno YOUTUBE_EMAIL o YOUTUBE_PASSWORD")
else:
    login_youtube_and_save_cookies(EMAIL, PASSWORD, OUTPUT_PATH)
