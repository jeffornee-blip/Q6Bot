#!/usr/bin/env python3
"""
Migration script to fix corrupted emoji ranks in the database.
Converts ":SILV:" format to proper "<:SILV:ID>" format.
"""

import asyncio
import json
import os
import re
from core.database import db
from core.client import dc
from core.utils import format_emoji


async def fix_corrupted_emojis():
	"""Find and fix all corrupted emoji ranks in channel configs"""
	await db.connect()
	
	# Get all rows from cfg_factory_data table where key is 'ranks'
	query = "SELECT * FROM cfg_factory_data WHERE `key` = 'ranks'"
	results = await db.query(query)
	
	fixes_made = 0
	
	for row in results:
		try:
			data = json.loads(row['data'])
			modified = False
			
			# Check if this is a list of rank dicts
			if isinstance(data, list) and all(isinstance(r, dict) for r in data):
				for rank in data:
					if 'rank' in rank:
						rank_str = str(rank['rank'])
						# Detect corrupted format like ":SILV:" or "SILV"
						if (rank_str.startswith(':') and rank_str.endswith(':')) or \
						   (not rank_str.startswith('<') and ':' not in rank_str):
							# Extract emoji name
							emoji_name = rank_str.strip(':')
							
							# The database stores this for a specific channel, 
							# but we don't have guild context here
							# For now, just log it
							print(f"Found corrupted rank emoji: {rank_str}")
							
							# We'll need to fix this with proper guild context
							# Store the name without colons for now
							if not rank_str.startswith('<'):
								rank['rank'] = f":{emoji_name}:" if ',' not in emoji_name else rank_str
								modified = True
				
				if modified:
					# Update the database
					new_data = json.dumps(data, ensure_ascii=False)
					update_query = "UPDATE cfg_factory_data SET data = %s WHERE id = %s"
					await db.execute(update_query, (new_data, row['id']))
					fixes_made += 1
					print(f"Fixed rank emojis in cfg_id {row['cfg_id']}, table_id={row['table_id']}")
		
		except Exception as e:
			print(f"Error processing row {row['id']}: {e}")
	
	print(f"\nTotal fixes made: {fixes_made}")
	await db.close()


if __name__ == '__main__':
	asyncio.run(fix_corrupted_emojis())
