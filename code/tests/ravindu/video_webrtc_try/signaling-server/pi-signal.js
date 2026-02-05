const WebSocket = require('ws');
const ws = new WebSocket("ws://192.168.8.199:3000");

ws.on('open', () => {
  ws.send(JSON.stringify({ role: "pi" }));

  // Send hardcoded offer (replace with GStreamer's offer later)
  ws.send(JSON.stringify({
    type: "offer",
    sdp: "REPLACE_ME_WITH_GSTREAMER_OFFER"
  }));
});

ws.on('message', (msg) => {
  const data = JSON.parse(msg);
  if (data.type === "answer") {
    // Send answer to GStreamer via stdin or pipe it into webrtcbin
    console.log("Received answer from browser:", data.sdp);
  }

  if (data.type === "ice") {
    console.log("Received ICE from browser:", data.candidate);
  }
});
