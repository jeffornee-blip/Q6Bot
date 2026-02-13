__all__ = [
	'create_pickup', 'delete_queue', 'show_queues', 'set_qc', 'set_queue', 'cfg_qc', 'cfg_queue',
	'set_qc_cfg', 'set_queue_cfg', 'reset_qc'
]

import json
from core.utils import find, get, split_big_text
from core.console import log
import bot


async def create_pickup(ctx, name: str, size: int = 8):
	""" Create new PickupQueue """
	ctx.check_perms(ctx.Perms.ADMIN)
	try:
		pq = await ctx.qc.new_queue(ctx, name, size, bot.PickupQueue)
	except ValueError as e:
		raise bot.Exc.ValueError(str(e))
	else:
		await ctx.success(f"[**{pq.name}** ({pq.status})]")


async def delete_queue(ctx, queue: str):
	""" Delete a queue """
	ctx.check_perms(ctx.Perms.ADMIN)
	if (q := get(ctx.qc.queues, name=queue)) is None:
		raise bot.Exc.NotFoundError(f"Queue '{queue}' not found on the channel..")
	await q.cfg.delete()
	ctx.qc.queues.remove(q)
	await show_queues(ctx)


async def show_queues(ctx):
	""" List all queues on the channel """
	if len(ctx.qc.queues):
		await ctx.reply("> [" + " | ".join(
			[f"**{q.name}** ({q.status})" for q in ctx.qc.queues]
		) + "]")
	else:
		await ctx.reply("> [ **no queues configured** ]")


async def set_qc(ctx, variable: str, value: str):
	""" Configure a QueueChannel variable """
	ctx.check_perms(ctx.Perms.ADMIN)

	if variable not in ctx.qc.cfg_factory.variables.keys():
		raise bot.Exc.SyntaxError(f"No such variable '{variable}'.")
	try:
		await ctx.qc.cfg.update({variable: value})
	except Exception as e:
		raise bot.Exc.ValueError(str(e))
	else:
		await ctx.success(f"Variable __{variable}__ configured.")


async def set_queue(ctx, queue: str, variable: str, value: str):
	""" Configure a Queue variable """
	ctx.check_perms(ctx.Perms.ADMIN)

	if (q := find(lambda i: i.name.lower() == queue.lower(), ctx.qc.queues)) is None:
		raise bot.Exc.SyntaxError(f"Queue '{queue}' not found on the channel.")
	if variable not in q.cfg_factory.variables.keys():
		raise bot.Exc.SyntaxError(f"No such variable '{variable}'.")

	try:
		await q.cfg.update({variable: value})
	except Exception as e:
		raise bot.Exc.ValueError(str(e))
	else:
		await ctx.success(f"**{q.name}** variable __{variable}__ configured.")


async def cfg_qc(ctx):
	""" List QueueChannel configuration """
	await ctx.ignore("Sent channel configuration in DM.")  # Have to reply to the slash command
	gen = split_big_text(
		json.dumps(ctx.qc.cfg.readable(), ensure_ascii=False, indent=2),
		prefix="```json\n", suffix="\n```", limit=2000, delimiter=",\n"
	)
	for piece in gen:
		await ctx.reply_dm(piece)


async def cfg_queue(ctx, queue: str):
	""" List a queue configuration """
	if (q := find(lambda i: i.name.lower() == queue.lower(), ctx.qc.queues)) is None:
		raise bot.Exc.SyntaxError(f"Queue '{queue}' not found on the channel.")
	await ctx.ignore(f"Sent **{queue}** configuration in DM.")  # Have to reply to the slash command
	gen = split_big_text(
		json.dumps(q.cfg.readable(), ensure_ascii=False, indent=2),
		prefix="```json\n", suffix="\n```", limit=2000, delimiter=",\n"
	)
	for piece in gen:
		await ctx.reply_dm(piece)


async def set_qc_cfg(ctx, cfg):
	""" Update QueueChannel configuration via JSON string """
	ctx.check_perms(ctx.Perms.ADMIN)
	try:
		await ctx.qc.cfg.update(json.loads(cfg))
	except Exception as e:
		raise bot.Exc.ValueError(str(e))
	else:
		await ctx.success(f"Channel configuration updated.")


async def set_queue_cfg(ctx, queue: str, cfg: str):
	""" Update queue configuration via JSON string """
	ctx.check_perms(ctx.Perms.ADMIN)
	if (q := find(lambda i: i.name.lower() == queue.lower(), ctx.qc.queues)) is None:
		raise bot.Exc.SyntaxError(f"Queue '{queue}' not found on the channel.")

	try:
		await q.cfg.update(json.loads(cfg))
	except Exception as e:
		raise bot.Exc.ValueError(str(e))
	else:
		await ctx.success(f"__{q.name}__ queue configuration updated.")


async def reset_qc(ctx):
	""" Reset QueueChannel configuration to defaults """
	ctx.check_perms(ctx.Perms.ADMIN)
	
	# Define the default ranks with correct emoji IDs
	default_ranks = [
		dict(rank="<:CHAD:1471666916040114257>", rating=0, role=None),
		dict(rank="<:WOOD:1471609879142600748>", rating=800, role=None),
		dict(rank="<:LEAD:1471609859500675082>", rating=1000, role=None),
		dict(rank="<:BRNZ:1471609838504251525>", rating=1200, role=None),
		dict(rank="<:SILV:1471609818413404191>", rating=1400, role=None),
		dict(rank="<:GOLD:1471609800042221742>", rating=1600, role=None),
		dict(rank="<:DIAM:1471609760104058880>", rating=1800, role=None),
		dict(rank="<:CHMP:1471609732853665834>", rating=2000, role=None),
		dict(rank="<:STAR:1471609701140791338>", rating=2200, role=None)
	]
	
	# Delete old config and set defaults with correct ranks
	await ctx.qc.cfg.delete()
	await ctx.qc.cfg.update({
		"emoji_ranks": True,
		"ranks": default_ranks
	})
	await ctx.success("Channel configuration reset to defaults.")
