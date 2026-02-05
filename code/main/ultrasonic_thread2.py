# ultrasonic_thread2.py
import RPi.GPIO as GPIO
import time
import multiprocessing
import signal
import sys

# GPIO pin pairs for two sensors: (TRIG, ECHO)
SENSORS = [(5, 6), (24, 25)]  # Sensor 1 (front), Sensor 2 (back)

# Global flag for graceful shutdown
running = True

def signal_handler(signum, frame):
    """Handle shutdown signals"""
    global running
    print(f"\n📡 Ultrasonic sensor received signal {signum}, shutting down...")
    running = False

def setup_gpio():
    """Setup GPIO pins for ultrasonic sensors"""
    GPIO.setmode(GPIO.BCM)
    GPIO.setwarnings(False)
    for trig, echo in SENSORS:
        GPIO.setup(trig, GPIO.OUT)
        GPIO.setup(echo, GPIO.IN)

def cleanup_gpio():
    """Clean up GPIO resources"""
    try:
        GPIO.cleanup()
        print("📡 Ultrasonic GPIO cleaned up")
    except Exception as e:
        print(f"⚠️ Error cleaning up ultrasonic GPIO: {e}")

def measure_single_distance(trig_pin, echo_pin, sensor_id):
    """Measure distance from a single ultrasonic sensor"""
    try:
        # Trigger pulse
        GPIO.output(trig_pin, True)
        time.sleep(0.00001)
        GPIO.output(trig_pin, False)

        # Wait for echo
        start_time = time.time()
        stop_time = time.time()

        timeout = time.time() + 0.04  # 40ms timeout

        while GPIO.input(echo_pin) == 0 and time.time() < timeout:
            start_time = time.time()

        while GPIO.input(echo_pin) == 1 and time.time() < timeout:
            stop_time = time.time()

        # Calculate distance
        time_elapsed = stop_time - start_time
        distance = (time_elapsed * 34300) / 2  # in cm

        # Validate distance reading
        if distance < 2 or distance > 400:  # HC-SR04 range is typically 2-400cm
            return 400  # Return max distance for invalid readings

        return distance

    except Exception as e:
        print(f"⚠️ Error measuring distance from sensor {sensor_id}: {e}")
        return 400  # Return safe max distance on error

def measure_distance(shared_distances):
    """Main function to continuously measure distances from all sensors"""
    global running
    
    # Set up signal handlers
    signal.signal(signal.SIGTERM, signal_handler)
    signal.signal(signal.SIGINT, signal_handler)
    
    try:
        # Setup GPIO
        setup_gpio()
        print("📡 Ultrasonic sensors initialized")
        
        consecutive_errors = 0
        max_consecutive_errors = 10
        
        while running:
            try:
                for i, (TRIG, ECHO) in enumerate(SENSORS):
                    if not running:
                        break
                        
                    distance = measure_single_distance(TRIG, ECHO, i+1)
                    
                    # Update shared distance array
                    shared_distances[i] = distance
                    
                    # Only print occasionally to reduce spam
                    if time.time() % 2 < 0.1:  # Print roughly every 2 seconds
                        sensor_name = "Front" if i == 0 else "Back"
                        print(f"📏 {sensor_name} Sensor: {distance:.2f} cm")
                    
                    # Small delay between sensor readings
                    if running:
                        time.sleep(0.05)
                
                # Reset error counter on successful cycle
                consecutive_errors = 0
                
                # Main loop delay
                time.sleep(0.1)
                
            except Exception as e:
                consecutive_errors += 1
                if consecutive_errors <= 3:  # Only show first few errors
                    print(f"⚠️ Error in ultrasonic measurement cycle: {e}")
                
                if consecutive_errors > max_consecutive_errors:
                    print(f"❌ Too many consecutive errors ({consecutive_errors}), stopping ultrasonic sensors")
                    break
                
                time.sleep(0.5)  # Wait longer on error
                
    except Exception as e:
        print(f"❌ Critical error in ultrasonic sensor process: {e}")
    
    finally:
        print("📡 Ultrasonic sensor process shutting down...")
        cleanup_gpio()
        sys.exit(0)

if __name__ == "__main__":
    # This allows the script to be run independently for testing
    import multiprocessing
    
    print("🧪 Testing ultrasonic sensors independently...")
    shared_distances = multiprocessing.Array('d', [100.0, 100.0])
    
    try:
        measure_distance(shared_distances)
    except KeyboardInterrupt:
        print("\n🛑 Test stopped by user")
    finally:
        cleanup_gpio()