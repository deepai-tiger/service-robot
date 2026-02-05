import asyncio
import cv2
import av
from aiortc import RTCPeerConnection, RTCSessionDescription, VideoStreamTrack, MediaPlayer, RTCIceCandidate
from aiortc.contrib.media import MediaBlackhole
import firebase_admin
from firebase_admin import credentials, firestore

# ---------- CONFIG ----------

FIREBASE_CRED_PATH = "serviceAccountKey.json"  # Download your service account JSON file
CALL_ID = "YOUR_CALL_ID"  # Change this dynamically or via args
ICE_SERVERS = [
    {"urls": "stun:stun.l.google.com:19302"},
    {"urls": "stun:stun1.l.google.com:19302"},
    {
        "urls": "turn:relay.metered.ca:80",
        "username": "openai",
        "credential": "openai"
    },
    {
        "urls": "turn:relay.metered.ca:443",
        "username": "openai",
        "credential": "openai"
    }
]

# ---------- FIREBASE SETUP ----------

cred = credentials.Certificate(FIREBASE_CRED_PATH)
firebase_admin.initialize_app(cred)
db = firestore.client()

# ---------- VIDEO TRACK ----------

class CameraVideoTrack(VideoStreamTrack):
    def __init__(self):
        super().__init__()
        self.cap = cv2.VideoCapture(0)

    async def recv(self):
        pts, time_base = await self.next_timestamp()
        ret, frame = self.cap.read()
        if not ret:
            return None

        frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        frame = av.VideoFrame.from_ndarray(frame, format="rgb24")
        frame.pts = pts
        frame.time_base = time_base
        return frame

# ---------- MAIN ----------

async def run(CALL_ID):
    pc = RTCPeerConnection(configuration={"iceServers": ICE_SERVERS})

    # Send video from Pi camera
    pc.addTrack(CameraVideoTrack())

    # Audio sink to play caller's audio
    player = MediaBlackhole()

    @pc.on("track")
    def on_track(track):
        if track.kind == "audio":
            player.addTrack(track)

    # Setup Firestore signaling
    call_doc = db.collection("calls").document(CALL_ID)
    answer_candidates = call_doc.collection("answerCandidates")
    offer_candidates = call_doc.collection("offerCandidates")

    @pc.on("icecandidate")
    async def on_icecandidate(candidate):
        if candidate:
            await answer_candidates.add(candidate.toJSON())

    # Get offer
    offer_snapshot = call_doc.get()
    offer = offer_snapshot.to_dict().get("offer")
    if not offer:
        print("No offer found for call ID")
        return

    await pc.setRemoteDescription(RTCSessionDescription(sdp=offer["sdp"], type=offer["type"]))
    answer = await pc.createAnswer()
    await pc.setLocalDescription(answer)

    # Send answer to Firestore
    await call_doc.update({"answer": {
        "type": pc.localDescription.type,
        "sdp": pc.localDescription.sdp
    }})

    # Handle offer ICE candidates
    def on_snapshot(snapshot, changes, read_time):
        for change in changes:
            if change.type.name == "ADDED":
                data = change.document.to_dict()
                candidate = RTCIceCandidate(
                    sdpMid=data.get("sdpMid"),
                    sdpMLineIndex=data.get("sdpMLineIndex"),
                    candidate=data.get("candidate")
                )
                asyncio.ensure_future(pc.addIceCandidate(candidate))

    offer_candidates.on_snapshot(on_snapshot)

    # Keep alive
    await asyncio.Future()

if __name__ == "__main__":
    import sys
    if len(sys.argv) < 2:
        print("Usage: python receiver.py CALL_ID")
        sys.exit(1)

    call_id = sys.argv[1]
    # logger.info(f"Starting WebRTC receiver for call ID: {call_id}")
    
    try:
        asyncio.run(run(call_id))
    except KeyboardInterrupt:
        print("Receiver stopped by user")
    except Exception as e: 
        print(f"Receiver failed: {e}")
        # logger.info("Receiver stopped by user")
    # except Exception as e:
    #     # logger.error(f"Receiver failed: {e}")
