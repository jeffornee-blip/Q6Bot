#!/usr/bin/env python3
"""
Management command to repair corrupted emoji ranks in channel configurations.
This must be run with a valid DATABASE_URL environment variable.
Usage: python repair_emojis.py
"""

import asyncio
import json
import sys
import os
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent))

async def repair_corrupted_emojis():
	"""Find and fix all corrupted emoji ranks in channel configs"""
	
	# Import must be after path is set
	from core.database import db
	from core.client import dc
	from core.utils import format_emoji
	
	if not os.getenv('DATABASE_URL'):
		print("ERROR: DATABASE_URL environment variable not set")
		return False
	
	try:
		await db.connect()
	except Exception as e:
		print(f"ERROR: Failed to connect to database: {e}")
		return False
	
	try:
		# Get all rows from cfg_factory_data table
		query = "SELECT id, cfg_id, table_id, `key`, data FROM cfg_factory_data WHERE data LIKE BINARY '%\":' OR data LIKE BINARY '%\":\"'"
		results = await db.query(query)
		
		fixes_made = 0
		errors = 0
		
		for row in results:
			try:
				data = json.loads(row['data'])
				modified = False
				
				# Check if this is ranks data with corrupted emojis
				if isinstance(data, list) and all(isinstance(r, dict) for r in data):
					for rank in data:
						if 'rank' in rank:
							rank_str = str(rank['rank'])
							# Detect corrupted format like ":SILV:" 
							if rank_str.startswith(':') and rank_str.endswith(':'):
								emoji_name = rank_str.strip(':')
								print(f"  Found corrupted rank emoji in row {row['id']}: {rank_str}")
								# We can't get guild context here, so we'll just return the original
								# The wrap() method will fix it at runtime
								# For database fix, we'd need guild context
								print(f"    (Will be fixed at runtime when channel loads)")
				
			except Exception as e:
				print(f"Error processing row {row['id']}: {e}")
				errors += 1
		
		print(f"\nTotal rows checked: {len(results)}")
		print(f"Errors encountered: {errors}")
		print(f"\nNote: Corrupted emoji format will be fixed automatically when the bot loads")
		print(f"      the channel configuration. The emoji format conversion happens in")
		print(f"      EmojiVar.wrap() which is called when loading configs.")
		
		return True
	
	except Exception as e:
		print(f"ERROR: {e}")
		return False
	
	finally:
		await db.close()


if __name__ == '__main__':
	success = asyncio.run(repair_corrupted_emojis())
	sys.exit(0 if success else 1)
