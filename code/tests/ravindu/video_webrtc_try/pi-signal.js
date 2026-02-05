// raspberry-pi/pi-signal.js
const WebSocket = require('ws');

const SIGNAL_SERVER_URL = 'ws://192.168.8.199:3000'; // Replace with your PC/server IP
const ws = new WebSocket(SIGNAL_SERVER_URL);

ws.on('open', () => {
  console.log('Connected to signaling server.');

  // Sample fake SDP offer for testing
  const sdpOffer = {
    type: 'offer',
    sdp: `v=0
o=- 46117348 2 IN IP4 127.0.0.1
s=-
t=0 0
a=group:BUNDLE 0
a=msid-semantic: WMS
m=video 9 UDP/TLS/RTP/SAVPF 96
c=IN IP4 0.0.0.0
a=mid:0
a=sendonly
a=rtcp-mux
a=rtpmap:96 VP8/90000
a=ice-ufrag:someufrag
a=ice-pwd:somepwd
a=fingerprint:sha-256 11:22:33:44:55:66:77:88:99:AA:BB:CC:DD:EE:FF:00:11:22:33:44:55:66:77:88:99:AA:BB:CC:DD:EE:FF:00
`
  };

  // Send to signaling server
  ws.send(JSON.stringify({ type: 'offer', data: sdpOffer }));
  console.log('Sent dummy offer.');
});

ws.on('message', (msg) => {
  const message = JSON.parse(msg);
  console.log('Received from server:', message);

  if (message.type === 'answer') {
    console.log('Received answer from browser.');
    // Normally you would pass this to GStreamer’s webrtcbin
  }
});

ws.on('error', (err) => {
  console.error('WebSocket error:', err);
});

ws.on('close', () => {
  console.log('Connection closed.');
});

