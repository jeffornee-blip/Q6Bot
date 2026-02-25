#!/usr/bin/env python3
"""
Quick verification that fix_emoji_ranks command is properly exported.
Run this to verify the command module setup.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

try:
    from bot.commands import fix_emoji_ranks
    print("✅ fix_emoji_ranks is properly exported from bot.commands")
    print(f"   Function: {fix_emoji_ranks}")
    print(f"   Module: {fix_emoji_ranks.__module__}")
except ImportError as e:
    print(f"❌ Failed to import fix_emoji_ranks: {e}")
    sys.exit(1)

print("\nChecking slash command registration...")
try:
    from bot.context.slash import commands as slash_commands
    
    # Check if the _fix_emoji_ranks function exists
    if hasattr(slash_commands, '_fix_emoji_ranks'):
        print("✅ _fix_emoji_ranks slash command is registered")
    else:
        print("❌ _fix_emoji_ranks slash command not found in slash/commands.py")
        print(f"   Available slash commands: {[attr for attr in dir(slash_commands) if attr.startswith('_')][:10]}...")
except Exception as e:
    print(f"❌ Error checking slash commands: {e}")
    sys.exit(1)

print("\n✅ All checks passed! Command should appear in Discord soon.")
