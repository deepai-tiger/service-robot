import cv2
import numpy as np
import os
import glob
import pickle

def calibrate_camera(images_dir="calibration_images", board_size=(9, 6), square_size=1.0, 
                    output_file="camera_calibration.pkl"):
    """
    Perform camera calibration using captured images
    
    Args:
        images_dir: directory containing calibration images
        board_size: tuple (width, height) - number of internal corners
        square_size: size of each square in real world units (e.g., mm, cm)
        output_file: file to save calibration results
    """
    # Prepare object points
    objp = np.zeros((board_size[0] * board_size[1], 3), np.float32)
    objp[:, :2] = np.mgrid[0:board_size[0], 0:board_size[1]].T.reshape(-1, 2) * square_size
    
    # Arrays to store object points and image points
    objpoints = []  # 3D points in real world space
    imgpoints = []  # 2D points in image plane
    
    # Get list of calibration images
    image_files = glob.glob(os.path.join(images_dir, "*.jpg"))
    image_files.extend(glob.glob(os.path.join(images_dir, "*.png")))
    
    if len(image_files) == 0:
        print(f"No images found in {images_dir}")
        return None
    
    print(f"Found {len(image_files)} calibration images")
    
    successful_detections = 0
    img_shape = None
    
    for i, image_file in enumerate(image_files):
        print(f"Processing image {i+1}/{len(image_files)}: {os.path.basename(image_file)}")
        
        img = cv2.imread(image_file)
        if img is None:
            print(f"Could not read image: {image_file}")
            continue
            
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        img_shape = gray.shape[::-1]  # (width, height)
        
        # Find chessboard corners
        ret, corners = cv2.findChessboardCorners(gray, board_size, None)
        
        if ret:
            # Refine corners
            corners_refined = cv2.cornerSubPix(gray, corners, (11, 11), (-1, -1),
                                             (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 30, 0.001))
            
            objpoints.append(objp)
            imgpoints.append(corners_refined)
            successful_detections += 1
            
            # Optionally visualize detected corners
            img_with_corners = img.copy()
            cv2.drawChessboardCorners(img_with_corners, board_size, corners_refined, ret)
            # cv2.imshow('Corners', img_with_corners)
            # cv2.waitKey(100)
        else:
            print(f"  - Could not find chessboard corners in {os.path.basename(image_file)}")
    
    cv2.destroyAllWindows()
    
    print(f"Successfully detected chessboard in {successful_detections}/{len(image_files)} images")
    
    if successful_detections < 10:
        print("Warning: Less than 10 successful detections. Calibration may be inaccurate.")
    
    if successful_detections == 0:
        print("No successful detections. Cannot calibrate camera.")
        return None
    
    # Perform camera calibration
    print("Performing camera calibration...")
    ret, camera_matrix, dist_coeffs, rvecs, tvecs = cv2.calibrateCamera(
        objpoints, imgpoints, img_shape, None, None)
    
    if ret:
        print("Camera calibration successful!")
        
        # Calculate calibration error
        total_error = 0
        for i in range(len(objpoints)):
            imgpoints2, _ = cv2.projectPoints(objpoints[i], rvecs[i], tvecs[i], camera_matrix, dist_coeffs)
            error = cv2.norm(imgpoints[i], imgpoints2, cv2.NORM_L2) / len(imgpoints2)
            total_error += error
        
        mean_error = total_error / len(objpoints)
        print(f"Mean reprojection error: {mean_error:.4f} pixels")
        
        # Print calibration results
        print("\nCalibration Results:")
        print("Camera Matrix:")
        print(camera_matrix)
        print("\nDistortion Coefficients:")
        print(dist_coeffs.flatten())
        
        # Calculate focal length in mm (assuming sensor width)
        sensor_width_mm = 3.68  # Common sensor width for webcams (adjust as needed)
        focal_length_mm = (camera_matrix[0, 0] * sensor_width_mm) / img_shape[0]
        print(f"\nEstimated focal length: {focal_length_mm:.2f} mm")
        
        # Save calibration results
        calibration_data = {
            'camera_matrix': camera_matrix,
            'dist_coeffs': dist_coeffs,
            'rvecs': rvecs,
            'tvecs': tvecs,
            'image_shape': img_shape,
            'reprojection_error': mean_error,
            'board_size': board_size,
            'square_size': square_size
        }
        
        with open(output_file, 'wb') as f:
            pickle.dump(calibration_data, f)
        
        print(f"\nCalibration data saved to: {output_file}")
        
        return calibration_data
    else:
        print("Camera calibration failed!")
        return None

def load_calibration(calibration_file="camera_calibration.pkl"):
    """
    Load camera calibration data from file
    
    Args:
        calibration_file: path to calibration file
        
    Returns:
        calibration_data: dictionary containing calibration parameters
    """
    try:
        with open(calibration_file, 'rb') as f:
            calibration_data = pickle.load(f)
        print(f"Calibration data loaded from: {calibration_file}")
        return calibration_data
    except FileNotFoundError:
        print(f"Calibration file not found: {calibration_file}")
        return None
    except Exception as e:
        print(f"Error loading calibration file: {e}")
        return None

if __name__ == "__main__":
    # Perform camera calibration
    calibration_data = calibrate_camera(
        images_dir="calibration_images",
        board_size=(9, 6),
        square_size=25.0,  # 25mm squares (adjust to your printed chessboard)
        output_file="camera_calibration.pkl"
    )
    
    if calibration_data:
        print("\nCalibration completed successfully!")
        print("You can now use the calibration data for ArUco marker detection.")
    else:
        print("\nCalibration failed. Please check your calibration images.")