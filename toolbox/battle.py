#!/usr/bin/env python3
"""Manager-controlled service that repeatedly clicks battle buttons."""

from __future__ import annotations

import sys
import time
import threading

from functions.script_functions import click
from functions.variables import (
    BATTLE_BUTTON_COORDINATES,
    BATTLE_BUTTON_ORDER,
    BATTLE_CLICK_DELAY,
    BATTLE_CYCLE_DELAY,
)


def battle_loop(stop_event: threading.Event) -> None:
    """Click the configured battle buttons until stopped."""
    while not stop_event.is_set():
        for name in BATTLE_BUTTON_ORDER:
            if stop_event.is_set():
                return

            x, y = BATTLE_BUTTON_COORDINATES[name]
            click(x, y)

            if stop_event.wait(BATTLE_CLICK_DELAY):
                return

        if stop_event.wait(BATTLE_CYCLE_DELAY):
            return


def main() -> None:
    """Run as a service controlled through stdin."""
    stop_event = threading.Event()
    worker = threading.Thread(
        target=battle_loop,
        args=(stop_event,),
        daemon=True,
    )
    worker.start()

    print("Battle service started.", flush=True)

    try:
        for line in sys.stdin:
            command = line.strip().upper()

            if command == "STOP":
                print("Stopping battle service.", flush=True)
                break

    except KeyboardInterrupt:
        pass

    finally:
        stop_event.set()
        worker.join()
        print("Battle service stopped.", flush=True)


if __name__ == "__main__":
    main()
