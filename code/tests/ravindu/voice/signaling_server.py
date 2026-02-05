#!/usr/bin/env python3
"""
Simple WebSocket-based signaling server for WebRTC peer connection
Run this on a machine accessible by both the Raspberry Pi and laptop
"""

import asyncio
import json
import logging
import websockets
from typing import Set, Dict

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class SignalingServer:
    def __init__(self):
        self.clients: Dict[str, websockets.WebSocketServerProtocol] = {}
        self.rooms: Dict[str, Set[str]] = {}
    
    async def register_client(self, websocket: websockets.WebSocketServerProtocol, client_id: str):
        """Register a new client"""
        self.clients[client_id] = websocket
        logger.info(f"Client {client_id} registered")
    
    async def unregister_client(self, client_id: str):
        """Unregister a client"""
        if client_id in self.clients:
            del self.clients[client_id]
            # Remove from all rooms
            for room_id, members in self.rooms.items():
                if client_id in members:
                    members.remove(client_id)
                    if not members:
                        del self.rooms[room_id]
                    break
        logger.info(f"Client {client_id} unregistered")
    
    async def join_room(self, client_id: str, room_id: str):
        """Add client to a room"""
        if room_id not in self.rooms:
            self.rooms[room_id] = set()
        self.rooms[room_id].add(client_id)
        logger.info(f"Client {client_id} joined room {room_id}")
    
    async def broadcast_to_room(self, sender_id: str, room_id: str, message: dict):
        """Broadcast message to all clients in room except sender"""
        if room_id not in self.rooms:
            return
        
        for client_id in self.rooms[room_id]:
            if client_id != sender_id and client_id in self.clients:
                try:
                    await self.clients[client_id].send(json.dumps(message))
                except websockets.exceptions.ConnectionClosed:
                    logger.warning(f"Connection to {client_id} closed")
                    await self.unregister_client(client_id)
    
    async def handle_client(self, websocket: websockets.WebSocketServerProtocol):
        """Handle WebSocket connection from client"""
        client_id = None
        try:
            async for raw_message in websocket:
                try:
                    message = json.loads(raw_message)
                    msg_type = message.get('type')
                    
                    if msg_type == 'register':
                        client_id = message.get('client_id')
                        await self.register_client(websocket, client_id)
                        await websocket.send(json.dumps({
                            'type': 'registered',
                            'client_id': client_id
                        }))
                    
                    elif msg_type == 'join_room':
                        room_id = message.get('room_id')
                        if client_id:
                            await self.join_room(client_id, room_id)
                            await websocket.send(json.dumps({
                                'type': 'joined_room',
                                'room_id': room_id
                            }))
                    
                    elif msg_type in ['offer', 'answer', 'ice_candidate']:
                        room_id = message.get('room_id')
                        if client_id and room_id:
                            await self.broadcast_to_room(client_id, room_id, message)
                    
                except json.JSONDecodeError:
                    logger.error(f"Invalid JSON from {client_id}")
                except Exception as e:
                    logger.error(f"Error handling message from {client_id}: {e}")
        
        except websockets.exceptions.ConnectionClosed:
            pass
        finally:
            if client_id:
                await self.unregister_client(client_id)

async def main():
    signaling_server = SignalingServer()
    
    # Start the WebSocket server
    start_server = websockets.serve(
        signaling_server.handle_client,
        "0.0.0.0",  # Listen on all interfaces
        8765,
        ping_interval=20,
        ping_timeout=10
    )
    
    logger.info("Signaling server starting on ws://0.0.0.0:8765")
    
    await start_server
    
    # Keep the server running
    await asyncio.Future()  # Run forever

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Signaling server stopped")