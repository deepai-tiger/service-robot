# data_manager.py
import json
import time
import os
from config_manager import WEBSOCKET_DATA_FILE, MQTT_LOG_FILE, ROBOT_CREDENTIALS_FILE

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