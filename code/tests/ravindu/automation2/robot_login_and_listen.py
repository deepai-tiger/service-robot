from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.edge.service import Service as EdgeService
from selenium.webdriver.edge.options import Options as EdgeOptions
import time
import json
import os
import threading
import sys
import traceback
from getpass import getpass

# Configuration file paths
CONFIG_FILE = "robot_config.json"
WEBSOCKET_DATA_FILE = "websocket_data.json"
MQTT_LOG_FILE = "mqtt_data_log.json"
SERVER_CONFIG_FILE = "server_config.json"

def load_robot_config():
    """Load robot credentials from config file"""
    try:
        if os.path.exists(CONFIG_FILE):
            with open(CONFIG_FILE, "r") as file:
                config = json.load(file)
                print(f"Loaded configuration for Robot ID: {config.get('robotId', 'Unknown')}")
                return config
        else:
            print("No configuration file found.")
            return None
    except Exception as e:
        print(f"Error loading configuration: {e}")
        return None

def save_robot_config(robot_id, password):
    """Save robot credentials to config file"""
    try:
        config = {
            "robotId": robot_id,
            "password": password,
            "lastUpdated": time.time()
        }
        with open(CONFIG_FILE, "w") as file:
            json.dump(config, file, indent=2)
        print(f"Configuration saved for Robot ID: {robot_id}")
        return True
    except Exception as e:
        print(f"Error saving configuration: {e}")
        return False

def get_user_credentials():
    """Get robot credentials from user input"""
    print("\n" + "="*50)
    print("ROBOT CREDENTIALS SETUP")
    print("="*50)
    
    robot_id = input("Enter Robot ID: ").strip()
    if not robot_id:
        print("Robot ID cannot be empty!")
        return None, None
    
    password = getpass("Enter Robot Password: ").strip()
    if not password:
        print("Password cannot be empty!")
        return None, None
    
    # Ask if user wants to save credentials
    save_choice = input("Save credentials for future use? (y/n): ").lower().strip()
    if save_choice in ['y', 'yes']:
        if save_robot_config(robot_id, password):
            print("Credentials saved successfully!")
        else:
            print("Failed to save credentials, but continuing...")
    
    return robot_id, password

def store_data_locally(data):
    """Store WebSocket/MQTT data locally"""
    try:
        # Store both in JSON file and a more persistent log
        with open(WEBSOCKET_DATA_FILE, "w") as file:
            json.dump(data, file, indent=2)
        
        # Append to log file with timestamp
        with open(MQTT_LOG_FILE, "a") as log_file:
            log_entry = {
                "timestamp": time.time(),
                "formatted_time": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime()),
                "data": data
            }
            log_file.write(json.dumps(log_entry) + "\n")
        
        print(f"✓ WebSocket data stored: {data}")
        return True
    except Exception as e:
        print(f"✗ Error storing WebSocket data locally: {e}")
        return False

def get_data_locally():
    """Retrieve locally stored WebSocket data"""
    try:
        if os.path.exists(WEBSOCKET_DATA_FILE):
            with open(WEBSOCKET_DATA_FILE, "r") as file:
                return json.load(file)
        else:
            print("No local WebSocket data found")
            return None
    except Exception as e:
        print(f"Error retrieving WebSocket data locally: {e}")
        return None

def wait_for_mqtt_message (driver, robot_id, timeout=18000):
    """Event-driven wait for MQTT authentication message."""
    print(f"🔄 Waiting for MQTT message for robot {robot_id}...")
    print(f"⏰ Timeout set to {timeout//3600} hours")

    from threading import Event, Thread
    import time

    result = {"data": None}
    done = Event()

    def watch_local_storage():
        check_count = 0
        while not done.is_set():
            try:
                websocket_data = driver.execute_script("return localStorage.getItem('webSocketData');")

                if websocket_data:
                    data = json.loads(websocket_data)

                    if data.get("type") == "connect" and data.get("user") and data["user"].get("token"):
                        print(f"\n📨 WebSocket data received: {data}")
                        print("🎉 MQTT authentication message received!")
                        print(f"🔑 ID Token: {data['user']['token'][:20]}...")
                        print(f"⏱️ Timestamp: {data.get('timestamp')}")
                        
                        if store_data_locally(data):
                            result["data"] = data
                        else:
                            print("⚠️ Failed to store data but continuing...")
                            result["data"] = data

                        done.set()
                        return

                check_count += 1
                if check_count % 15 == 0: # if check_count is a multiple of 15
                    elapsed = int(time.time() - start_time) # calculate elapsed time
                    remaining = timeout - elapsed # calculate remaining time
                    print(f"⏳ Waiting... {elapsed//60}m elapsed, {remaining//60}m remaining") # print elapsed and remaining time
                time.sleep(2) # Check every 2 seconds

            except Exception as e:
                print(f"\n⚠️ Error checking for MQTT message: {e}")
                time.sleep(5)

    start_time = time.time()
    thread = Thread(target=watch_local_storage)
    thread.start()

    done.wait(timeout)
    thread.join()

    if result["data"]:
        return result["data"]

    print(f"\n⏰ Timeout: No MQTT message received within {timeout//3600} hours")
    return None

def setup_webdriver():
    """Setup and return Edge WebDriver"""
    try:
        edge_options = EdgeOptions()
        edge_options.add_argument("--disable-gpu")
        edge_options.add_argument("--no-sandbox")
        edge_options.add_argument("--disable-dev-shm-usage")
        edge_options.add_argument("--disable-web-security")
        edge_options.add_argument("--allow-running-insecure-content")
        
        # Uncomment for headless mode
        # edge_options.add_argument("--headless")
        
        service = EdgeService("C:/Users/ravin/Downloads/edgedriver_win64/msedgedriver.exe")
        driver = webdriver.Edge(service=service, options=edge_options)
        driver.set_page_load_timeout(30)
        return driver
    except Exception as e:
        print(f"❌ Failed to setup WebDriver: {e}")
        raise

def load_server_config():
    """Load server configuration from file"""
    try:
        if os.path.exists(SERVER_CONFIG_FILE):
            with open(SERVER_CONFIG_FILE, "r") as file:
                config = json.load(file)
                server_ip = config.get("serverIp")
                if server_ip:
                    print(f"Loaded server IP: {server_ip}")
                    return server_ip
                else:
                    print("Server IP not found in configuration file.")
                    return None
        else:
            print("No server configuration file found.")
            return None
    except Exception as e:
        print(f"Error loading server configuration: {e}")
        return None

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

def main_robot_process():
    """Main robot process that handles login and MQTT monitoring"""
    driver = None
    
    try:
        # Load or get robot credentials
        config = load_robot_config()
        
        if config and config.get('robotId') and config.get('password'):
            robot_id = config['robotId']
            password = config['password']
            print(f"✅ Using saved credentials for Robot ID: {robot_id}")
        else:
            print("🔧 No valid configuration found. Setting up new credentials...")
            robot_id, password = get_user_credentials()
            
            if not robot_id or not password:
                print("❌ Invalid credentials provided. Exiting...")
                return False

        print(f"\n🚀 Starting robot monitoring process for: {robot_id}")
        print("=" * 60)
        
        # Setup WebDriver
        driver = setup_webdriver()
        
        # Perform login
        if not perform_login(driver, robot_id, password):
            print("❌ Login failed. Check credentials and try again.")
            return False
        
        # Wait for WebSocket connection
        time.sleep(3)
        
        # Check WebSocket connection
        max_websocket_retries = 5
        websocket_ready = False
        
        for attempt in range(max_websocket_retries):
            if check_websocket_connection(driver):
                websocket_ready = True
                break
            else:
                print(f"🔄 WebSocket not ready, attempt {attempt + 1}/{max_websocket_retries}")
                time.sleep(2)
        
        if not websocket_ready:
            print("❌ WebSocket connection failed after multiple attempts")
            return False
        
        # Wait for MQTT message
        print("\n📡 Starting MQTT message monitoring...")
        mqtt_data = wait_for_mqtt_message(driver, robot_id)
        
        if mqtt_data:
            print("\n🎉 MQTT Data Processing Complete!")
            print("📊 Final data:")
            print(json.dumps(mqtt_data, indent=2))
            
            # Keep monitoring for additional messages
            print("\n🔄 Continuing to monitor for additional messages...")
            print("Press Ctrl+C to exit...")
            
            try:
                while True:
                    # Check for new messages every 30 seconds
                    time.sleep(30)
                    new_data = driver.execute_script("return localStorage.getItem('webSocketData');")
                    if new_data:
                        try:
                            parsed_data = json.loads(new_data)
                            if parsed_data != mqtt_data:  # New message
                                print(f"📨 New message received: {parsed_data}")
                                store_data_locally(parsed_data)
                                mqtt_data = parsed_data
                        except:
                            pass  # Ignore parsing errors
                            
            except KeyboardInterrupt:
                print("\n🛑 Monitoring stopped by user")
                return True
        else:
            print("⏰ No MQTT message received within timeout period")
            return False
            
    except Exception as e:
        print(f"❌ Critical error in main process: {e}")
        traceback.print_exc()
        return False
        
    finally:
        if driver:
            print("🔒 Closing browser...")
            try:
                driver.quit()
            except:
                pass  # Ignore errors when closing driver

def main():
    """Main function with auto-restart capability"""
    max_retries = 3
    retry_count = 0
    
    print("🤖 Robot MQTT Monitor Starting...")
    print(f"📁 Config file: {CONFIG_FILE}")
    print(f"📁 Data files: {WEBSOCKET_DATA_FILE}, {MQTT_LOG_FILE}")
    
    while retry_count < max_retries:
        try:
            print(f"\n🔄 Attempt {retry_count + 1}/{max_retries}")
            
            success = main_robot_process()
            
            if success:
                print("✅ Process completed successfully!")
                break
            else:
                retry_count += 1
                if retry_count < max_retries:
                    wait_time = 10 * retry_count  # Increasing wait time
                    print(f"⏳ Waiting {wait_time} seconds before retry...")
                    time.sleep(wait_time)
                
        except KeyboardInterrupt:
            print("\n🛑 Process interrupted by user")
            break
        except Exception as e:
            print(f"💥 Unexpected error: {e}")
            traceback.print_exc()
            retry_count += 1
            
            if retry_count < max_retries:
                wait_time = 15 * retry_count
                print(f"⏳ Waiting {wait_time} seconds before retry...")
                time.sleep(wait_time)
    
    if retry_count >= max_retries:
        print(f"❌ Process failed after {max_retries} attempts")
        sys.exit(1)
    
    print("🏁 Robot MQTT Monitor finished")

if __name__ == "__main__":
    main()