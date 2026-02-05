import asyncio
import json
import firebase_admin
from firebase_admin import credentials, firestore
from aiortc import RTCPeerConnection, RTCSessionDescription, RTCIceCandidate, MediaStreamTrack
from aiortc.contrib.media import MediaPlayer
import pyaudio
import logging

# Set up logging to see what's happening
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# 🔑 Firebase setup
firebase_config_path = 'serviceAccountKey.json'  # Download from Firebase console
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

# Play received audio using PyAudio
class AudioReceiver(MediaStreamTrack):
    kind = "audio"

    def __init__(self, track):
        super().__init__()
        self.track = track
        self.p = None
        self.stream = None
        self.setup_audio()

    def setup_audio(self):
        """Setup PyAudio with better error handling"""
        try:
            self.p = pyaudio.PyAudio()
            
            # Try to find a working audio device
            device_index = None
            for i in range(self.p.get_device_count()):
                device_info = self.p.get_device_info_by_index(i)
                if device_info['maxOutputChannels'] > 0:
                    device_index = i
                    logger.info(f"Using audio device: {device_info['name']}")
                    break
            
            if device_index is None:
                logger.warning("No audio output device found")
                return
                
            self.stream = self.p.open(
                format=pyaudio.paInt16,
                channels=1,
                rate=48000,
                output=True,
                output_device_index=device_index,
                frames_per_buffer=1024
            )
            logger.info("Audio stream opened successfully")
            
        except Exception as e:
            logger.error(f"Failed to setup audio: {e}")
            self.p = None
            self.stream = None

    async def recv(self):
        frame = await self.track.recv()
        if self.stream:
            try:
                # Convert audio frame to the correct format
                # WebRTC audio frames are typically in different formats
                if hasattr(frame, 'to_ndarray'):
                    # Convert to numpy array first
                    audio_array = frame.to_ndarray()
                    # Ensure it's in the right format (int16)
                    if audio_array.dtype != 'int16':
                        # Convert float to int16
                        audio_array = (audio_array * 32767).astype('int16')
                    audio_data = audio_array.tobytes()
                elif hasattr(frame, 'planes') and frame.planes:
                    # Alternative method for older versions
                    audio_data = frame.planes[0].to_bytes()
                else:
                    logger.warning("Unknown audio frame format")
                    return frame
                
                if len(audio_data) > 0:
                    self.stream.write(audio_data)
                    
            except Exception as e:
                logger.error(f"Error playing audio: {e}")
                # Try simpler approach - just log the frame info
                logger.info(f"Audio frame received: {type(frame)}, format: {getattr(frame, 'format', 'unknown')}")
        return frame

    def __del__(self):
        if self.stream:
            self.stream.stop_stream()
            self.stream.close()
        if self.p:
            self.p.terminate()

async def run_receiver(call_id):
    from aiortc import RTCConfiguration

    pc = RTCPeerConnection(configuration=RTCConfiguration(iceServers=ICE_SERVERS))

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
                logger.info(f"Added ICE candidate: {candidate_dict}")
            except Exception as e:
                logger.error(f"Error adding ICE candidate: {e}")

    @pc.on("track")
    def on_track(track):
        logger.info(f"Track received: {track.kind}")
        if track.kind == "audio":
            receiver = AudioReceiver(track)
            asyncio.ensure_future(play_audio(receiver))
        # If you wanted to handle video, you'd add code here

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
                    # Parse the candidate string to extract required fields
                    candidate_str = candidate['candidate']
                    parts = candidate_str.split()
                    
                    if len(parts) >= 8:
                        # Extract required fields from candidate string
                        # Format: "candidate:foundation component protocol priority ip port typ type"
                        foundation = parts[0].split(':')[1]
                        component = int(parts[1])
                        protocol = parts[2]
                        priority = int(parts[3])
                        ip = parts[4]
                        port = int(parts[5])
                        typ = parts[6]  # should be "typ"
                        type_val = parts[7]  # host, srflx, prflx, relay
                        
                        # Create RTCIceCandidate with all required parameters
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
                    logger.error(f"Error adding remote ICE candidate: {e}")
                    # Try alternative approach - create from SDP string
                    try:
                        from aiortc.rtcicecandidatetest import candidate_from_sdp
                        ice_candidate = candidate_from_sdp(candidate['candidate'])
                        ice_candidate.sdpMid = candidate['sdpMid']
                        ice_candidate.sdpMLineIndex = candidate['sdpMLineIndex']
                        asyncio.ensure_future(pc.addIceCandidate(ice_candidate))
                        logger.info(f"Added remote ICE candidate (fallback method)")
                    except Exception as e2:
                        logger.error(f"Fallback method also failed: {e2}")

    offer_candidates.on_snapshot(on_offer_candidate)

    # Keep alive
    logger.info("WebRTC receiver is running...")
    try:
        while True:
            await asyncio.sleep(1)
    except KeyboardInterrupt:
        logger.info("Shutting down...")
        await pc.close()

async def play_audio(receiver):
    """Keep the audio receiver running"""
    try:
        while True:
            await receiver.recv()
    except Exception as e:
        logger.error(f"Error in audio playback: {e}")

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