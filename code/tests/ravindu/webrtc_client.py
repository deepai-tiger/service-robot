import argparse
import asyncio
import json
import logging
import os
import cv2
import numpy as np
import time

from aiortc import RTCPeerConnection, RTCSessionDescription
from aiortc.contrib.media import MediaPlayer, MediaBlackhole
from aiortc.contrib.signaling import BYE, object_from_string, object_to_string

# Configure logging
logging.basicConfig(level=logging.INFO)

async def fetch_json(url, params):
    import aiohttp
    
    async with aiohttp.ClientSession() as session:
        async with session.post(url, json=params) as response:
            return await response.json()

async def run(server_url, display):
    # Create peer connection
    pc = RTCPeerConnection()

    # Create data channel for signaling
    channel = pc.createDataChannel("signaling")
    channel_open = asyncio.Event()

    @channel.on("open")
    def on_open():
        logging.info("Data channel opened")
        channel_open.set()

    @channel.on("message")
    def on_message(message):
        logging.info(f"Received message: {message}")

    # Create offer
    await pc.setLocalDescription(await pc.createOffer())
    
    # Exchange offer with server
    response = await fetch_json(f"{server_url}/offer", {
        "sdp": pc.localDescription.sdp,
        "type": pc.localDescription.type,
    })
    
    # Set remote description
    await pc.setRemoteDescription(RTCSessionDescription(sdp=response["sdp"], type=response["type"]))
    
    # Set up video receiver
    @pc.on("track")
    def on_track(track):
        logging.info(f"Received track: {track.kind}")
        if track.kind == "video":
            asyncio.create_task(display_video(track, display))
    
    # Wait for connection to be established
    while pc.iceConnectionState != "connected":
        await asyncio.sleep(0.1)
    
    # Keep connection alive
    try:
        await asyncio.Future()
    except asyncio.CancelledError:
        pass
    finally:
        # Close connection
        await pc.close()

async def display_video(track, display):
    # Create window if display is enabled
    if display:
        cv2.namedWindow("WebRTC Video", cv2.WINDOW_NORMAL)
    
    # Process video frames
    while True:
        try:
            frame = await track.recv()
            if display:
                # Convert frame to OpenCV format
                img = frame.to_ndarray(format="bgr24")
                
                # Display frame
                cv2.imshow("WebRTC Video", img)
                
                # Check for quit key
                key = cv2.waitKey(1) & 0xFF
                if key == ord('q'):
                    break
        except Exception as e:
            logging.error(f"Error displaying video: {e}")
            break
    
    # Close window
    if display:
        cv2.destroyAllWindows()

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="WebRTC video client")
    parser.add_argument("--server", default="http://localhost:8080", help="Server URL")
    parser.add_argument("--no-display", action="store_true", help="Don't display video")
    args = parser.parse_args()
    
    # Run client
    try:
        asyncio.run(run(args.server, not args.no_display))
    except KeyboardInterrupt:
        logging.info("Client stopped")