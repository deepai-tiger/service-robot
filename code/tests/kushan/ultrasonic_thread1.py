import RPi.GPIO as GPIO
import time
import multiprocessing

# GPIO Pins for Ultrasonic Sensor
TRIG = 5  # GPIO pin for Trigger
ECHO = 6  # GPIO pin for Echo

# Setup GPIO
GPIO.setmode(GPIO.BCM)
GPIO.setup(TRIG, GPIO.OUT)
GPIO.setup(ECHO, GPIO.IN)

def measure_distance(shared_distance):
    while True:
        # Send Trigger Pulse
        GPIO.output(TRIG, True)
        time.sleep(0.00001)  # 10µs pulse
        GPIO.output(TRIG, False)

        # Wait for Echo response
        start_time = time.time()
        stop_time = time.time()

        while GPIO.input(ECHO) == 0:
            start_time = time.time()
        
        while GPIO.input(ECHO) == 1:
            stop_time = time.time()
        
        # Calculate distance
        time_elapsed = stop_time - start_time
        distance = (time_elapsed * 34300) / 2  # Speed of sound = 34300 cm/s

        # Update shared memory
        shared_distance.value = distance

        print(f"🔍 Distance Measured: {distance:.2f} cm")
        time.sleep(0.05)  # Read distance every 0.05 seconds

if __name__ == "__main__":
    shared_distance = multiprocessing.Value("d", 100.0)  # Default value: 100cm
    measure_distance(shared_distance)

