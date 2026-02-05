import cv2
import numpy as np
import os
import time

def capture_calibration_images(board_size=(9, 6), num_images=20, output_dir="calibration_images"):
    """
    Capture calibration images using webcam
    
    Args:
        board_size: tuple (width, height) - number of internal corners
        num_images: number of calibration images to capture
        output_dir: directory to save calibration images
    """
    # Create output directory
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)
    
    # Initialize camera
    cap = cv2.VideoCapture(0)
    
    if not cap.isOpened():
        print("Error: Could not open camera")
        return
    
    # Set camera resolution (optional)
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)
    
    # Prepare object points
    objp = np.zeros((board_size[0] * board_size[1], 3), np.float32)
    objp[:, :2] = np.mgrid[0:board_size[0], 0:board_size[1]].T.reshape(-1, 2)
    
    captured_count = 0
    
    print(f"Capturing {num_images} calibration images...")
    print("Instructions:")
    print("- Hold the chessboard in front of the camera")
    print("- Move it to different positions and angles")
    print("- Press SPACE when the chessboard is detected (green corners)")
    print("- Press 'q' to quit")
    
    while captured_count < num_images:
        ret, frame = cap.read()
        if not ret:
            print("Error: Could not read frame")
            break
        
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        
        # Find chessboard corners
        ret_corners, corners = cv2.findChessboardCorners(gray, board_size, None)
        
        # Display frame
        display_frame = frame.copy()
        
        if ret_corners:
            # Refine corners
            corners_refined = cv2.cornerSubPix(gray, corners, (11, 11), (-1, -1), 
                                             (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 30, 0.001))
            
            # Draw corners
            cv2.drawChessboardCorners(display_frame, board_size, corners_refined, ret_corners)
            
            # Add text
            cv2.putText(display_frame, f"Chessboard detected! Press SPACE to capture ({captured_count}/{num_images})", 
                       (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
        else:
            cv2.putText(display_frame, f"No chessboard detected ({captured_count}/{num_images})", 
                       (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255), 2)
        
        cv2.putText(display_frame, "Press SPACE to capture, 'q' to quit", 
                   (10, display_frame.shape[0] - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)
        
        cv2.imshow('Calibration Image Capture', display_frame)
        
        key = cv2.waitKey(1) & 0xFF
        
        if key == ord(' ') and ret_corners:
            # Save the image
            filename = os.path.join(output_dir, f"calibration_{captured_count:02d}.jpg")
            cv2.imwrite(filename, frame)
            captured_count += 1
            print(f"Captured image {captured_count}/{num_images}: {filename}")
            
            # Brief pause to avoid multiple captures
            time.sleep(0.5)
            
        elif key == ord('q'):
            print("Capture cancelled by user")
            break
    
    cap.release()
    cv2.destroyAllWindows()
    
    if captured_count >= num_images:
        print(f"Successfully captured {captured_count} calibration images!")
        print(f"Images saved in: {output_dir}")
    else:
        print(f"Only captured {captured_count}/{num_images} images")

if __name__ == "__main__":
    # Capture calibration images
    capture_calibration_images(board_size=(9, 6), num_images=20, output_dir="calibration_images")