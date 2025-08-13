import os
import time
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.common.action_chains import ActionChains
from dotenv import load_dotenv
from pathlib import Path
import requests

load_dotenv()

class YouTubeCookieExtractor:
    """
    Extractor completo de cookies de YouTube con múltiples métodos y anti-detección avanzada
    """
    
    def __init__(self, email: str, password: str, output_path: str = None):
        self.email = email
        self.password = password
        self.output_path = output_path or "cookies/youtube_cookies.txt"
        self.driver = None
        
    def _setup_chrome_options(self, headless: bool = False) -> Options:
        """Configuración avanzada de Chrome para evitar detección"""
        chrome_options = Options()
        
        # Anti-detección básica
        chrome_options.add_argument("--disable-blink-features=AutomationControlled")
        chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
        chrome_options.add_experimental_option('useAutomationExtension', False)
        chrome_options.add_argument("--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
        
        # Optimización de rendimiento
        chrome_options.add_argument("--disable-dev-shm-usage")
        chrome_options.add_argument("--disable-extensions")
        chrome_options.add_argument("--disable-plugins")
        chrome_options.add_argument("--disable-javascript-harmony-shipping")
        chrome_options.add_argument("--disable-background-timer-throttling")
        chrome_options.add_argument("--disable-backgrounding-occluded-windows")
        chrome_options.add_argument("--disable-renderer-backgrounding")
        chrome_options.add_argument("--disable-features=TranslateUI")
        chrome_options.add_argument("--disable-ipc-flooding-protection")
        chrome_options.add_argument("--no-first-run")
        chrome_options.add_argument("--no-service-autorun")
        chrome_options.add_argument("--password-store=basic")
        chrome_options.add_argument("--lang=en-US")
        
        # Configuraciones de privacidad
        prefs = {
            "credentials_enable_service": False,
            "profile.password_manager_enabled": False,
            "profile.default_content_setting_values.notifications": 2,
            "profile.default_content_settings.popups": 0,
            "profile.managed_default_content_settings.images": 2
        }
        chrome_options.add_experimental_option("prefs", prefs)
        
        if headless:
            chrome_options.add_argument("--headless=new")
        else:
            chrome_options.add_argument("--start-maximized")
        
        chrome_options.add_argument("--disable-gpu")
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-web-security")
        chrome_options.add_argument("--allow-running-insecure-content")
        
        return chrome_options
    
    def _apply_stealth_scripts(self, driver):
        """Aplicar scripts avanzados anti-detección"""
        stealth_js = """
            // Remove webdriver traces
            Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
            
            // Mock navigator properties
            Object.defineProperty(navigator, 'languages', {get: () => ['en-US', 'en']});
            Object.defineProperty(navigator, 'plugins', {get: () => [1, 2, 3, 4, 5]});
            Object.defineProperty(navigator, 'platform', {get: () => 'Win32'});
            Object.defineProperty(navigator, 'hardwareConcurrency', {get: () => 4});
            
            // Mock chrome object
            window.chrome = {
                runtime: {},
                loadTimes: function() { return {}; },
                csi: function() { return {}; },
                app: {}
            };
            
            // Override permission queries
            const originalQuery = window.navigator.permissions.query;
            window.navigator.permissions.query = (parameters) => (
                parameters.name === 'notifications' ?
                    Promise.resolve({ state: Notification.permission }) :
                    originalQuery(parameters)
            );
            
            // Remove automation indicators
            delete window.cdc_adoQpoasnfa76pfcZLmcfl_Array;
            delete window.cdc_adoQpoasnfa76pfcZLmcfl_Promise;
            delete window.cdc_adoQpoasnfa76pfcZLmcfl_Symbol;
            delete window.cdc_adoQpoasnfa76pfcZLmcfl_Object;
        """
        
        driver.execute_script(stealth_js)
        driver.execute_cdp_cmd('Page.addScriptToEvaluateOnNewDocument', {"source": stealth_js})
    
    def _save_cookies_netscape_format(self, driver, filename: str):
        """Guarda cookies en formato Netscape para yt-dlp"""
        # Crear directorio si no existe
        Path(filename).parent.mkdir(parents=True, exist_ok=True)
        
        # Obtener cookies de múltiples dominios
        all_cookies = []
        
        # Cookies del dominio actual
        current_cookies = driver.get_cookies()
        all_cookies.extend(current_cookies)
        
        # Navegar a YouTube para obtener cookies específicas
        current_url = driver.current_url
        if "youtube.com" not in current_url:
            print("🔄 Navegando a YouTube para obtener cookies específicas...")
            driver.get("https://www.youtube.com")
            time.sleep(5)
            
            youtube_cookies = driver.get_cookies()
            existing_names = {c['name'] for c in all_cookies}
            for cookie in youtube_cookies:
                if cookie['name'] not in existing_names:
                    all_cookies.append(cookie)
        
        # Obtener cookies de YouTube Music
        try:
            print("🔄 Obteniendo cookies de YouTube Music...")
            driver.get("https://music.youtube.com")
            time.sleep(3)
            music_cookies = driver.get_cookies()
            
            existing_names = {c['name'] for c in all_cookies}
            for cookie in music_cookies:
                if cookie['name'] not in existing_names:
                    all_cookies.append(cookie)
        except:
            print("⚠️ No se pudieron obtener cookies de YouTube Music")
        
        # Escribir cookies al archivo
        with open(filename, "w", encoding="utf-8") as f:
            f.write("# Netscape HTTP Cookie File\n")
            f.write("# This file is generated by YouTube Cookie Extractor. Do not edit.\n")
            
            all_cookies.sort(key=lambda x: x['domain'])
            
            for c in all_cookies:
                domain = c['domain']
                if not domain.startswith('.') and not domain.startswith('www.'):
                    domain = '.' + domain
                
                flag = "TRUE" if domain.startswith(".") else "FALSE"
                path = c['path']
                secure = "TRUE" if c['secure'] else "FALSE"
                expiry = str(c.get('expiry', 0))
                name = c['name']
                value = c['value']
                
                line = f"{domain}\t{flag}\t{path}\t{secure}\t{expiry}\t{name}\t{value}\n"
                f.write(line)
    
    def _wait_for_human_verification(self, driver, max_wait=300):
        """Espera verificación manual como CAPTCHA o 2FA"""
        print("🤖 Detectando si hay verificaciones pendientes...")
        start_time = time.time()
        
        while time.time() - start_time < max_wait:
            current_url = driver.current_url.lower()
            
            if any(keyword in current_url for keyword in ['challenge', 'verify', 'captcha']):
                print("🔒 Verificación detectada. Esperando intervención manual...")
                print("⏳ Resuelve la verificación en el navegador y el script continuará automáticamente...")
                time.sleep(5)
                continue
            
            if "youtube.com" in current_url or "myaccount.google.com" in current_url:
                print("✅ Verificación completada exitosamente")
                return True
            
            time.sleep(2)
        
        return False
    
    def _enter_email(self, driver):
        """Ingresar email con múltiples métodos"""
        print("🔄 Ingresando email...")
        email_selectors = [
            (By.ID, "identifierId"),
            (By.NAME, "identifier"),
            (By.CSS_SELECTOR, "input[type='email']"),
            (By.XPATH, "//input[@type='email']")
        ]
        
        email_input = None
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
            driver.save_screenshot("debug_no_email_field.png")
            raise Exception("No se pudo encontrar el campo de email")
        
        # Método JavaScript para ingresar email
        try:
            driver.execute_script("""
                var emailField = arguments[0];
                var email = arguments[1];
                
                emailField.focus();
                emailField.value = '';
                emailField.value = email;
                
                var events = ['input', 'change', 'blur'];
                events.forEach(function(eventType) {
                    var event = new Event(eventType, {bubbles: true, cancelable: true});
                    emailField.dispatchEvent(event);
                });
            """, email_input, self.email)
            print("✅ Email ingresado con JavaScript")
        except Exception as e:
            print(f"⚠️ JavaScript falló: {e}, usando método alternativo...")
            email_input.clear()
            ActionChains(driver).click(email_input).pause(0.5).send_keys(self.email).perform()
        
        time.sleep(2)
        
        # Hacer clic en Next
        next_buttons = [
            (By.ID, "identifierNext"),
            (By.CSS_SELECTOR, "[data-test-id='identifierNext']"),
            (By.XPATH, "//span[text()='Next']/../.."),
            (By.XPATH, "//div[@role='button' and .//span[contains(text(), 'Next')]]")
        ]
        
        for by_type, selector in next_buttons:
            try:
                next_button = driver.find_element(by_type, selector)
                driver.execute_script("arguments[0].click();", next_button)
                print("✅ Botón 'Next' para email clickeado")
                break
            except NoSuchElementException:
                continue
        else:
            email_input.send_keys(Keys.ENTER)
            print("⚠️ Usé Enter para email")
    
    def _enter_password(self, driver):
        """Ingresar contraseña con métodos múltiples"""
        print("🔄 Ingresando contraseña...")
        
        password_selectors = [
            (By.NAME, "password"),
            (By.ID, "password"),
            (By.CSS_SELECTOR, "input[type='password']"),
            (By.XPATH, "//input[@type='password']"),
            (By.XPATH, "//input[@name='Passwd']")
        ]
        
        password_input = None
        for attempt in range(5):
            print(f"Intento de contraseña {attempt + 1}/5...")
            
            for by_type, selector in password_selectors:
                try:
                    password_input = WebDriverWait(driver, 8).until(
                        EC.presence_of_element_located((by_type, selector))
                    )
                    
                    WebDriverWait(driver, 5).until(
                        EC.element_to_be_clickable((by_type, selector))
                    )
                    
                    if password_input.is_enabled() and password_input.is_displayed():
                        print(f"✅ Campo de contraseña listo: {selector}")
                        break
                    else:
                        password_input = None
                        
                except TimeoutException:
                    continue
            
            if password_input:
                break
                
            if attempt < 4:
                time.sleep(3)
        
        if not password_input:
            current_url = driver.current_url.lower()
            if any(word in current_url for word in ['challenge', 'verify', 'captcha']):
                print("🔒 Verificación de seguridad detectada...")
                if self._wait_for_human_verification(driver):
                    time.sleep(5)
                    for by_type, selector in password_selectors:
                        try:
                            password_input = driver.find_element(by_type, selector)
                            if password_input.is_enabled() and password_input.is_displayed():
                                break
                        except:
                            continue
            
            if not password_input:
                driver.save_screenshot("debug_no_password_field.png")
                raise Exception("No se pudo encontrar el campo de contraseña después de múltiples intentos")
        
        # Métodos múltiples para ingresar contraseña
        password_success = False
        methods = [
            "javascript_ultimate",
            "action_chains", 
            "selenium_basic",
            "character_by_character"
        ]
        
        for method in methods:
            try:
                print(f"🔄 Método de contraseña: {method}")
                
                if method == "javascript_ultimate":
                    driver.execute_script("""
                        var passwordField = arguments[0];
                        var password = arguments[1];
                        
                        passwordField.removeAttribute('readonly');
                        passwordField.removeAttribute('disabled');
                        passwordField.style.pointerEvents = 'auto';
                        passwordField.style.display = 'block';
                        passwordField.style.visibility = 'visible';
                        
                        passwordField.focus();
                        passwordField.value = '';
                        passwordField.value = password;
                        
                        var events = [
                            'focus', 'click', 'keydown', 'keypress', 'input', 
                            'keyup', 'change', 'blur'
                        ];
                        
                        events.forEach(function(eventType) {
                            var event = new Event(eventType, {
                                bubbles: true, 
                                cancelable: true,
                                view: window
                            });
                            passwordField.dispatchEvent(event);
                        });
                        
                        return passwordField.value === password;
                    """, password_input, self.password)
                    
                elif method == "action_chains":
                    ActionChains(driver).move_to_element(password_input).click().pause(0.5).send_keys(self.password).perform()
                    
                elif method == "selenium_basic":
                    password_input.clear()
                    password_input.send_keys(self.password)
                    
                elif method == "character_by_character":
                    password_input.clear()
                    for char in self.password:
                        password_input.send_keys(char)
                        time.sleep(0.02)
                
                time.sleep(1)
                entered_value = password_input.get_attribute("value")
                
                if entered_value and len(entered_value) >= len(self.password) * 0.8:
                    print(f"✅ Contraseña ingresada correctamente con {method}")
                    password_success = True
                    break
                else:
                    print(f"⚠️ {method} falló - Valor: {len(entered_value) if entered_value else 0} caracteres")
                    
            except Exception as e:
                print(f"⚠️ Método {method} falló: {e}")
                continue
        
        if not password_success:
            print("⚠️ Todos los métodos de contraseña fallaron, continuando de todos modos...")
        
        time.sleep(2)
        
        # Hacer clic en Next para contraseña
        password_next_buttons = [
            (By.ID, "passwordNext"),
            (By.CSS_SELECTOR, "[data-test-id='passwordNext']"),
            (By.XPATH, "//div[@role='button' and .//span[contains(text(), 'Next')]]"),
            (By.XPATH, "//span[text()='Next']/../..")
        ]
        
        for by_type, selector in password_next_buttons:
            try:
                next_button = driver.find_element(by_type, selector)
                driver.execute_script("arguments[0].click();", next_button)
                print("✅ Botón 'Next' para contraseña clickeado")
                break
            except NoSuchElementException:
                continue
        else:
            password_input.send_keys(Keys.ENTER)
            print("⚠️ Usé Enter para contraseña")
    
    def extract_cookies_automatic(self, headless: bool = False):
        """Método automático completo para extraer cookies"""
        print("🚀 Iniciando extracción automática de cookies...")
        
        chrome_options = self._setup_chrome_options(headless)
        driver = webdriver.Chrome(options=chrome_options)
        self._apply_stealth_scripts(driver)
        
        try:
            # Fase 1: Establecer sesión con YouTube
            print("🔄 Fase 1: Estableciendo sesión con YouTube...")
            driver.get("https://www.youtube.com")
            time.sleep(3)
            
            # Hacer clic en Sign In
            try:
                sign_in_selectors = [
                    (By.CSS_SELECTOR, "a[aria-label*='Sign in']"),
                    (By.XPATH, "//a[contains(@href, 'accounts.google.com')]"),
                    (By.CSS_SELECTOR, "[href*='accounts.google.com/signin']"),
                    (By.XPATH, "//yt-button-renderer//a[contains(@href, 'signin')]")
                ]
                
                sign_in_clicked = False
                for by_type, selector in sign_in_selectors:
                    try:
                        sign_in_btn = WebDriverWait(driver, 10).until(
                            EC.element_to_be_clickable((by_type, selector))
                        )
                        driver.execute_script("arguments[0].click();", sign_in_btn)
                        print("✅ Botón 'Sign In' de YouTube clickeado")
                        sign_in_clicked = True
                        break
                    except TimeoutException:
                        continue
                
                if not sign_in_clicked:
                    print("⚠️ No se encontró botón de Sign In, navegando directamente...")
                    driver.get("https://accounts.google.com/signin/v2/identifier?service=youtube&continue=https://www.youtube.com/&hl=en")
                    
            except Exception as e:
                print(f"⚠️ Error en botón Sign In: {e}")
                driver.get("https://accounts.google.com/signin/v2/identifier?service=youtube&continue=https://www.youtube.com/&hl=en")
            
            time.sleep(5)
            
            # Fase 2: Ingresar email
            print("🔄 Fase 2: Ingresando email...")
            self._enter_email(driver)
            time.sleep(5)
            
            # Fase 3: Ingresar contraseña
            print("🔄 Fase 3: Ingresando contraseña...")
            self._enter_password(driver)
            
            # Fase 4: Manejar verificaciones post-login
            print("🔄 Fase 4: Manejando verificaciones post-login...")
            start_time = time.time()
            max_wait = 120
            
            while time.time() - start_time < max_wait:
                current_url = driver.current_url.lower()
                
                if "youtube.com" in current_url or "myaccount.google.com" in current_url:
                    print("✅ Login exitoso!")
                    break
                    
                if any(word in current_url for word in ['challenge', 'verify', 'captcha']):
                    print("🔒 Verificación adicional requerida...")
                    if not headless:
                        print("👤 Resuelve la verificación manualmente en el navegador...")
                        self._wait_for_human_verification(driver, max_wait=max_wait - int(time.time() - start_time))
                    else:
                        print("❌ Verificación requerida pero modo headless activo")
                        return False
                
                time.sleep(3)
            
            # Fase 5: Recopilar cookies completas
            print("🔄 Fase 5: Recolectando cookies de YouTube...")
            
            if "youtube.com" not in driver.current_url:
                driver.get("https://www.youtube.com")
                time.sleep(5)
            
            # Navegar a diferentes páginas para obtener todas las cookies
            youtube_pages = [
                "https://www.youtube.com/",
                "https://www.youtube.com/feed/subscriptions",
                "https://www.youtube.com/playlist?list=WL",
                "https://music.youtube.com/"
            ]
            
            for page in youtube_pages:
                try:
                    print(f"📄 Visitando: {page}")
                    driver.get(page)
                    time.sleep(3)
                except:
                    continue
            
            driver.get("https://www.youtube.com")
            time.sleep(5)
            
            # Verificar sesión
            try:
                WebDriverWait(driver, 20).until(
                    EC.any_of(
                        EC.presence_of_element_located((By.ID, "avatar-btn")),
                        EC.presence_of_element_located((By.CSS_SELECTOR, "[aria-label*='Account menu']")),
                        EC.presence_of_element_located((By.CSS_SELECTOR, "#buttons ytd-topbar-menu-button-renderer")),
                        EC.presence_of_element_located((By.ID, "guide-button"))
                    )
                )
                print("✅ Sesión de YouTube verificada")
            except TimeoutException:
                print("⚠️ No se pudo verificar completamente la sesión, pero continuando...")
            
            # Guardar cookies
            self._save_cookies_netscape_format(driver, self.output_path)
            print(f"✅ Cookies completas guardadas en '{self.output_path}'")
            
            return True
            
        except Exception as e:
            print(f"❌ Error durante el login: {str(e)}")
            try:
                driver.save_screenshot("debug_login_error.png")
                print("📸 Screenshot guardada como 'debug_login_error.png'")
            except:
                pass
            return False
            
        finally:
            driver.quit()
    
    def extract_cookies_manual(self):
        """Modo manual guiado para extraer cookies"""
        print("🔄 Iniciando modo de intervención manual mejorado...")
        print("📋 Instrucciones detalladas:")
        print("1. Se abrirá Chrome automáticamente")
        print("2. El script intentará completar email y contraseña")
        print("3. SI aparece CAPTCHA o 2FA, resuélvelo TÚ manualmente")
        print("4. NAVEGA manualmente a diferentes páginas de YouTube:")
        print("   - https://www.youtube.com/")
        print("   - https://www.youtube.com/feed/subscriptions")
        print("   - https://music.youtube.com/")
        print("5. Cuando termines, presiona ENTER aquí")
        
        chrome_options = Options()
        chrome_options.add_argument("--disable-blink-features=AutomationControlled")
        chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
        chrome_options.add_experimental_option('useAutomationExtension', False)
        chrome_options.add_argument("--start-maximized")
        
        driver = webdriver.Chrome(options=chrome_options)
        driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
        
        try:
            print("🔄 Navegando a YouTube...")
            driver.get("https://www.youtube.com")
            time.sleep(3)
            
            try:
                sign_in_btn = driver.find_element(By.CSS_SELECTOR, "a[aria-label*='Sign in']")
                sign_in_btn.click()
                time.sleep(3)
            except:
                driver.get("https://accounts.google.com/signin/v2/identifier?service=youtube&continue=https://www.youtube.com/")
                time.sleep(3)
            
            # Intentar completar email automáticamente
            try:
                email_input = driver.find_element(By.ID, "identifierId")
                email_input.clear()
                email_input.send_keys(self.email)
                time.sleep(1)
                driver.find_element(By.ID, "identifierNext").click()
                print("✅ Email completado automáticamente")
                time.sleep(5)
                
                try:
                    password_input = driver.find_element(By.NAME, "password")
                    password_input.clear()
                    password_input.send_keys(self.password)
                    time.sleep(1)
                    driver.find_element(By.ID, "passwordNext").click()
                    print("✅ Contraseña completada automáticamente")
                except:
                    print("⚠️ Completa la contraseña manualmente")
                    
            except:
                print("⚠️ Completa el login manualmente")
            
            print("\n" + "="*60)
            print("👤 INTERVENCIÓN MANUAL REQUERIDA")
            print("="*60)
            print("🔧 Completa cualquier verificación que aparezca")
            print("🌐 Navega a estas páginas para obtener todas las cookies:")
            print("   1. https://www.youtube.com/")
            print("   2. https://www.youtube.com/feed/subscriptions")
            print("   3. https://music.youtube.com/")
            print("⏳ Cuando hayas terminado, presiona ENTER aquí...")
            print("="*60)
            
            input()
            
            current_url = driver.current_url
            if "youtube.com" not in current_url:
                print("🔄 Navegando a YouTube para recoger cookies...")
                driver.get("https://www.youtube.com")
                time.sleep(5)
            
            self._save_cookies_netscape_format(driver, self.output_path)
            print(f"✅ Cookies guardadas en '{self.output_path}'")
            
            return True
            
        except Exception as e:
            print(f"❌ Error en modo manual: {e}")
            return False
        finally:
            driver.quit()
    
    def test_cookies(self):
        """Prueba exhaustiva de las cookies guardadas"""
        try:
            cookies_dict = {}
            with open(self.output_path, 'r') as f:
                for line in f:
                    if line.startswith('#') or not line.strip():
                        continue
                    parts = line.strip().split('\t')
                    if len(parts) >= 7:
                        domain = parts[0]
                        name = parts[5]
                        value = parts[6]
                        
                        if 'youtube' in domain or 'google' in domain:
                            cookies_dict[name] = value
            
            print(f"🔍 Probando con {len(cookies_dict)} cookies...")
            
            test_urls = [
                "https://www.youtube.com/",
                "https://www.youtube.com/feed/subscriptions",
                "https://music.youtube.com/"
            ]
            
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
                'Accept-Language': 'en-US,en;q=0.5',
                'Accept-Encoding': 'gzip, deflate, br',
                'Connection': 'keep-alive'
            }
            
            session = requests.Session()
            session.headers.update(headers)
            
            success_count = 0
            for url in test_urls:
                try:
                    response = session.get(url, cookies=cookies_dict, timeout=30)
                    
                    if response.status_code == 200:
                        content = response.text.lower()
                        
                        login_indicators = [
                            'ytd-masthead',
                            '"isloggedin":true',
                            '"logged_in":true',
                            'ytInitialData',
                            'account-name'
                        ]
                        
                        if any(indicator in content for indicator in login_indicators):
                            print(f"✅ {url} - Autenticado correctamente")
                            success_count += 1
                        else:
                            print(f"⚠️ {url} - Respuesta recibida pero sin indicadores de login")
                    else:
                        print(f"❌ {url} - Error HTTP {response.status_code}")
                        
                except Exception as e:
                    print(f"❌ {url} - Error: {e}")
            
            if success_count >= len(test_urls) * 0.5:
                print("✅ Las cookies funcionan correctamente")
                return True
            else:
                print("❌ Las cookies no parecen funcionar adecuadamente")
                return False
                
        except Exception as e:
            print(f"❌ Error probando cookies: {e}")
            return False
    
    def run(self, mode: str = "hybrid", headless: bool = False):
        """
        Ejecutar extracción de cookies
        
        Args:
            mode: "automatic", "manual", o "hybrid"
            headless: True para ejecutar sin interfaz gráfica
        """
        success = False
        
        if mode == "automatic":
            print("\n🤖 Iniciando modo automático avanzado...")
            success = self.extract_cookies_automatic(headless=headless)
            
        elif mode == "manual":
            print("\n👤 Iniciando modo manual guiado...")
            success = self.extract_cookies_manual()
            
        else:  # hybrid mode
            print("\n🔄 Iniciando modo híbrido...")
            print("🤖 Intentando primero automático...")
            success = self.extract_cookies_automatic(headless=headless)
            
            if not success:
                print("\n❌ Modo automático falló.")
                retry_manual = input("¿Quieres intentar modo manual? (Y/n): ").strip().lower()
                if retry_manual != 'n':
                    print("\n👤 Cambiando a modo manual...")
                    success = self.extract_cookies_manual()
        
        # Resultados y pruebas
        if success:
            print("\n" + "="*60)
            print("🎉 ¡EXTRACCIÓN COMPLETADA EXITOSAMENTE!")
            print("="*60)
            
            print("\n🔍 Probando cookies extraídas...")
            test_result = self.test_cookies()
            
            if test_result:
                print("\n✅ COOKIES VALIDADAS - Listas para usar")
                print("🚀 Ahora puedes usar yt-dlp con estas cookies:")
                print(f"   yt-dlp --cookies {self.output_path} [URL]")
                
                try:
                    with open(self.output_path, 'r') as f:
                        lines = f.readlines()
                        cookie_lines = [l for l in lines if not l.startswith('#') and l.strip()]
                        youtube_cookies = [l for l in cookie_lines if 'youtube' in l.lower()]
                        google_cookies = [l for l in cookie_lines if 'google' in l.lower()]
                        
                    print(f"\n📊 Estadísticas de cookies:")
                    print(f"   📝 Total de cookies: {len(cookie_lines)}")
                    print(f"   🎥 Cookies de YouTube: {len(youtube_cookies)}")
                    print(f"   🔍 Cookies de Google: {len(google_cookies)}")
                    
                except:
                    pass
                    
            elif test_result is None:
                print("\n⚠️ No se pudieron probar las cookies (falta requests)")
                print("🤞 Pero deberían funcionar con yt-dlp")
                
            else:
                print("\n⚠️ Las cookies pueden no funcionar completamente")
                print("💡 Sugerencias:")
                print("   - Intenta el modo manual si usaste automático")
                print("   - Verifica que tienes acceso completo a YouTube")
                print("   - Considera usar una contraseña de aplicación")
        
        else:
            print("\n" + "="*60)
            print("❌ EXTRACCIÓN FALLÓ")
            print("="*60)
            self._show_troubleshooting_tips()
        
        print(f"\n📁 Archivo de cookies: {self.output_path}")
        print("🔚 Proceso terminado.")
        
        return success
    
    def _show_troubleshooting_tips(self):
        """Mostrar consejos de solución de problemas"""
        print("\n🔧 Soluciones recomendadas:")
        print("1. 🔑 Usa una contraseña de aplicación:")
        print("   - Ve a tu cuenta de Google")
        print("   - Seguridad → Verificación en 2 pasos → Contraseñas de aplicaciones")
        print("   - Genera una contraseña específica para esta aplicación")
        
        print("\n2. ⚙️ Configuración de cuenta:")
        print("   - Desactiva temporalmente la verificación en 2 pasos")
        print("   - Asegúrate de que tu cuenta no esté bloqueada")
        
        print("\n3. 🌐 Método manual alternativo:")
        print("   - Usa la extensión 'Get cookies.txt LOCALLY' en Chrome")
        print("   - Inicia sesión en YouTube manualmente")
        print("   - Exporta las cookies directamente")
        
        print("\n4. 🐛 Debug:")
        print("   - Revisa las screenshots generadas")
        print("   - Verifica tu conexión a internet")
        print("   - Intenta desde una IP diferente")


# Funciones de conveniencia para mantener compatibilidad
def save_cookies_netscape_format(driver, filename: str):
    """Función legacy para compatibilidad"""
    extractor = YouTubeCookieExtractor("", "", filename)
    extractor._save_cookies_netscape_format(driver, filename)


def login_youtube_and_save_cookies(email: str, password: str, output_path: str, headless: bool = False):
    """Función legacy para compatibilidad"""
    extractor = YouTubeCookieExtractor(email, password, output_path)
    return extractor.extract_cookies_automatic(headless)


def test_cookies_comprehensive(cookie_path: str):
    """Función legacy para compatibilidad"""
    extractor = YouTubeCookieExtractor("", "", cookie_path)
    return extractor.test_cookies()


def manual_intervention_mode(email: str, password: str, output_path: str):
    """Función legacy para compatibilidad"""
    extractor = YouTubeCookieExtractor(email, password, output_path)
    return extractor.extract_cookies_manual()


# Función principal mejorada
def main():
    """Función principal con interfaz mejorada"""
    EMAIL = os.getenv("YOUTUBE_EMAIL")
    PASSWORD = os.getenv("YOUTUBE_PASSWORD")
    OUTPUT_PATH = os.getenv("YOUTUBE_COOKIES_PATH", "app/cookies/cookies.txt")
    
    if not EMAIL or not PASSWORD:
        print("❌ Falta configurar variables de entorno YOUTUBE_EMAIL o YOUTUBE_PASSWORD")
        print("📝 Configura tu archivo .env con:")
        print("   YOUTUBE_EMAIL=tu_email@gmail.com")
        print("   YOUTUBE_PASSWORD=tu_contraseña_o_app_password")
        print("   YOUTUBE_COOKIES_PATH=app/cookies/cookies.txt")
        return False
    
    # Crear directorio de cookies si no existe
    Path(OUTPUT_PATH).parent.mkdir(parents=True, exist_ok=True)
    
    print("🚀 YouTube Cookie Extractor - Versión Estructurada")
    print("="*60)
    print("🎯 Este script obtiene TODAS las cookies necesarias para yt-dlp")
    print("🔐 Incluye cookies de YouTube, YouTube Music y Google")
    print("🤖 Usa técnicas avanzadas anti-detección")
    print("="*60)
    
    print("\n📋 Modos disponibles:")
    print("1. 🤖 Automático Avanzado - Usa múltiples técnicas de evasión")
    print("2. 👤 Manual Guiado - Te guía paso a paso para máxima efectividad")
    print("3. 🔄 Híbrido - Intenta automático, luego manual si falla")
    
    while True:
        mode_input = input("\n🔧 Elige modo (1, 2, 3, o Enter para híbrido): ").strip()
        if mode_input in ['1', '2', '3', '']:
            break
        print("⚠️ Por favor elige 1, 2, 3 o presiona Enter")
    
    # Mapear entrada a modo
    mode_map = {'1': 'automatic', '2': 'manual', '3': 'hybrid', '': 'hybrid'}
    mode = mode_map[mode_input]
    
    # Crear extractor y ejecutar
    extractor = YouTubeCookieExtractor(EMAIL, PASSWORD, OUTPUT_PATH)
    return extractor.run(mode=mode, headless=False)


if __name__ == "__main__":
    main()