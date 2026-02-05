import RPi.GPIO as GPIO
import time
import csv
import os

# Define GPIO pins
TRIG = 23  # GPIO23 (Physical pin 16)
ECHO = 24  # GPIO24 (Physical pin 18)

# Setup GPIO mode
GPIO.setmode(GPIO.BCM)
GPIO.setup(TRIG, GPIO.OUT)
GPIO.setup(ECHO, GPIO.IN)

def get_distance():
    # Ensure trigger is low initially
    GPIO.output(TRIG, False)
    time.sleep(0.1)  # Sensor stabilization time

    # Send a 10µs pulse to trigger the sensor
    GPIO.output(TRIG, True)
    time.sleep(0.00001)  # 10µs pulse
    GPIO.output(TRIG, False)

    # Wait for echo signal to start
    start_time = time.time()
    timeout_start = time.time()
    while GPIO.input(ECHO) == 0:
        start_time = time.time()
        if time.time() - timeout_start > 0.02:  # 20ms timeout
            return -1

    # Wait for echo signal to end
    stop_time = time.time()
    timeout_start = time.time()
    while GPIO.input(ECHO) == 1:
        stop_time = time.time()
        if time.time() - timeout_start > 0.02:  # 20ms timeout
            return -1

    # Calculate distance
    elapsed_time = stop_time - start_time
    distance = (elapsed_time * 34300) / 2  # Convert to cm

    return round(distance, 2)

def save_to_csv(data, filename="ultra.csv"):
    file_exists = os.path.exists(filename)
    
    with open(filename, mode='a', newline='') as file:
        writer = csv.writer(file)
        if not file_exists:
            writer.writerow(["Distance (cm)"])  # Write header if file does not exist
        writer.writerows(data)

try:
    measurements = []
    for i in range(20):
        dist = get_distance()
        if dist != -1:  # Ignore invalid readings
            measurements.append([dist])
            print(f"Measurement {i+1}: {dist} cm")
        else:
            print("Invalid reading, retrying...")
        time.sleep(0.5)  # Reduce CPU load and ensure sensor stability
    
    if measurements:
        save_to_csv(measurements)
        print("Measurements saved to ultra.csv")
    else:
        print("No valid measurements to save.")

except KeyboardInterrupt:
    print("\nMeasurement stopped by user")

finally:
    GPIO.cleanup()
