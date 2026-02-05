# mqtt_monitor.py
import json
import time
from threading import Event, Thread
from data_manager import store_data_locally

def wait_for_mqtt_message(driver, robot_id, timeout=18000):
    """Event-driven wait for MQTT authentication message."""
    print(f"🔄 Waiting for MQTT message for robot {robot_id}...")
    print(f"⏰ Timeout set to {timeout//3600} hours")

    result = {"data": None}
    done = Event()

    def watch_local_storage():
        check_count = 0
        while not done.is_set():
            try:
                websocket_data = driver.execute_script("return localStorage.getItem('webSocketData');")

                if websocket_data:
                    data = json.loads(websocket_data)

                    if data.get("type") == "connect" and data.get("user") and data["user"].get("token"):
                        print(f"\n📨 WebSocket data received: {data}")
                        print("🎉 MQTT authentication message received!")
                        print(f"🔑 ID Token: {data['user']['token'][:20]}...")
                        print(f"⏱️ Timestamp: {data.get('timestamp')}")
                        
                        if store_data_locally(data):
                            result["data"] = data
                        else:
                            print("⚠️ Failed to store data but continuing...")
                            result["data"] = data

                        done.set()
                        return

                check_count += 1
                if check_count % 15 == 0: # if check_count is a multiple of 15
                    elapsed = int(time.time() - start_time) # calculate elapsed time
                    remaining = timeout - elapsed # calculate remaining time
                    print(f"⏳ Waiting... {elapsed//60}m elapsed, {remaining//60}m remaining") # print elapsed and remaining time
                time.sleep(2) # Check every 2 seconds

            except Exception as e:
                print(f"\n⚠️ Error checking for MQTT message: {e}")
                time.sleep(5)

    start_time = time.time()
    thread = Thread(target=watch_local_storage)
    thread.start()

    done.wait(timeout)
    thread.join()

    if result["data"]:
        return result["data"]

    print(f"\n⏰ Timeout: No MQTT message received within {timeout//3600} hours")
    return None