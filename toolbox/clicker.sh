

#!/usr/bin/env bash
# Usage: clicker.sh X Y

set -euo pipefail

if [[ $# -ne 2 ]]; then
    echo "Usage: clicker.sh X Y" >&2
    exit 1
fi

if [[ ! "$1" =~ ^[0-9]+$ || ! "$2" =~ ^[0-9]+$ ]]; then
    echo "Error: X and Y must be non-negative integers." >&2
    exit 1
fi

wdotool mousemove "$1" "$2"
wdotool click 1
