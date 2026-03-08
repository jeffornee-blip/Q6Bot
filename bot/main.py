# -*- coding: utf-8 -*-
import traceback
import json
from nextcord import Interaction

from core.console import log
from core.database import db
from core.config import cfg
from core.utils import error_embed, ok_embed, get

import bot


async def enable_channel(message):
	if not (message.author.id == cfg.DC_OWNER_ID or message.channel.permissions_for(message.author).administrator):
		await message.channel.send(embed=error_embed(
			"One must posses the guild administrator permissions in order to use this command."
		))
		return
	if message.channel.id not in bot.queue_channels.keys():
		bot.queue_channels[message.channel.id] = await bot.QueueChannel.create(message.channel)
		await message.channel.send(embed=ok_embed("The bot has been enabled."))
	else:
		await message.channel.send(
			embed=error_embed("The bot is already enabled on this channel.")
		)


async def disable_channel(message):
	if not (message.author.id == cfg.DC_OWNER_ID or message.channel.permissions_for(message.author).administrator):
		await message.channel.send(embed=error_embed(
			"One must posses the guild administrator permissions in order to use this command."
		))
		return
	qc = bot.queue_channels.get(message.channel.id)
	if qc:
		for queue in qc.queues:
			await queue.cfg.delete()
		await qc.cfg.delete()
		bot.queue_channels.pop(message.channel.id)
		await message.channel.send(embed=ok_embed("The bot has been disabled."))
	else:
		await message.channel.send(embed=error_embed("The bot is not enabled on this channel."))


def update_qc_lang(qc_cfg):
	bot.queue_channels[qc_cfg.p_key].update_lang()


def update_rating_system(qc_cfg):
	bot.queue_channels[qc_cfg.p_key].update_rating_system()


async def save_state_async():
	"""Async version of save_state that properly awaits database operations"""
	log.info("Saving state to database (async)...")
	queues = []
	for qc in bot.queue_channels.values():
		for q in qc.queues:
			if q.length > 0:
				queues.append(q.serialize())

	matches = []
	for match in bot.active_matches:
		matches.append(match.serialize())

	try:
		# Clear old state
		await db.delete('bot_state', where={'id': 'queue_state'})
		
		# Save new state
		await db.insert('bot_state', dict(
			id='queue_state',
			data=json.dumps(dict(
				queues=queues, 
				matches=matches, 
				allow_offline=bot.allow_offline, 
				expire=bot.expire.serialize(), 
				countdown_channel_id=bot.scheduler.countdown_channel_id
			))
		))
		log.info(f"State saved successfully to database. {len(queues)} queues, {len(matches)} matches.")
	except Exception as e:
		log.error(f"Failed to save state: {e}")
		raise


async def load_state():
	try:
		# Try to load from database first
		log.info("Loading state from database...")
		
		# Ensure table exists
		try:
			result = await db.select_one(['data'], 'bot_state', where={'id': 'queue_state'})
			if not result:
				log.info("No saved state found in database - bot_state table is empty.")
				return
			log.info(f"Found saved state in database, parsing JSON...")
			
			# Debug: check what we're trying to parse
			state_data = result.get('data') if isinstance(result, dict) else result[0]
			if not state_data:
				log.error("Database returned empty data for bot_state")
				raise ValueError("Database returned empty data")
			
			log.debug(f"Raw state data length: {len(state_data)} characters")
			data = json.loads(state_data)
			log.info(f"Successfully parsed state JSON: {len(data.get('queues', []))} queues, {len(data.get('matches', []))} matches")
		except Exception as e:
			# Table doesn't exist or query failed, try old JSON file
			log.error(f"Database state load failed - Type: {type(e).__name__}, Error: {e}", exc_info=True)
			log.info(f"Attempting to load from JSON file as fallback...")
			try:
				with open("saved_state.json", "r") as f:
					data = json.loads(f.read())
			except IOError:
				log.info("No saved state file found, starting fresh.")
				return

		log.info("Loading state into memory...")

		bot.allow_offline = data.get('allow_offline', {})

		queues_loaded = 0
		for qd in data.get('queues', []):
			if qd.get('queue_type') in ['PickupQueue', None]:
				try:
					await bot.PickupQueue.from_json(qd)
					queues_loaded += 1
					log.info(f"Loaded queue {qd.get('queue_id')} with {len(qd.get('players', []))} players")
				except bot.Exc.ValueError as e:
					log.error(f"Failed to load queue state ({qd.get('queue_id')}): {str(e)}")
			else:
				log.error(f"Got unknown queue type '{qd.get('queue_type')}'.")

		matches_loaded = 0
		for md in data.get('matches', []):
			try:
				await bot.Match.from_json(md)
				matches_loaded += 1
			except bot.Exc.ValueError as e:
				log.error(f"Failed to load match {md['match_id']}: {str(e)}")

		if 'expire' in data:
			await bot.expire.load_json(data['expire'])

		if 'countdown_channel_id' in data:
			bot.scheduler.countdown_channel_id = data['countdown_channel_id']
			log.info(f"Countdown channel loaded: {bot.scheduler.countdown_channel_id}")
		
		log.info(f"State loaded successfully: {queues_loaded} queues, {matches_loaded} matches.")
	except Exception as e:
		log.error(f"Unexpected error loading state: {e}")
		return


async def remove_players(*users, reason=None, calling_priority=None):
	"""Remove players from queues based on priority.
	
	If calling_priority is None, removes from all queues (backward compatible).
	If calling_priority is set, only removes from queues with priority <= calling_priority.
	"""
	for qc in set((q.qc for q in bot.active_queues)):
		await qc.remove_members(
			*users, 
			reason=reason,
			skip_high_priority=(calling_priority is not None),
			calling_priority=calling_priority
		)


async def expire_auto_ready(frame_time):
	for user_id, at in list(bot.auto_ready.items()):
		if at < frame_time:
			bot.auto_ready.pop(user_id)


async def initialize_factories():
	"""Initialize all database FactoryTable instances and stat tables after database connection.
	This must be called after database.connect() to avoid hanging on module import."""
	log.info("Initializing database tables...")
	try:
		# Ensure bot_state table exists for saving queue state
		await db.execute("""
			CREATE TABLE IF NOT EXISTS bot_state (
				id VARCHAR(255) PRIMARY KEY,
				data LONGTEXT NOT NULL,
				updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
			)
		""")
		log.info("  ✓ Bot state table ready")
		
		# Initialize stats tables
		log.info("  Initializing stats tables...")
		await bot.stats.ensure_tables()
		log.info("  ✓ Stats tables initialized")
		
		# Initialize noadds tables
		log.info("  Initializing noadds tables...")
		await bot.noadds.ensure_tables()
		log.info("  ✓ Noadds tables initialized")
		
		# Initialize QueueChannel factory
		log.info("  Initializing QueueChannel factory...")
		await bot.QueueChannel.cfg_factory.table.initialize()
		log.info("  ✓ QueueChannel factory initialized")
		
		# Initialize PickupQueue factory
		log.info("  Initializing PickupQueue factory...")
		await bot.PickupQueue.cfg_factory.table.initialize()
		log.info("  ✓ PickupQueue factory initialized")
		
		log.info("All database initialization complete")
	except Exception as e:
		log.error(f"Error initializing database tables: {e}\n{traceback.format_exc()}")
		raise
