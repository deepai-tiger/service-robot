import RPi.GPIO as GPIO
import time
import multiprocessing

# GPIO pin pairs for two sensors: (TRIG, ECHO)
SENSORS = [(5, 6), (24, 25)]  # Sensor 1 (front), Sensor 2 (back)

# Setup GPIO
GPIO.setmode(GPIO.BCM)
for trig, echo in SENSORS:
    GPIO.setup(trig, GPIO.OUT)
    GPIO.setup(echo, GPIO.IN)

def measure_distance(shared_distances):
    while True:
        for i, (TRIG, ECHO) in enumerate(SENSORS):
            # Trigger pulse
            GPIO.output(TRIG, True)
            time.sleep(0.00001)
            GPIO.output(TRIG, False)

            # Wait for echo
            start_time = time.time()
            stop_time = time.time()

            timeout = time.time() + 0.04  # 40ms timeout

            while GPIO.input(ECHO) == 0 and time.time() < timeout:
                start_time = time.time()

            while GPIO.input(ECHO) == 1 and time.time() < timeout:
                stop_time = time.time()

            # Calculate distance
            time_elapsed = stop_time - start_time
            distance = (time_elapsed * 34300) / 2  # in cm

            # Save distance
            shared_distances[i] = distance
            print(f"📏 Sensor {i+1} Distance: {distance:.2f} cm")

            time.sleep(0.05)  # Small delay before switching sensors
