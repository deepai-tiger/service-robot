import asyncio
import websockets
import cv2
import base64
import numpy as np

async def receive_video():
    uri = "ws://192.168.8.139:8765"  # Replace with Pi's IP
    try:
        async with websockets.connect(uri) as websocket:
            print(f"Connected to server at {uri}")
            while True:
                try:
                    data = await websocket.recv()
                    jpg_original = base64.b64decode(data)
                    np_arr = np.frombuffer(jpg_original, dtype=np.uint8)
                    frame = cv2.imdecode(np_arr, cv2.IMREAD_COLOR)

                    cv2.imshow("WebSocket Video Feed", frame)
                    if cv2.waitKey(1) & 0xFF == ord('q'):
                        break
                except websockets.exceptions.ConnectionClosed as e:
                    print(f"Connection closed: {e}")
                    break
                except Exception as e:
                    print(f"Error processing video frame: {e}")
                    break
    except ConnectionRefusedError:
        print(f"Could not connect to server at {uri}. Make sure the server is running.")
    except Exception as e:
        print(f"Unexpected error: {e}")
    finally:
        cv2.destroyAllWindows()
        print("Video client shutdown")

if __name__ == "__main__":
    asyncio.run(receive_video())