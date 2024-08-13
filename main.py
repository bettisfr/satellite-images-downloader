import ee
import os
import requests
from geopy.distance import geodesic
from geopy.point import Point
from PIL import Image, ImageChops


####### Parameters
# Resolution in meters [minimum 0.6]
scale = 2

# Radius in meters of a circle that defines the region of interest
buffer_radius = 2000

# Latitude of the bottom-left corner of the area
latitude_bottom_left = 37.910715173463

# Longitude of the bottom-left corner of the area
longitude_bottom_left = -91.77332884614303

# Length of the area in meters
area_length = 8000

# Height of the area in meters
area_height = 8000


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


def download_image(latitude, longitude, pair):
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
            'scale': scale,  # NAIP images are typically 1m resolution
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

    output_path = f'{out_folder}/naip_{x}_{y}.tif'
    with open(output_path, 'wb') as file:
        file.write(response.content)

    print(f'Image downloaded and saved as {output_path}')

    # Crop black borders
    crop_black_borders(output_path)


def batch():
    # Authentication and initialization
    ee.Authenticate()
    ee.Initialize(project='ee-francescobettisorbelli')

    num_rows = int(area_height / buffer_radius)
    num_columns = int(area_length / buffer_radius)

    # Create a starting point as a geopy Point object
    start_point = Point(latitude_bottom_left, longitude_bottom_left)

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
            download_image(new_latitude, new_longitude, (x, y))


if __name__ == "__main__":
    batch()
