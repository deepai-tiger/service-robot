#!/usr/bin/env python3
"""
Laptop WebRTC Audio Client
Handles audio input/output via built-in microphone and speakers
"""

import asyncio
import json
import logging
import signal
import sys
import numpy as np
import pyaudio
import websockets
from aiortc import RTCPeerConnection, RTCSessionDescription, RTCIceCandidate
from aiortc.contrib.media import MediaStreamTrack
from aiortc.mediastreams import MediaStreamError
from threading import Thread
import time
from queue import Queue, Empty

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Audio configuration
SAMPLE_RATE = 16000
CHANNELS = 1
CHUNK_SIZE = 1024
FORMAT = pyaudio.paInt16

class AudioInputTrack(MediaStreamTrack):
    """Custom audio track for capturing microphone input"""
    
    kind = "audio"
    
    def __init__(self, device_index=None):
        super().__init__()
        self.device_index = device_index
        self.audio = pyaudio.PyAudio()
        self.stream = None
        self.audio_queue = Queue(maxsize=50)
        self.running = False
        
    async def recv(self):
        """Receive audio frame"""
        if not self.running:
            await self.start_recording()
        
        # Get audio data from queue
        try:
            audio_data = self.audio_queue.get(timeout=0.1)
            # Convert to required format for aiortc
            frame = self._create_audio_frame(audio_data)
            return frame
        except Empty:
            # Return silence if no audio available
            silence = np.zeros(CHUNK_SIZE, dtype=np.int16)
            return self._create_audio_frame(silence.tobytes())
    
    def _create_audio_frame(self, data):
        """Create audio frame from raw data"""
        # This is a simplified frame creation - in practice you'd want proper AudioFrame
        # For this example, we'll return the raw data wrapped appropriately
        class SimpleAudioFrame:
            def __init__(self, data):
                self.data = data
                self.sample_rate = SAMPLE_RATE
                self.channels = CHANNELS
        return SimpleAudioFrame(data)
    
    async def start_recording(self):
        """Start audio recording in separate thread"""
        if self.running:
            return
            
        try:
            self.stream = self.audio.open(
                format=FORMAT,
                channels=CHANNELS,
                rate=SAMPLE_RATE,
                input=True,
                input_device_index=self.device_index,
                frames_per_buffer=CHUNK_SIZE,
                stream_callback=self._audio_callback
            )
            self.stream.start_stream()
            self.running = True
            logger.info("Started audio recording")
        except Exception as e:
            logger.error(f"Failed to start recording: {e}")
    
    def _audio_callback(self, in_data, frame_count, time_info, status):
        """Callback for audio input"""
        try:
            self.audio_queue.put_nowait(in_data)
        except:
            pass  # Queue full, drop frame
        return (None, pyaudio.paContinue)
    
    async def stop_recording(self):
        """Stop audio recording"""
        self.running = False
        if self.stream:
            self.stream.stop_stream()
            self.stream.close()
        self.audio.terminate()

class AudioPlayer:
    """Audio playback handler"""
    
    def __init__(self, device_index=None):
        self.device_index = device_index
        self.audio = pyaudio.PyAudio()
        self.stream = None
        self.playback_queue = Queue()
        self.running = False
        
    def start_playback(self):
        """Start audio playback"""
        if self.running:
            return
            
        try:
            self.stream = self.audio.open(
                format=FORMAT,
                channels=CHANNELS,
                rate=SAMPLE_RATE,
                output=True,
                output_device_index=self.device_index,
                frames_per_buffer=CHUNK_SIZE,
                stream_callback=self._playback_callback
            )
            self.stream.start_stream()
            self.running = True
            logger.info("Started audio playback")
        except Exception as e:
            logger.error(f"Failed to start playback: {e}")
    
    def _playback_callback(self, in_data, frame_count, time_info, status):
        """Callback for audio output"""
        try:
            data = self.playback_queue.get_nowait()
            return (data, pyaudio.paContinue)
        except Empty:
            # Return silence if no audio available
            silence = np.zeros(frame_count * CHANNELS, dtype=np.int16)
            return (silence.tobytes(), pyaudio.paContinue)
    
    def play_audio(self, data):
        """Add audio data to playback queue"""
        try:
            self.playback_queue.put_nowait(data)
        except:
            pass  # Queue full, drop frame
    
    def stop_playback(self):
        """Stop audio playback"""
        self.running = False
        if self.stream:
            self.stream.stop_stream()
            self.stream.close()
        self.audio.terminate()

class LaptopAudioClient:
    """Main WebRTC audio client for Laptop"""
    
    def __init__(self, signaling_server_url, room_id="audio_room"):
        self.signaling_server_url = signaling_server_url
        self.room_id = room_id
        self.client_id = "laptop"
        
        # WebRTC components
        self.pc = RTCPeerConnection()
        self.websocket = None
        
        # Audio components
        self.audio_input = None
        self.audio_player = None
        
        # Setup WebRTC event handlers
        self.pc.on("track", self.on_track)
        self.pc.on("icecandidate", self.on_ice_candidate)
        
    def find_default_audio_devices(self):
        """Find default audio devices"""
        audio = pyaudio.PyAudio()
        default_input_index = None
        default_output_index = None
        
        # Get default devices
        try:
            default_input_info = audio.get_default_input_device_info()
            default_input_index = default_input_info['index']
            logger.info(f"Default input device: {default_input_info['name']}")
        except OSError:
            logger.warning("No default input device found")
        
        try:
            default_output_info = audio.get_default_output_device_info()
            default_output_index = default_output_info['index']
            logger.info(f"Default output device: {default_output_info['name']}")
        except OSError:
            logger.warning("No default output device found")
        
        # List all available devices for reference
        logger.info("Available audio devices:")
        for i in range(audio.get_device_count()):
            info = audio.get_device_info_by_index(i)
            logger.info(f"Device {i}: {info['name']} - Inputs: {info['maxInputChannels']}, Outputs: {info['maxOutputChannels']}")
        
        audio.terminate()
        return default_input_index, default_output_index
    
    async def connect_to_signaling_server(self):
        """Connect to the WebSocket signaling server"""
        try:
            self.websocket = await websockets.connect(self.signaling_server_url)
            logger.info(f"Connected to signaling server: {self.signaling_server_url}")
            
            # Register with server
            await self.websocket.send(json.dumps({
                'type': 'register',
                'client_id': self.client_id
            }))
            
            # Join room
            await self.websocket.send(json.dumps({
                'type': 'join_room',
                'room_id': self.room_id
            }))
            
        except Exception as e:
            logger.error(f"Failed to connect to signaling server: {e}")
            raise
    
    async def handle_signaling_messages(self):
        """Handle incoming signaling messages"""
        try:
            async for raw_message in self.websocket:
                message = json.loads(raw_message)
                msg_type = message.get('type')
                
                if msg_type == 'offer':
                    await self.handle_offer(message)
                elif msg_type == 'answer':
                    await self.handle_answer(message)
                elif msg_type == 'ice_candidate':
                    await self.handle_ice_candidate(message)
                elif msg_type in ['registered', 'joined_room']:
                    logger.info(f"Server response: {message}")
                    
        except websockets.exceptions.ConnectionClosed:
            logger.info("Signaling connection closed")
        except Exception as e:
            logger.error(f"Error in signaling: {e}")
    
    async def handle_offer(self, message):
        """Handle incoming WebRTC offer"""
        logger.info("Received offer")
        
        # Set remote description
        offer = RTCSessionDescription(
            sdp=message['sdp'],
            type=message['sdp_type']
        )
        await self.pc.setRemoteDescription(offer)
        
        # Add our audio track before creating answer
        input_index, output_index = self.find_default_audio_devices()
        
        if input_index is not None:
            self.audio_input = AudioInputTrack(device_index=input_index)
            self.pc.addTrack(self.audio_input)
            logger.info(f"Added audio input track (device {input_index})")
        
        if output_index is not None:
            self.audio_player = AudioPlayer(device_index=output_index)
            self.audio_player.start_playback()
            logger.info(f"Started audio output (device {output_index})")
        
        # Create and send answer
        answer = await self.pc.createAnswer()
        await self.pc.setLocalDescription(answer)
        
        await self.websocket.send(json.dumps({
            'type': 'answer',
            'room_id': self.room_id,
            'sdp': self.pc.localDescription.sdp,
            'sdp_type': self.pc.localDescription.type
        }))
        
        logger.info("Sent answer")
    
    async def handle_answer(self, message):
        """Handle incoming WebRTC answer"""
        logger.info("Received answer")
        
        answer = RTCSessionDescription(
            sdp=message['sdp'],
            type=message['sdp_type']
        )
        await self.pc.setRemoteDescription(answer)
    
    async def handle_ice_candidate(self, message):
        """Handle incoming ICE candidate"""
        if message.get('candidate'):
            candidate = RTCIceCandidate(
                component=message['component'],
                foundation=message['foundation'],
                ip=message['ip'],
                port=message['port'],
                priority=message['priority'],
                protocol=message['protocol'],
                type=message['type']
            )
            await self.pc.addIceCandidate(candidate)
    
    async def on_ice_candidate(self, candidate):
        """Handle outgoing ICE candidate"""
        if candidate:
            await self.websocket.send(json.dumps({
                'type': 'ice_candidate',
                'room_id': self.room_id,
                'candidate': candidate.candidate,
                'component': candidate.component,
                'foundation': candidate.foundation,
                'ip': candidate.ip,
                'port': candidate.port,
                'priority': candidate.priority,
                'protocol': candidate.protocol,
                'type': candidate.type
            }))
    
    def on_track(self, track):
        """Handle incoming audio track"""
        logger.info("Received remote audio track")
        
        if track.kind == "audio":
            # Start processing incoming audio
            asyncio.create_task(self.process_incoming_audio(track))
    
    async def process_incoming_audio(self, track):
        """Process incoming audio frames"""
        while True:
            try:
                frame = await track.recv()
                # Play received audio
                if self.audio_player and hasattr(frame, 'data'):
                    self.audio_player.play_audio(frame.data)
            except MediaStreamError:
                logger.info("Audio track ended")
                break
            except Exception as e:
                logger.error(f"Error processing audio: {e}")
    
    async def wait_for_offer(self):
        """Wait for incoming offer (laptop acts as answerer)"""
        logger.info("Waiting for offer from Raspberry Pi...")
        # The laptop will wait for the Raspberry Pi to send an offer
        # This is handled in handle_signaling_messages()
    
    async def run(self):
        """Main run loop"""
        try:
            # Connect to signaling server
            await self.connect_to_signaling_server()
            
            # Wait for offer and handle signaling messages
            await self.handle_signaling_messages()
            
        except Exception as e:
            logger.error(f"Error in run loop: {e}")
        finally:
            await self.cleanup()
    
    async def cleanup(self):
        """Cleanup resources"""
        logger.info("Cleaning up...")
        
        if self.audio_input:
            await self.audio_input.stop_recording()
        
        if self.audio_player:
            self.audio_player.stop_playback()
        
        if self.pc:
            await self.pc.close()
        
        if self.websocket:
            await self.websocket.close()

async def main():
    # Configuration
    signaling_server_url = "ws://192.168.8.199:8765"  # Replace with actual server IP
    
    client = LaptopAudioClient(signaling_server_url)
    
    # Handle Ctrl+C gracefully
    def signal_handler(sig, frame):
        logger.info("Received interrupt signal")
        asyncio.create_task(client.cleanup())
        sys.exit(0)
    
    signal.signal(signal.SIGINT, signal_handler)
    
    try:
        await client.run()
    except KeyboardInterrupt:
        logger.info("Application stopped by user")
    except Exception as e:
        logger.error(f"Application error: {e}")

if __name__ == "__main__":
    asyncio.run(main())