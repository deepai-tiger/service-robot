import cv2
import numpy as np
import pickle
import math
import time

class ArUcoDetectorRPi:
    def __init__(self, calibration_file="camera_calibration.pkl", 
                 dictionary_type=cv2.aruco.DICT_6X6_250, marker_size=50.0):
        """
        Raspberry Pi optimized ArUco marker detector
        """
        self.dictionary_type = dictionary_type
        self.marker_size = marker_size
        
        # Load camera calibration
        self.load_calibration(calibration_file)
        
        # Create ArUco dictionary and detector parameters
        self.aruco_dict = cv2.aruco.getPredefinedDictionary(dictionary_type)
        self.detector_params = cv2.aruco.DetectorParameters()
        
        # Optimized detector parameters for RPi
        self.detector_params.adaptiveThreshWinSizeMin = 5
        self.detector_params.adaptiveThreshWinSizeMax = 15
        self.detector_params.adaptiveThreshWinSizeStep = 5
        self.detector_params.minMarkerPerimeterRate = 0.05
        self.detector_params.maxMarkerPerimeterRate = 2.0
        
        # Create detector
        self.detector = cv2.aruco.ArucoDetector(self.aruco_dict, self.detector_params)
        
        # Performance optimization flags
        self.show_detailed_info = False  # Toggle for detailed display
        self.show_grid = False  # Toggle for grid display
        self.frame_skip = 2  # Process every nth frame
        self.frame_count = 0
        
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
            print("Running without calibration")
            self.camera_matrix = None
            self.dist_coeffs = None
            self.calibrated = False
            
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
        
        # Simplified orientation calculation
        rmat, _ = cv2.Rodrigues(rvec)
        
        # Quick yaw calculation (most important for tracking)
        yaw = math.atan2(rmat[1, 0], rmat[0, 0])
        yaw_deg = math.degrees(yaw)
        
        return distance, yaw_deg
    
    def calculate_centering_metrics(self, marker_center, frame_shape):
        """
        Simplified centering calculation for RPi
        """
        frame_height, frame_width = frame_shape[:2]
        frame_center_x = frame_width >> 1  # Bit shift for faster division
        frame_center_y = frame_height >> 1
        
        # Calculate offset from center
        offset_x = marker_center[0] - frame_center_x
        offset_y = marker_center[1] - frame_center_y
        
        # Quick centering percentage using Manhattan distance (faster than Euclidean)
        max_offset = max(frame_center_x, frame_center_y)
        current_offset = max(abs(offset_x), abs(offset_y))
        centering_percentage = max(0, 100 - (current_offset * 100 // max_offset))
        
        # Simple direction
        direction = ""
        if abs(offset_x) > 20:
            direction += "R" if offset_x > 0 else "L"
        if abs(offset_y) > 20:
            direction += "D" if offset_y > 0 else "U"
        if not direction:
            direction = "C"
        
        return {
            'centering_percentage': centering_percentage,
            'direction': direction,
            'frame_center': (frame_center_x, frame_center_y)
        }
    
    def draw_minimal_visualization(self, frame, marker_center, centering_metrics):
        """Minimal visualization for RPi"""
        frame_center = centering_metrics['frame_center']
        
        # Only draw center crosshair (most important)
        cv2.line(frame, (frame_center[0] - 10, frame_center[1]), 
                (frame_center[0] + 10, frame_center[1]), (0, 255, 255), 1)
        cv2.line(frame, (frame_center[0], frame_center[1] - 10), 
                (frame_center[0], frame_center[1] + 10), (0, 255, 255), 1)
        
        # Draw line to marker (thinner line)
        cv2.line(frame, frame_center, tuple(marker_center), (255, 0, 255), 1)
        
        # Small marker center dot
        cv2.circle(frame, tuple(marker_center), 3, (0, 0, 255), -1)
    
    def draw_markers_and_pose(self, frame, corners, ids, rvecs, tvecs):
        """
        Optimized drawing for RPi
        """
        if ids is not None:
            # Draw detected markers (simplified)
            cv2.aruco.drawDetectedMarkers(frame, corners, ids)
            
            for i in range(len(ids)):
                marker_center = np.mean(corners[i][0], axis=0).astype(int)
                centering_metrics = self.calculate_centering_metrics(marker_center, frame.shape)
                
                # Draw minimal visualization
                self.draw_minimal_visualization(frame, marker_center, centering_metrics)
                
                # Minimal text info
                if self.calibrated and rvecs is not None and tvecs is not None:
                    distance, yaw = self.calculate_distance_and_orientation(rvecs[i], tvecs[i])
                    info_text = f"ID:{ids[i][0]} D:{distance:.0f}mm C:{centering_metrics['centering_percentage']:.0f}% {centering_metrics['direction']}"
                else:
                    info_text = f"ID:{ids[i][0]} C:{centering_metrics['centering_percentage']:.0f}% {centering_metrics['direction']}"
                
                # Single line of text
                text_size = cv2.getTextSize(info_text, cv2.FONT_HERSHEY_SIMPLEX, 0.4, 1)[0]
                text_x = max(5, marker_center[0] - text_size[0] // 2)
                text_y = max(20, marker_center[1] - 20)
                
                # Simple text without background rectangle
                cv2.putText(frame, info_text, (text_x, text_y), 
                          cv2.FONT_HERSHEY_SIMPLEX, 0.4, (0, 255, 0), 1)
                
                # Simplified console output
                if self.calibrated and rvecs is not None and tvecs is not None:
                    print(f"ID {ids[i][0]}: Dist={distance:.0f}mm, Yaw={yaw:.0f}°, Center={centering_metrics['centering_percentage']:.0f}%")
                else:
                    print(f"ID {ids[i][0]}: Center={centering_metrics['centering_percentage']:.0f}%")
        
        return frame

def main():
    """Optimized main function for RPi"""
    detector = ArUcoDetectorRPi(
        calibration_file="camera_calibration.pkl",
        dictionary_type=cv2.aruco.DICT_6X6_250,
        marker_size=50.0
    )
    
    # Initialize camera with lower resolution
    cap = cv2.VideoCapture(0)
    
    if not cap.isOpened():
        print("Error: Could not open camera")
        return
    
    # RPi optimized camera settings
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)   # Reduced resolution
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
    cap.set(cv2.CAP_PROP_FPS, 15)            # Lower FPS
    cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)      # Reduce buffer
    
    print("RPi ArUco Detection Started")
    print("Lower resolution and FPS for better performance")
    print("Press 'q' to quit, 's' to save frame")
    print("Press 'd' to toggle detailed info")
    
    frame_count = 0
    fps_start_time = time.time()
    fps_frame_count = 0
    
    while True:
        ret, frame = cap.read()
        if not ret:
            print("Error: Could not read frame")
            break
        
        # Frame skipping for performance
        if frame_count % detector.frame_skip != 0:
            frame_count += 1
            continue
        
        # Detect markers
        corners, ids, rejected = detector.detect_markers(frame)
        
        # Estimate pose if markers detected
        rvecs, tvecs = detector.estimate_pose(corners, ids)
        
        # Draw markers and pose information
        frame = detector.draw_markers_and_pose(frame, corners, ids, rvecs, tvecs)
        
        # Calculate and display FPS
        fps_frame_count += 1
        if fps_frame_count % 30 == 0:  # Update FPS every 30 frames
            fps_end_time = time.time()
            fps = 30 / (fps_end_time - fps_start_time)
            fps_start_time = fps_end_time
            
        # Minimal status display
        cv2.putText(frame, f"FPS: {fps:.1f}", (10, 25), 
                   cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)
        
        if ids is not None:
            cv2.putText(frame, f"Markers: {len(ids)}", (10, 45), 
                       cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 1)
        
        # Display frame
        cv2.imshow('RPi ArUco Detection', frame)
        
        key = cv2.waitKey(1) & 0xFF
        
        if key == ord('q'):
            break
        elif key == ord('s'):
            filename = f"rpi_aruco_{int(time.time())}.jpg"
            cv2.imwrite(filename, frame)
            print(f"Frame saved as: {filename}")
        elif key == ord('d'):
            detector.show_detailed_info = not detector.show_detailed_info
            print(f"Detailed info: {detector.show_detailed_info}")
        
        frame_count += 1
    
    cap.release()
    cv2.destroyAllWindows()
    print("RPi ArUco detection stopped")

if __name__ == "__main__":
    main()