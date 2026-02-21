import traceback
from time import time
from nextcord import ChannelType, Activity, ActivityType

from core.client import dc
from core.console import log
from core.config import cfg
import bot


@dc.event
async def on_init():
	await bot.stats.check_match_id_counter()
	bot.scheduler.start()


@dc.event
async def on_think(frame_time):
	for match in bot.active_matches:
		try:
			await match.think(frame_time)
		except Exception as e:
			log.error("\n".join([
				f"Error at Match.think().",
				f"match_id: {match.id:06d}).",
				f"{str(e)}. Traceback:\n{traceback.format_exc()}=========="
			]))
			bot.active_matches.remove(match)
			break
	await bot.expire.think(frame_time)
	await bot.noadds.think(frame_time)
	await bot.stats.jobs.think(frame_time)
	await bot.expire_auto_ready(frame_time)
	await bot.scheduler.think(frame_time)


@dc.event
async def on_message(message):
	if message.channel.type == ChannelType.private and message.author.id != dc.user.id:
		await message.channel.send(cfg.HELP)

	if message.channel.type != ChannelType.text:
		return

	if message.content == '!enable_pubobot':
		await bot.enable_channel(message)
	elif message.content == '!disable_pubobot':
		await bot.disable_channel(message)
	elif message.content.startswith('!set_countdown_channel'):
		# Handle countdown channel command
		parts = message.content.split(' ', 1)
		if len(parts) < 2:
			await message.channel.send("❌ Usage: `!set_countdown_channel #channel`")
			return
		
		channel_str = parts[1].strip()
		channel = None
		
		# Try to find channel by mention or ID
		if channel_str.startswith('<#') and channel_str.endswith('>'):
			channel_id = int(channel_str[2:-1])
			channel = message.guild.get_channel(channel_id)
		else:
			try:
				channel_id = int(channel_str)
				channel = message.guild.get_channel(channel_id)
			except ValueError:
				channel = next((c for c in message.guild.text_channels if c.name == channel_str.lstrip('#')), None)
		
		if not channel:
			await message.channel.send(f"❌ Channel '{parts[1]}' not found.")
			return
		
		# Check permissions
		if not (message.author.id == cfg.DC_OWNER_ID or message.channel.permissions_for(message.author).administrator):
			await message.channel.send("❌ You need administrator permissions to use this command.")
			return
		
		bot.scheduler.countdown_channel_id = channel.id
		await message.channel.send(f"✅ Countdown channel set to {channel.mention}")
		return
	
	# Resend the 41 Alert to the bottom if countdown is active
	await bot.scheduler.resend_alert_if_active()


@dc.event
async def on_reaction_add(reaction, user):
	if user.id != dc.user.id and reaction.message.id in bot.waiting_reactions.keys():
		await bot.waiting_reactions[reaction.message.id](reaction, user)


@dc.event
async def on_reaction_remove(reaction, user):  # FIXME: this event does not get triggered for some reason
	if user.id != dc.user.id and reaction.message.channel.id in bot.waiting_reactions.keys():
		await bot.waiting_reactions[reaction.message.id](reaction, user, remove=True)


@dc.event
async def on_ready():
	await dc.change_presence(activity=Activity(type=ActivityType.watching, name=cfg.STATUS))
	if not bot.bot_was_ready:  # Connected for the first time, load everything
		log.info(f"Logged in discord as '{dc.user.name}#{dc.user.discriminator}'.")
		log.info("Loading queue channels...")
		for channel_id in await bot.QueueChannel.cfg_factory.p_keys():
			channel = dc.get_channel(channel_id)
			if channel:
				bot.queue_channels[channel_id] = await bot.QueueChannel.create(channel)
				await bot.queue_channels[channel_id].update_info(channel)
				log.info(f"\tInit channel {channel.guild.name}>#{channel.name} successful.")
			else:
				log.info(f"\tCould not reach a text channel with id {channel_id}.")

		await bot.load_state()
		bot.bot_was_ready = True
		bot.bot_ready = True
		log.info("Done.")
	else:  # Reconnected, fetch new channel objects
		bot.bot_ready = True
		log.info("Reconnected to discord.")


@dc.event
async def on_disconnect():
	log.info("Connection to discord is lost.")
	bot.bot_ready = False


@dc.event
async def on_resumed():
	log.info("Connection to discord is resumed.")
	if bot.bot_was_ready:
		bot.bot_ready = True


@dc.event
async def on_presence_update(before, after):
	if after.raw_status not in ['idle', 'offline']:
		return
	if after.id in bot.allow_offline:
		if bot.allow_offline[after.id] > int(time()):
			return
		else:
			bot.allow_offline.pop(after.id, None)

	for qc in filter(lambda i: i.guild_id == after.guild.id, bot.queue_channels.values()):
		if after.raw_status == "offline" and qc.cfg.remove_offline:
			await qc.remove_members(after, reason="offline")

		if after.raw_status == "idle" and qc.cfg.remove_afk and bot.expire.get(qc, after) is None:
			await qc.remove_members(after, reason="afk", highlight=True)


@dc.event
async def on_member_remove(member):
	for qc in filter(lambda i: i.id == member.guild.id, bot.queue_channels.values()):
		await qc.remove_members(member, reason="left guild")
