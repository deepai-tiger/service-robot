import asyncio
import json
import firebase_admin
from firebase_admin import credentials, firestore
from aiortc import RTCPeerConnection, RTCConfiguration, RTCIceServer, RTCSessionDescription, RTCIceCandidate

# Build the ICE servers list
ice_servers = [
    RTCIceServer(urls=["stun:stun.l.google.com:19302"]),
    RTCIceServer(urls=["stun:stun1.l.google.com:19302"]),
    RTCIceServer(
        urls=["turn:relay.metered.ca:80"],
        username="openai",
        credential="openai"
    ),
    RTCIceServer(
        urls=["turn:relay.metered.ca:443"],
        username="openai",
        credential="openai"
    ),
]

# Build the config object
config = RTCConfiguration(iceServers=ice_servers)

async def main(call_id):
    # Initialize Firebase only if not already initialized
    if not firebase_admin._apps:
        cred = credentials.Certificate('serviceAccountKey.json')
        firebase_admin.initialize_app(cred)
    db = firestore.client()

    # Get the current event loop
    loop = asyncio.get_running_loop()

    # Create RTCPeerConnection
    pc = RTCPeerConnection(configuration=config)

    # Connect to Firestore
    call_ref = db.collection('calls').document(call_id)
    offer_candidates_ref = call_ref.collection('offerCandidates')
    answer_candidates_ref = call_ref.collection('answerCandidates')

    # Set up ICE candidate gathering
    @pc.on("icecandidate")
    async def on_icecandidate(candidate):
        print("ICE candidate event:", candidate)
        if candidate:
            result = await answer_candidates_ref.add({
                "candidate": candidate.candidate,
                "sdpMid": candidate.sdpMid,
                "sdpMLineIndex": candidate.sdpMLineIndex
            })
            print("Candidate sent to Firestore:", result)
        else:
            print("ICE candidate event: None (gathering complete)")

    # Get offer
    call_doc = call_ref.get()
    if not call_doc.exists:
        print(f"No call found with ID {call_id}")
        return
    call_data = call_doc.to_dict()
    offer = call_data.get("offer")
    if not offer:
        print(f"No offer found in call {call_id}")
        return

    # Add a dummy data channel to ensure ICE gathering starts
    # pc.createDataChannel("chat")

    await pc.setRemoteDescription(RTCSessionDescription(sdp=offer["sdp"], type=offer["type"]))

    # Create and set local answer
    answer = await pc.createAnswer()
    await pc.setLocalDescription(answer)

    # Send answer
    call_ref.update({
        "answer": {
            "type": pc.localDescription.type,
            "sdp": pc.localDescription.sdp
        }
    })

    # Listen for remote ICE candidates
    def on_snapshot(col_snapshot, changes, read_time):
        for change in changes:
            if change.type.name == 'ADDED':
                data = change.document.to_dict()
                candidate_dict = {
                    "candidate": data["candidate"],
                    "sdpMid": data["sdpMid"],
                    "sdpMLineIndex": data["sdpMLineIndex"]
                }
                asyncio.run_coroutine_threadsafe(pc.addIceCandidate(candidate_dict), loop)
    offer_candidates_ref.on_snapshot(on_snapshot)

    # Just wait forever (or until connection closes)
    print("Connection established! (success)")
    await asyncio.Future()  # keeps the script running

if __name__ == "__main__":
    call_id = input("Enter Call ID to answer: ")
    asyncio.run(main(call_id))
