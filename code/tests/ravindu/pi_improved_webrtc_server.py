import argparse
import asyncio
import json
import logging
import os
import ssl
import uuid
import signal
import sys
import fractions
import threading
import time

from aiohttp import web
from aiortc import MediaStreamTrack, RTCPeerConnection, RTCSessionDescription
from aiortc.contrib.media import MediaRelay

from picamera2 import Picamera2
import cv2
import numpy as np

# Configure logging
logging.basicConfig(level=logging.INFO)

# Global variables
pcs = set()
relay = MediaRelay()
picam2 = None
frame_buffer = None
frame_lock = threading.Lock()
running = True

# Camera thread to continuously capture frames
def camera_capture_thread():
    global frame_buffer, running, picam2
    
    logging.info("Starting camera capture thread")
    while running:
        try:
            if picam2:
                # Capture a frame
                frame = picam2.capture_array()
                
                # Convert to BGR format if needed
                if frame.shape[2] == 4:  # XRGB/XBGR format
                    frame = cv2.cvtColor(frame, cv2.COLOR_BGRA2BGR)
                
                # Update frame buffer with thread safety
                with frame_lock:
                    frame_buffer = frame.copy()
                
                # Add a small delay to control frame rate
                time.sleep(0.033)  # ~30fps
        except Exception as e:
            logging.error(f"Camera capture error: {e}")
            time.sleep(0.5)  # Wait before trying again
    
    logging.info("Camera capture thread stopped")

# Camera video track
class PiCameraStreamTrack(MediaStreamTrack):
    kind = "video"

    def __init__(self):
        super().__init__()
        self.frame_counter = 0
        
    async def recv(self):
        global frame_buffer
        
        from av import VideoFrame
        
        # Wait for a valid frame
        while running:
            # Get frame from buffer with thread safety
            with frame_lock:
                current_frame = frame_buffer.copy() if frame_buffer is not None else None
            
            if current_frame is not None:
                try:
                    # Create VideoFrame
                    video_frame = VideoFrame.from_ndarray(current_frame, format="bgr24")
                    
                    # Add timestamp and frame counter
                    video_frame.pts = self.frame_counter
                    video_frame.time_base = fractions.Fraction(1, 30)
                    self.frame_counter += 1
                    
                    return video_frame
                except Exception as e:
                    logging.error(f"Frame conversion error: {e}")
            
            # Wait before trying again
            await asyncio.sleep(0.033)  # ~30fps

# Web server routes
async def index(request):
    try:
        current_dir = os.path.dirname(os.path.abspath(__file__))
        with open(os.path.join(current_dir, "index.html"), "r") as file:
            content = file.read()
        return web.Response(content_type="text/html", text=content)
    except FileNotFoundError:
        return web.Response(text="Error: index.html not found", status=404)

async def javascript(request):
    try:
        current_dir = os.path.dirname(os.path.abspath(__file__))
        with open(os.path.join(current_dir, "client.js"), "r") as file:
            content = file.read()
        return web.Response(content_type="application/javascript", text=content)
    except FileNotFoundError:
        return web.Response(text="Error: client.js not found", status=404)

async def offer(request):
    params = await request.json()
    offer = RTCSessionDescription(sdp=params["sdp"], type=params["type"])

    pc = RTCPeerConnection()
    pc_id = f"PeerConnection({uuid.uuid4()})"
    pcs.add(pc)

    def log_info(msg, *args):
        logging.info(pc_id + " " + msg, *args)

    log_info("Created for %s", request.remote)

    # Prepare local media
    video_track = PiCameraStreamTrack()
    video_sender = pc.addTrack(relay.subscribe(video_track))
    
    # Handle offer
    await pc.setRemoteDescription(offer)
    
    # Send answer
    answer = await pc.createAnswer()
    await pc.setLocalDescription(answer)

    # Handle ICE connection state
    @pc.on("iceconnectionstatechange")
    async def on_iceconnectionstatechange():
        log_info("ICE connection state is %s", pc.iceConnectionState)
        if pc.iceConnectionState == "failed":
            await pc.close()
            pcs.discard(pc)
            
    # Handle peer connection closed
    @pc.on("connectionstatechange")
    async def on_connectionstatechange():
        log_info("Connection state is %s", pc.connectionState)
        if pc.connectionState == "failed":
            await pc.close()
            pcs.discard(pc)

    # Return answer to client
    return web.Response(
        content_type="application/json",
        text=json.dumps(
            {"sdp": pc.localDescription.sdp, "type": pc.localDescription.type}
        ),
    )

async def on_shutdown(app):
    global running
    
    # Set running flag to False to stop all threads
    running = False
    logging.info("Shutting down...")
    
    # Close peer connections
    coros = [pc.close() for pc in pcs]
    await asyncio.gather(*coros)
    pcs.clear()
    
    # Wait for threads to finish
    time.sleep(1)

def cleanup_camera():
    global picam2
    
    # Stop camera
    if picam2:
        try:
            logging.info("Stopping camera...")
            picam2.stop()
            picam2.close()
            picam2 = None
            logging.info("Camera stopped")
        except Exception as e:
            logging.error(f"Error stopping camera: {e}")

def init_camera(width=640, height=480):
    global picam2
    
    try:
        # Create and configure camera
        picam2 = Picamera2()
        
        # Configure camera with a more robust approach
        config = picam2.create_video_configuration(
            main={"size": (width, height), "format": "XBGR8888"},
            lores={"size": (320, 240), "format": "YUV420"},
            buffer_count=4
        )
        picam2.configure(config)
        
        # Start camera
        picam2.start()
        logging.info(f"Camera initialized with resolution {width}x{height}")
        
        # Wait a moment for camera to initialize
        time.sleep(1)
        
        # Test capture a frame to verify camera works
        test_frame = picam2.capture_array()
        if test_frame is None or test_frame.size == 0:
            logging.error("Camera test frame is empty or invalid")
            return False
        
        logging.info(f"Camera test frame shape: {test_frame.shape}")
        return True
        
    except Exception as e:
        logging.error(f"Failed to initialize camera: {e}")
        return False

def create_html_files():
    # Create index.html
    with open("index.html", "w") as f:
        f.write("""<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Raspberry Pi Camera WebRTC</title>
    <style>
        body {
            font-family: Arial, sans-serif;
            margin: 0;
            padding: 20px;
            background: #f5f5f5;
            display: flex;
            flex-direction: column;
            align-items: center;
        }
        h1 {
            color: #333;
        }
        #video {
            max-width: 100%;
            border: 1px solid #ddd;
            border-radius: 8px;
            margin: 20px 0;
            background: #000;
        }
        button {
            background: #4CAF50;
            color: white;
            border: none;
            padding: 10px 20px;
            text-align: center;
            text-decoration: none;
            display: inline-block;
            font-size: 16px;
            margin: 10px 2px;
            cursor: pointer;
            border-radius: 4px;
        }
        button:hover {
            background: #45a049;
        }
        button:disabled {
            background: #cccccc;
            cursor: not-allowed;
        }
        #stats {
            margin-top: 20px;
            font-family: monospace;
            white-space: pre;
            background: #eee;
            padding: 10px;
            border-radius: 4px;
            max-width: 600px;
            overflow-x: auto;
        }
        .status {
            padding: 5px 10px;
            margin: 10px 0;
            border-radius: 4px;
            background: #ffeb3b;
        }
    </style>
</head>
<body>
    <h1>Raspberry Pi Camera WebRTC Stream</h1>
    <div class="status" id="connectionStatus">Status: Disconnected</div>
    <video id="video" autoplay playsinline width="640" height="480"></video>
    <div>
        <button id="start" onclick="start()">Start</button>
        <button id="stop" disabled onclick="stop()">Stop</button>
    </div>
    <div id="stats"></div>
    
    <script src="client.js"></script>
</body>
</html>
""")
    
    # Create client.js
    with open("client.js", "w") as f:
        f.write("""// Global variables
let pc = null;
let statsInterval = null;

// Start WebRTC connection
async function start() {
    const videoElement = document.getElementById('video');
    const startButton = document.getElementById('start');
    const stopButton = document.getElementById('stop');
    const statsDiv = document.getElementById('stats');
    const statusDiv = document.getElementById('connectionStatus');
    
    // Update status
    statusDiv.textContent = 'Status: Connecting...';
    statusDiv.style.background = '#ffeb3b';
    
    // Disable start button and enable stop button
    startButton.disabled = true;
    stopButton.disabled = false;
    
    try {
        // Create peer connection
        pc = new RTCPeerConnection({
            sdpSemantics: 'unified-plan',
            iceCandidatePoolSize: 10,
        });
        
        // Handle ICE candidate events
        pc.onicecandidate = (event) => {
            if (event.candidate) {
                console.log('ICE candidate:', event.candidate);
            }
        };
        
        // Handle ICE connection state changes
        pc.oniceconnectionstatechange = () => {
            console.log('ICE connection state:', pc.iceConnectionState);
            if (pc.iceConnectionState === 'connected' or pc.iceConnectionState === 'completed') {
                statusDiv.textContent = 'Status: Connected';
                statusDiv.style.background = '#4CAF50';
                statusDiv.style.color = 'white';
            } else if (pc.iceConnectionState === 'failed' or pc.iceConnectionState === 'disconnected') {
                statusDiv.textContent = 'Status: Connection failed';
                statusDiv.style.background = '#f44336';
                statusDiv.style.color = 'white';
                stop();
            }
        };
        
        // Handle track events
        pc.ontrack = (event) => {
            if (event.track.kind === 'video') {
                videoElement.srcObject = event.streams[0];
                console.log('Received remote video track');
                
                // Add an event listener to handle video playing
                videoElement.onplaying = () => {
                    console.log('Video is now playing');
                };
                
                // Add error handling for video
                videoElement.onerror = (error) => {
                    console.error('Video error:', error);
                };
            }
        };
        
        // Create offer
        await pc.setLocalDescription(await pc.createOffer({
            offerToReceiveVideo: true,
            offerToReceiveAudio: false,
        }));
        
        // Exchange the offer with the server
        const response = await fetch('/offer', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                sdp: pc.localDescription.sdp,
                type: pc.localDescription.type,
            }),
        });
        
        // Process the answer from the server
        const answer = await response.json();
        await pc.setRemoteDescription(answer);
        
        // Start stats collection
        statsInterval = setInterval(async () => {
            if (pc) {
                const stats = await pc.getStats();
                let statsOutput = '';
                
                stats.forEach(report => {
                    if (report.type === 'inbound-rtp' && report.kind === 'video') {
                        statsOutput += `Resolution: ${report.frameWidth}x${report.frameHeight}\n`;
                        statsOutput += `Frames Decoded: ${report.framesDecoded}\n`;
                        statsOutput += `Frames Per Second: ${report.framesPerSecond?.toFixed(2) || 'N/A'}\n`;
                        statsOutput += `Packets Received: ${report.packetsReceived}\n`;
                        statsOutput += `Packets Lost: ${report.packetsLost}\n`;

                        if (report.bytesReceived) {
                            const kilobits = report.bytesReceived * 8 / 1000;
                            const elapsed = (report.timestamp - report.firstTimestamp) / 1000;
                            const kbps = (kilobits / elapsed).toFixed(2);
                            statsOutput += `Bitrate: ${kbps} kbps\n`;
                        }
                    }
                });
                
                statsDiv.textContent = statsOutput || 'Collecting stats...';
            }
        }, 1000);
        
    } catch (e) {
        console.error('Failed to initialize WebRTC:', e);
        statsDiv.textContent = `Error: ${e.toString()}`;
        statusDiv.textContent = 'Status: Error - ' + e.toString();
        statusDiv.style.background = '#f44336';
        statusDiv.style.color = 'white';
        stop();
    }
}

// Stop WebRTC connection
function stop() {
    const videoElement = document.getElementById('video');
    const startButton = document.getElementById('start');
    const stopButton = document.getElementById('stop');
    const statsDiv = document.getElementById('stats');
    const statusDiv = document.getElementById('connectionStatus');
    
    // Update status
    statusDiv.textContent = 'Status: Disconnected';
    statusDiv.style.background = '#ffeb3b';
    statusDiv.style.color = 'black';
    
    // Enable start button and disable stop button
    startButton.disabled = false;
    stopButton.disabled = true;
    
    // Clear stats interval
    if (statsInterval) {
        clearInterval(statsInterval);
        statsInterval = null;
    }
    
    // Close peer connection
    if (pc) {
        pc.close();
        pc = null;
    }
    
    // Clear video element
    if (videoElement.srcObject) {
        videoElement.srcObject.getTracks().forEach(track => track.stop());
        videoElement.srcObject = null;
    }
    
    // Clear stats
    statsDiv.textContent = '';
}

// Handle page unload
window.addEventListener('beforeunload', () => {
    stop();
});
""")
    
    logging.info("Created HTML and JS files")

def signal_handler(sig, frame):
    logging.info(f"Received signal {sig}, shutting down...")
    cleanup_camera()
    sys.exit(0)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="WebRTC Raspberry Pi Camera server")
    parser.add_argument("--host", default="0.0.0.0", help="Host for HTTP server (default: 0.0.0.0)")
    parser.add_argument("--port", type=int, default=8080, help="Port for HTTP server (default: 8080)")
    parser.add_argument("--width", type=int, default=640, help="Camera width (default: 640)")
    parser.add_argument("--height", type=int, default=480, help="Camera height (default: 480)")
    parser.add_argument("--cert-file", help="SSL certificate file (for HTTPS)")
    parser.add_argument("--key-file", help="SSL key file (for HTTPS)")
    parser.add_argument("--debug", action="store_true", help="Enable debug logging")
    args = parser.parse_args()
    
    # Set logging level
    if args.debug:
        logging.basicConfig(level=logging.DEBUG)
    
    # Register signal handlers for clean shutdown
    signal.signal(signal.SIGINT, signal_handler)  # Ctrl+C
    signal.signal(signal.SIGTERM, signal_handler)  # termination
    
    # Initialize camera
    if not init_camera(args.width, args.height):
        logging.error("Failed to initialize camera. Exiting.")
        sys.exit(1)
    
    # Start camera capture thread
    capture_thread = threading.Thread(target=camera_capture_thread, daemon=True)
    capture_thread.start()
    
    # Ensure the HTML files exist in the same directory as the script
    current_dir = os.path.dirname(os.path.abspath(__file__))
    if not os.path.exists(os.path.join(current_dir, "index.html")) or \
       not os.path.exists(os.path.join(current_dir, "client.js")):
        create_html_files()

    # Create web application and add routes
    app = web.Application()
    app.router.add_get("/", index)
    app.router.add_get("/client.js", javascript)
    app.router.add_post("/offer", offer)
    app.on_shutdown.append(on_shutdown)

    # Configure SSL
    if args.cert_file and args.key_file:
        ssl_context = ssl.SSLContext()
        ssl_context.load_cert_chain(args.cert_file, args.key_file)
    else:
        ssl_context = None

    # Start server
    try:
        web.run_app(
            app, host=args.host, port=args.port, ssl_context=ssl_context
        )
    except KeyboardInterrupt:
        logging.info("Server stopped by user")
    except Exception as e:
        logging.error(f"Server error: {e}")
    finally:
        cleanup_camera()