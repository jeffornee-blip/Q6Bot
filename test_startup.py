#!/usr/bin/env python3
"""Absolute minimal startup test"""
import sys
import os

# Write immediately
open('/tmp/test.txt', 'w').write('Python is running\n')
print('Python is running', flush=True)
sys.exit(0)
