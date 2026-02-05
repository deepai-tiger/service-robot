import RPi.GPIO as GPIO
import time

# GPIO pin setup
sound_pin = 17      # D0 pin of sound sensor
buzzer_pin = 18     # Buzzer or speaker pin (use a resistor or transistor)

GPIO.setmode(GPIO.BCM)
GPIO.setup(sound_pin, GPIO.IN)
GPIO.setup(buzzer_pin, GPIO.OUT)

# Set up PWM for buzzer
pwm = GPIO.PWM(buzzer_pin, 1000)  # 1kHz tone

print("Listening for sound... Press Ctrl+C to exit")

try:
    while True:
        if GPIO.input(sound_pin) == 0:  # Sound detected (low signal)
            print("Sound detected!")
            pwm.start(50)  # Start PWM with 50% duty cycle
            time.sleep(0.5)  # Beep for 0.5 sec
            pwm.stop()
        time.sleep(0.1)  # Polling interval

except KeyboardInterrupt:
    print("Exiting...")
    GPIO.cleanup()
