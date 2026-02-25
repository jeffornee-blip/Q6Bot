#!/bin/bash
set -x  # Print all commands being executed
set -u  # Error on undefined variables

echo "=== BASH STARTUP SCRIPT STARTED ==="
date
echo "Python version:"
python --version
echo "Current directory:"
pwd
echo "Files in current directory:"
ls -la
echo "Starting Python bot..."
exec python -u PUBobot2.py
