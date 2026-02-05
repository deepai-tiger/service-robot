# config_manager.py
import json
import os
import time
from getpass import getpass

# Configuration file paths
CONFIG_FILE = "robot_config.json"
WEBSOCKET_DATA_FILE = "websocket_data.json"
MQTT_LOG_FILE = "mqtt_data_log.json"
ROBOT_CREDENTIALS_FILE = "robot_mqtt_credentials.json"
SERVER_CONFIG_FILE = "server_config.json"
SYSTEM_STATE_FILE = "system_state.json"

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