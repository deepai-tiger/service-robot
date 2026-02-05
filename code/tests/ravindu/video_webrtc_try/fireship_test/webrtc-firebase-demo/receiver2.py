import asyncio
import json
import firebase_admin
from firebase_admin import credentials, firestore
from aiortc import RTCPeerConnection, RTCSessionDescription, RTCIceCandidate, MediaStreamTrack
import logging
import wave
import threading
import time

# Set up logging to see what's happening
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# 🔑 Firebase setup
firebase_config_path = 'serviceAccountKey.json'
cred = credentials.Certificate(firebase_config_path)
firebase_admin.initialize_app(cred)
db = firestore.client()

# ICE servers
from aiortc import RTCIceServer

ICE_SERVERS = [
    RTCIceServer(urls="stun:stun.l.google.com:19302"),
    RTCIceServer(urls="stun:stun1.l.google.com:19302"),
    RTCIceServer(urls="turn:relay.metered.ca:80", username="openai", credential="openai"),
    RTCIceServer(urls="turn:relay.metered.ca:443", username="openai", credential="openai")
]

# Save received audio to file
class AudioRecorder(MediaStreamTrack):
    kind = "audio"

    def __init__(self, track):
        super().__init__()
        self.track = track
        self.audio_file = None
        self.frame_count = 0
        self.setup_recording()

    def setup_recording(self):
        """Setup audio recording to file"""
        try:
            filename = f"received_audio_{int(time.time())}.wav"
            self.audio_file = wave.open(filename, 'wb')
            self.audio_file.setnchannels(1)  # mono
            self.audio_file.setsampwidth(2)  # 16-bit
            self.audio_file.setframerate(48000)  # 48kHz
            logger.info(f"Recording audio to: {filename}")
        except Exception as e:
            logger.error(f"Failed to setup audio recording: {e}")
            self.audio_file = None

    async def recv(self):
        frame = await self.track.recv()
        if self.audio_file:
            try:
                self.frame_count += 1
                
                # Convert audio frame to bytes
                if hasattr(frame, 'to_ndarray'):
                    audio_array = frame.to_ndarray()
                    # Ensure correct format
                    if audio_array.dtype != 'int16':
                        audio_array = (audio_array * 32767).astype('int16')
                    audio_data = audio_array.tobytes()
                elif hasattr(frame, 'planes') and frame.planes:
                    audio_data = frame.planes[0].to_bytes()
                else:
                    logger.warning("Unknown audio frame format")
                    return frame
                
                if len(audio_data) > 0:
                    self.audio_file.writeframes(audio_data)
                    
                    # Log progress every 100 frames
                    if self.frame_count % 100 == 0:
                        logger.info(f"Recorded {self.frame_count} audio frames")
                        
            except Exception as e:
                logger.error(f"Error recording audio: {e}")
                logger.info(f"Frame type: {type(frame)}")
                if hasattr(frame, 'format'):
                    logger.info(f"Frame format: {frame.format}")
                
        return frame

    def close(self):
        if self.audio_file:
            self.audio_file.close()
            logger.info(f"Audio recording closed. Total frames: {self.frame_count}")

async def run_receiver(call_id):
    from aiortc import RTCConfiguration

    pc = RTCPeerConnection(configuration=RTCConfiguration(iceServers=ICE_SERVERS))
    audio_recorder = None

    call_ref = db.collection("calls").document(call_id)
    answer_candidates = call_ref.collection("answerCandidates")
    offer_candidates = call_ref.collection("offerCandidates")

    @pc.on("icecandidate")
    async def on_icecandidate(event):
        if event.candidate:
            try:
                candidate_dict = {
                    'candidate': str(event.candidate.candidate),
                    'sdpMid': event.candidate.sdpMid,
                    'sdpMLineIndex': event.candidate.sdpMLineIndex
                }
                answer_candidates.add(candidate_dict)
                logger.info(f"Added local ICE candidate")
            except Exception as e:
                logger.error(f"Error adding ICE candidate: {e}")

    @pc.on("track")
    def on_track(track):
        logger.info(f"Track received: {track.kind}")
        if track.kind == "audio":
            nonlocal audio_recorder
            audio_recorder = AudioRecorder(track)
            asyncio.ensure_future(process_audio(audio_recorder))

    # Get offer
    try:
        offer_data = call_ref.get().to_dict()
        if not offer_data or "offer" not in offer_data:
            logger.error("No valid offer found.")
            return

        offer = RTCSessionDescription(sdp=offer_data["offer"]["sdp"], type=offer_data["offer"]["type"])
        await pc.setRemoteDescription(offer)
        logger.info("Remote description set successfully")

        # Create answer
        answer = await pc.createAnswer()
        await pc.setLocalDescription(answer)
        logger.info("Local description set successfully")

        # Send answer to Firestore
        call_ref.update({
            "answer": {
                "type": pc.localDescription.type,
                "sdp": pc.localDescription.sdp
            }
        })
        logger.info("Answer sent to Firestore")

    except Exception as e:
        logger.error(f"Error setting up WebRTC connection: {e}")
        return

    # Listen for ICE candidates from caller
    def on_offer_candidate(snapshot, changes, read_time):
        for change in changes:
            if change.type.name == 'ADDED':
                candidate = change.document.to_dict()
                try:
                    # Parse candidate string manually
                    candidate_str = candidate['candidate']
                    parts = candidate_str.split()
                    
                    if len(parts) >= 8:
                        foundation = parts[0].split(':')[1]
                        component = int(parts[1])
                        protocol = parts[2]
                        priority = int(parts[3])
                        ip = parts[4]
                        port = int(parts[5])
                        type_val = parts[7]
                        
                        ice_candidate = RTCIceCandidate(
                            ip=ip,
                            port=port,
                            protocol=protocol,
                            priority=priority,
                            foundation=foundation,
                            component=component,
                            type=type_val,
                            sdpMid=candidate['sdpMid'],
                            sdpMLineIndex=candidate['sdpMLineIndex']
                        )
                        asyncio.ensure_future(pc.addIceCandidate(ice_candidate))
                        logger.info(f"Added remote ICE candidate: {type_val} {ip}:{port}")
                    else:
                        logger.warning(f"Invalid candidate format: {candidate_str}")
                        
                except Exception as e:
                    logger.error(f"Error parsing ICE candidate: {e}")
                    # Skip this candidate and continue
                    continue

    offer_candidates.on_snapshot(on_offer_candidate)

    # Keep alive
    logger.info("WebRTC receiver is running...")
    try:
        while True:
            await asyncio.sleep(1)
    except KeyboardInterrupt:
        logger.info("Shutting down...")
        if audio_recorder:
            audio_recorder.close()
        await pc.close()

async def process_audio(recorder):
    """Keep the audio recorder running"""
    try:
        while True:
            await recorder.recv()
    except Exception as e:
        logger.error(f"Error in audio processing: {e}")
        if recorder:
            recorder.close()

if __name__ == "__main__":
    import sys
    if len(sys.argv) < 2:
        print("Usage: python receiver.py CALL_ID")
        sys.exit(1)

    call_id = sys.argv[1]
    logger.info(f"Starting WebRTC receiver for call ID: {call_id}")
    
    try:
        asyncio.run(run_receiver(call_id))
    except KeyboardInterrupt:
        logger.info("Receiver stopped by user")
    except Exception as e:
        logger.error(f"Receiver failed: {e}")