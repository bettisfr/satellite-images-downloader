import ee
import os
import requests
import random
from geopy.distance import geodesic
from geopy.point import Point
import matplotlib.pyplot as plt
import numpy as np
from PIL import Image, ImageChops

####### Parameters
# Latitude of the bottom-left corner of the area
latitude_bottom_left = 37.910715173463

# Longitude of the bottom-left corner of the area
longitude_bottom_left = -91.77332884614303

# Length of the area in meters
area_length = 20000

# Height of the area in meters
area_height = 20000


def crop_black_borders(image_path):
    """Crops black borders from the image and saves the result."""
    image = Image.open(image_path).convert("RGB")  # Ensure image is in RGB mode
    bg = Image.new(image.mode, image.size, (0, 0, 0))  # Create a black background image
    diff = ImageChops.difference(image, bg)

    # Enhance the difference image to handle dark variations
    diff = ImageChops.add(diff, diff, 2.0, -100)

    bbox = diff.getbbox()
    if bbox:
        image = image.crop(bbox)
        image.save(image_path)
        print(f"Cropped and saved: {image_path}")
    else:
        print(f"No need to crop: {image_path}")


def download_image(latitude, longitude, scale, buffer_radius, pair):
    x, y = pair

    # NAIP imagery is available only for the United States
    point_us = ee.Geometry.Point(longitude, latitude)

    # Select the NAIP image collection
    collection = ee.ImageCollection('USDA/NAIP/DOQQ') \
        .filterBounds(point_us) \
        .filterDate('2020-01-01', '2023-12-31') \
        .first()

    # Define visualization parameters
    vis_params = {
        'bands': ['R', 'G', 'B'],  # True color RGB
        'min': 0,
        'max': 255,
    }

    # Visualize the image
    image = collection.visualize(**vis_params)

    region = point_us.buffer(buffer_radius).bounds().getInfo()['coordinates']

    # Get the download URL
    try:
        url = image.getDownloadURL({
            'scale': scale,
            'region': region,
            'format': 'GeoTIFF'
        })
    except ee.ee_exception.EEException as e:
        print(e)
        print(f"Try to *either* increase 'scale' (now {scale}) or decrease 'buffer_radius' (now {buffer_radius})")
        exit(-1)

    # Download the image
    response = requests.get(url)

    # Save the image to a file
    out_folder = f'out/size{buffer_radius}_res{scale}'
    if not os.path.exists(out_folder):
        os.makedirs(out_folder)

    output_path = f'{out_folder}/naip_{x}_{y}__{latitude}_{longitude}.tif'
    with open(output_path, 'wb') as file:
        file.write(response.content)

    print(f'Image downloaded and saved as {output_path}')

    # Crop black borders
    crop_black_borders(output_path)


def download_satellite_images(scale, buffer_radius):
    # Authentication and initialization
    ee.Authenticate()
    ee.Initialize(project='ee-francescobettisorbelli')

    num_rows = int(area_height / buffer_radius)
    num_columns = int(area_length / buffer_radius)

    # Create a starting point as a geopy Point object
    start_point = Point(latitude_bottom_left, longitude_bottom_left)

    print(f"Grid formed by {num_rows} rows and {num_columns} columns")

    for x in range(num_rows):
        for y in range(num_columns):
            # Calculate distance in meters from the starting point
            distance_east = y * 2 * buffer_radius
            distance_north = x * 2 * buffer_radius

            # Calculate new point using geodesic function
            new_point = geodesic(meters=distance_east).destination(start_point, 90)  # East direction
            new_point = geodesic(meters=distance_north).destination(new_point, 0)  # North direction

            # Extract latitude and longitude
            new_latitude, new_longitude = new_point.latitude, new_point.longitude

            print(f'Evaluating {x}, {y} located at {new_latitude}, {new_longitude}')

            # Download the image for the calculated location
            download_image(new_latitude, new_longitude, scale, buffer_radius, (x, y))


def manipulate_image_improved(image_path, output_path, crop_size):
    with Image.open(image_path) as img:
        width, height = img.size
        print(width, height)

        # Start from the center of the image
        center_x = width // 2
        center_y = height // 2

        # Randomize a rotation angle between 0 and 359 degrees
        rotation_angle = random.randint(0, 359)
        print(f"Rotation Angle: {rotation_angle}°")

        # Rotate the entire image around its center
        rotated_img = img.rotate(rotation_angle, resample=Image.BICUBIC, center=(center_x, center_y))

        # Calculate the top-left corner of the crop box centered on the rotated image
        crop_box = (
            center_x - crop_size // 2,
            center_y - crop_size // 2,
            center_x + crop_size // 2,
            center_y + crop_size // 2
        )

        # Crop the square from the rotated image
        cropped_img = rotated_img.crop(crop_box)

        # Save the cropped image
        cropped_img.save(output_path)
        print(f"Saved cropped image to {output_path}")


def create_random_uav_images(scale, buffer_radius, crop_size):
    out_folder = f'out/size{buffer_radius}_res{scale}'
    out_uav_folder = f'out_uav/size{buffer_radius}_res{scale}'

    os.makedirs(out_uav_folder, exist_ok=True)

    if scale != 0.6:
        print("For this task, please use scale=0.6")
        exit(-1)

    for root, _, files in os.walk(out_folder):
        for file in files:
            parts = file.split('_')
            x = parts[1]
            y = parts[2]
            latitude = parts[4]
            longitude = parts[5].split('.tif')[0]

            # Print the extracted values
            print(f"x: {x}, y: {y}, latitude: {latitude}, longitude: {longitude}")

            # Full path to the input image
            file_path = os.path.join(root, file)

            # Define the output path
            output_path = os.path.join(out_uav_folder, file)

            # Call the image manipulation function
            manipulate_image_improved(file_path, output_path, crop_size)


if __name__ == "__main__":
    # parameters: scale, buffer_radius
    # These will be the "satellite images"
    download_satellite_images(3, 2000)
    download_satellite_images(4, 3000)
    download_satellite_images(3, 4000)

    # These will be the "UAV images"
    download_satellite_images(0.6, 800)
    # From these, randomly extract some portions...
    # parameters: scale, buffer_radius, crop_size
    create_random_uav_images(0.6, 800, 500)
