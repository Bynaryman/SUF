#!/usr/bin/env python
from PIL import Image, ImageDraw, ImageFont
from pdk_configs import PDKS
from division_configs import division_configs
import os

def merge_images_into_grid(image_paths, grid_size):
    # Cell dimensions
    cell_width = 200
    cell_height = 200

    # Margin for labels
    top_margin = 40
    left_margin = 150

    # Calculate overall size
    width = grid_size[0] * cell_width + left_margin
    height = grid_size[1] * cell_height + top_margin

    # Create a black rectangle to use as a placeholder for missing images
    black_rect = Image.new('RGB', (cell_width, cell_height), (0, 0, 0))

    # Create a new blank image with the calculated size
    merged_image = Image.new('RGB', (width, height), (255, 255, 255))
    draw = ImageDraw.Draw(merged_image)

    # Use a basic font included with Pillow
    font = ImageFont.load_default()
    #font = ImageFont.truetype("arial.ttf", 18)

    # Draw PDK labels on the top
    for col, pdk in enumerate(PDKS):
        x_offset = left_margin + col * cell_width + (cell_width // 2)
        draw.text((x_offset, 10), pdk, font=font, fill=(0, 0, 0))

    # Draw division labels on the left and images in the grid
    for row, division in enumerate(division_configs.keys()):
        y_offset = top_margin + row * cell_height + (cell_height // 2)
        draw.text((10, y_offset), division, font=font, fill=(0, 0, 0))

        for col, pdk in enumerate(PDKS):
            draw.rectangle([x_offset, y_offset, x_offset + cell_width, y_offset + cell_height], outline="red")
            #print(f"{pdk}_{division}")
            image_path = f"/tmp/{pdk}_{division}.png"
            print(image_path)
            # Load the image if it exists, else use the black rectangle
            if os.path.exists(image_path):
                img = Image.open(image_path)
                print(f"Loaded {image_path}")
            else:
                img = black_rect.copy()
                print(f"{image_path} not found. Using black rectangle.")

            img.resize((cell_width,cell_height))

            # Place the image/black rectangle into the merged image
            #x_offset = left_margin + col * cell_width
            #y_offset = top_margin + row * cell_height
            merged_image.paste(img, (x_offset, y_offset))

    return merged_image

if __name__ == "__main__":
    # Define the grid size: Columns represent PDKS and rows represent division_configs
    grid_size = (len(PDKS), len(division_configs))

    merged = merge_images_into_grid(None, grid_size)  # Passing None since we're directly using the configs in the function now
    #merged.show()  # To display the merged image
    merged.save("merged_image_with_labels.jpg")  # To save the merged image
