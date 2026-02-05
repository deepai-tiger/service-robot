import asyncio
import websockets
import cv2
import numpy as np
from picamera2 import Picamera2

# Initialize the camera
picam2 = Picamera2()
picam2.configure(picam2.create_video_configuration(main={"size": (320 * 3, 240 * 3)}))
picam2.start()

async def video_stream(websocket):  # <- Include 'path' parameter!
    print(f"[+] Client connected: {websocket.remote_address}")
    try:
        while True:
            frame = picam2.capture_array()
            _, buffer = cv2.imencode('.jpg', frame)
            # Send the raw image data as binary (not base64)
            await websocket.send(buffer.tobytes())
            await asyncio.sleep(0.1)  # lower framerate to reduce bandwidth
    except websockets.exceptions.ConnectionClosed as e:
        print(f"[x] WebSocket closed: {e}")
    except Exception as e:
        print(f"[!] Error during stream: {e}")

async def main():
    server = await websockets.serve(video_stream, '0.0.0.0', 8765)
    print("[*] WebSocket server started on ws://0.0.0.0:8765")
    await server.wait_closed()

if __name__ == "__main__":
    asyncio.run(main())
