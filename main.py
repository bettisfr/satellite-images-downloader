import math

import ee
import os
import requests
import random
from geopy.distance import geodesic
from geopy.point import Point
import matplotlib.pyplot as plt
import numpy as np
from PIL import Image, ImageChops


def crop_black_borders(image_path):
    image = Image.open(image_path).convert("RGB")
    bg = Image.new(image.mode, image.size, (0, 0, 0))
    diff = ImageChops.difference(image, bg)

    # Enhance the difference image to handle dark variations
    diff = ImageChops.add(diff, diff, 2.0, -100)

    bbox = diff.getbbox()
    if bbox:
        image = image.crop(bbox)
        image.save(image_path)
        print(f"Cropped")
    else:
        print(f"No need to crop")


def get_image(center_point, dest_point, pair, buffer_radius, scale, rotation_angle):
    dest_latitude, dest_longitude = dest_point.latitude, dest_point.longitude
    center_latitude, center_longitude = center_point.latitude, center_point.longitude
    x, y = pair

    # Authentication and initialization
    ee.Authenticate()
    ee.Initialize(project='ee-francescobettisorbelli')

    # NAIP imagery is available only for the United States
    point_US = ee.Geometry.Point(dest_longitude, dest_latitude)

    # Select the NAIP image collection
    collection = ee.ImageCollection('USDA/NAIP/DOQQ') \
        .filterBounds(point_US) \
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

    # Defines a region within a circle of radius buffer_radius centered at point_US
    region = point_US.buffer(buffer_radius).bounds().getInfo()['coordinates']

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
        return 1

    # Download the image
    response = requests.get(url)

    # Save the image to a file
    out_folder = f'dataset/{x}_{y}__{center_latitude}_{center_longitude}'
    if not os.path.exists(out_folder):
        os.makedirs(out_folder)

    output_path = f'{out_folder}/naip_br{buffer_radius}_s{scale}_r{rotation_angle}.tif'
    with open(output_path, 'wb') as file:
        file.write(response.content)

    print(f'Image downloaded={output_path}')

    crop_black_borders(output_path)

    rotate_image(output_path, rotation_angle)

    return 0


def download_satellite_images(p0, cell_side, num_cells_x, num_cells_y, iterations):
    # Create a starting point as a geopy Point object
    start_point = Point(p0[0], p0[1])

    print(f"Grid formed by {num_cells_x} x {num_cells_y} cells")

    for x in range(num_cells_x):
        for y in range(num_cells_y):
            # Calculate distance in meters from the starting point
            distance_east = y * cell_side
            distance_north = x * cell_side

            # Calculate new point using geodesic function
            center_point = geodesic(meters=distance_east).destination(start_point, 90)  # East direction
            center_point = geodesic(meters=distance_north).destination(center_point, 0)  # North direction

            # dist = geodesic(start_point, center_point).km

            print(f"Evaluating ({x}, {y}) located at ({center_point.latitude}, {center_point.longitude})")

            buffer_radius = int(cell_side / 2)
            scales = [0.6, 1, 2, 3, 4, 5]

            i = 0
            while i < iterations:
                delta_x = random.randint(-buffer_radius, buffer_radius)
                delta_y = random.randint(-buffer_radius, buffer_radius)

                dest_point = geodesic(meters=delta_x).destination(center_point, 90)
                dest_point = geodesic(meters=delta_y).destination(dest_point, 0)
                dist = math.sqrt(delta_x**2 + delta_y**2)
                new_buffer_radius = int(buffer_radius - dist)

                rotation_angle = random.randint(0, 359)

                scale = random.choice(scales)
                if new_buffer_radius < 300 or (new_buffer_radius < 500 and scale >= 3):
                    continue

                print(f"  Generating image {i+1}/{iterations}")
                status = get_image(center_point, dest_point, (x, y), new_buffer_radius, scale, rotation_angle)
                if status == 1:
                    continue

                i = i+1


def rotate_image(image_path, rotation_angle):
    with Image.open(image_path) as img:
        width, height = img.size

        # Start from the center of the image
        center_x = width // 2
        center_y = height // 2

        # Rotate the entire image around its center
        rotated_img = img.rotate(rotation_angle, resample=Image.BICUBIC, center=(center_x, center_y))

        # Save the cropped image
        rotated_img.save(image_path)
        print(f"Rotated")


if __name__ == "__main__":
    ####### Parameters
    # Latitude and longitude of the bottom-left cell center of the area, respectively
    p_0 = (37.910715173463, -91.77332884614303)

    # Number of cells along x-axis and y-axis, respectively
    num_cells_x, num_cells_y = 10, 10

    # Cell side (it is a square) in meters
    cell_side = 2000

    # How many random images to take for each cell
    iterations = 100

    download_satellite_images(p_0, cell_side, num_cells_x, num_cells_y, iterations)
