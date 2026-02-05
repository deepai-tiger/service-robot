import cv2
import numpy as np
import matplotlib.pyplot as plt
import os

def generate_aruco_markers(marker_ids=[0, 1, 2, 3, 4], marker_size=200, 
                          dictionary_type=cv2.aruco.DICT_6X6_250, output_dir="aruco_markers"):
    """
    Generate ArUco markers and save them as images
    
    Args:
        marker_ids: list of marker IDs to generate
        marker_size: size of markers in pixels
        dictionary_type: ArUco dictionary type
        output_dir: directory to save marker images
    """
    # Create output directory
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)
    
    # Create ArUco dictionary
    aruco_dict = cv2.aruco.getPredefinedDictionary(dictionary_type)
    
    print(f"Generating {len(marker_ids)} ArUco markers...")
    
    for marker_id in marker_ids:
        # Generate marker
        marker_img = cv2.aruco.generateImageMarker(aruco_dict, marker_id, marker_size)
        
        # Save marker
        filename = os.path.join(output_dir, f"aruco_marker_{marker_id}.png")
        cv2.imwrite(filename, marker_img)
        
        print(f"Generated marker ID {marker_id}: {filename}")
        
        # Display marker (optional)
        plt.figure(figsize=(4, 4))
        plt.imshow(marker_img, cmap='gray')
        plt.title(f'ArUco Marker ID: {marker_id}')
        plt.axis('off')
        plt.tight_layout()
        plt.savefig(os.path.join(output_dir, f"aruco_marker_{marker_id}_display.png"), 
                   bbox_inches='tight', dpi=300)
        plt.show()
    
    print(f"\nAll markers saved in: {output_dir}")
    print("\nInstructions:")
    print("1. Print the generated markers on white paper")
    print("2. Make sure they are printed clearly without blur")
    print("3. Cut them out and place them on a flat surface")
    print("4. Use them for pose estimation")

def generate_aruco_board(board_size=(4, 4), marker_size=100, marker_separation=20,
                        dictionary_type=cv2.aruco.DICT_6X6_250, output_path="aruco_board.png"):
    """
    Generate an ArUco board with multiple markers
    
    Args:
        board_size: tuple (width, height) - number of markers
        marker_size: size of each marker in pixels
        marker_separation: separation between markers in pixels
        dictionary_type: ArUco dictionary type
        output_path: path to save the board image
    """
    # Create ArUco dictionary
    aruco_dict = cv2.aruco.getPredefinedDictionary(dictionary_type)
    
    # Create board
    board = cv2.aruco.GridBoard(board_size, marker_size, marker_separation, aruco_dict)
    
    # Calculate board image size
    board_width = board_size[0] * marker_size + (board_size[0] - 1) * marker_separation
    board_height = board_size[1] * marker_size + (board_size[1] - 1) * marker_separation
    
    # Generate board image
    board_img = cv2.aruco.Board.generateImage(board, (board_width, board_height))
    
    # Save board
    cv2.imwrite(output_path, board_img)
    
    print(f"ArUco board generated: {output_path}")
    print(f"Board size: {board_size[0]}x{board_size[1]} markers")
    print(f"Marker size: {marker_size} pixels")
    print(f"Marker separation: {marker_separation} pixels")
    
    # Display board
    plt.figure(figsize=(10, 8))
    plt.imshow(board_img, cmap='gray')
    plt.title(f'ArUco Board ({board_size[0]}x{board_size[1]} markers)')
    plt.axis('off')
    plt.tight_layout()
    plt.show()
    
    return board

if __name__ == "__main__":
    # Generate individual ArUco markers
    print("Generating individual ArUco markers...")
    generate_aruco_markers(
        marker_ids=[0, 1, 2, 3, 4, 5, 6, 7, 8, 9],
        marker_size=200,
        dictionary_type=cv2.aruco.DICT_6X6_250,
        output_dir="aruco_markers"
    )
    
    print("\n" + "="*50 + "\n")
    
    # Generate ArUco board
    print("Generating ArUco board...")
    generate_aruco_board(
        board_size=(4, 3),
        marker_size=100,
        marker_separation=20,
        dictionary_type=cv2.aruco.DICT_6X6_250,
        output_path="aruco_board.png"
    )
    
    print("\nArUco marker generation completed!")
    print("Available dictionary types:")
    print("- cv2.aruco.DICT_4X4_50")
    print("- cv2.aruco.DICT_4X4_100")
    print("- cv2.aruco.DICT_4X4_250")
    print("- cv2.aruco.DICT_4X4_1000")
    print("- cv2.aruco.DICT_5X5_50")
    print("- cv2.aruco.DICT_5X5_100")
    print("- cv2.aruco.DICT_5X5_250")
    print("- cv2.aruco.DICT_5X5_1000")
    print("- cv2.aruco.DICT_6X6_50")
    print("- cv2.aruco.DICT_6X6_100")
    print("- cv2.aruco.DICT_6X6_250")
    print("- cv2.aruco.DICT_6X6_1000")
    print("- cv2.aruco.DICT_7X7_50")
    print("- cv2.aruco.DICT_7X7_100")
    print("- cv2.aruco.DICT_7X7_250")
    print("- cv2.aruco.DICT_7X7_1000")