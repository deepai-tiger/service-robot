import asyncio
import websockets
import cv2
import base64
import numpy as np
from picamera2 import Picamera2

picam2 = Picamera2()
picam2.configure(picam2.create_video_configuration(main={"size": (320, 240)}))
picam2.start()

async def video_stream(websocket, path):  # <- Include 'path' parameter!
    print(f"[+] Client connected: {websocket.remote_address}")
    try:
        while True:
            frame = picam2.capture_array()
            _, buffer = cv2.imencode('.jpg', frame)
            encoded = base64.b64encode(buffer).decode('utf-8')
            await websocket.send(encoded)
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
