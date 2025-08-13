import os
import time
from pathlib import Path
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager
from dotenv import load_dotenv
load_dotenv()

# ==============================
# CONFIGURACIÓN
# ==============================
YOUTUBE_EMAIL = os.getenv("YOUTUBE_EMAIL")
YOUTUBE_PASSWORD = os.getenv("YOUTUBE_PASSWORD")
COOKIES_FILE = Path("app/cookies/cookies.txt")

# ==============================
# LOGIN Y EXTRACCIÓN
# ==============================

def login_youtube_and_save_cookies():
    print("=" * 80)
    print("🤖 YouTube Cookie Extractor - 100% Automático y Actualizado")
    print("=" * 80)

    # Configuración Chrome
    chrome_options = Options()
    chrome_options.add_argument("--start-maximized")
    chrome_options.add_argument("--disable-blink-features=AutomationControlled")

    driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=chrome_options)
    wait = WebDriverWait(driver, 15)

    try:
        print("🌐 Abriendo página de login...")
        driver.get("https://accounts.google.com/signin/v2/identifier?service=youtube")

        # Paso 1: ingresar email
        print("✉️ Ingresando email...")
        email_input = wait.until(EC.presence_of_element_located((By.ID, "identifierId")))
        email_input.clear()
        email_input.send_keys(YOUTUBE_EMAIL)
        email_input.send_keys(Keys.RETURN)

        # Paso intermedio: elegir cuenta (si aparece)
        try:
            choose_account = wait.until(EC.presence_of_element_located((By.XPATH, "//div[@data-identifier]")))
            print("👤 Detectada pantalla de selección de cuenta, eligiendo automáticamente...")
            choose_account.click()
        except:
            pass

        # Paso 2: esperar campo contraseña o pasos extra
        try:
            print("🔑 Esperando campo contraseña...")
            password_input = wait.until(EC.presence_of_element_located((By.NAME, "Passwd")))
            password_input.clear()
            password_input.send_keys(YOUTUBE_PASSWORD)
            password_input.send_keys(Keys.RETURN)
        except:
            print("⚠️ No apareció el campo contraseña, puede que haya un paso extra (captcha o 2FA).")
            print("⏸️ Pausando para que lo completes manualmente...")
            input("Presiona Enter cuando hayas terminado el login en el navegador...")

        # Paso 3: esperar que cargue YouTube
        print("⏳ Esperando que cargue YouTube...")
        wait.until(EC.url_contains("youtube.com"))

        # ==============================
        # GUARDAR COOKIES
        # ==============================
        print("💾 Guardando cookies en formato Netscape...")
        cookies = driver.get_cookies()
        with open(COOKIES_FILE, "w", encoding="utf-8") as f:
            f.write("# Netscape HTTP Cookie File\n")
            for cookie in cookies:
                domain = cookie.get("domain", "")
                flag = "TRUE" if domain.startswith(".") else "FALSE"
                path = cookie.get("path", "/")
                secure = "TRUE" if cookie.get("secure", False) else "FALSE"
                expiry = str(cookie.get("expiry", 0))
                name = cookie.get("name", "")
                value = cookie.get("value", "")
                f.write("\t".join([domain, flag, path, secure, expiry, name, value]) + "\n")

        print(f"✅ Cookies guardadas en {COOKIES_FILE.resolve()}")

    finally:
        driver.quit()


if __name__ == "__main__":
    login_youtube_and_save_cookies()
