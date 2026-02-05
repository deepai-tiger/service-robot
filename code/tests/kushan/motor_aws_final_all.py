import RPi.GPIO as GPIO
import time
import paho.mqtt.client as mqtt
import os
import threading  # For auto-stop timer

# Define GPIO pins for the motors
IN1 = 13 #17  # Motor 1
IN2 = 27 #19
IN3 = 22  # Motor 2
IN4 = 23

AWS_ENDPOINT = "a2cdp9hijgdiig-ats.iot.ap-southeast-2.amazonaws.com"
THING_NAME = "3yp-device2"
MQTT_TOPIC = "robot/ap-southeast-2:e70e9d78-b1ec-c0b0-db33-71e5e3e33e6a/control"
CERT_FILE = "../../cert/567ac5f9b0348408455bfc91506042fe17270e042a0499705711a24c5c7a6883-certificate.pem.crt"
KEY_FILE = "../../cert/567ac5f9b0348408455bfc91506042fe17270e042a0499705711a24c5c7a6883-private.pem.key"
CA_CERT = "../../cert/AmazonRootCA1.pem"

# Validate certificate paths
for file in [CA_CERT, CERT_FILE, KEY_FILE]:
    if not os.path.exists(file):
        raise FileNotFoundError(f"Certificate file not found: {file}")

# Setup GPIO
GPIO.setmode(GPIO.BCM)
GPIO.setup(IN1, GPIO.OUT)
GPIO.setup(IN2, GPIO.OUT)
GPIO.setup(IN3, GPIO.OUT)
GPIO.setup(IN4, GPIO.OUT)
GPIO.setwarnings(False)

# Auto-stop timer variable
motor_timer = None

# Function to stop motors after timeout
def stop_motor_after_timeout(timeout=5):
    global motor_timer
    if motor_timer:
        motor_timer.cancel()  # Cancel previous timer if any
    motor_timer = threading.Timer(timeout, motor_stop)
    motor_timer.start()

# Function to move motors forward
def motor_forward():
    print("🚀 Moving forward")
    GPIO.output(IN1, GPIO.HIGH)
    GPIO.output(IN2, GPIO.LOW)
    GPIO.output(IN3, GPIO.HIGH)
    GPIO.output(IN4, GPIO.LOW)
    stop_motor_after_timeout()

# Function to move motors backward
def motor_backward():
    print("🔄 Moving backward")
    GPIO.output(IN1, GPIO.LOW)
    GPIO.output(IN2, GPIO.HIGH)
    GPIO.output(IN3, GPIO.LOW)
    GPIO.output(IN4, GPIO.HIGH)
    stop_motor_after_timeout()

# Function to turn left (motors move in opposite directions)
def motor_left():
    print("⬅️ Turning left")
    GPIO.output(IN1, GPIO.LOW)
    GPIO.output(IN2, GPIO.HIGH)
    GPIO.output(IN3, GPIO.HIGH)
    GPIO.output(IN4, GPIO.LOW)
    stop_motor_after_timeout()

# Function to turn right (motors move in opposite directions)
def motor_right():
    print("➡️ Turning right")
    GPIO.output(IN1, GPIO.HIGH)
    GPIO.output(IN2, GPIO.LOW)
    GPIO.output(IN3, GPIO.LOW)
    GPIO.output(IN4, GPIO.HIGH)
    stop_motor_after_timeout()

# Function to stop motors
def motor_stop():
    print("🛑 Stopping motors")
    GPIO.output(IN1, GPIO.LOW)
    GPIO.output(IN2, GPIO.LOW)
    GPIO.output(IN3, GPIO.LOW)
    GPIO.output(IN4, GPIO.LOW)

# MQTT callback for successful connection
def on_connect(client, userdata, flags, rc):
    if rc == 0:
        print("✅ Connected to AWS IoT Core")
        client.subscribe(MQTT_TOPIC)
        print(f"📡 Subscribed to topic: {MQTT_TOPIC}")
    else:
        print(f"⚠️ Connection failed with error code {rc}")

# MQTT callback when a message is received
def on_message(client, userdata, msg):
    global motor_timer
    payload = msg.payload.decode()
    print(f"📩 Message received: {payload}")

    if payload == '{"key":"ArrowUp"}':
        motor_forward()
    elif payload == '{"key":"ArrowDown"}':
        motor_backward()
    elif payload == '{"key":"ArrowLeft"}':
        motor_left()
    elif payload == '{"key":"ArrowRight"}':
        motor_right()
    else:
        motor_stop()
        if motor_timer:
            motor_timer.cancel()

# MQTT client setup
client = mqtt.Client()

# Set TLS certificates for AWS IoT
client.tls_set(ca_certs=CA_CERT, certfile=CERT_FILE, keyfile=KEY_FILE)

# Attach callbacks
client.on_connect = on_connect
client.on_message = on_message

# Connect to AWS IoT Core
print(f"🔗 Connecting to AWS IoT Core at {AWS_ENDPOINT}...")
client.connect(AWS_ENDPOINT, 8883, 60)

# Start MQTT client loop
try:
    client.loop_start()
    print("✅ MQTT client running... Waiting for messages.")
    while True:
        time.sleep(1)
except KeyboardInterrupt:
    print("\n🛑 Stopping MQTT client...")
finally:
    motor_stop()
    GPIO.cleanup()
    client.loop_stop()
    print("✅ Cleanup complete. Exiting.")

