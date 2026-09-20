#!/bin/sh
# Usage:
# ./test.sh            # Runs the full unit test suite
# ./test.sh -k routes  # Passes extra args through to pytest
#
# Set PYTHON to override the interpreter, e.g.:
# PYTHON=/path/to/python ./test.sh

set -e

SCRIPT_DIR="$(CDPATH= command cd -- "$(dirname -- "$0")" && pwd -P)"
cd "$SCRIPT_DIR"

# Point the app at the test directory so runtime files (config, sessions,
# bangs cache) are kept out of app/static
export APP_ROOT="$SCRIPT_DIR/test"
export STATIC_FOLDER="$APP_ROOT/static"

# Set up static files for testing
if [ -L "$STATIC_FOLDER" ] || [ -f "$STATIC_FOLDER" ]; then
    rm -f "$STATIC_FOLDER"
fi
ln -s "$SCRIPT_DIR/app/static" "$STATIC_FOLDER"

# Clear out build directory
rm -f "$SCRIPT_DIR"/app/static/build/*.js
rm -f "$SCRIPT_DIR"/app/static/build/*.css

"${PYTHON:-python3}" -m pytest test/ -v "$@"
