import json
import time
import os
import threading
import multiprocessing
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

# === Load MQTT credentials from file ===
with open("mqtt_data_log.json", "r") as f:
    data = json.load(f)

aws_access_key = data["data"]["user"]["awsAccessKey"]
aws_secret_key = data["data"]["user"]["awsSecretKey"]
aws_session_token = data["data"]["user"]["awsSessionToken"]
region = data["data"]["user"]["awsRegion"]
endpoint = data["data"]["user"]["awsHost"]
topic = data["data"]["user"]["topic"]

distence = 50
shared_distances = multiprocessing.Array('d', [100.0, 100.0])  # [front, back]
blocked_directions = multiprocessing.Array('b', [0, 0])        # [front_blocked, back_blocked]
motor_timer = None

# === Motor control functions ===
def stop_motor_after_timeout(timeout=0.3):
    global motor_timer
    if motor_timer:
        motor_timer.cancel()
    motor_timer = threading.Timer(timeout, motor_stop)
    motor_timer.start()

def motor_forward():
    print("🚀 Moving forward")
    GPIO.output(IN1, GPIO.HIGH)
    GPIO.output(IN2, GPIO.LOW)
    GPIO.output(IN3, GPIO.HIGH)
    GPIO.output(IN4, GPIO.LOW)
    stop_motor_after_timeout()

def motor_backward():
    print("🔄 Moving backward")
    GPIO.output(IN1, GPIO.LOW)
    GPIO.output(IN2, GPIO.HIGH)
    GPIO.output(IN3, GPIO.LOW)
    GPIO.output(IN4, GPIO.HIGH)
    stop_motor_after_timeout()

def motor_left():
    print("⬅️ Turning left")
    GPIO.output(IN1, GPIO.LOW)
    GPIO.output(IN2, GPIO.HIGH)
    GPIO.output(IN3, GPIO.HIGH)
    GPIO.output(IN4, GPIO.LOW)
    stop_motor_after_timeout()

def motor_right():
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
    while True:
        front, back = shared_distances[0], shared_distances[1]
        blocked_directions[0] = 1 if front < distence else 0
        blocked_directions[1] = 1 if back < distence else 0
        print(f"📏 Front: {front:.2f} cm | Back: {back:.2f} cm | Blocked: F={blocked_directions[0]} B={blocked_directions[1]}")
        time.sleep(0.5)

# === MQTT message handler ===
def customCallback(client, userdata, message):
    global motor_timer
    payload = message.payload.decode()
    print(f"📩 Received message: {payload}")

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

# === Start background threads ===
ultrasonic_process = multiprocessing.Process(target=measure_distance, args=(shared_distances,))
ultrasonic_process.start()

obstacle_process = multiprocessing.Process(target=monitor_obstacles)
obstacle_process.start()

# === Keep the main thread alive ===
try:
    while True:
        time.sleep(1)

except KeyboardInterrupt:
    print("\n🛑 Shutting down...")

finally:
    motor_stop()
    GPIO.cleanup()
    ultrasonic_process.terminate()
    obstacle_process.terminate()
    mqtt_client.disconnect()
    print("✅ Cleanup complete. Goodbye!")
