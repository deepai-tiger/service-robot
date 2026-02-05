import RPi.GPIO as GPIO
import time

# Define GPIO pins
IN1 = 17  # GPIO 17 (Pin 11)
IN2 = 27  # GPIO 27 (Pin 13)

# Setup
GPIO.setmode(GPIO.BCM)
GPIO.setup(IN1, GPIO.OUT)
GPIO.setup(IN2, GPIO.OUT)

# Function to move motor forward
def motor_forward():
    GPIO.output(IN1, GPIO.HIGH)
    GPIO.output(IN2, GPIO.LOW)

# Run the motor
try:
    print("Motor running forward...")
    motor_forward()
    time.sleep(20)  # Run motor for 5 seconds
finally:
    GPIO.output(IN1, GPIO.LOW)
    GPIO.output(IN2, GPIO.LOW)
    GPIO.cleanup()
    print("Motor stopped and GPIO cleaned up.")
