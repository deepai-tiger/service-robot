import cv2
import numpy as np
import pickle
import math
import time

class ArUcoDetector:
    def __init__(self, calibration_file="camera_calibration.pkl", 
                 dictionary_type=cv2.aruco.DICT_6X6_250, marker_size=50.0):
        """
        Initialize ArUco marker detector
        
        Args:
            calibration_file: path to camera calibration file
            dictionary_type: ArUco dictionary type
            marker_size: actual size of markers in mm
        """
        self.dictionary_type = dictionary_type
        self.marker_size = marker_size  # in mm
        
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
            
    def detect_markers(self, frame):
        """
        Detect ArUco markers in frame
        
        Args:
            frame: input image
            
        Returns:
            corners: detected marker corners
            ids: detected marker IDs
            rejected: rejected marker candidates
        """
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        corners, ids, rejected = self.detector.detectMarkers(gray)
        return corners, ids, rejected
    
    def estimate_pose(self, corners, ids):
        """
        Estimate pose of detected markers
        
        Args:
            corners: detected marker corners
            ids: detected marker IDs
            
        Returns:
            rvecs: rotation vectors
            tvecs: translation vectors
        """
        if not self.calibrated or ids is None:
            return None, None
            
        # Estimate pose for each marker
        rvecs, tvecs, _ = cv2.aruco.estimatePoseSingleMarkers(
            corners, self.marker_size, self.camera_matrix, self.dist_coeffs)
        
        return rvecs, tvecs
    
    def calculate_distance_and_orientation(self, rvec, tvec):
        """
        Calculate distance and orientation from pose vectors
        
        Args:
            rvec: rotation vector
            tvec: translation vector
            
        Returns:
            distance: distance to marker in mm
            angles: orientation angles (roll, pitch, yaw) in degrees
        """
        # Distance is the magnitude of translation vector
        distance = np.linalg.norm(tvec)
        
        # Convert rotation vector to rotation matrix
        rmat, _ = cv2.Rodrigues(rvec)
        
        # Extract Euler angles from rotation matrix
        # Using ZYX convention (yaw, pitch, roll)
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
        
        # Convert to degrees
        roll_deg = math.degrees(roll)
        pitch_deg = math.degrees(pitch)
        yaw_deg = math.degrees(yaw)
        
        return distance, (roll_deg, pitch_deg, yaw_deg)
    
    def calculate_centering_metrics(self, marker_center, frame_shape):
        """
        Calculate how centered a marker is from the frame center
        
        Args:
            marker_center: (x, y) coordinates of marker center
            frame_shape: shape of the frame (height, width, channels)
            
        Returns:
            centering_metrics: dictionary with centering information
        """
        frame_height, frame_width = frame_shape[:2]
        frame_center_x = frame_width // 2
        frame_center_y = frame_height // 2
        
        # Calculate offset from center
        offset_x = marker_center[0] - frame_center_x
        offset_y = marker_center[1] - frame_center_y
        
        # Calculate distance from center
        distance_from_center = math.sqrt(offset_x**2 + offset_y**2)
        
        # Calculate maximum possible distance (corner of frame)
        max_distance = math.sqrt(frame_center_x**2 + frame_center_y**2)
        
        # Calculate centering percentage (100% = perfectly centered, 0% = at corner)
        centering_percentage = max(0, 100 - (distance_from_center / max_distance) * 100)
        
        # Calculate horizontal and vertical centering percentages
        horizontal_centering = max(0, 100 - (abs(offset_x) / frame_center_x) * 100)
        vertical_centering = max(0, 100 - (abs(offset_y) / frame_center_y) * 100)
        
        # Determine direction from center
        direction = ""
        if abs(offset_x) > 10:  # threshold to avoid noise
            direction += "Right" if offset_x > 0 else "Left"
        if abs(offset_y) > 10:
            direction += "Bottom" if offset_y > 0 else "Top"
        if not direction:
            direction = "Centered"
        
        return {
            'offset_x': offset_x,
            'offset_y': offset_y,
            'distance_from_center': distance_from_center,
            'centering_percentage': centering_percentage,
            'horizontal_centering': horizontal_centering,
            'vertical_centering': vertical_centering,
            'direction': direction,
            'frame_center': (frame_center_x, frame_center_y)
        }
    
    def draw_centering_visualization(self, frame, marker_center, centering_metrics):
        """
        Draw centering visualization on the frame
        
        Args:
            frame: input image
            marker_center: (x, y) coordinates of marker center
            centering_metrics: centering metrics dictionary
        """
        frame_center = centering_metrics['frame_center']
        
        # Draw frame center crosshair
        cv2.line(frame, (frame_center[0] - 20, frame_center[1]), 
                (frame_center[0] + 20, frame_center[1]), (0, 255, 255), 2)
        cv2.line(frame, (frame_center[0], frame_center[1] - 20), 
                (frame_center[0], frame_center[1] + 20), (0, 255, 255), 2)
        
        # Draw line from frame center to marker center
        cv2.line(frame, frame_center, tuple(marker_center), (255, 0, 255), 2)
        
        # Draw marker center point
        cv2.circle(frame, tuple(marker_center), 5, (0, 0, 255), -1)
        
        # Draw centering grid (optional - for better visual reference)
        height, width = frame.shape[:2]
        # Vertical lines
        for i in range(1, 3):
            x = width * i // 3
            cv2.line(frame, (x, 0), (x, height), (100, 100, 100), 1)
        # Horizontal lines
        for i in range(1, 3):
            y = height * i // 3
            cv2.line(frame, (0, y), (width, y), (100, 100, 100), 1)
    
    def draw_markers_and_pose(self, frame, corners, ids, rvecs, tvecs):
        """
        Draw detected markers and their pose on the frame
        
        Args:
            frame: input image
            corners: detected marker corners
            ids: detected marker IDs
            rvecs: rotation vectors
            tvecs: translation vectors
            
        Returns:
            frame: image with drawn markers and pose information
        """
        if ids is not None:
            # Draw detected markers
            cv2.aruco.drawDetectedMarkers(frame, corners, ids)
            
            if self.calibrated and rvecs is not None and tvecs is not None:
                # Draw pose axes for each marker
                for i in range(len(ids)):
                    cv2.drawFrameAxes(frame, self.camera_matrix, self.dist_coeffs,
                                    rvecs[i], tvecs[i], self.marker_size * 0.5)
                    
                    # Calculate distance and orientation
                    distance, angles = self.calculate_distance_and_orientation(rvecs[i], tvecs[i])
                    roll, pitch, yaw = angles
                    
                    # Get marker center for text placement
                    marker_center = np.mean(corners[i][0], axis=0).astype(int)
                    
                    # Calculate centering metrics
                    centering_metrics = self.calculate_centering_metrics(marker_center, frame.shape)
                    
                    # Draw centering visualization
                    self.draw_centering_visualization(frame, marker_center, centering_metrics)
                    
                    # Draw marker information
                    info_text = [
                        f"ID: {ids[i][0]}",
                        f"Dist: {distance:.1f}mm",
                        f"Roll: {roll:.1f}°",
                        f"Pitch: {pitch:.1f}°",
                        f"Yaw: {yaw:.1f}°",
                        f"Centered: {centering_metrics['centering_percentage']:.1f}%",
                        f"H-Center: {centering_metrics['horizontal_centering']:.1f}%",
                        f"V-Center: {centering_metrics['vertical_centering']:.1f}%",
                        f"Direction: {centering_metrics['direction']}"
                    ]
                    
                    # Draw text with background
                    y_offset = 0
                    for text in info_text:
                        text_size = cv2.getTextSize(text, cv2.FONT_HERSHEY_SIMPLEX, 0.45, 1)[0]
                        text_x = marker_center[0] - text_size[0] // 2
                        text_y = marker_center[1] - 100 + y_offset
                        
                        # Ensure text stays within frame bounds
                        text_x = max(5, min(text_x, frame.shape[1] - text_size[0] - 5))
                        text_y = max(15, min(text_y, frame.shape[0] - 5))
                        
                        # Draw background rectangle
                        cv2.rectangle(frame, (text_x - 3, text_y - 12), 
                                    (text_x + text_size[0] + 3, text_y + 3), 
                                    (0, 0, 0), -1)
                        
                        # Draw text
                        cv2.putText(frame, text, (text_x, text_y), 
                                  cv2.FONT_HERSHEY_SIMPLEX, 0.45, (0, 255, 0), 1)
                        
                        y_offset += 16
                    
                    # Print to console with centering info
                    print(f"Marker ID {ids[i][0]}: Distance={distance:.1f}mm, "
                          f"Roll={roll:.1f}°, Pitch={pitch:.1f}°, Yaw={yaw:.1f}°, "
                          f"Centering={centering_metrics['centering_percentage']:.1f}%, "
                          f"Direction={centering_metrics['direction']}")
            else:
                # If not calibrated, still show centering info
                for i in range(len(ids)):
                    marker_center = np.mean(corners[i][0], axis=0).astype(int)
                    centering_metrics = self.calculate_centering_metrics(marker_center, frame.shape)
                    
                    # Draw centering visualization
                    self.draw_centering_visualization(frame, marker_center, centering_metrics)
                    
                    # Draw basic info
                    info_text = [
                        f"ID: {ids[i][0]}",
                        f"Centered: {centering_metrics['centering_percentage']:.1f}%",
                        f"H-Center: {centering_metrics['horizontal_centering']:.1f}%",
                        f"V-Center: {centering_metrics['vertical_centering']:.1f}%",
                        f"Direction: {centering_metrics['direction']}"
                    ]
                    
                    y_offset = 0
                    for text in info_text:
                        text_size = cv2.getTextSize(text, cv2.FONT_HERSHEY_SIMPLEX, 0.45, 1)[0]
                        text_x = marker_center[0] - text_size[0] // 2
                        text_y = marker_center[1] - 60 + y_offset
                        
                        # Ensure text stays within frame bounds
                        text_x = max(5, min(text_x, frame.shape[1] - text_size[0] - 5))
                        text_y = max(15, min(text_y, frame.shape[0] - 5))
                        
                        # Draw background rectangle
                        cv2.rectangle(frame, (text_x - 3, text_y - 12), 
                                    (text_x + text_size[0] + 3, text_y + 3), 
                                    (0, 0, 0), -1)
                        
                        # Draw text
                        cv2.putText(frame, text, (text_x, text_y), 
                                  cv2.FONT_HERSHEY_SIMPLEX, 0.45, (0, 255, 0), 1)
                        
                        y_offset += 16
                    
                    print(f"Marker ID {ids[i][0]}: Centering={centering_metrics['centering_percentage']:.1f}%, "
                          f"Direction={centering_metrics['direction']}")
        
        return frame

def main():
    """Main function to run ArUco marker detection"""
    # Initialize detector
    detector = ArUcoDetector(
        calibration_file="camera_calibration.pkl",
        dictionary_type=cv2.aruco.DICT_6X6_250,
        marker_size=50.0  # Adjust this to your actual marker size in mm
    )
    
    # Initialize camera
    cap = cv2.VideoCapture(0)
    
    if not cap.isOpened():
        print("Error: Could not open camera")
        return
    
    # Set camera resolution
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)
    
    print("ArUco Marker Detection Started")
    print("Instructions:")
    print("- Point camera at ArUco markers")
    print("- Distance, orientation, and centering will be displayed")
    print("- Yellow crosshair shows frame center")
    print("- Purple line shows distance from center to marker")
    print("- Press 'q' to quit")
    print("- Press 's' to save current frame")
    
    frame_count = 0
    
    while True:
        ret, frame = cap.read()
        if not ret:
            print("Error: Could not read frame")
            break
        
        # Detect markers
        corners, ids, rejected = detector.detect_markers(frame)
        
        # Estimate pose if markers detected
        rvecs, tvecs = detector.estimate_pose(corners, ids)
        
        # Draw markers and pose information
        frame = detector.draw_markers_and_pose(frame, corners, ids, rvecs, tvecs)
        
        # Add frame information
        cv2.putText(frame, f"Frame: {frame_count}", (10, 30), 
                   cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)
        
        if ids is not None:
            cv2.putText(frame, f"Markers detected: {len(ids)}", (10, 60), 
                       cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
        else:
            cv2.putText(frame, "No markers detected", (10, 60), 
                       cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255), 2)
        
        # Display calibration status
        calib_status = "Calibrated" if detector.calibrated else "Not Calibrated"
        cv2.putText(frame, f"Status: {calib_status}", (10, 90), 
                   cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 0), 2)
        
        cv2.putText(frame, "Press 'q' to quit, 's' to save frame", 
                   (10, frame.shape[0] - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)
        
        # Display frame
        cv2.imshow('ArUco Marker Detection', frame)
        
        key = cv2.waitKey(1) & 0xFF
        
        if key == ord('q'):
            break
        elif key == ord('s'):
            # Save current frame
            filename = f"aruco_detection_{int(time.time())}.jpg"
            cv2.imwrite(filename, frame)
            print(f"Frame saved as: {filename}")
        
        frame_count += 1
    
    cap.release()
    cv2.destroyAllWindows()
    print("ArUco detection stopped")

def detect_from_image(image_path, detector=None):
    """
    Detect ArUco markers from a single image
    
    Args:
        image_path: path to input image
        detector: ArUcoDetector instance (optional)
    """
    if detector is None:
        detector = ArUcoDetector()
    
    # Load image
    frame = cv2.imread(image_path)
    if frame is None:
        print(f"Could not load image: {image_path}")
        return
    
    # Detect markers
    corners, ids, rejected = detector.detect_markers(frame)
    
    # Estimate pose
    rvecs, tvecs = detector.estimate_pose(corners, ids)
    
    # Draw results
    result_frame = detector.draw_markers_and_pose(frame, corners, ids, rvecs, tvecs)
    
    # Display results
    cv2.imshow('ArUco Detection - Static Image', result_frame)
    cv2.waitKey(0)
    cv2.destroyAllWindows()
    
    # Save result
    output_path = image_path.replace('.', '_detected.')
    cv2.imwrite(output_path, result_frame)
    print(f"Detection result saved as: {output_path}")

if __name__ == "__main__":
    # Run real-time detection
    main()
    
    # Uncomment to test with a static image
    # detect_from_image("test_image.jpg")