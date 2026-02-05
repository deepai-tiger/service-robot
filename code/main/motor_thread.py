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
import subprocess
import signal
import read_battery_precentage

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
video_process = None

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
    global mqtt_client, ultrasonic_process, obstacle_process, motor_timer, system_running,read_battery_precentage_process
    
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

    if video_process and video_process.poll() is None:
        print("🛑 Terminating video process...")
        video_process.terminate()
        video_process.wait()

    if read_battery_precentage_process and read_battery_precentage_process.is_alive():
        print("🛑 Terminating read battery precentage process...")
        read_battery_precentage_process.terminate()
        read_battery_precentage_process.wait()

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
def stop_motor_after_timeout(timeout=0.2):
    global motor_timer
    if motor_timer:
        motor_timer.cancel()
    motor_timer = threading.Timer(timeout, motor_stop)
    motor_timer.start()

def motor_forward(timeout=0.2):
    if not system_running:
        return
    print("🚀 Moving forward")
    GPIO.output(IN1, GPIO.HIGH)
    GPIO.output(IN2, GPIO.LOW)
    GPIO.output(IN3, GPIO.HIGH)
    GPIO.output(IN4, GPIO.LOW)
    stop_motor_after_timeout(timeout)

def motor_backward(timeout=0.2):
    if not system_running:
        return
    print("🔄 Moving backward")
    GPIO.output(IN1, GPIO.LOW)
    GPIO.output(IN2, GPIO.HIGH)
    GPIO.output(IN3, GPIO.LOW)
    GPIO.output(IN4, GPIO.HIGH)
    stop_motor_after_timeout(timeout)

def motor_left(timeout=0.2):
    if not system_running:
        return
    print("⬅️ Turning left")
    GPIO.output(IN1, GPIO.LOW)
    GPIO.output(IN2, GPIO.HIGH)
    GPIO.output(IN3, GPIO.HIGH)
    GPIO.output(IN4, GPIO.LOW)
    stop_motor_after_timeout(timeout)

def motor_right(timeout=0.2):
    if not system_running:
        return
    print("➡️ Turning right")
    GPIO.output(IN1, GPIO.HIGH)
    GPIO.output(IN2, GPIO.LOW)
    GPIO.output(IN3, GPIO.LOW)
    GPIO.output(IN4, GPIO.HIGH)
    stop_motor_after_timeout(timeout)

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
    global motor_timer, system_running, video_process
    
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
            if msg_data.get("type") == "videocall_on" and msg_data.get("callId"):
                call_id = msg_data["callId"]
                if video_process is None:
                    print(f"📞 Starting video call process with Call ID: {call_id}")
                    video_process = subprocess.Popen(["python3", "video_call_manager.py", call_id])
                return

            elif msg_data.get("type") == "videocall_off":
                if video_process and video_process.poll() is None:
                    print("📴 Stopping video call process...")
                    video_process.send_signal(signal.SIGINT)
                    video_process.wait()
                    video_process = None
                return

            # Handle regular commands with timestamp checking
            if msg_data.get("key") and msg_data.get("timestamp"):
                if msg_data.get("duration") is None:
                    msg_data["duration"] = 0.2
                command_time = msg_data["timestamp"]
                current_time = int(time.time() * 1000)  # Current time in milliseconds
                time_diff = current_time - command_time
                duration = msg_data["duration"]
                
                # Check if command is too old (e.g., older than 2 seconds)
                if time_diff > 2000:
                    print(f"⏰ Command too old, ignoring. Age: {time_diff}ms")
                    return
                
                key = msg_data["key"]
                
                if key == "ArrowUp":
                    if blocked_directions[0]:
                        print("🚫 Obstacle ahead!")
                        motor_stop()
                        return
                    motor_forward(timeout=duration)

                elif key == "ArrowDown": 
                    if blocked_directions[1]:
                        print("🚫 Obstacle behind!")
                        motor_stop()
                        return
                    motor_backward(timeout=duration)

                elif key == "ArrowLeft":
                    motor_left(timeout=duration)

                elif key == "ArrowRight":
                    motor_right(timeout=duration)

                else:
                    print("❓ Unknown command key")
                    motor_stop()
                    if motor_timer:
                        motor_timer.cancel()
                return

        except json.JSONDecodeError:
            pass  # Not a JSON message, handle as regular control command
        
    #     # Handle legacy string format commands (without timestamp)
    #     if payload == '{"key":"ArrowUp"}': 
    #         if blocked_directions[0]:
    #             print("🚫 Obstacle ahead!")
    #             motor_stop()
    #             return
    #         motor_forward()

    #     elif payload == '{"key":"ArrowDown"}': 
    #         if blocked_directions[1]:
    #             print("🚫 Obstacle behind!")
    #             motor_stop()
    #             return
    #         motor_backward()

    #     elif payload == '{"key":"ArrowLeft"}':
    #         motor_left()

    #     elif payload == '{"key":"ArrowRight"}':
    #         motor_right()

    #     else:
    #         print("❓ Unknown command")
    #         motor_stop()
    #         if motor_timer:
    #             motor_timer.cancel()
                
    except Exception as e:
        print(f"⚠️ Error processing MQTT message: {e}")



def main():
    """Main function to initialize and run the robot control system"""
    global mqtt_client, ultrasonic_process, obstacle_process, system_running,read_battery_precentage_process
    
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
        mqtt_client.configureCredentials("../cert/AmazonRootCA1.pem")  # Only the CA is needed for WebSocket

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

        print("Starting battery precentage monitoring process...")
        mqtt_config = {
            "endpoint": endpoint,
            "access_key": aws_access_key,
            "secret_key": aws_secret_key,
            "session_token": aws_session_token,
            "ca_path": "../cert/AmazonRootCA1.pem",
            "topic": topic
        }

        read_battery_precentage_process = multiprocessing.Process(
            target=read_battery_precentage.read_serial_batter_status,
            args=(mqtt_config,)
        )
        read_battery_precentage_process.start()


        # Update system state
        save_system_state({
            "connected": True, 
            "processes": [ultrasonic_process.pid, obstacle_process.pid, read_battery_precentage_process.pid]
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