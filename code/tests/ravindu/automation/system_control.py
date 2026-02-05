# system_control.py
"""
System Control Script for Robot Management

This script allows you to send disconnect/reconnect commands to the robot
via MQTT for testing and manual control.
"""

import json
import time
import os
from AWSIoTPythonSDK.MQTTLib import AWSIoTMQTTClient

def load_mqtt_credentials():
    """Load MQTT credentials from the robot's credential file"""
    try:
        if os.path.exists("mqtt_data_log.json"):
            with open("mqtt_data_log.json", "r") as f:
                data = json.load(f)
                return data["data"]["user"]
        else:
            print("❌ No MQTT credentials file found")
            return None
    except Exception as e:
        print(f"❌ Error loading MQTT credentials: {e}")
        return None

def setup_mqtt_client(credentials):
    """Setup MQTT client for sending commands"""
    try:
        client = AWSIoTMQTTClient("systemControlClient", useWebsocket=True)
        client.configureEndpoint(credentials["awsHost"], 443)
        client.configureCredentials("../../../cert/AmazonRootCA1.pem")
        
        client.configureIAMCredentials(
            credentials["awsAccessKey"],
            credentials["awsSecretKey"], 
            credentials["awsSessionToken"]
        )
        
        client.configureAutoReconnectBackoffTime(1, 32, 20)
        client.configureOfflinePublishQueueing(-1)
        client.configureDrainingFrequency(2)
        client.configureConnectDisconnectTimeout(10)
        client.configureMQTTOperationTimeout(5)
        
        client.connect()
        print("✅ Connected to MQTT broker")
        return client
        
    except Exception as e:
        print(f"❌ Error setting up MQTT client: {e}")
        return None

def send_system_command(command_type):
    """Send a system command (disconnect/reconnect) to the robot"""
    try:
        # Load credentials
        credentials = load_mqtt_credentials()
        if not credentials:
            return False
        
        # Setup MQTT client
        client = setup_mqtt_client(credentials)
        if not client:
            return False
        
        # Prepare command message
        command = {
            "type": command_type,
            "timestamp": int(time.time() * 1000),
            "source": "system_control"
        }
        
        message = json.dumps(command)
        topic = credentials["topic"]
        
        print(f"📡 Sending {command_type} command to topic: {topic}")
        print(f"📨 Message: {message}")
        
        # Send command
        client.publish(topic, message, 1)
        print(f"✅ {command_type.capitalize()} command sent successfully")
        
        # Wait a moment then disconnect
        time.sleep(2)
        client.disconnect()
        
        return True
        
    except Exception as e:
        print(f"❌ Error sending {command_type} command: {e}")
        return False

def main():
    """Main function with interactive menu"""
    print("🤖 Robot System Control")
    print("=" * 40)
    
    while True:
        print("\nAvailable commands:")
        print("1. Send DISCONNECT command")
        print("2. Send RECONNECT command")
        print("3. Check system status")
        print("4. Exit")
        
        try:
            choice = input("\nEnter your choice (1-4): ").strip()
            
            if choice == "1":
                print("\n🔌 Sending disconnect command...")
                if send_system_command("disconnect"):
                    print("✅ Disconnect command sent")
                    print("📋 The robot should stop all processes and wait for a new connect message")
                else:
                    print("❌ Failed to send disconnect command")
            
            elif choice == "2":
                print("\n🔄 Sending reconnect command...")
                if send_system_command("reconnect"):
                    print("✅ Reconnect command sent")
                    print("📋 The robot should restart using existing credentials")
                else:
                    print("❌ Failed to send reconnect command")
            
            elif choice == "3":
                print("\n📊 Checking system status...")
                # Check if credential files exist
                files_to_check = [
                    ("MQTT Credentials", "mqtt_data_log.json"),
                    ("Robot Credentials", "robot_mqtt_credentials.json"),
                    ("System State", "system_state.json"),
                    ("WebSocket Data", "websocket_data.json")
                ]
                
                for name, filename in files_to_check:
                    status = "✅ EXISTS" if os.path.exists(filename) else "❌ NOT FOUND"
                    print(f"{name}: {status}")
                
                # Check system state
                try:
                    if os.path.exists("system_state.json"):
                        with open("system_state.json", "r") as f:
                            state = json.load(f)
                            connected = state.get("connected", False)
                            processes = state.get("processes", [])
                            print(f"Connection Status: {'🟢 CONNECTED' if connected else '🔴 DISCONNECTED'}")
                            print(f"Active Processes: {len(processes)}")
                except Exception as e:
                    print(f"⚠️ Error reading system state: {e}")
            
            elif choice == "4":
                print("👋 Goodbye!")
                break
            
            else:
                print("❌ Invalid choice. Please enter 1-4.")
                
        except KeyboardInterrupt:
            print("\n\n👋 Goodbye!")
            break
        except Exception as e:
            print(f"❌ Unexpected error: {e}")

if __name__ == "__main__":
    main()