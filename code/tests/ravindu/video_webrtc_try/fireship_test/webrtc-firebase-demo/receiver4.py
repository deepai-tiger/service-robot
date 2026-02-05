import asyncio
import cv2
from aiortc import RTCPeerConnection, RTCSessionDescription, VideoStreamTrack, MediaStreamTrack, RTCIceCandidate
from aiortc.contrib.media import MediaPlayer
import firebase_admin
from firebase_admin import credentials, firestore

# Initialize Firebase
cred = credentials.Certificate("serviceAccountKey.json")  # Download your service account key JSON from Firebase console
firebase_admin.initialize_app(cred)
db = firestore.client()

# ICE server config
ICE_SERVERS = [
    {
        "urls": "stun:stun.l.google.com:19302"
    },
    {
        "urls": "stun:stun1.l.google.com:19302"
    },
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

async def run_receiver(call_id):
    from aiortc import RTCConfiguration, RTCIceServer

    ice_servers = [
        RTCIceServer(**s) for s in ICE_SERVERS
    ]
    pc = RTCPeerConnection(configuration=RTCConfiguration(iceServers=ice_servers))
    
    # Capture local video + audio
    player = MediaPlayer("video=HD Webcam", format="dshow")  # Replace with your webcam name  # Linux example
    # player = MediaPlayer("default", format="dshow")  # Windows example if you want default webcam

    if player.video:
        pc.addTrack(player.video)
    if player.audio:
        pc.addTrack(player.audio)
    
    # Firestore signaling
    call_doc = db.collection('calls').document(call_id)
    answer_candidates = call_doc.collection('answerCandidates')
    offer_candidates = call_doc.collection('offerCandidates')

    @pc.on("icecandidate")
    async def on_icecandidate(candidate):
        if candidate:
            await answer_candidates.add(candidate.toJSON())

    @pc.on("track")
    def on_track(track):
        if track.kind == "audio":
            @track.on("frame")
            def on_frame(frame):
                # We're receiving audio - could process or just print info
                print("Received audio frame")
        else:
            print(f"Unexpected track kind: {track.kind}")

    # Get offer
    call_data = call_doc.get().to_dict()
    offer = call_data.get("offer")
    if not offer:
        print("No offer found!")
        return

    await pc.setRemoteDescription(RTCSessionDescription(sdp=offer["sdp"], type=offer["type"]))
    answer = await pc.createAnswer()
    await pc.setLocalDescription(answer)

    await call_doc.update({"answer": {
        "type": pc.localDescription.type,
        "sdp": pc.localDescription.sdp
    }})

    # Listen for offer ICE candidates
    offer_candidates.on_snapshot(lambda snap, changes, ts:
        [pc.addIceCandidate(RTCIceCandidate(**change.document.to_dict())) for change in changes if change.type.name == "ADDED"]
    )

    # Keep the connection alive
    print("Receiver is running... press Ctrl+C to quit.")
    while True:
        await asyncio.sleep(1)

if __name__ == "__main__":
    call_id = input("Enter Call ID to answer: ").strip()
    asyncio.run(run_receiver(call_id))
