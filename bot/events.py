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

		# Send deploy message to patch notes channel
		patch_notes_channel = dc.get_channel(1480019437129170975)
		if patch_notes_channel:
				try:
					from nextcord import Embed, Color
					from core.config import __version__
					embed = Embed(
						title=f"Q6 Bot — Patch Notes V{__version__}",
						color=Color.blurple()
					)
					embed.add_field(
						name="New — Season System",
						value="• `/season end` — Admins can now end the current season, archiving all player standings to a permanent record. Displays a Top 12 podium (20+ games required) with final ratings, then resets all ratings, W/L/D, and streaks for a fresh start. Match and rating history are preserved.",
						inline=False
					)
					embed.add_field(
						name="New — Role Leaderboards",
						value="• `/leaderboard_chaser`, `/leaderboard_seeker`, `/leaderboard_beater`, `/leaderboard_keeper`, `/leaderboard_flex` — View the leaderboard filtered by player role. Also available as message commands with aliases `!lbc`, `!lbs`, `!lbb`, `!lbk`, `!lbf`. Supports pagination.",
						inline=False
					)
					embed.add_field(
						name="Improved — Player Profile (`/rank`)",
						value="• **Rating Graph** — Your last 20 rating changes displayed as a visual sparkline with start and end values.\n• **Favorite Teammates** — Shows your top 3 most frequent same-team co-players and how many games you've shared.",
						inline=False
					)
					embed.add_field(
						name="Improved — 41 Alert Countdown",
						value="• The ⚠️ 41 Alert now only triggers when a draft actually completes during the :33–:41 window, instead of firing every hour regardless.\n• Continuously monitors for completed drafts — if a draft finishes at any point between :33 and :41, the alert is sent immediately.\n• The ✅ Safe to Queue message at :42 only appears if the alert was triggered.",
						inline=False
					)
					await patch_notes_channel.send(embed=embed)
					log.info("Deploy message sent.")
				except Exception as e:
					log.error(f"Failed to send deploy message: {e}")
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
