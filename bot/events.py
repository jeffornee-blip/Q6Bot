import traceback
from nextcord import ChannelType, Activity, ActivityType, Embed, Color

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


async def handle_owner_dm(message):
	"""Handle DM commands from the bot owner."""
	try:
		await _handle_owner_dm(message)
	except Exception as e:
		await message.channel.send(f"Error: {e}")


async def _handle_owner_dm(message):
	text = message.content.strip()
	parts = text.split(None, 1)
	cmd = parts[0].lower() if parts else ""

	def parse_id(s):
		"""Strip <>, [], #, and whitespace from an ID string, then convert to int."""
		return int(s.strip("<>[]#"))

	if cmd == "!channels":
		lines = []
		for guild in dc.guilds:
			lines.append(f"**{guild.name}** (ID: {guild.id})")
			for ch in guild.text_channels:
				lines.append(f"  #{ch.name} — `{ch.id}`")
		if not lines:
			await message.channel.send("Bot is not in any guilds.")
		else:
			# Split into chunks to stay under 2000 char limit
			chunk = ""
			for line in lines:
				if len(chunk) + len(line) + 1 > 1900:
					await message.channel.send(chunk)
					chunk = ""
				chunk += line + "\n"
			if chunk:
				await message.channel.send(chunk)

	elif cmd == "!send":
		# !send <channel_id> <message>
		parts = text.split(None, 2)
		if len(parts) < 3:
			await message.channel.send("Usage: `!send <channel_id> <message>`")
			return
		try:
			channel = dc.get_channel(parse_id(parts[1]))
		except ValueError:
			await message.channel.send("Invalid channel ID.")
			return
		if not channel:
			await message.channel.send("Channel not found.")
			return
		sent = await channel.send(parts[2])
		await message.channel.send(f"Sent in #{channel.name} (msg ID: `{sent.id}`)")

	elif cmd == "!reply":
		# !reply <channel_id> <message_id> <message>
		parts = text.split(None, 3)
		if len(parts) < 4:
			await message.channel.send("Usage: `!reply <channel_id> <message_id> <message>`")
			return
		try:
			channel = dc.get_channel(parse_id(parts[1]))
			target = await channel.fetch_message(parse_id(parts[2]))
		except (ValueError, AttributeError):
			await message.channel.send("Invalid channel or message ID.")
			return
		except Exception as e:
			await message.channel.send(f"Error: {e}")
			return
		sent = await target.reply(parts[3])
		await message.channel.send(f"Replied in #{channel.name} (msg ID: `{sent.id}`)")

	elif cmd == "!dm":
		# !dm <user_id> <message>
		parts = text.split(None, 2)
		if len(parts) < 3:
			await message.channel.send("Usage: `!dm <user_id> <message>`")
			return
		try:
			user = await dc.fetch_user(parse_id(parts[1]))
		except (ValueError, Exception) as e:
			await message.channel.send(f"Could not find user: {e}")
			return
		await user.send(parts[2])
		await message.channel.send(f"DM sent to {user.name}.")

	elif cmd == "!recent":
		# !recent <channel_id> [count] — show recent messages
		parts = text.split()
		if len(parts) < 2:
			await message.channel.send("Usage: `!recent <channel_id> [count]`")
			return
		try:
			channel = dc.get_channel(parse_id(parts[1]))
		except ValueError:
			await message.channel.send("Invalid channel ID.")
			return
		if not channel:
			await message.channel.send("Channel not found.")
			return
		try:
			count = min(parse_id(parts[2]), 20) if len(parts) > 2 else 5
		except ValueError:
			count = 5
		try:
			lines = []
			async for msg in channel.history(limit=count):
				preview = msg.content[:100] if msg.content else "(no text)"
				lines.append(f"`{msg.id}` **{msg.author.name}**: {preview}")
			if lines:
				await message.channel.send("\n".join(reversed(lines)))
			else:
				await message.channel.send("No messages found.")
		except Exception as e:
			await message.channel.send(f"Error reading channel: {e}")

	elif cmd == "!ownerhelp":
		await message.channel.send(
			"**Owner DM Commands:**\n"
			"`!channels` — list all guilds & channels\n"
			"`!send <channel_id> <message>` — send a message\n"
			"`!reply <channel_id> <message_id> <message>` — reply to a message\n"
			"`!dm <user_id> <message>` — DM a user\n"
			"`!recent <channel_id> [count]` — show recent messages (max 20)\n"
			"`!ownerhelp` — show this help"
		)
	else:
		await message.channel.send(
			"Unknown command. Send `!ownerhelp` for available commands."
		)


@dc.event
async def on_message(message):
	if message.channel.type == ChannelType.private and message.author.id != dc.user.id:
		if message.author.id == cfg.DC_OWNER_ID:
			await handle_owner_dm(message)
		else:
			await message.channel.send(cfg.HELP)

	if message.channel.type != ChannelType.text:
		return

	if message.content == '!enable_pubobot':
		await bot.enable_channel(message)
	elif message.content == '!disable_pubobot':
		await bot.disable_channel(message)
	
	# Resend the 41 Alert to the bottom if countdown is active (only for non-bot messages)
	if message.author.id != dc.user.id:
		await bot.scheduler.resend_alert_if_active()

	# If a non-bot message mentions the @Q Ping role in the designated channel, send the specialty positions embed
	if message.author.id != dc.user.id and message.channel.id == 1466135433959309457 and message.role_mentions:
		q_ping_role = next((r for r in message.role_mentions if r.name == "Q Ping"), None)
		if q_ping_role and (qc := bot.queue_channels.get(message.channel.id)):
			# Find the most populated queue
			q = next(iter(sorted(
				(i for i in qc.queues if i.length),
				key=lambda i: i.length, reverse=True
			)), None)
			if q:
				title_msg = f"Please add to **{q.name}**, `{q.cfg.size - q.length}` players left!"
				embed = Embed(
					description=f"{title_msg}\n\n**Specialty Positions Needed:**\n{q._get_specialty_positions_msg()}",
					color=Color.blurple()
				)
				await message.channel.send(embed=embed)


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
	# ...existing code...
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

		# DM the owner on startup
		try:
			if cfg.DC_OWNER_ID:
				owner = await dc.fetch_user(cfg.DC_OWNER_ID)
				if owner:
					await owner.send("Bot is online. Send `!ownerhelp` for available commands.")
		except Exception as e:
			log.error(f"Failed to DM owner: {e}")

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
		return  # Player has offline immunity enabled

	for qc in filter(lambda i: i.guild_id == after.guild.id, bot.queue_channels.values()):
		if after.raw_status == "offline" and qc.cfg.remove_offline:
			await qc.remove_members(after, reason="offline")

		if after.raw_status == "idle" and qc.cfg.remove_afk and bot.expire.get(qc, after) is None:
			await qc.remove_members(after, reason="afk", highlight=True)


@dc.event
async def on_member_remove(member):
	for qc in filter(lambda i: i.id == member.guild.id, bot.queue_channels.values()):
		await qc.remove_members(member, reason="left guild")
