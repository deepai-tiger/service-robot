import cv2
import numpy as np
import matplotlib.pyplot as plt

def generate_chessboard_pattern(board_size=(9, 6), square_size=50, output_path="chessboard.png"):
    """
    Generate a chessboard pattern for camera calibration
    
    Args:
        board_size: tuple (width, height) - number of internal corners
        square_size: size of each square in pixels
        output_path: path to save the chessboard image
    """
    # Calculate image dimensions
    img_width = (board_size[0] + 1) * square_size
    img_height = (board_size[1] + 1) * square_size
    
    # Create chessboard pattern
    chessboard = np.zeros((img_height, img_width), dtype=np.uint8)
    
    for i in range(board_size[1] + 1):
        for j in range(board_size[0] + 1):
            if (i + j) % 2 == 0:
                y_start = i * square_size
                y_end = (i + 1) * square_size
                x_start = j * square_size
                x_end = (j + 1) * square_size
                chessboard[y_start:y_end, x_start:x_end] = 255
    
    # Save the chessboard
    cv2.imwrite(output_path, chessboard)
    print(f"Chessboard pattern saved as {output_path}")
    
    # Display the chessboard
    plt.figure(figsize=(10, 8))
    plt.imshow(chessboard, cmap='gray')
    plt.title(f'Chessboard Pattern ({board_size[0]}x{board_size[1]} corners)')
    plt.axis('off')
    plt.show()
    
    return chessboard

if __name__ == "__main__":
    # Generate chessboard pattern
    # Standard sizes: (9,6), (8,6), (7,5)
    generate_chessboard_pattern(board_size=(9, 6), square_size=50, output_path="chessboard_9x6.png")
    
    print("Instructions:")
    print("1. Print the generated chessboard pattern")
    print("2. Make sure it's printed flat without distortion")
    print("3. Use it for camera calibration")