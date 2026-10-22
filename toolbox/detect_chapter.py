
#!/usr/bin/env python3
"""Detect the current Arc and Chapter from the game screen."""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path




# Find the project root without hardcoding the user's home directory.
PROJECT_ROOT = next(
    (
        parent
        for parent in Path(__file__).resolve().parents
        if (parent / "functions" / "script_functions.py").is_file()
    ),
    None,
)

if PROJECT_ROOT is None:
    raise RuntimeError("Could not locate the project functions directory.")

sys.path.insert(0, str(PROJECT_ROOT))



# Import script_functions and variables from functions
from functions.script_functions import (  # noqa: E402
    capture_screenshot,
    crop_image,
    prepare_ocr_image,
    read_ocr,
)
from functions.variables import (  # noqa: E402
    CHAPTER_CROP,
    CHAPTER_OCR_DEBUG,
    TESSERACT_CONFIG,
)


#--Patten to Parse the ocr as computer machine-readable
CHAPTER_PATTERN = re.compile(
    r"arc\s*(\d+)\s*[-–—]\s*chapter\s*(\d+)",
    re.IGNORECASE,
)

#-------Main detect_chapter function to parse ocr
def parse_chapter(text: str) -> dict[str, int | str] | None:
    """Parse OCR text into a structured Arc.Chapter identifier."""
    normalized = " ".join(text.split())
    match = CHAPTER_PATTERN.search(normalized)

    if match is None:
        return None

    arc = int(match.group(1))
    chapter = int(match.group(2))

    return {
        "arc": arc,
        "chapter": chapter,
        "id": f"{arc}.{chapter}",
    }



#------detect_chapter from ocr and use Patten
def detect_chapter() -> dict[str, int | str] | None:
    """Capture the screen, read the heading, and return its chapter data."""
    screenshot = capture_screenshot()
    heading = crop_image(screenshot, CHAPTER_CROP)
    processed = prepare_ocr_image(heading)
    text = read_ocr(processed, TESSERACT_CONFIG)

    if CHAPTER_OCR_DEBUG:
        import cv2

        cv2.imwrite("/tmp/rezero-chapter-crop.png", heading)
        cv2.imwrite("/tmp/rezero-chapter-ocr.png", processed)

    return parse_chapter(text)


#main
def main() -> None:
    try:
        result = detect_chapter()
        # stdout is machine-readable for the manager.
        print(json.dumps(result))
    except Exception as exc:
        # Keep diagnostic information separate from the JSON result.
        print(f"detect_chapter: {exc}", file=sys.stderr)
        raise SystemExit(1)


if __name__ == "__main__":
    main()
