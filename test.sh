#!/bin/sh
# Runs every unit test script individually and prints a summary.
# Usage: ./test.sh [pytest extra args...]

SCRIPT_DIR="$(CDPATH= command cd -- "$(dirname -- "$0")" && pwd -P)"
cd "$SCRIPT_DIR"

# Match the environment used by './run test' (and CI)
export APP_ROOT="$SCRIPT_DIR/test"
export STATIC_FOLDER="$APP_ROOT/static"
if [ ! -e "$STATIC_FOLDER" ]; then
    ln -s "$SCRIPT_DIR/app/static" "$STATIC_FOLDER"
fi

PYTHON="${PYTHON:-python3}"

PASSED=""
FAILED=""

for test_file in test/test_*.py; do
    echo "=================================================================="
    echo "Running $test_file"
    echo "=================================================================="
    if "$PYTHON" -m pytest -v "$test_file" "$@"; then
        PASSED="$PASSED $test_file"
    else
        FAILED="$FAILED $test_file"
    fi
    echo
done

echo "=================================================================="
echo "Summary"
echo "=================================================================="
for f in $PASSED; do
    echo "PASS: $f"
done
for f in $FAILED; do
    echo "FAIL: $f"
done

if [ -n "$FAILED" ]; then
    exit 1
fi
