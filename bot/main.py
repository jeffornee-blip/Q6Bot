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


def save_state():
	log.info("Saving state...")
	queues = []
	for qc in bot.queue_channels.values():
		for q in qc.queues:
			if q.length > 0:
				queues.append(q.serialize())

	matches = []
	for match in bot.active_matches:
		matches.append(match.serialize())

	f = open("saved_state.json", 'w')
	f.write(json.dumps(dict(queues=queues, matches=matches, allow_offline=bot.allow_offline, expire=bot.expire.serialize(), countdown_channel_id=bot.scheduler.countdown_channel_id)))
	f.close()


async def load_state():
	try:
		with open("saved_state.json", "r") as f:
			data = json.loads(f.read())
	except IOError:
		return

	log.info("Loading state...")

	bot.allow_offline = {}  # Initialize as empty dict; timestamps don't persist across restarts


	for qd in data['queues']:
		if qd.get('queue_type') in ['PickupQueue', None]:
			try:
				await bot.PickupQueue.from_json(qd)
			except bot.Exc.ValueError as e:
				log.error(f"Failed to load queue state ({qd.get('queue_id')}): {str(e)}")
		else:
			log.error(f"Got unknown queue type '{qd.get('queue_type')}'.")

	for md in data['matches']:
		try:
			await bot.Match.from_json(md)
		except bot.Exc.ValueError as e:
			log.error(f"Failed to load match {md['match_id']}: {str(e)}")

	if 'expire' in data.keys():
		await bot.expire.load_json(data['expire'])

	if 'countdown_channel_id' in data.keys():
		bot.scheduler.countdown_channel_id = data['countdown_channel_id']
		log.info(f"Countdown channel loaded: {bot.scheduler.countdown_channel_id}")


async def remove_players(*users, reason=None):
	for qc in set((q.qc for q in bot.active_queues)):
		await qc.remove_members(*users, reason=reason)


async def expire_auto_ready(frame_time):
	for user_id, at in list(bot.auto_ready.items()):
		if at < frame_time:
			bot.auto_ready.pop(user_id)


async def initialize_factories():
	"""Initialize all database FactoryTable instances and stat tables after database connection.
	This must be called after database.connect() to avoid hanging on module import."""
	log.info("Initializing database tables...")
	try:
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
