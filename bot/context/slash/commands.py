from typing import Callable
from asyncio import wait_for, shield
from asyncio.exceptions import TimeoutError as aTimeoutError
from nextcord import Interaction, SlashOption, Member, TextChannel
import traceback
import time

from core.client import dc
from core.utils import error_embed, ok_embed, parse_duration, get_nick
from core.console import log
from core.config import cfg

import bot

from . import SlashContext, autocomplete, groups

servers = getattr(cfg, "DC_SLASH_SERVERS", [])
guild_kwargs = dict(guild_ids=servers) if servers else dict()


def _auto_queue(interaction: Interaction, queue: str | None):
	qc = bot.queue_channels.get(interaction.channel_id)
	if qc and queue is None:
		if len(qc.queues) == 1:
			return qc.queues[0].name
	return queue


def _parse_duration(ctx: SlashContext, s: str):
	try:
		return parse_duration(s)
	except ValueError:
		raise bot.Exc.SyntaxError(ctx.qc.gt(
			"Invalid duration format. Syntax: 3h2m1s or 03:02:01."
		))


async def run_slash(coro: Callable, interaction: Interaction, **kwargs):
	passed_time = time.time() - (((int(interaction.id) >> 22) + 1420070400000) / 1000.0)

	if passed_time >= 3.0:
		log.error('Skipping an outdated interaction.')
		return

	if not bot.bot_ready:
		await interaction.response.send_message(
			embed=error_embed("Bot is under connection, please try again later...", title="Error")
		)
		return

	qc = bot.queue_channels.get(interaction.channel_id)
	if qc is None:
		await interaction.response.send_message(
			embed=error_embed("Not in a queue channel.", title="Error")
		)
		return

	ctx = SlashContext(qc, interaction)
	try:
		await wait_for(
			shield(run_slash_coro(ctx, coro, **kwargs)),
			timeout=max(2.5 - passed_time, 0)
		)
	except (TimeoutError, aTimeoutError):
		log.info('Deferring /slash command')
		await interaction.response.defer()


async def run_slash_coro(ctx: SlashContext, coro: Callable, **kwargs):
	log.command(
		f"{ctx.channel.guild.name} | #{ctx.channel.name} | "
		f"{get_nick(ctx.author)}: /{coro.__name__} {kwargs}"
	)

	try:
		await coro(ctx, **kwargs)
	except bot.Exc.PubobotException as e:
		await ctx.error(str(e), title=e.__class__.__name__)
	except Exception as e:
		await ctx.error(str(e), title="RuntimeError")
		log.error("\n".join([
			f"Error processing /slash command {coro.__name__}.",
			f"QC: {ctx.channel.guild.name}>#{ctx.channel.name} ({ctx.qc.id}).",
			f"Member: {ctx.author} ({ctx.author.id}).",
			f"Kwargs: {kwargs}.",
			f"Exception: {str(e)}. Traceback:\n{traceback.format_exc()}=========="
		]))


# =========================
# QUEUE ADMIN COMMANDS
# =========================

@groups.admin_queue.subcommand(name='start', description='Start the queue.')
async def _start_queue(
	interaction: Interaction,
	queue: str = SlashOption(required=False)
):
	queue = _auto_queue(interaction, queue)
	await run_slash(bot.commands.start, interaction=interaction, queue=queue)

_start_queue.on_autocomplete("queue")(autocomplete.queues)


@groups.admin_queue.subcommand(name='show', description='Show a queue configuration.')
async def _cfg_queue(
	interaction: Interaction,
	queue: str = SlashOption(required=False)
):
	queue = _auto_queue(interaction, queue)
	await run_slash(bot.commands.cfg_queue, interaction=interaction, queue=queue)

_cfg_queue.on_autocomplete("queue")(autocomplete.queues)


@groups.admin_queue.subcommand(name='set', description='Configure a queue variable.')
async def _set_queue(
	interaction: Interaction,
	queue: str = SlashOption(required=False),
	variable: str = SlashOption(),
	value: str = SlashOption()
):
	queue = _auto_queue(interaction, queue)
	await run_slash(
		bot.commands.set_queue,
		interaction=interaction,
		queue=queue,
		variable=variable,
		value=value
	)

_set_queue.on_autocomplete("queue")(autocomplete.queues)
_set_queue.on_autocomplete("variable")(autocomplete.queue_variables)


@groups.admin_queue.subcommand(name='delete', description='Delete a queue.')
async def _delete_queue(
	interaction: Interaction,
	queue: str = SlashOption(required=False)
):
	queue = _auto_queue(interaction, queue)
	await run_slash(bot.commands.delete_queue, interaction=interaction, queue=queue)

_delete_queue.on_autocomplete("queue")(autocomplete.queues)


@groups.admin_queue.subcommand(name='clear', description='Remove players from the queues.')
async def _reset(
	interaction: Interaction,
	queue: str = SlashOption(required=False)
):
	queue = _auto_queue(interaction, queue)
	await run_slash(bot.commands.reset, interaction=interaction, queue=queue)

_reset.on_autocomplete("queue")(autocomplete.queues)


@groups.admin_queue.subcommand(name='split', description='Split the queue into N matches.')
async def _split_queue(
	interaction: Interaction,
	queue: str = SlashOption(required=False),
	group_size: int = SlashOption(required=False),
	sort_by_rating: bool = SlashOption(required=False)
):
	queue = _auto_queue(interaction, queue)
	await run_slash(
		bot.commands.split,
		interaction=interaction,
		queue=queue,
		group_size=group_size,
		sort_by_rating=sort_by_rating
	)

_split_queue.on_autocomplete("queue")(autocomplete.queues)


# =========================
# CHANNEL ENABLE / DISABLE
# =========================

@groups.admin_channel.subcommand(name='enable', description='Enable the bot on this channel.')
async def enable_channel(interaction: Interaction):
	if not isinstance(interaction.channel, TextChannel):
		return await interaction.response.send_message(
			embed=error_embed('Must be used on a text channel.'), ephemeral=True
		)

	if not interaction.user.guild_permissions.administrator:
		return await interaction.response.send_message(
			embed=error_embed('You must possess server administrator permissions.'), ephemeral=True
		)

	if bot.queue_channels.get(interaction.channel_id):
		return await interaction.response.send_message(
			embed=error_embed('This channel is already enabled.'), ephemeral=True
		)

	bot.queue_channels[interaction.channel.id] = await bot.QueueChannel.create(interaction.channel)
	await interaction.response.send_message(embed=ok_embed('The bot has been enabled.'))


@groups.admin_channel.subcommand(name='disable', description='Disable the bot on this channel.')
async def disable_channel(interaction: Interaction):
	if not interaction.user.guild_permissions.administrator:
		return await interaction.response.send_message(
			embed=error_embed('You must possess server administrator permissions.'), ephemeral=True
		)

	qc = bot.queue_channels.pop(interaction.channel_id, None)
	if not qc:
		return await interaction.response.send_message(
			embed=error_embed('This channel is not enabled.'), ephemeral=True
		)

	await interaction.response.send_message(embed=ok_embed('The bot has been disabled.'))
