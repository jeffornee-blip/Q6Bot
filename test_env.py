#!/usr/bin/env python3
import sys
import os

print("Python version:", sys.version)
print("Python executable:", sys.executable)
print("CWD:", os.getcwd())
print("PATH:", os.environ.get('PATH', 'NOT SET'))
print("PYTHONPATH:", os.environ.get('PYTHONPATH', 'NOT SET'))
print("DC_BOT_TOKEN:", "SET" if os.environ.get('DC_BOT_TOKEN') else "NOT SET")
print("DATABASE_URL:", "SET" if os.environ.get('DATABASE_URL') else "NOT SET")

print("\nLocal files:")
for f in os.listdir('.'):
    if not f.startswith('.'):
        print(f"  {f}")

print("\nTrying to import core...")
try:
    import core
    print("✓ core imported successfully")
except Exception as e:
    print(f"✗ Failed to import core: {e}")

print("\nTrying to import bot...")
try:
    import bot
    print("✓ bot imported successfully")
except Exception as e:
    print(f"✗ Failed to import bot: {e}")
