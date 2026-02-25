#!/usr/bin/env python3
"""Minimal startup wrapper that writes immediately to prove Python is running"""

# FIRST POSSIBLE OPERATION
with open('python_started.txt', 'w') as f:
    f.write("Python interpreter definitely started\n")

# NOW try to import and run the main bot
try:
    import PUBobot2
except Exception as e:
    with open('python_error.txt', 'w') as f:
        f.write(f"Error importing PUBobot2: {e}\n")
        import traceback
        f.write(traceback.format_exc())
    raise
