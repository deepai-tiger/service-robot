# robot_login_and_listen2.py
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.chrome.service import Service as ChromeService
from selenium.webdriver.chrome.options import Options as ChromeOptions
import time
import json
import os
import threading
import sys
import traceback
import subprocess
import signal
from getpass import getpass

# Configuration file paths
CONFIG_FILE = "robot_config.json"
WEBSOCKET_DATA_FILE = "websocket_data.json"
MQTT_LOG_FILE = "mqtt_data_log.json"
ROBOT_CREDENTIALS_FILE = "robot_mqtt_credentials.json"
SERVER_CONFIG_FILE = "server_config.json"
SYSTEM_STATE_FILE = "system_state.json"

# Global variables for process management
motor_process = None
system_state = {"connected": False, "processes": []}

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

def save_system_state(state):
    """Save current system state"""
    try:
        with open(SYSTEM_STATE_FILE, "w") as file:
            json.dump(state, file, indent=2)
    except Exception as e:
        print(f"Error saving system state: {e}")

def load_system_state():
    """Load system state"""
    try:
        if os.path.exists(SYSTEM_STATE_FILE):
            with open(SYSTEM_STATE_FILE, "r") as file:
                return json.load(file)
    except Exception as e:
        print(f"Error loading system state: {e}")
    return {"connected": False, "processes": []}

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
        
        # Write to log file with timestamp
        with open(MQTT_LOG_FILE, "w") as log_file:
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

def extract_mqtt_credentials(data, robot_id):
    """Extract MQTT credentials from WebSocket data and save for robot control"""
    try:
        credentials = {
            "robotId": robot_id,
            "token": data.get("user", {}).get("token"),
            "timestamp": data.get("timestamp"),
            "topic": data.get("user", {}).get("topic"),  # Generated topic based on robot ID
            "extracted_at": time.time()
        }
        
        with open(ROBOT_CREDENTIALS_FILE, "w") as file:
            json.dump(credentials, file, indent=2)
        
        print(f"✓ MQTT credentials extracted and saved to {ROBOT_CREDENTIALS_FILE}")
        return True
    except Exception as e:
        print(f"✗ Error extracting MQTT credentials: {e}")
        return False

def start_robot_control():
    """Start the robot control script"""
    global motor_process, system_state
    try:
        print("🤖 Starting robot control script...")
        # Start the robot control script as a subprocess
        motor_process = subprocess.Popen([sys.executable, "motor_thread.py"])
        system_state["connected"] = True
        system_state["processes"] = [motor_process.pid]
        save_system_state(system_state)
        
        print("✅ Robot control script started successfully")
        return True
    except Exception as e:
        print(f"❌ Failed to start robot control script: {e}")
        return False

def stop_robot_control():
    """Stop all robot control processes"""
    global motor_process, system_state
    try:
        print("🛑 Stopping robot control processes...")
        
        if motor_process and motor_process.poll() is None:
            # Send termination signal to motor process
            motor_process.terminate()
            try:
                motor_process.wait(timeout=10)  # Wait up to 10 seconds
            except subprocess.TimeoutExpired:
                print("⚠️ Process didn't terminate gracefully, forcing kill...")
                motor_process.kill()
                motor_process.wait()
        
        # Clean up any remaining processes
        for pid in system_state.get("processes", []):
            try:
                os.kill(pid, signal.SIGTERM)
                time.sleep(1)
                os.kill(pid, signal.SIGKILL)  # Force kill if still running
            except ProcessLookupError:
                pass  # Process already terminated
            except Exception as e:
                print(f"⚠️ Error terminating process {pid}: {e}")
        
        # Clear credentials and state
        if os.path.exists(ROBOT_CREDENTIALS_FILE):
            os.remove(ROBOT_CREDENTIALS_FILE)
        if os.path.exists(MQTT_LOG_FILE):
            os.remove(MQTT_LOG_FILE)
        if os.path.exists(WEBSOCKET_DATA_FILE):
            os.remove(WEBSOCKET_DATA_FILE)
            
        system_state = {"connected": False, "processes": []}
        save_system_state(system_state)
        
        motor_process = None
        print("✅ Robot control stopped and cleaned up")
        return True
        
    except Exception as e:
        print(f"❌ Error stopping robot control: {e}")
        return False

def restart_robot_control():
    """Restart robot control using existing credentials"""
    try:
        if not os.path.exists(ROBOT_CREDENTIALS_FILE):
            print("❌ No existing credentials found for restart")
            return False
            
        print("🔄 Restarting robot control with existing credentials...")
        return start_robot_control()
        
    except Exception as e:
        print(f"❌ Error restarting robot control: {e}")
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

def wait_for_mqtt_message(driver, robot_id, timeout=18000):
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
        
        # Use system-installed chromedriver
        service = ChromeService("/usr/bin/chromedriver")
        driver = webdriver.Chrome(service=service, options=chrome_options)
        driver.set_page_load_timeout(30)
        
        # Additional fullscreen setup
        driver.maximize_window()
        
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
    global system_state
    driver = None
    
    try:
        # Load system state
        system_state = load_system_state()
        
        # Check if we need to reconnect with existing credentials
        if system_state.get("connected") and os.path.exists(ROBOT_CREDENTIALS_FILE):
            print("🔄 Attempting to reconnect with existing credentials...")
            if restart_robot_control():
                print("✅ Successfully reconnected!")
                return True
            else:
                print("❌ Failed to reconnect, starting fresh...")
                stop_robot_control()
        
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
        max_websocket_retries = 50
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
            
            # Extract credentials for robot control
            if extract_mqtt_credentials(mqtt_data, robot_id):
                print("🔑 MQTT credentials prepared for robot control")
                
                # Start robot control script
                if start_robot_control():
                    print("🤖 Robot control is now active!")
                    
                    # Close only WebSocket connection, keep browser open
                    close_websocket_connection(driver)
                    
                    print("✅ System is now running in MQTT-only mode")
                    print("📡 Robot will wait for disconnect/reconnect commands via MQTT")
                    
                    # Wait for system commands or manual interrupt
                    return wait_for_system_commands(driver)
                else:
                    print("⚠️ Failed to start robot control, but credentials are saved")
            
            return False
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

def wait_for_system_commands(driver):
    """Wait for disconnect/reconnect commands or manual interrupt"""
    global motor_process, system_state
    
    try:
        print("\n🎯 Monitoring system state...")
        print("💡 System will respond to MQTT disconnect/reconnect commands")
        print("🛑 Press Ctrl+C to manually stop the system")
        
        while True:
            # Check if motor process is still running
            if motor_process and motor_process.poll() is not None:
                print("⚠️ Motor process terminated unexpectedly")
                break
            
            # Check for system state changes
            current_state = load_system_state()
            
            if not current_state.get("connected", False):
                print("📡 Disconnect command received via MQTT")
                # Close browser and restart entire process
                print("🔒 Closing browser for full restart...")
                try:
                    driver.quit()
                except:
                    pass
                return False  # This will cause main() to restart the entire process
            
            time.sleep(5)  # Check every 5 seconds
            
    except KeyboardInterrupt:
        print("\n🛑 Manual shutdown requested")
        stop_robot_control()
        return True
    
    except Exception as e:
        print(f"❌ Error in system monitoring: {e}")
        return False
    
    return True

def main():
    """Main function with auto-restart capability"""
    max_retries = 3
    retry_count = 0
    
    print("🤖 Robot MQTT Monitor Starting...")
    print(f"📁 Config file: {CONFIG_FILE}")
    print(f"📁 Data files: {WEBSOCKET_DATA_FILE}, {MQTT_LOG_FILE}")
    print(f"📁 Robot credentials file: {ROBOT_CREDENTIALS_FILE}")
    print(f"📁 System state file: {SYSTEM_STATE_FILE}")
    
    # Cleanup any existing processes on startup
    stop_robot_control()
    
    while retry_count < max_retries:
        try:
            print(f"\n🔄 Attempt {retry_count + 1}/{max_retries}")
            
            success = main_robot_process()
            
            if success:
                print("✅ Process completed successfully!")
                # After successful completion, wait for new connect message
                print("🔄 Waiting for new connection...")
                continue  # Loop back to wait for new connection
            else:
                retry_count += 1
                if retry_count < max_retries:
                    wait_time = 10 * retry_count  # Increasing wait time
                    print(f"⏳ Waiting {wait_time} seconds before retry...")
                    time.sleep(wait_time)
                
        except KeyboardInterrupt:
            print("\n🛑 Process interrupted by user")
            stop_robot_control()
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