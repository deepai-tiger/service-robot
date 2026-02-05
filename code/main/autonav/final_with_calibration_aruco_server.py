import asyncio
import websockets
import json
import cv2
import numpy as np
import base64
import pickle
import math
import time
import os
import threading
from io import BytesIO
from PIL import Image

class ArUcoWebSocketServer:
    def __init__(self, calibration_file="camera_calibration.pkl",
                 dictionary_type=cv2.aruco.DICT_6X6_250, marker_size=50.0,
                 calibration_mode=False, board_size=(9, 6), num_calibration_images=20):
        """
        Initialize ArUco WebSocket server

        Args:
            calibration_file: path to camera calibration file
            dictionary_type: ArUco dictionary type
            marker_size: actual size of markers in mm
            calibration_mode: if True, server will capture calibration images
            board_size: tuple (width, height) - number of internal corners for chessboard
            num_calibration_images: number of calibration images to capture
        """
        self.dictionary_type = dictionary_type
        self.marker_size = marker_size
        self.connected_clients = set()
        
        # Calibration mode settings
        self.calibration_mode = calibration_mode
        self.board_size = board_size
        self.num_calibration_images = num_calibration_images
        self.calibration_output_dir = "calibration_images"
        self.captured_count = 0
        
        if self.calibration_mode:
            print("=" * 60)
            print("CALIBRATION MODE ENABLED")
            print("=" * 60)
            print("The server will capture calibration images instead of detecting ArUco markers.")
            print(f"Target: {self.num_calibration_images} images")
            print(f"Board size: {self.board_size[0]}x{self.board_size[1]} internal corners")
            print(f"Output directory: {self.calibration_output_dir}")
            print("Instructions:")
            print("- Connect from the web interface and start video call")
            print("- Start ArUco detection to begin receiving frames")
            print("- Hold chessboard in front of camera")
            print("- Press ENTER in this console when chessboard is detected to capture")
            print("- Repeat until all images are captured")
            print("=" * 60)
            
            # Create calibration output directory
            if not os.path.exists(self.calibration_output_dir):
                os.makedirs(self.calibration_output_dir)
                print(f"Created directory: {self.calibration_output_dir}")
            
            # Start input thread for calibration
            self.current_frame = None
            self.frame_lock = threading.Lock()
            self.input_thread = threading.Thread(target=self._calibration_input_handler, daemon=True)
            self.input_thread.start()
            
        else:
            # Regular ArUco detection mode
            # Load camera calibration
            self.load_calibration(calibration_file)

            # Create ArUco dictionary and detector parameters
            self.aruco_dict = cv2.aruco.getPredefinedDictionary(dictionary_type)
            self.detector_params = cv2.aruco.DetectorParameters()

            # Optimize detector parameters for better detection
            self.detector_params.adaptiveThreshWinSizeMin = 3
            self.detector_params.adaptiveThreshWinSizeMax = 23
            self.detector_params.adaptiveThreshWinSizeStep = 10
            self.detector_params.adaptiveThreshConstant = 7
            self.detector_params.minMarkerPerimeterRate = 0.03
            self.detector_params.maxMarkerPerimeterRate = 4.0
            self.detector_params.polygonalApproxAccuracyRate = 0.03
            self.detector_params.minCornerDistanceRate = 0.05
            self.detector_params.minDistanceToBorder = 3
            self.detector_params.minMarkerDistanceRate = 0.05

            # Create detector
            self.detector = cv2.aruco.ArucoDetector(self.aruco_dict, self.detector_params)

        # Statistics
        self.frame_count = 0
        self.detection_count = 0
        self.start_time = time.time()

        if not self.calibration_mode:
            print("ArUco WebSocket Server initialized")
            print(f"Dictionary: {dictionary_type}")
            print(f"Marker size: {marker_size}mm")
            print(f"Calibrated: {self.calibrated}")

    def _calibration_input_handler(self):
        """Handle console input for calibration mode"""
        while self.captured_count < self.num_calibration_images:
            try:
                input()  # Wait for Enter key
                with self.frame_lock:
                    if self.current_frame is not None:
                        self._capture_calibration_image(self.current_frame)
            except KeyboardInterrupt:
                break
            except EOFError:
                break

    def _capture_calibration_image(self, frame):
        """Capture a calibration image if chessboard is detected"""
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        
        # Find chessboard corners
        ret_corners, corners = cv2.findChessboardCorners(gray, self.board_size, None)
        
        if ret_corners:
            # Refine corners
            corners_refined = cv2.cornerSubPix(gray, corners, (11, 11), (-1, -1), 
                                             (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 30, 0.001))
            
            # Save the image
            filename = os.path.join(self.calibration_output_dir, f"calibration_{self.captured_count:02d}.jpg")
            cv2.imwrite(filename, frame)
            self.captured_count += 1
            
            print(f"✓ Captured image {self.captured_count}/{self.num_calibration_images}: {filename}")
            
            if self.captured_count >= self.num_calibration_images:
                print("=" * 60)
                print("CALIBRATION IMAGE CAPTURE COMPLETE!")
                print(f"Successfully captured {self.captured_count} calibration images!")
                print(f"Images saved in: {self.calibration_output_dir}")
                print("You can now run your calibration script to generate camera_calibration.pkl")
                print("=" * 60)
        else:
            print(f"⚠ No chessboard detected in frame. Please adjust position and try again.")
            print(f"   Progress: {self.captured_count}/{self.num_calibration_images}")

    def load_calibration(self, calibration_file):
        """Load camera calibration parameters"""
        try:
            with open(calibration_file, 'rb') as f:
                calibration_data = pickle.load(f)

            self.camera_matrix = calibration_data['camera_matrix']
            self.dist_coeffs = calibration_data['dist_coeffs']
            self.calibrated = True
            print(f"Camera calibration loaded from: {calibration_file}")

        except FileNotFoundError:
            print(f"Calibration file not found: {calibration_file}")
            print("Running without calibration - distance measurements will be inaccurate")
            self.camera_matrix = None
            self.dist_coeffs = None
            self.calibrated = False

    def base64_to_image(self, base64_string):
        """Convert base64 string to OpenCV image"""
        try:
            # Remove data URL prefix if present
            if base64_string.startswith('data:image'):
                base64_string = base64_string.split(',')[1]

            # Decode base64
            image_data = base64.b64decode(base64_string)

            # Convert to PIL Image
            pil_image = Image.open(BytesIO(image_data))

            # Convert to OpenCV format
            opencv_image = cv2.cvtColor(np.array(pil_image), cv2.COLOR_RGB2BGR)

            return opencv_image

        except Exception as e:
            print(f"Error converting base64 to image: {e}")
            return None

    def detect_markers(self, frame):
        """Detect ArUco markers in frame"""
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        corners, ids, rejected = self.detector.detectMarkers(gray)
        return corners, ids, rejected

    def estimate_pose(self, corners, ids):
        """Estimate pose of detected markers"""
        if not self.calibrated or ids is None:
            return None, None

        rvecs, tvecs, _ = cv2.aruco.estimatePoseSingleMarkers(
            corners, self.marker_size, self.camera_matrix, self.dist_coeffs)

        return rvecs, tvecs

    def calculate_distance_and_orientation(self, rvec, tvec):
        """Calculate distance and orientation from pose vectors"""
        distance = np.linalg.norm(tvec)

        rmat, _ = cv2.Rodrigues(rvec)

        sy = math.sqrt(rmat[0, 0] * rmat[0, 0] + rmat[1, 0] * rmat[1, 0])

        singular = sy < 1e-6

        if not singular:
            roll = math.atan2(rmat[2, 1], rmat[2, 2])
            pitch = math.atan2(-rmat[2, 0], sy)
            yaw = math.atan2(rmat[1, 0], rmat[0, 0])
        else:
            roll = math.atan2(-rmat[1, 2], rmat[1, 1])
            pitch = math.atan2(-rmat[2, 0], sy)
            yaw = 0

        roll_deg = math.degrees(roll)
        pitch_deg = math.degrees(pitch)
        yaw_deg = math.degrees(yaw)

        return distance, (roll_deg, pitch_deg, yaw_deg)

    def calculate_centering_metrics(self, marker_center, frame_shape):
        """Calculate how centered a marker is horizontally from the frame center"""
        frame_height, frame_width = frame_shape[:2]
        frame_center_x = frame_width // 2

        offset_x = marker_center[0] - frame_center_x
        max_horizontal_distance = frame_center_x

        horizontal_centering_percentage = max(0, 100 - (abs(offset_x) / max_horizontal_distance) * 100)

        direction = ""
        if abs(offset_x) > 20: # A small threshold to consider it "centered"
            direction += "Right" if offset_x > 0 else "Left"
        if not direction:
            direction = "Centered" # Changed from "Horizontally Centered" to match navigate_robot logic

        return {
            'offset_x': int(offset_x),
            'horizontal_centering_percentage': float(horizontal_centering_percentage),
            'direction': direction,
            'frame_center_x': int(frame_center_x)
        }

    def navigate_robot(self, marker_data):
        """
        Generates robot navigation commands based on marker data.
        marker_data should contain 'direction', 'distance_mm', and 'pitch_deg'.
        """
        direction = marker_data.get('direction')
        distance = marker_data.get('distance_mm')
        pitch = marker_data.get('pitch_deg')

        commands = []

        if direction is None or distance is None or pitch is None:
            # Cannot navigate without complete data
            return ["WAIT"] # Or an appropriate default command

        # Step 1: Tilt Correction (only if abs(pitch) > 30 and distance > 500)
        if abs(pitch) > 40:
            if distance <= 500:
                commands.append("ArrowDown")  # Move back to gain space
                return commands

            if pitch > 0: # Tilted forward/up (marker is below center, or angled down)
                commands.append("ArrowLeft")     # Rotate right to correct tilt (assuming robot rotates right for ArrowLeft input to level)
                commands.append("ArrowLeft")
                commands.append("ArrowLeft")
                commands.append("ArrowUp")       # Move a bit forward
                commands.append("ArrowUp")       # Move a bit forward
                commands.append("ArrowRight")    # Rotate back to original orientation
                commands.append("ArrowRight") 
                commands.append("ArrowRight") 
            else: # Tilted backward/down (marker is above center, or angled up)
                commands.append("ArrowRight")    # Rotate left to correct tilt
                commands.append("ArrowRight")
                commands.append("ArrowRight")
                commands.append("ArrowUp")       # Move a bit forward
                commands.append("ArrowUp") 
                commands.append("ArrowLeft")     # Rotate back to original orientation
                commands.append("ArrowLeft")
                commands.append("ArrowLeft")

            return commands  # Don't proceed to next step this round

        # Step 2: Horizontal Centering
        if direction == "Left":
            commands.append("ArrowLeft")  # Rotate left ~20°
        elif direction == "Right":
            commands.append("ArrowRight")  # Rotate right ~20°

        # Step 3: Move closer
        elif direction == "Centered":
            if distance > 300:
                commands.append("ArrowUp")
            else:
                # Marker is centered and close enough
                commands.append("STOP")  # Or no-op
        return commands

    def process_frame_calibration(self, frame):
        """Process frame for calibration mode"""
        # Store current frame for calibration capture
        with self.frame_lock:
            self.current_frame = frame.copy()
        
        # Check if chessboard is detected for display purposes
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        ret_corners, corners = cv2.findChessboardCorners(gray, self.board_size, None)
        
        # Create response for calibration mode
        if ret_corners:
            status_message = f"Chessboard detected! Press ENTER in console to capture ({self.captured_count}/{self.num_calibration_images})"
            detection_status = "detected"
        else:
            status_message = f"No chessboard detected. Adjust position ({self.captured_count}/{self.num_calibration_images})"
            detection_status = "not_detected"
        
        return {
            'calibration_mode': True,
            'status': status_message,
            'detection_status': detection_status,
            'captured_count': self.captured_count,
            'total_needed': self.num_calibration_images,
            'board_size': self.board_size,
            'completed': self.captured_count >= self.num_calibration_images
        }

    def process_frame(self, frame):
        """Process a frame and detect ArUco markers (regular mode)"""
        print("Processing frame for ArUco markers...")
        self.frame_count += 1

        # Detect markers
        corners, ids, rejected = self.detect_markers(frame)

        detection_results = []

        if ids is not None:
            self.detection_count += 1

            # Estimate pose
            rvecs, tvecs = self.estimate_pose(corners, ids)

            for i in range(len(ids)):
                marker_center = np.mean(corners[i][0], axis=0).astype(int)
                centering_metrics = self.calculate_centering_metrics(marker_center, frame.shape)

                marker_result = {
                    'id': int(ids[i][0]),
                    'center_x': int(marker_center[0]),
                    'horizontal_centering_percentage': centering_metrics['horizontal_centering_percentage'],
                    'direction': centering_metrics['direction'],
                    'offset_x': centering_metrics['offset_x'],
                    'commands': [] # Initialize commands list
                }

                if self.calibrated and rvecs is not None and tvecs is not None:
                    distance, angles = self.calculate_distance_and_orientation(rvecs[i], tvecs[i])
                    _, pitch, _ = angles

                    marker_result.update({
                        'distance_mm': float(distance),
                        'pitch_deg': float(pitch)
                    })

                    # Generate navigation commands using the new function
                    # Ensure the data passed to navigate_robot matches its expected structure
                    nav_data = {
                        'direction': marker_result['direction'],
                        'distance_mm': marker_result['distance_mm'],
                        'pitch_deg': marker_result['pitch_deg']
                    }
                    marker_result['commands'] = self.navigate_robot(nav_data)
                else:
                    # If not calibrated, or pose estimation failed, provide default commands
                    marker_result['commands'] = ["CALIBRATION_NEEDED"]

                detection_results.append(marker_result)

                # Print to console (simplified)
                if self.calibrated and rvecs is not None:
                    print(f"Marker ID {ids[i][0]}: Distance={marker_result['distance_mm']:.1f}mm, "
                          f"Pitch={marker_result['pitch_deg']:.1f}°, "
                          f"Horizontal Centering={marker_result['horizontal_centering_percentage']:.1f}%, "
                          f"Direction={marker_result['direction']}, "
                          f"Commands={marker_result['commands']}")
                else:
                    print(f"Marker ID {ids[i][0]}: Horizontal Centering={marker_result['horizontal_centering_percentage']:.1f}%, "
                          f"Direction={marker_result['direction']}, "
                          f"Commands={marker_result['commands']}")

        return detection_results

    def get_statistics(self):
        """Get processing statistics"""
        elapsed_time = time.time() - self.start_time
        fps = self.frame_count / elapsed_time if elapsed_time > 0 else 0
        detection_rate = (self.detection_count / self.frame_count * 100) if self.frame_count > 0 else 0

        return {
            'frames_processed': int(self.frame_count),
            'detections': int(self.detection_count),
            'fps': float(fps),
            'detection_rate': float(detection_rate),
            'elapsed_time': float(elapsed_time)
        }

    async def handle_client(self, websocket):
        """Handle WebSocket client connection"""
        self.connected_clients.add(websocket)
        client_addr = websocket.remote_address

        try:
            # Send connection confirmation
            await websocket.send(json.dumps({
                'type': 'status',
                'message': 'Connected to ArUco detection server',
                'calibration_mode': self.calibration_mode
            }))

            async for message in websocket:
                try:
                    data = json.loads(message)

                    if data['type'] == 'frame':
                        # Process frame
                        frame = self.base64_to_image(data['data'])

                        if frame is not None:
                            if self.calibration_mode:
                                # Calibration mode processing
                                calibration_result = self.process_frame_calibration(frame)
                                
                                response = {
                                    'type': 'calibration_result',
                                    'calibration_data': calibration_result
                                }
                            else:
                                # Regular ArUco detection processing
                                detection_results = self.process_frame(frame)

                                response = {
                                    'type': 'detection_result',
                                    'markers_count': len(detection_results),
                                    'markers': detection_results,
                                    'statistics': self.get_statistics()
                                }

                            await websocket.send(json.dumps(response))
                        else:
                            await websocket.send(json.dumps({
                                'type': 'error',
                                'message': 'Failed to process frame'
                            }))

                    elif data['type'] == 'get_stats':
                        # Send statistics
                        await websocket.send(json.dumps({
                            'type': 'statistics',
                            'data': self.get_statistics()
                        }))

                except json.JSONDecodeError:
                    await websocket.send(json.dumps({
                        'type': 'error',
                        'message': 'Invalid JSON message'
                    }))

                except Exception as e:
                    print(f"Error processing message: {e}")
                    await websocket.send(json.dumps({
                        'type': 'error',
                        'message': str(e)
                    }))

        except websockets.exceptions.ConnectionClosed:
            print(f"Client disconnected: {client_addr}")

        except Exception as e:
            print(f"Error handling client {client_addr}: {e}")

        finally:
            self.connected_clients.discard(websocket)

    async def start_server(self, host='localhost', port=8765):
        """Start the WebSocket server"""
        mode_str = "CALIBRATION" if self.calibration_mode else "DETECTION"
        print(f"Starting ArUco WebSocket server ({mode_str} MODE) on {host}:{port}")

        async with websockets.serve(self.handle_client, host, port):
            print("Server started. Waiting for connections...")
            if not self.calibration_mode:
                print("Press Ctrl+C to stop the server")
            
            try:
                await asyncio.Future()  # Run forever
            except KeyboardInterrupt:
                print("\nServer stopped by user")

def main():
    """Main function to run the ArUco WebSocket server"""
    
    # CONFIGURATION: Set calibration_mode to True to capture calibration images
    CALIBRATION_MODE = False  # Change this to True for calibration mode
    
    if CALIBRATION_MODE:
        # Calibration mode settings
        server = ArUcoWebSocketServer(
            calibration_mode=True,
            board_size=(9, 6),  # Chessboard internal corners (width, height)
            num_calibration_images=20  # Number of calibration images to capture
        )
    else:
        # Regular detection mode settings
        server = ArUcoWebSocketServer(
            calibration_file="camera_calibration.pkl",
            dictionary_type=cv2.aruco.DICT_6X6_250,
            marker_size=50.0,  # Adjust this to your actual marker size in mm
            calibration_mode=False
        )

    # Start the server
    asyncio.run(server.start_server())

if __name__ == "__main__":
    main()