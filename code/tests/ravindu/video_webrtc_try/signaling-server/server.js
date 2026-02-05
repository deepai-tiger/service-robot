const WebSocket = require('ws');
const express = require('express');
const app = express();
const server = require('http').createServer(app);
const wss = new WebSocket.Server({ server });

let piSocket = null;
let clientSocket = null;

wss.on('connection', (ws) => {
  ws.on('message', (message) => {
    const msg = JSON.parse(message);

    if (msg.role === 'pi') {
      piSocket = ws;
    } else if (msg.role === 'client') {
      clientSocket = ws;
    }

    if (msg.type === 'offer' && clientSocket) {
      clientSocket.send(message);
    } else if (msg.type === 'answer' && piSocket) {
      piSocket.send(message);
    } else if (msg.type === 'ice') {
      (msg.to === 'pi' ? piSocket : clientSocket)?.send(message);
    }
  });
});

app.use(express.static('public'));

server.listen(3000, () => {
  console.log('Signaling server on http://localhost:3000');
});
