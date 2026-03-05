#!/bin/bash
#
# Docker wrapper for mdy (markdowny)
# Usage: Run from directory containing your files
#
# Build:  docker build -t mdy .
# Run:    ./docker-run.sh -i input.md -o output.docx
#         ./docker-run.sh -i input.md -o output.pdf -f pdf
#         cat input.md | ./docker-run.sh              # pipe input
#

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
IMAGE="mdy"

# Build the image if it doesn't exist
if ! docker image inspect "$IMAGE" > /dev/null 2>&1; then
    echo "Building Docker image..."
    docker build -t "$IMAGE" "$SCRIPT_DIR"
fi

# Check if input is being piped
if [ ! -t 0 ] && [ -z "$1" ]; then
    # Piped input - read from stdin
    INPUT_CONTENT=$(cat)
    echo "$INPUT_CONTENT" > /data/input.md
    exec docker run --rm -i -v "$SCRIPT_DIR:/data" -w /data "$IMAGE" -i /data/input.md "$@"
fi

# Normal execution - pass through arguments
# Use -t only if stdout is a TTY
if [ -t 1 ]; then
    exec docker run --rm -it -v "$SCRIPT_DIR:/data" -w /data "$IMAGE" "$@"
else
    exec docker run --rm -i -v "$SCRIPT_DIR:/data" -w /data "$IMAGE" "$@"
fi
