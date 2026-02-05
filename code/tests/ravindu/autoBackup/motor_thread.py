# motor_thread.py
import json
import time
import os
import threading
import multiprocessing
import signal
import sys
from AWSIoTPythonSDK.MQTTLib import AWSIoTMQTTClient
from ultrasonic_thread2 import measure_distance
import RPi.GPIO as GPIO

# Motor GPIO pins
IN1, IN2 = 13, 27
IN3, IN4 = 22, 23

GPIO.setmode(GPIO.BCM)
GPIO.setwarnings(False)
GPIO.setup(IN1, GPIO.OUT)
GPIO.setup(IN2, GPIO.OUT)
GPIO.setup(IN3, GPIO.OUT)
GPIO.setup(IN4, GPIO.OUT)

# Global variables
distence = 50
shared_distances = multiprocessing.Array('d', [100.0, 100.0])  # [front, back]
blocked_directions = multiprocessing.Array('b', [0, 0])        # [front_blocked, back_blocked]
motor_timer = None
mqtt_client = None
ultrasonic_process = None
obstacle_process = None
system_running = True

# Configuration files
MQTT_LOG_FILE = "mqtt_data_log.json"
SYSTEM_STATE_FILE = "system_state.json"

def signal_handler(signum, frame):
    """Handle shutdown signals"""
    global system_running
    print(f"\n🔔 Received signal {signum}, initiating shutdown...")
    system_running = False
    cleanup_and_exit()

def save_system_state(state):
    """Save current system state"""
    try:
        with open(SYSTEM_STATE_FILE, "w") as file:
            json.dump(state, file, indent=2)
    except Exception as e:
        print(f"Error saving system state: {e}")

def cleanup_and_exit():
    """Clean up resources and exit"""
    global mqtt_client, ultrasonic_process, obstacle_process, motor_timer, system_running
    
    print("🧹 Starting cleanup process...")
    system_running = False
    
    # Stop motor timer
    if motor_timer:
        motor_timer.cancel()
    
    # Stop motors
    motor_stop()
    
    # Disconnect MQTT
    if mqtt_client:
        try:
            mqtt_client.disconnect()
            print("📡 MQTT client disconnected")
        except Exception as e:
            print(f"⚠️ Error disconnecting MQTT: {e}")
    
    # Terminate processes
    if ultrasonic_process and ultrasonic_process.is_alive():
        ultrasonic_process.terminate()
        ultrasonic_process.join(timeout=5)
        if ultrasonic_process.is_alive():
            ultrasonic_process.kill()
        print("📏 Ultrasonic process terminated")
    
    if obstacle_process and obstacle_process.is_alive():
        obstacle_process.terminate()
        obstacle_process.join(timeout=5)
        if obstacle_process.is_alive():
            obstacle_process.kill()
        print("🚧 Obstacle monitoring process terminated")
    
    # GPIO cleanup
    GPIO.cleanup()
    print("🔌 GPIO cleaned up")
    
    # Update system state
    save_system_state({"connected": False, "processes": []})
    
    print("✅ Cleanup complete")
    sys.exit(0)

def disconnect_system():
    """Handle disconnect command - stop everything and clear credentials"""
    global system_running
    
    print("🔌 Processing disconnect command...")
    system_running = False
    
    # Clear credentials and data files
    files_to_remove = [
        "robot_mqtt_credentials.json",
        "mqtt_data_log.json",
        "websocket_data.json"
    ]
    
    for file_path in files_to_remove:
        try:
            if os.path.exists(file_path):
                os.remove(file_path)
                print(f"🗑️ Removed {file_path}")
        except Exception as e:
            print(f"⚠️ Error removing {file_path}: {e}")
    
    # Update system state to disconnected
    save_system_state({"connected": False, "processes": []})
    
    print("📡 System disconnected - waiting for new connect message")
    cleanup_and_exit()

def reconnect_system():
    """Handle reconnect command - restart with existing credentials"""
    print("🔄 Processing reconnect command...")
    
    # Check if credentials exist
    if not os.path.exists(MQTT_LOG_FILE):
        print("❌ No existing credentials found for reconnect")
        return
    
    print("✅ Reconnecting with existing credentials...")
    # The system will automatically reconnect using the existing credentials
    # This is handled by the main initialization process

# === Motor control functions ===
def stop_motor_after_timeout(timeout=0.3):
    global motor_timer
    if motor_timer:
        motor_timer.cancel()
    motor_timer = threading.Timer(timeout, motor_stop)
    motor_timer.start()

def motor_forward():
    if not system_running:
        return
    print("🚀 Moving forward")
    GPIO.output(IN1, GPIO.HIGH)
    GPIO.output(IN2, GPIO.LOW)
    GPIO.output(IN3, GPIO.HIGH)
    GPIO.output(IN4, GPIO.LOW)
    stop_motor_after_timeout()

def motor_backward():
    if not system_running:
        return
    print("🔄 Moving backward")
    GPIO.output(IN1, GPIO.LOW)
    GPIO.output(IN2, GPIO.HIGH)
    GPIO.output(IN3, GPIO.LOW)
    GPIO.output(IN4, GPIO.HIGH)
    stop_motor_after_timeout()

def motor_left():
    if not system_running:
        return
    print("⬅️ Turning left")
    GPIO.output(IN1, GPIO.LOW)
    GPIO.output(IN2, GPIO.HIGH)
    GPIO.output(IN3, GPIO.HIGH)
    GPIO.output(IN4, GPIO.LOW)
    stop_motor_after_timeout()

def motor_right():
    if not system_running:
        return
    print("➡️ Turning right")
    GPIO.output(IN1, GPIO.HIGH)
    GPIO.output(IN2, GPIO.LOW)
    GPIO.output(IN3, GPIO.LOW)
    GPIO.output(IN4, GPIO.HIGH)
    stop_motor_after_timeout()

def motor_stop():
    print("🛑 Stopping motors")
    GPIO.output(IN1, GPIO.LOW)
    GPIO.output(IN2, GPIO.LOW)
    GPIO.output(IN3, GPIO.LOW)
    GPIO.output(IN4, GPIO.LOW)

# === Obstacle monitoring thread ===
def monitor_obstacles():
    global system_running
    while system_running:
        try:
            front, back = shared_distances[0], shared_distances[1]
            blocked_directions[0] = 1 if front < distence else 0
            blocked_directions[1] = 1 if back < distence else 0
            print(f"📏 Front: {front:.2f} cm | Back: {back:.2f} cm | Blocked: F={blocked_directions[0]} B={blocked_directions[1]}")
            time.sleep(0.5)
        except Exception as e:
            if system_running:
                print(f"⚠️ Error in obstacle monitoring: {e}")
            time.sleep(1)

# === MQTT message handler ===
def customCallback(client, userdata, message):
    global motor_timer, system_running
    
    if not system_running:
        return
        
    try:
        payload = message.payload.decode()
        print(f"📩 Received message: {payload}")
        
        # Try to parse as JSON for system commands
        try:
            msg_data = json.loads(payload)
            
            # Handle system commands
            if msg_data.get("type") == "disconnect":
                print("🔌 Disconnect command received")
                disconnect_system()
                return
            elif msg_data.get("type") == "reconnect":
                print("🔄 Reconnect command received")
                reconnect_system()
                return
                
        except json.JSONDecodeError:
            pass  # Not a JSON message, handle as regular control command
        
        # Handle regular control commands
        if payload == '{"key":"ArrowUp"}':
            if blocked_directions[0]:
                print("🚫 Obstacle ahead!")
                motor_stop()
                return
            motor_forward()

        elif payload == '{"key":"ArrowDown"}':
            if blocked_directions[1]:
                print("🚫 Obstacle behind!")
                motor_stop()
                return
            motor_backward()

        elif payload == '{"key":"ArrowLeft"}':
            motor_left()

        elif payload == '{"key":"ArrowRight"}':
            motor_right()

        else:
            print("❓ Unknown command")
            motor_stop()
            if motor_timer:
                motor_timer.cancel()
                
    except Exception as e:
        print(f"⚠️ Error processing MQTT message: {e}")

def main():
    """Main function to initialize and run the robot control system"""
    global mqtt_client, ultrasonic_process, obstacle_process, system_running
    
    # Set up signal handlers
    signal.signal(signal.SIGTERM, signal_handler)
    signal.signal(signal.SIGINT, signal_handler)
    
    try:
        # === Load MQTT credentials from file ===
        if not os.path.exists(MQTT_LOG_FILE):
            print("❌ No MQTT credentials file found")
            sys.exit(1)
            
        with open(MQTT_LOG_FILE, "r") as f:
            data = json.load(f)

        aws_access_key = data["data"]["user"]["awsAccessKey"]
        aws_secret_key = data["data"]["user"]["awsSecretKey"]
        aws_session_token = data["data"]["user"]["awsSessionToken"]
        region = data["data"]["user"]["awsRegion"]
        endpoint = data["data"]["user"]["awsHost"]
        topic = data["data"]["user"]["topic"]

        print(f"🔑 Loaded MQTT credentials for topic: {topic}")

        # === Setup AWSIoTPythonSDK MQTT Client with WebSocket ===
        mqtt_client = AWSIoTMQTTClient("pythonClient", useWebsocket=True)
        mqtt_client.configureEndpoint(endpoint, 443)
        mqtt_client.configureCredentials("../../../cert/AmazonRootCA1.pem")  # Only the CA is needed for WebSocket

        # Configure credentials
        mqtt_client.configureIAMCredentials(aws_access_key, aws_secret_key, aws_session_token)

        # Configurations (timeouts and more)
        mqtt_client.configureAutoReconnectBackoffTime(1, 32, 20)
        mqtt_client.configureOfflinePublishQueueing(-1)  # Infinite queueing
        mqtt_client.configureDrainingFrequency(2)
        mqtt_client.configureConnectDisconnectTimeout(10)
        mqtt_client.configureMQTTOperationTimeout(5)

        # Connect and subscribe
        print(f"🔗 Connecting to {endpoint} using WebSocket...")
        mqtt_client.connect()
        mqtt_client.subscribe(topic, 1, customCallback)
        print(f"✅ Subscribed to {topic}. Waiting for messages...")

        # === Start background processes ===
        print("🚀 Starting ultrasonic sensor process...")
        ultrasonic_process = multiprocessing.Process(target=measure_distance, args=(shared_distances,))
        ultrasonic_process.start()

        print("🚧 Starting obstacle monitoring process...")
        obstacle_process = multiprocessing.Process(target=monitor_obstacles)
        obstacle_process.start()

        # Update system state
        save_system_state({
            "connected": True, 
            "processes": [ultrasonic_process.pid, obstacle_process.pid]
        })

        print("🤖 Robot control system fully initialized!")
        print("📡 Listening for MQTT commands...")
        print("🎯 System commands: disconnect, reconnect")
        print("🎮 Control commands: ArrowUp, ArrowDown, ArrowLeft, ArrowRight")

        # === Keep the main thread alive ===
        while system_running:
            try:
                # Check if processes are still alive
                if ultrasonic_process and not ultrasonic_process.is_alive():
                    print("⚠️ Ultrasonic process died, restarting...")
                    ultrasonic_process = multiprocessing.Process(target=measure_distance, args=(shared_distances,))
                    ultrasonic_process.start()
                
                if obstacle_process and not obstacle_process.is_alive():
                    print("⚠️ Obstacle monitoring process died, restarting...")
                    obstacle_process = multiprocessing.Process(target=monitor_obstacles)
                    obstacle_process.start()
                
                time.sleep(5)  # Check every 5 seconds
                
            except KeyboardInterrupt:
                print("\n🛑 Keyboard interrupt received")
                break
            except Exception as e:
                print(f"⚠️ Error in main loop: {e}")
                time.sleep(1)

    except Exception as e:
        print(f"❌ Critical error in robot control: {e}")
    
    finally:
        cleanup_and_exit()

if __name__ == "__main__":
    main()