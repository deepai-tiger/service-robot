# robot_main.py
import json
import time
import sys
import traceback
import os
import threading
from config_manager import (
    load_robot_config, get_user_credentials, load_system_state, save_robot_config,
    CONFIG_FILE, WEBSOCKET_DATA_FILE, MQTT_LOG_FILE, 
    ROBOT_CREDENTIALS_FILE, SYSTEM_STATE_FILE
)
from data_manager import extract_mqtt_credentials
from process_manager import (
    start_robot_control, stop_robot_control, restart_robot_control,
    wait_for_system_commands
)
from webdriver_manager import (
    setup_webdriver, perform_login, check_websocket_connection,
    close_websocket_connection, collect_credentials_from_web
)
from mqtt_monitor import wait_for_mqtt_message
from wifi_manager import main as wifi_setup

def main_robot_process():
    """Main robot process that handles login and MQTT monitoring"""
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
            print("🔧 No valid configuration found. Redirecting to web interface for credentials...")
            driver = setup_webdriver()
            robot_id, password = collect_credentials_from_web(driver)
            
            if not robot_id or not password:
                print("❌ Failed to collect credentials. Exiting...")
                return False
            
            save_robot_config(robot_id, password)
            print("✅ Credentials saved successfully!")

        print(f"\n🚀 Starting robot monitoring process for: {robot_id}")
        print("=" * 60)
        
        # Setup WebDriver
        if not driver:
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

def main():
    """Main function with indefinite retry capability"""
    print("🤖 Robot MQTT Monitor Starting...")
    
    # Initialize WiFi manager
    print("📶 Starting WiFi setup...")
    wifi_thread = threading.Thread(target=wifi_setup)
    wifi_thread.daemon = True
    wifi_thread.start()
    
    print(f"📁 Config file: {CONFIG_FILE}")
    print(f"📁 Data files: {WEBSOCKET_DATA_FILE}, {MQTT_LOG_FILE}")
    print(f"📁 Robot credentials file: {ROBOT_CREDENTIALS_FILE}")
    print(f"📁 System state file: {SYSTEM_STATE_FILE}")
    
    # Cleanup any existing processes on startup
    stop_robot_control()
    
    while True:  # Retry indefinitely
        try:
            print("\n🔄 Starting main robot process...")
            
            success = main_robot_process()
            
            if success:
                print("✅ Process completed successfully!")
                # After successful completion, wait for new connect message
                print("🔄 Waiting for new connection...")
                continue  # Loop back to wait for new connection
            else:
                print("⚠️ Process failed. Retrying...")
                time.sleep(10)  # Wait before retrying
                
        except KeyboardInterrupt:
            print("\n🛑 Process interrupted by user")
            stop_robot_control()
            break
        except Exception as e:
            print(f"💥 Unexpected error: {e}")
            traceback.print_exc()
            print("⚠️ Retrying after unexpected error...")
            time.sleep(15)  # Wait before retrying
    
    print("🏁 Robot MQTT Monitor finished")

if __name__ == "__main__":
    main()