#!/usr/bin/env python3
"""Minimal test - just write to a file"""
import sys
import os

# Write to file immediately
try:
    with open('python_test.log', 'w') as f:
        f.write(f'Python {sys.version}\n')
        f.write(f'CWD: {os.getcwd()}\n')
        f.write(f'Files: {os.listdir(".")}\n')
except Exception as e:
    print(f'Error: {e}', flush=True)
    sys.exit(1)

print('Test complete', flush=True)
sys.exit(0)
