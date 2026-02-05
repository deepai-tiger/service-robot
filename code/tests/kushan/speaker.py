import RPi.GPIO as GPIO
import time

buzzer_pin = 18  # Must be a PWM-capable GPIO pin (like 18)

GPIO.setmode(GPIO.BCM)
GPIO.setup(buzzer_pin, GPIO.OUT)

pwm = GPIO.PWM(buzzer_pin, 440)  # 440 Hz (A4 musical note)
pwm.start(20)  # 50% duty cycle (volume)

print("Playing tone...")
time.sleep(10)  # Tone duration
pwm.stop()

GPIO.cleanup()
