
"""Shared configurable settings for toolbox scripts."""
#imports

from dataclasses import dataclass


#declaration
@dataclass(frozen=True)
class BattleButton:
    name: str
    x: int
    y: int




#chapter_detector.py Settings ---------------------



# Screenshot command. {output} is replaced with the temporary output path.
# For grim, this captures the full screen.
SCREENSHOT_COMMAND = ["grim", "{output}"]

# Temporary screenshot location.
SCREENSHOT_PATH = "/tmp/rezero-screen.png"

# OCR debug images are only written when explicitly enabled.
CHAPTER_OCR_DEBUG = False

# Heading crop, expressed as fractions of screen width and height:
# (top, bottom, left, right)
CHAPTER_CROP = (0.20, 0.32, 0.35, 0.65)

# Tesseract page segmentation mode.
TESSERACT_CONFIG = "--psm 6"


#-------battle.py  Settings ------------------------------

# Default battle-button coordinates.
# The coordinate file can override these values later.
BATTLE_BUTTON_COORDINATES = {
    "REST": (1236, 669),
    "GUARD": (1400, 661),
    "LIGHT ATTACK": (1567, 665),
    "HEAVY ATTACK": (1732, 663),
    "ability_1": (1080, 771),
    "ability_2": (1241, 776),
    "ability_3": (1405, 778),
    "ability_4": (1568, 775),
    "ability_5": (1735, 774),
}

# Change this list to change the clicking order.
BATTLE_BUTTON_ORDER = [
    "REST",
    "GUARD",
    "LIGHT ATTACK",
    "HEAVY ATTACK",
    "ability_1",
    "ability_2",
    "ability_3",
    "ability_4",
    "ability_5",
]

# Battle clicking delays, in seconds.
BATTLE_CLICK_DELAY = 0.1
BATTLE_CYCLE_DELAY = 0.1




# ----- Battle detector configuration -----

BATTLE_LOG_REGION = (1031, 235, 1134, 264)
BATTLE_LOG_SCALE = 1.0
BATTLE_MATCH_THRESHOLD = 0.70

BATTLE_REFERENCE_IMAGE = "battle_log_reference.png"
BATTLE_CURRENT_IMAGE = "battle_log_current.png"

