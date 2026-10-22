

"""Reusable utilities shared by standalone toolbox scripts."""

from __future__ import annotations

import subprocess
from pathlib import Path

import cv2
import pytesseract

from functions.variables import SCREENSHOT_COMMAND, SCREENSHOT_PATH



# ----- for chapter_detector.py-----------------

#------ function for screen capture--------
def capture_screenshot():
    """Capture a screenshot and return it as an OpenCV image."""
    output_path = Path(SCREENSHOT_PATH)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    command = [
        argument.replace("{output}", str(output_path))
        for argument in SCREENSHOT_COMMAND
    ]

    subprocess.run(command, check=True)

    image = cv2.imread(str(output_path))
    if image is None:
        raise RuntimeError(
            f"Screenshot command produced no readable image: {output_path}"
        )

    return image

#------- function for cropping image(Universal)-------

def crop_image(image, crop):
    """Crop an image using fractional (top, bottom, left, right) bounds."""
    top, bottom, left, right = crop
    height, width = image.shape[:2]

    y1 = int(height * top)
    y2 = int(height * bottom)
    x1 = int(width * left)
    x2 = int(width * right)

    if not (0 <= x1 < x2 <= width and 0 <= y1 < y2 <= height):
        raise ValueError("Crop bounds are invalid for this image.")

    return image[y1:y2, x1:x2]

#-------- Ocr preprocessing function---------------
def prepare_ocr_image(image, scale=3):
    """Convert a cropped image to enlarged, thresholded grayscale."""
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    enlarged = cv2.resize(
        gray,
        None,
        fx=scale,
        fy=scale,
        interpolation=cv2.INTER_CUBIC,
    )
    _, processed = cv2.threshold(
        enlarged,
        0,
        255,
        cv2.THRESH_BINARY + cv2.THRESH_OTSU,
    )
    return processed

#------- Call tesseract for ocr function---------------
def read_ocr(image, config="--psm 6"):
    """Return raw Tesseract text for an image."""
    return pytesseract.image_to_string(image, config=config).strip()





# ----- Function for cropping by absolute coordinates -----

def crop_image_by_coordinates(image, x, y, width, height):
    """Crop an image using absolute pixel coordinates."""
    image_height, image_width = image.shape[:2]

    x2 = x + width
    y2 = y + height

    if not (
        0 <= x < x2 <= image_width
        and 0 <= y < y2 <= image_height
    ):
        raise ValueError(
            "Crop coordinates are outside the image boundaries."
        )

    return image[y:y2, x:x2]




# ----- Function for capturing a screen region --------

def capture_region(x1, y1, x2, y2, output_name="region.png", scale=1.0):
    """Capture a rectangular screen region and save it under captures/.

    Coordinates:
        (x1, y1): upper-left corner
        (x2, y2): lower-right corner

    scale:
        1.0 = original resolution
        0.5 = half width and height
        0.25 = quarter width and height
    """
    from pathlib import Path
    import subprocess
    import cv2

    if not (x1 < x2 and y1 < y2):
        raise ValueError("Invalid region: upper-left must precede lower-right.")

    if not (0 < scale <= 1.0):
        raise ValueError("Scale must be greater than 0 and at most 1.0.")

    project_root = Path(__file__).resolve().parent.parent
    captures_dir = project_root / "captures"
    captures_dir.mkdir(parents=True, exist_ok=True)

    output_path = captures_dir / output_name

    width = x2 - x1
    height = y2 - y1

    subprocess.run(
        [
            "grim",
            "-g", f"{x1},{y1} {width}x{height}",
            str(output_path),
        ],
        check=True,
    )

    if scale < 1.0:
        image = cv2.imread(str(output_path))

        if image is None:
            raise RuntimeError(f"Could not read captured image: {output_path}")

        new_width = max(1, round(width * scale))
        new_height = max(1, round(height * scale))

        image = cv2.resize(
            image,
            (new_width, new_height),
            interpolation=cv2.INTER_AREA,
        )

        if not cv2.imwrite(str(output_path), image):
            raise RuntimeError(f"Could not save resized image: {output_path}")

    return str(output_path)


#-----for Battle.py function---------------

# click

def click(x: int, y: int) -> None:
    """Move the pointer to desktop coordinates and perform one left click."""
    subprocess.run(
        ["wdotool", "mousemove", str(x), str(y)],
        check=True,
    )
    subprocess.run(
        ["wdotool", "click", "1"],
        check=True,
    )




# ----- Image comparison function -----

def compare_images(image_a, image_b):
    """Return the proportion of matching pixels between two images."""
    import cv2
    import numpy as np

    if image_a is None or image_b is None:
        raise ValueError("Cannot compare an empty image.")

    if image_a.shape != image_b.shape:
        raise ValueError(
            f"Image dimensions differ: {image_a.shape} vs {image_b.shape}"
        )

    gray_a = cv2.cvtColor(image_a, cv2.COLOR_BGR2GRAY)
    gray_b = cv2.cvtColor(image_b, cv2.COLOR_BGR2GRAY)

    difference = cv2.absdiff(gray_a, gray_b)

    # Treat small pixel variations as matching.
    matching_pixels = np.count_nonzero(difference <= 20)
    total_pixels = difference.size

    return matching_pixels / total_pixels





