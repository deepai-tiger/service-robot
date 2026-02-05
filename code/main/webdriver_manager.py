# webdriver_manager.py
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.chrome.service import Service as ChromeService
from selenium.webdriver.chrome.options import Options as ChromeOptions
import time
from config_manager import load_server_config
import tempfile#####


def setup_webdriver():
    """Setup and return Chrome WebDriver for Raspberry Pi"""
    try:
        chrome_options = ChromeOptions()
        chrome_options.add_argument("--disable-gpu")
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        chrome_options.add_argument("--disable-web-security")
        chrome_options.add_argument("--allow-running-insecure-content")
        chrome_options.add_argument("--disable-extensions")
        chrome_options.add_argument("--disable-background-timer-throttling")
        chrome_options.add_argument("--disable-backgrounding-occluded-windows")
        chrome_options.add_argument("--disable-renderer-backgrounding")
        chrome_options.add_argument("--start-fullscreen")
        
        
        # Uncomment for headless mode (recommended for Raspberry Pi)
        # chrome_options.add_argument("--headless")
        #####
        user_data_dir = tempfile.mkdtemp()
        chrome_options.add_argument(f"--user-data-dir={user_data_dir}")
        #####
        # Use system-installed chromedriver
        service = ChromeService("/usr/bin/chromedriver")
        driver = webdriver.Chrome(service=service, options=chrome_options)
        driver.set_page_load_timeout(30)
        
        # Additional fullscreen setup
        driver.fullscreen_window()
        
        return driver
    except Exception as e:
        print(f"❌ Failed to setup WebDriver: {e}")
        raise

def perform_login(driver, robot_id, password):
    """Perform robot login"""
    try:
        server_ip = load_server_config()
        if not server_ip:
            print("❌ Server IP not configured. Exiting...")
            return False

        print("🌐 Navigating to login page...")
        driver.get(f"http://{server_ip}:5001/robot-login")
        time.sleep(3)

        print("🔍 Finding login elements...")
        robot_id_input = driver.find_element(By.XPATH, "//input[@placeholder='Robot ID']")
        robot_id_input.clear()
        robot_id_input.send_keys(robot_id)

        password_input = driver.find_element(By.XPATH, "//input[@placeholder='Password']")
        password_input.clear()
        password_input.send_keys(password)

        print("📝 Submitting login form...")
        password_input.send_keys(Keys.RETURN)
        time.sleep(5)

        current_url = driver.current_url
        print(f"📍 Current URL after login: {current_url}")
        
        return True
        
    except Exception as e:
        print(f"❌ Login failed: {e}")
        return False

def check_websocket_connection(driver):
    """Check WebSocket connection status"""
    try:
        websocket_status = driver.execute_script("""
            return window.webSocketManager ? 
                   (window.webSocketManager.ws ? window.webSocketManager.ws.readyState : 'No WebSocket') : 
                   'No WebSocketManager';
        """)
        
        print(f"🔌 WebSocket status: {websocket_status}")
        
        if websocket_status == 1:  # WebSocket.OPEN
            print("✅ WebSocket connection established successfully!")
            return True
        else:
            print("⚠️ WebSocket connection not ready")
            return False
            
    except Exception as e:
        print(f"❌ Error checking WebSocket status: {e}")
        return False

def close_websocket_connection(driver):
    """Close only the WebSocket connection, keep browser open"""
    try:
        print("🔌 Closing WebSocket connection...")
        driver.execute_script("""
            if (window.webSocketManager && window.webSocketManager.ws) {
                window.webSocketManager.ws.close();
                console.log('WebSocket connection closed');
            }
        """)
        print("✅ WebSocket connection closed, browser remains open")
        return True
    except Exception as e:
        print(f"❌ Error closing WebSocket connection: {e}")
        return False

def collect_credentials_from_web(driver):
    """Redirect user to a web interface to enter credentials and collect them after form submission."""
    try:
        server_ip = load_server_config()
        if not server_ip:
            print("❌ Server IP not configured. Exiting...")
            return None, None

        print("🌐 Redirecting to credentials setup page...")
        driver.get(f"http://{server_ip}:5001/robot-login")
        time.sleep(2)  # Give the page time to load

        # Inject JavaScript to flag when form is submitted
        driver.execute_script("""
            if (!window.__credentialsCollected) {
                window.__credentialsCollected = false;
                const form = document.querySelector('form.login-form');
                form.addEventListener('submit', function(event) {
                    event.preventDefault(); // prevent actual submission (optional)
                    window.__credentialsCollected = true;
                });
            }
        """)

        print("🔍 Waiting for user to submit the login form...")

        while True:
            is_submitted = driver.execute_script("return window.__credentialsCollected;")
            if is_submitted:
                robot_id = driver.execute_script("return document.querySelector('input[placeholder=\"Robot ID\"]').value || '';").strip()
                password = driver.execute_script("return document.querySelector('input[placeholder=\"Password\"]').value || '';").strip()
                
                if robot_id and password:
                    print("✅ Credentials submitted by user")
                    return robot_id, password
                else:
                    print("⚠️ Form submitted but fields are empty. Waiting...")
            
            time.sleep(1)

    except Exception as e:
        print(f"❌ Error collecting credentials from web: {e}")
        return None, None