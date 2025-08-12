import os
import time
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException
from selenium.webdriver.common.keys import Keys
from dotenv import load_dotenv

load_dotenv()

def save_cookies_netscape_format(driver, filename: str):
    """
    Guarda cookies en formato Netscape para yt-dlp y similares.
    """
    cookies = driver.get_cookies()
    with open(filename, "w", encoding="utf-8") as f:
        f.write("# Netscape HTTP Cookie File\n")
        for c in cookies:
            domain = c['domain']
            flag = "TRUE" if domain.startswith(".") else "FALSE"
            path = c['path']
            secure = "TRUE" if c['secure'] else "FALSE"
            expiry = str(c.get('expiry', 0))
            name = c['name']
            value = c['value']
            line = f"{domain}\t{flag}\t{path}\t{secure}\t{expiry}\t{name}\t{value}\n"
            f.write(line)

def login_youtube_and_save_cookies(email: str, password: str, output_path: str, headless: bool = False):
    """
    Realiza login en YouTube con Selenium y guarda cookies en formato Netscape.
    """
    chrome_options = Options()
    
    # Improved Chrome options for better bot detection avoidance
    chrome_options.add_argument("--disable-blink-features=AutomationControlled")
    chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
    chrome_options.add_experimental_option('useAutomationExtension', False)
    chrome_options.add_argument("--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
    
    # Additional anti-detection measures
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--disable-extensions")
    chrome_options.add_argument("--disable-plugins")
    chrome_options.add_argument("--disable-images")  # Faster loading
    chrome_options.add_argument("--disable-javascript-harmony-shipping")
    chrome_options.add_argument("--disable-background-timer-throttling")
    chrome_options.add_argument("--disable-backgrounding-occluded-windows")
    chrome_options.add_argument("--disable-renderer-backgrounding")
    chrome_options.add_argument("--disable-features=TranslateUI")
    chrome_options.add_argument("--disable-ipc-flooding-protection")
    
    # Performance improvements
    chrome_options.add_argument("--max_old_space_size=4096")
    chrome_options.add_argument("--no-first-run")
    chrome_options.add_argument("--no-service-autorun")
    chrome_options.add_argument("--password-store=basic")
    
    # Language and locale
    chrome_options.add_argument("--lang=en-US")
    
    # Prefs to avoid detection
    prefs = {
        "credentials_enable_service": False,
        "profile.password_manager_enabled": False,
        "profile.default_content_setting_values.notifications": 2
    }
    chrome_options.add_experimental_option("prefs", prefs)
    
    if headless:
        chrome_options.add_argument("--headless=new")
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--window-size=1920,1080")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--disable-web-security")
    chrome_options.add_argument("--allow-running-insecure-content")

    driver = webdriver.Chrome(options=chrome_options)
    
    # Advanced anti-detection scripts
    driver.execute_script("""
        // Remove webdriver property
        Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
        
        // Mock languages and plugins
        Object.defineProperty(navigator, 'languages', {get: () => ['en-US', 'en']});
        Object.defineProperty(navigator, 'plugins', {get: () => [1, 2, 3, 4, 5]});
        
        // Mock permissions
        const originalQuery = window.navigator.permissions.query;
        window.navigator.permissions.query = (parameters) => (
            parameters.name === 'notifications' ?
                Promise.resolve({ state: Notification.permission }) :
                originalQuery(parameters)
        );
        
        // Hide automation indicators
        window.chrome = {
            runtime: {},
            loadTimes: function() {},
            csi: function() {},
            app: {}
        };
        
        // Mock media devices
        Object.defineProperty(navigator, 'mediaDevices', {
            get: () => ({
                enumerateDevices: () => Promise.resolve([])
            })
        });
    """)
    
    # Set additional properties to look more human
    driver.execute_cdp_cmd('Page.addScriptToEvaluateOnNewDocument', {
        "source": """
            delete window.cdc_adoQpoasnfa76pfcZLmcfl_Array;
            delete window.cdc_adoQpoasnfa76pfcZLmcfl_Promise;
            delete window.cdc_adoQpoasnfa76pfcZLmcfl_Symbol;
        """
    })
    
    try:
        print("🔄 Navegando a Google Sign-in...")
        driver.get("https://accounts.google.com/signin/v2/identifier?service=youtube&continue=https://www.youtube.com/&hl=en")
        
        # Wait for page to load
        time.sleep(3)
        
        # Try multiple selectors for email input
        email_input = None
        email_selectors = [
            (By.ID, "identifierId"),
            (By.NAME, "identifier"),
            (By.CSS_SELECTOR, "input[type='email']"),
            (By.XPATH, "//input[@type='email']")
        ]
        
        print("🔄 Buscando campo de email...")
        for by_type, selector in email_selectors:
            try:
                email_input = WebDriverWait(driver, 10).until(
                    EC.element_to_be_clickable((by_type, selector))
                )
                print(f"✅ Campo de email encontrado: {selector}")
                break
            except TimeoutException:
                continue
        
        if not email_input:
            raise Exception("No se pudo encontrar el campo de email")
        
        # Enter email with human-like typing
        email_input.clear()
        time.sleep(1)
        for char in email:
            email_input.send_keys(char)
            time.sleep(0.1)  # Human-like typing speed
        
        time.sleep(2)
        
        # Click next button
        next_buttons = [
            (By.ID, "identifierNext"),
            (By.CSS_SELECTOR, "[data-test-id='identifierNext']"),
            (By.XPATH, "//span[text()='Next']/../.."),
            (By.XPATH, "//div[@role='button']//span[contains(text(), 'Next')]"),
        ]
        
        next_clicked = False
        for by_type, selector in next_buttons:
            try:
                next_button = driver.find_element(by_type, selector)
                driver.execute_script("arguments[0].click();", next_button)
                next_clicked = True
                print("✅ Botón 'Next' clickeado")
                break
            except NoSuchElementException:
                continue
        
        if not next_clicked:
            # Try pressing Enter as fallback
            email_input.send_keys(Keys.ENTER)
            print("⚠️ Usé Enter como alternativa")
        
        time.sleep(5)  # Wait for password page
        
        # Multiple selectors for password field
        password_input = None
        password_selectors = [
            (By.NAME, "password"),
            (By.ID, "password"),
            (By.CSS_SELECTOR, "input[type='password']"),
            (By.XPATH, "//input[@type='password']"),
            (By.XPATH, "//input[@name='Passwd']"),
        ]
        
        print("🔄 Buscando campo de contraseña...")
        password_input = None
        
        # Wait longer and check for various states
        for attempt in range(3):  # Try multiple times
            print(f"Intento {attempt + 1}/3...")
            
            for by_type, selector in password_selectors:
                try:
                    # First wait for presence
                    element = WebDriverWait(driver, 10).until(
                        EC.presence_of_element_located((by_type, selector))
                    )
                    
                    # Then wait for it to be clickable/enabled
                    password_input = WebDriverWait(driver, 5).until(
                        EC.element_to_be_clickable((by_type, selector))
                    )
                    
                    # Additional check - make sure it's actually interactable
                    if password_input.is_enabled() and password_input.is_displayed():
                        print(f"✅ Campo de contraseña encontrado y listo: {selector}")
                        break
                    else:
                        print(f"⚠️ Campo encontrado pero no interactuable: {selector}")
                        password_input = None
                        
                except TimeoutException:
                    continue
                except Exception as e:
                    print(f"⚠️ Error con selector {selector}: {e}")
                    continue
            
            if password_input:
                break
                
            # If not found, wait a bit and try again
            if attempt < 2:
                print("⏳ Esperando un momento antes de reintentar...")
                time.sleep(3)
        
        if not password_input:
            # Check if there's a CAPTCHA or 2FA challenge
            page_source = driver.page_source.lower()
            current_url = driver.current_url.lower()
            
            print(f"🔍 URL actual: {driver.current_url}")
            
            if "captcha" in page_source or "captcha" in current_url:
                print("❌ CAPTCHA detectado. Necesitas resolverlo manualmente.")
            elif "challenge" in current_url or "verify" in page_source or "phone" in page_source:
                print("❌ Verificación de 2FA/seguridad requerida.")
            elif "signin/v2/challenge" in current_url:
                print("❌ Google requiere verificación adicional.")
            else:
                print("❌ No se encontró el campo de contraseña.")
            
            # Save screenshot for debugging
            driver.save_screenshot("debug_password_page.png")
            print("📸 Screenshot guardada como 'debug_password_page.png'")
            
            # Try to find any input fields on the page for debugging
            try:
                all_inputs = driver.find_elements(By.TAG_NAME, "input")
                print(f"🔍 Campos de input encontrados: {len(all_inputs)}")
                for i, inp in enumerate(all_inputs[:5]):  # Show first 5
                    try:
                        inp_type = inp.get_attribute("type")
                        inp_name = inp.get_attribute("name")
                        inp_id = inp.get_attribute("id")
                        print(f"  {i+1}. type='{inp_type}', name='{inp_name}', id='{inp_id}'")
                    except:
                        pass
            except:
                pass
                
            raise Exception("No se pudo encontrar el campo de contraseña")
        
        # Multiple methods to enter password - more aggressive approach
        password_entered = False
        
        # Method 1: JavaScript direct (most reliable for Google)
        try:
            print("🔄 Método 1: JavaScript directo...")
            driver.execute_script("""
                var element = arguments[0];
                var password = arguments[1];
                
                // Remove readonly and disabled attributes
                element.removeAttribute('readonly');
                element.removeAttribute('disabled');
                
                // Focus on element
                element.focus();
                
                // Clear and set value
                element.value = '';
                element.value = password;
                
                // Trigger events that Google expects
                var events = ['focus', 'input', 'keydown', 'keypress', 'keyup', 'change', 'blur'];
                events.forEach(function(eventType) {
                    var event = new Event(eventType, {bubbles: true, cancelable: true});
                    element.dispatchEvent(event);
                });
            """, password_input, password)
            
            # Verify the password was entered
            time.sleep(1)
            entered_value = password_input.get_attribute("value")
            if entered_value == password:
                print("✅ Contraseña ingresada correctamente con JavaScript")
                password_entered = True
            else:
                print(f"⚠️ Valor verificado: {len(entered_value)} caracteres (esperado: {len(password)})")
                
        except Exception as e:
            print(f"⚠️ Método JavaScript falló: {e}")
        
        # Method 2: Selenium send_keys with extra steps
        if not password_entered:
            try:
                print("🔄 Método 2: Selenium mejorado...")
                
                # Click to focus
                driver.execute_script("arguments[0].click();", password_input)
                time.sleep(0.5)
                
                # Clear field multiple ways
                password_input.clear()
                driver.execute_script("arguments[0].value = '';", password_input)
                
                # Send keys slowly
                for char in password:
                    password_input.send_keys(char)
                    time.sleep(0.05)
                
                # Verify
                entered_value = password_input.get_attribute("value")
                if entered_value == password:
                    print("✅ Contraseña ingresada correctamente con Selenium")
                    password_entered = True
                    
            except Exception as e:
                print(f"⚠️ Método Selenium falló: {e}")
        
        # Method 3: Clipboard simulation
        if not password_entered:
            try:
                print("🔄 Método 3: Simulación de clipboard...")
                
                # Focus and select all
                password_input.click()
                driver.execute_script("arguments[0].select();", password_input)
                
                # Use JavaScript to simulate paste
                driver.execute_script("""
                    var element = arguments[0];
                    var text = arguments[1];
                    
                    element.value = text;
                    
                    // Simulate paste event
                    var pasteEvent = new ClipboardEvent('paste', {
                        clipboardData: new DataTransfer()
                    });
                    
                    element.dispatchEvent(pasteEvent);
                    element.dispatchEvent(new Event('input', {bubbles: true}));
                """, password_input, password)
                
                entered_value = password_input.get_attribute("value")
                if entered_value == password:
                    print("✅ Contraseña ingresada correctamente con clipboard")
                    password_entered = True
                    
            except Exception as e:
                print(f"⚠️ Método clipboard falló: {e}")
        
        # Method 4: Character by character with events
        if not password_entered:
            try:
                print("🔄 Método 4: Carácter por carácter con eventos...")
                
                password_input.clear()
                driver.execute_script("arguments[0].focus();", password_input)
                
                for i, char in enumerate(password):
                    # Send character
                    password_input.send_keys(char)
                    
                    # Trigger input event for each character
                    driver.execute_script("""
                        var element = arguments[0];
                        element.dispatchEvent(new Event('input', {bubbles: true}));
                    """, password_input)
                    
                    time.sleep(0.02)
                
                entered_value = password_input.get_attribute("value")
                if entered_value == password:
                    print("✅ Contraseña ingresada correctamente carácter por carácter")
                    password_entered = True
                    
            except Exception as e:
                print(f"⚠️ Método carácter por carácter falló: {e}")
        
        if not password_entered:
            print("❌ Ningún método pudo ingresar la contraseña")
            print("🔍 Información de debug:")
            print(f"   - Campo encontrado: {password_input.tag_name}")
            print(f"   - Habilitado: {password_input.is_enabled()}")
            print(f"   - Visible: {password_input.is_displayed()}")
            print(f"   - Valor actual: '{password_input.get_attribute('value')}'")
            
            # Try one last time with raw JavaScript
            try:
                print("🔄 Último intento: JavaScript crudo...")
                driver.execute_script(f"document.querySelector('input[name=\"password\"]').value = '{password}';")
                time.sleep(1)
                final_value = password_input.get_attribute("value")
                if final_value == password:
                    print("✅ Último intento exitoso")
                    password_entered = True
            except:
                pass
        
        if not password_entered:
            # Save screenshot and continue - sometimes it works even if we can't verify
            driver.save_screenshot("password_entry_failed.png")
            print("⚠️ No se pudo verificar la entrada de contraseña, pero continuando...")
            print("📸 Screenshot guardada como 'password_entry_failed.png'")
            
            # Set the password one more time before clicking next
            try:
                driver.execute_script(f"arguments[0].value = '{password}';", password_input)
            except:
                pass
        
        time.sleep(2)
        
        # Click password next button
        password_next_buttons = [
            (By.ID, "passwordNext"),
            (By.CSS_SELECTOR, "[data-test-id='passwordNext']"),
            (By.XPATH, "//span[text()='Next']/../.."),
            (By.XPATH, "//div[@role='button']//span[contains(text(), 'Next')]"),
        ]
        
        next_clicked = False
        for by_type, selector in password_next_buttons:
            try:
                next_button = driver.find_element(by_type, selector)
                driver.execute_script("arguments[0].click();", next_button)
                next_clicked = True
                print("✅ Botón de contraseña 'Next' clickeado")
                break
            except NoSuchElementException:
                continue
        
        if not next_clicked:
            password_input.send_keys(Keys.ENTER)
            print("⚠️ Usé Enter como alternativa para contraseña")
        
        # Wait for redirect to YouTube with longer timeout
        print("🔄 Esperando redirección a YouTube...")
        try:
            WebDriverWait(driver, 60).until(
                EC.any_of(
                    EC.url_contains("youtube.com"),
                    EC.url_contains("myaccount.google.com")
                )
            )
        except TimeoutException:
            current_url = driver.current_url
            if "challenge" in current_url or "signin/challenge" in current_url:
                print("❌ Desafío de seguridad detectado. Posible 2FA o verificación adicional requerida.")
                print("Ejecuta el script sin headless (headless=False) para completar manualmente.")
            else:
                print(f"❌ No se redirigió a YouTube. URL actual: {current_url}")
            
            # Save screenshot for debugging
            driver.save_screenshot("debug_final_page.png")
            print("📸 Screenshot guardada como 'debug_final_page.png'")
            return False
        
        # Navigate to YouTube to ensure we have YouTube cookies
        if "youtube.com" not in driver.current_url:
            print("🔄 Navegando a YouTube...")
            driver.get("https://www.youtube.com")
            time.sleep(5)
        
        # Wait for YouTube to load and establish session
        try:
            WebDriverWait(driver, 30).until(
                EC.any_of(
                    EC.presence_of_element_located((By.ID, "avatar-btn")),
                    EC.presence_of_element_located((By.CSS_SELECTOR, "[aria-label*='Account menu']")),
                    EC.presence_of_element_located((By.ID, "guide-button"))
                )
            )
            print("✅ Sesión de YouTube establecida")
        except TimeoutException:
            print("⚠️ No se pudo verificar la sesión de YouTube, pero continuando...")
        
        # Additional wait for cookies to be set
        time.sleep(5)
        
        # Save cookies
        save_cookies_netscape_format(driver, output_path)
        print(f"✅ Cookies guardadas en '{output_path}'")
        
        return True
        
    except Exception as e:
        print(f"❌ Error durante el proceso de login: {str(e)}")
        # Save screenshot for debugging
        try:
            driver.save_screenshot("debug_error.png")
            print("📸 Screenshot de error guardada como 'debug_error.png'")
        except:
            pass
        return False
        
    finally:
        driver.quit()

def test_cookies(cookie_path: str):
    """
    Prueba las cookies guardadas haciendo una petición a YouTube
    """
    try:
        import requests
        
        # Read cookies from file
        cookies_dict = {}
        with open(cookie_path, 'r') as f:
            for line in f:
                if line.startswith('#') or not line.strip():
                    continue
                parts = line.strip().split('\t')
                if len(parts) >= 7:
                    name = parts[5]
                    value = parts[6]
                    cookies_dict[name] = value
        
        # Test request to YouTube
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        }
        
        response = requests.get('https://www.youtube.com/', cookies=cookies_dict, headers=headers)
        
        if response.status_code == 200 and 'ytInitialData' in response.text:
            print("✅ Cookies funcionan correctamente")
            return True
        else:
            print("❌ Las cookies no parecen funcionar")
            return False
            
    except ImportError:
        print("⚠️ 'requests' no está instalado. No se pueden probar las cookies.")
        return None
    except Exception as e:
        print(f"❌ Error probando cookies: {e}")
        return False

def manual_intervention_mode(email: str, password: str, output_path: str):
    """
    Modo de intervención manual donde el usuario puede completar el login manualmente
    """
    print("🔄 Iniciando modo de intervención manual...")
    print("📋 Instrucciones:")
    print("1. Se abrirá el navegador automáticamente")
    print("2. El script completará el email automáticamente")
    print("3. Si aparece CAPTCHA o 2FA, resuélvelo manualmente")
    print("4. Presiona ENTER en esta consola cuando hayas completado el login")
    
    chrome_options = Options()
    chrome_options.add_argument("--disable-blink-features=AutomationControlled")
    chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
    chrome_options.add_experimental_option('useAutomationExtension', False)
    chrome_options.add_argument("--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
    chrome_options.add_argument("--window-size=1200,800")
    
    driver = webdriver.Chrome(options=chrome_options)
    driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
    
    try:
        # Navigate to Google login
        print("🔄 Navegando a Google Sign-in...")
        driver.get("https://accounts.google.com/signin/v2/identifier?service=youtube&continue=https://www.youtube.com/")
        
        # Try to fill email automatically
        time.sleep(3)
        try:
            email_input = driver.find_element(By.ID, "identifierId")
            email_input.clear()
            email_input.send_keys(email)
            time.sleep(1)
            driver.find_element(By.ID, "identifierNext").click()
            print("✅ Email completado automáticamente")
        except:
            print("⚠️ No se pudo completar el email automáticamente")
        
        # Wait for user to complete manually
        print("\n⏳ Completa el login manualmente en el navegador...")
        print("⏳ Cuando hayas completado el login y estés en YouTube, presiona ENTER aquí...")
        input()
        
        # Check if we're logged in
        current_url = driver.current_url
        if "youtube.com" not in current_url:
            print("🔄 Navegando a YouTube...")
            driver.get("https://www.youtube.com")
            time.sleep(5)
        
        # Save cookies
        save_cookies_netscape_format(driver, output_path)
        print(f"✅ Cookies guardadas en '{output_path}'")
        
        return True
        
    except Exception as e:
        print(f"❌ Error: {e}")
        return False
    finally:
        driver.quit()

if __name__ == "__main__":
    EMAIL = os.getenv("YOUTUBE_EMAIL")
    PASSWORD = os.getenv("YOUTUBE_PASSWORD")
    OUTPUT_PATH = os.getenv("YOUTUBE_COOKIES_PATH", "./cookies.txt")
    
    if not EMAIL or not PASSWORD:
        print("❌ Falta configurar variables de entorno YOUTUBE_EMAIL o YOUTUBE_PASSWORD")
    else:
        print("🚀 Iniciando proceso de extracción de cookies de YouTube...")
        print("\n🤖 Modo automático vs 👤 Modo manual:")
        print("1. Automático: Intenta hacer todo sin intervención")
        print("2. Manual: Abre navegador para que completes login manualmente")
        
        mode = input("\nElige modo (1 para automático, 2 para manual, Enter para automático): ").strip()
        
        if mode == "2":
            success = manual_intervention_mode(EMAIL, PASSWORD, OUTPUT_PATH)
        else:
            # Try automatic mode first
            success = login_youtube_and_save_cookies(EMAIL, PASSWORD, OUTPUT_PATH, headless=False)
            
            # If automatic fails, offer manual mode
            if not success:
                print("\n❌ Modo automático falló.")
                retry_manual = input("¿Quieres intentar modo manual? (y/N): ").strip().lower()
                if retry_manual == 'y':
                    success = manual_intervention_mode(EMAIL, PASSWORD, OUTPUT_PATH)
        
        if success:
            print("\n🎉 ¡Proceso completado exitosamente!")
            
            # Test the cookies
            print("\n🔍 Probando cookies...")
            test_result = test_cookies(OUTPUT_PATH)
            
            if test_result:
                print("✅ Las cookies están listas para usar con yt-dlp")
            elif test_result is None:
                print("⚠️ No se pudieron probar las cookies, pero deberían funcionar")
            
        else:
            print("\n❌ El proceso falló completamente.")
            print("💡 Soluciones alternativas:")
            print("   1. Usa una contraseña de aplicación si tienes 2FA")
            print("   2. Desactiva 2FA temporalmente")
            print("   3. Exporta cookies manualmente desde el navegador")