#!/bin/bash

# Ensure output goes to file and terminal
LOG_FILE="startup_output.log"

{
    echo "=== BASH STARTUP SCRIPT STARTED ==="
    date
    echo "PWD: $PWD"
    echo "Python version:"
    python --version
    echo ""
    echo "Current directory contents:"
    ls -la
    echo ""
    echo "Starting Python bot with unbuffered output..."
    python -u PUBobot2.py
} | tee -a "$LOG_FILE"
