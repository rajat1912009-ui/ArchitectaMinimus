

#!/usr/bin/env python3
"""Persistent battle detector controlled through stdin."""

import os
import select
import sys
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

import cv2

from functions.script_functions import (
    capture_region,
    prepare_ocr_image,
    read_ocr,
)
from functions.variables import BATTLE_LOG_REGION, BATTLE_LOG_SCALE

EXPECTED_BATTLE_TEXT = "Combat Log"
CURRENT_IMAGE = "battle_log_current.png"
POLL_INTERVAL = 0.15


def detect_battle() -> bool:
    """Capture the battle indicator and return its detected state."""
    current_path = capture_region(
        *BATTLE_LOG_REGION,
        output_name=CURRENT_IMAGE,
        scale=BATTLE_LOG_SCALE,
    )

    image = cv2.imread(current_path)
    if image is None:
        raise RuntimeError(f"Could not read capture: {current_path}")

    processed = prepare_ocr_image(image, scale=3)
    text = read_ocr(processed, config="--psm 7")

    normalized = " ".join(text.casefold().split())
    normalized = normalized.replace("[", "l")
    expected = " ".join(EXPECTED_BATTLE_TEXT.casefold().split())

    return expected in normalized


def main() -> int:
    enabled = False
    last_state = None
    input_buffer = ""

    print("READY", flush=True)

    try:
        while True:
            readable, _, _ = select.select(
                [sys.stdin], [], [], POLL_INTERVAL
            )

            if readable:
                chunk = os.read(sys.stdin.fileno(), 4096)

                if not chunk:
                    print("STOPPED", flush=True)
                    return 0

                input_buffer += chunk.decode("utf-8")

                while "\n" in input_buffer:
                    command, input_buffer = input_buffer.split("\n", 1)
                    command = command.strip().upper()

                    if command == "ENABLE":
                        enabled = True
                        last_state = None
                        print("ENABLED", flush=True)

                    elif command == "DISABLE":
                        enabled = False
                        last_state = None
                        print("DISABLED", flush=True)

                    elif command == "STOP":
                        print("STOPPED", flush=True)
                        return 0

                    elif command:
                        print("ERROR unknown_command", flush=True)

            if enabled:
                detected = detect_battle()

                if detected != last_state:
                    print("YES" if detected else "NO", flush=True)
                    last_state = detected

    except (OSError, RuntimeError, ValueError, cv2.error) as error:
        print(f"ERROR {error}", flush=True)
        return 2
    except KeyboardInterrupt:
        print("STOPPED interrupted", flush=True)
        return 130


if __name__ == "__main__":
    sys.exit(main())
