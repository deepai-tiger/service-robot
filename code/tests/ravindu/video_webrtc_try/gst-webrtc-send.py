#!/usr/bin/env python3
import sys, asyncio, json, websockets, gi

import gi
gi.require_version('Gst', '1.0')
from gi.repository import Gst
gi.require_version('GstWebRTC', '1.0')
from gi.repository import Gst, GstWebRTC, GObject, GLib

Gst.init(None)

SIGNALING_SERVER = "ws://192.168.8.199>:3000"

pipeline = None
webrtc = None
ws = None

def send_sdp_offer(promise, _, __):
    reply = webrtc.emit('get-offer')
    offer = reply.get_value('offer')
    webrtc.emit('set-local-description', offer, None)
    text = offer.sdp.as_text()
    asyncio.ensure_future(ws.send(json.dumps({ 'type': 'offer', 'sdp': text, 'role': 'pi' })))

def on_negotiation_needed(element):
    promise = Gst.Promise.new_with_change_func(send_sdp_offer, element, None)
    element.emit('create-offer', None, promise)

def on_ice_candidate(_, mlineindex, candidate):
    ice = json.dumps({ 'type': 'ice', 'candidate': { 'candidate': candidate, 'sdpMLineIndex': mlineindex }, 'role': 'pi' })
    asyncio.ensure_future(ws.send(ice))

async def setup_call():
    global pipeline, webrtc
    desc = "v4l2src ! videoconvert ! vp8enc ! rtpvp8pay ! webrtcbin name=sendrecv"
    pipeline = Gst.parse_launch(desc)
    webrtc = pipeline.get_by_name('sendrecv')
    webrtc.connect('on-negotiation-needed', on_negotiation_needed)
    webrtc.connect('on-ice-candidate', on_ice_candidate)
    pipeline.set_state(Gst.State.PLAYING)

async def consume_signaling():
    global ws
    async with websockets.connect(SIGNALING_SERVER) as websocket:
        ws = websocket
        await ws.send(json.dumps({ 'role': 'pi' }))

        await setup_call()

        async for message in ws:
            msg = json.loads(message)
            if msg['type'] == 'answer':
                sdp = GstSdp.SDPMessage.new()
                GstSdp.sdp_message_parse_buffer(bytes(msg['sdp'], 'utf-8'), sdp)
                answer = GstWebRTC.WebRTCSessionDescription.new(GstWebRTC.WebRTCSDPType.ANSWER, sdp)
                webrtc.emit('set-remote-description', answer, None)
            elif msg['type'] == 'ice':
                webrtc.emit('add-ice-candidate', msg['candidate']['sdpMLineIndex'], msg['candidate']['candidate'])

def main():
    loop = asyncio.get_event_loop()
    loop.run_until_complete(consume_signaling())

if __name__ == '__main__':
    GObject.threads_init()
    main()
