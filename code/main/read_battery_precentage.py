import time
from AWSIoTPythonSDK.MQTTLib import AWSIoTMQTTClient


def read_serial_batter_status(mqtt_config, port='/dev/ttyUSB0', baudrate=9600, timeout=1):
    """
    Reads battery percentage from serial and publishes to AWS IoT MQTT topic.
    """
    import serial
    import json

    print("🔋 Battery percentage monitoring started...")

    # Setup AWS MQTT client inside the process
    mqtt_client = AWSIoTMQTTClient("batteryClient", useWebsocket=True)
    mqtt_client.configureEndpoint(mqtt_config["endpoint"], 443)
    mqtt_client.configureCredentials(mqtt_config["ca_path"])
    mqtt_client.configureIAMCredentials(
        mqtt_config["access_key"],
        mqtt_config["secret_key"],
        mqtt_config["session_token"]
    )
    mqtt_client.configureConnectDisconnectTimeout(10)
    mqtt_client.configureMQTTOperationTimeout(5)

    mqtt_client.connect()

    # Setup Serial
    ser = serial.Serial(port, baudrate, timeout=timeout)

    try:
        while True:
            line = ser.readline().decode('utf-8', errors='ignore').strip()
            if line:
                payload = json.dumps({"battery_percentage": line})
                print(f"🔋 Publishing: {payload}")
                mqtt_client.publish(mqtt_config["topic"], payload, 0)
                time.sleep(60)
    except KeyboardInterrupt:
        print("❌ Battery monitoring interrupted")
    finally:
        ser.close()
        mqtt_client.disconnect()
        print("🔌 Serial and MQTT disconnected")
