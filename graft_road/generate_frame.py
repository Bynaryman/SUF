#!/usr/bin/env python
from PIL import Image
from pdk_configs import PDKS
from division_configs import division_configs
import os

def merge_images_into_grid(image_paths, grid_size, final_size):
    # Calculate the size of each cell in the grid
    cell_width = final_size[0] // grid_size[0]
    cell_height = final_size[1] // grid_size[1]

    # Create a black rectangle to use as a placeholder for missing images
    black_rect = Image.new('RGB', (cell_width, cell_height), (0, 0, 0))

    # Create a new blank image with the desired final size
    merged_image = Image.new('RGB', final_size, (255, 255, 255))

    for i, image_path in enumerate(image_paths):
        # Load the image if it exists, else use the black rectangle
        img = Image.open(image_path) if os.path.exists(image_path) else black_rect.copy()

        # Resize image to fit into the cell (in case it exists and is not of cell size)
        img = img.resize((cell_width, cell_height))

        # Calculate position
        x_offset = (i % grid_size[0]) * cell_width
        y_offset = (i // grid_size[0]) * cell_height

        # Paste the image/black rectangle into the merged image
        merged_image.paste(img, (x_offset, y_offset))

    return merged_image

def merge_images_into_grid(image_paths, grid_size, final_size):
    # Calculate the size of each cell in the grid
    cell_width = final_size[0] // grid_size[0]
    cell_height = final_size[1] // grid_size[1]

    # Create a black rectangle to use as a placeholder for missing images
    black_rect = Image.new('RGB', (cell_width, cell_height), (0, 0, 0))

    # Create a new blank image with the desired final size
    merged_image = Image.new('RGB', final_size, (255, 255, 255))

    for row, division in enumerate(division_configs.keys()):
        for col, pdk in enumerate(PDKS):
            image_path = f"/tmp/{pdk}_{division}.png"
            # Load the image if it exists, else use the black rectangle
            img = Image.open(image_path) if os.path.exists(image_path) else black_rect.copy()

            # Resize image to fit into the cell
            img = img.resize((cell_width, cell_height))

            # Calculate position
            x_offset = col * cell_width
            y_offset = row * cell_height

            # Paste the image/black rectangle into the merged image
            merged_image.paste(img, (x_offset, y_offset))

    return merged_image

if __name__ == "__main__":
    # Generate image paths based on configurations
    image_paths = [f"/tmp/{pdk}_{division}.png" for pdk in PDKS for division in division_configs.keys()]

    # Define the grid size. Here, we're assuming a grid size based on the number of images.
    total_images = len(image_paths)
    grid_width = int(total_images ** 0.5) + 1  # Simplified calculation
    grid_height = (total_images // grid_width) + 1
    grid_size = (grid_width, grid_height)

    # Define the final size, e.g., for HD: (1280, 720), for 4K: (3840, 2160)
    final_size = (3840, 2160)

    merged = merge_images_into_grid(image_paths, grid_size, final_size)
    #merged.show()  # To display the merged image
    merged.save("merged_image.jpg")  # To save the merged image

