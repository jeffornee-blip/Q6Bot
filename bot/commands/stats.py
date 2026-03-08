__all__ = ['last_game', 'stats', 'top', 'rank', 'leaderboard', 'season_leaderboard']

import re
from time import time
from math import ceil
from nextcord import Member, Embed, Colour

from core.utils import get, find, seconds_to_str, get_nick, discord_table
from core.database import db

import bot


async def last_game(ctx, queue: str = None, player: Member = None, match_id: int = None):
	lg = None

	if match_id:
		lg = await db.select_one(
			['*'], "qc_matches", where=dict(channel_id=ctx.qc.id, match_id=match_id), order_by="match_id", limit=1
		)
	elif queue:
		if queue := find(lambda q: q.name.lower() == queue.lower(), ctx.qc.queues):
			lg = await db.select_one(
				['*'], "qc_matches", where=dict(channel_id=ctx.qc.id, queue_id=queue.id), order_by="match_id", limit=1
			)

	elif player and (member := await ctx.get_member(player)) is not None:
		if match := await db.select_one(
			['match_id'], "qc_player_matches", where=dict(channel_id=ctx.qc.id, user_id=member.id),
			order_by="match_id", limit=1
		):
			lg = await db.select_one(
				['*'], "qc_matches", where=dict(channel_id=ctx.qc.id, match_id=match['match_id'])
			)

	else:
		lg = await db.select_one(
			['*'], "qc_matches", where=dict(channel_id=ctx.qc.id), order_by="match_id", limit=1
		)

	players = await db.select(
		['user_id', 'nick', 'team'], "qc_player_matches",
		where=dict(match_id=lg['match_id'])
	)

async def stats(ctx, player: Member = None):
	if player:
		if (member := await ctx.get_member(player)) is not None:
			data = await bot.stats.user_stats(ctx.qc.id, member.id)
			target = get_nick(member)
		else:
			raise bot.Exc.NotFoundError(ctx.qc.gt("Specified user not found."))
	else:
		data = await bot.stats.qc_stats(ctx.qc.id)
		target = f"#{ctx.channel.name}"

	embed = Embed(
		title=ctx.qc.gt("Stats for __{target}__").format(target=target),
		colour=Colour(0x50e3c2),
		description=ctx.qc.gt("**Total matches: {count}**").format(count=data['total'])
	)
	for q in data['queues']:
		embed.add_field(name=q['queue_name'], value=str(q['count']), inline=True)

	await ctx.reply(embed=embed)


async def top(ctx, period=None):
	if period in ["day", ctx.qc.gt("day")]:
		time_gap = int(time()) - (60 * 60 * 24)
	elif period in ["week", ctx.qc.gt("week")]:
		time_gap = int(time()) - (60 * 60 * 24 * 7)
	elif period in ["month", ctx.qc.gt("month")]:
		time_gap = int(time()) - (60 * 60 * 24 * 30)
	elif period in ["year", ctx.qc.gt("year")]:
		time_gap = int(time()) - (60 * 60 * 24 * 365)
	else:
		time_gap = None

	data = await bot.stats.top(ctx.qc.id, time_gap=time_gap)
	embed = Embed(
		title=ctx.qc.gt("Top 10 players for __{target}__").format(target=f"#{ctx.channel.name}"),
		colour=Colour(0x50e3c2),
		description=ctx.qc.gt("**Total matches: {count}**").format(count=data['total'])
	)
	for p in data['players']:
		embed.add_field(name=p['nick'], value=str(p['count']), inline=True)
	await ctx.reply(embed=embed)


async def rank(ctx, player: Member = None):
	target = ctx.author if not player else await ctx.get_member(player)
	if not target:
		raise bot.Exc.SyntaxError(ctx.qc.gt("Specified user not found."))

	# Get player's direct data
	p = await db.select_one(
		['user_id', 'rating', 'deviation', 'channel_id', 'wins', 'losses', 'draws', 'is_hidden', 'streak'],
		'qc_players',
		where={'channel_id': ctx.qc.rating.channel_id, 'user_id': target.id}
	)
	
	if p:
		# Calculate rank placement only if player is not hidden
		place = "?"
		if p['rating'] is not None and not p['is_hidden']:
			# Fast rank calculation: count players with higher ratings (non-hidden only)
			# Much faster than loading entire leaderboard
			ranked_players = await db.select(
				['rating'],
				'qc_players',
				where={'channel_id': ctx.qc.rating.channel_id, 'is_hidden': 0}
			)
			# Count how many non-null rated players have higher rating
			place = sum(1 for x in ranked_players if x['rating'] is not None and x['rating'] > p['rating']) + 1
		
		embed = Embed(title=f"__{get_nick(target)}__", colour=Colour(0x7289DA))
		embed.add_field(name="№", value=f"**{place}**", inline=True)
		embed.add_field(name=ctx.qc.gt("Matches"), value=f"**{(p['wins'] + p['losses'] + p['draws'])}**", inline=True)
		if p['rating']:
			embed.add_field(name=ctx.qc.gt("Rank"), value=f"{ctx.qc.rating_rank(p['rating'])['rank']}", inline=True)
			embed.add_field(name=ctx.qc.gt("Rating"), value=f"**{p['rating']}**±{p['deviation']}")
		else:
			embed.add_field(name=ctx.qc.gt("Rank"), value="?", inline=True)
			embed.add_field(name=ctx.qc.gt("Rating"), value="**?**")
		embed.add_field(
			name="W/L/D/S",
			value="**{wins}**/**{losses}**/**{draws}**/**{streak}**".format(**p),
			inline=True
		)
		embed.add_field(name=ctx.qc.gt("Winrate"), value="**{}%**\n\u200b".format(
			int(p['wins'] * 100 / (p['wins'] + p['losses'] or 1))
		), inline=True)
		if target.display_avatar:
			embed.set_thumbnail(url=target.display_avatar.url)
		changes = await db.select(
			('at', 'rating_change', 'match_id', 'reason'),
			'qc_rating_history', where=dict(user_id=target.id, channel_id=ctx.qc.rating.channel_id),
			order_by='id', limit=5
		)
		if len(changes):
			embed.add_field(
				name=ctx.qc.gt("Last changes:"),
				value="\n".join((
					"\u200b \u200b **{change}** \u200b | {ago} ago | {reason}{match_id}".format(
						ago=seconds_to_str(int(time() - c['at'])),
						reason=c['reason'],
						match_id=f"(__{c['match_id']:06d}__)" if c['match_id'] else "",
						change=("+" if c['rating_change'] >= 0 else "") + str(c['rating_change'])
					) for c in changes)
				)
			)
		await ctx.reply(embed=embed)
	else:
		raise bot.Exc.ValueError(ctx.qc.gt("No rating data found."))


async def leaderboard(ctx, page: int = 1):
	page = (page or 1) - 1

	data = await ctx.qc.get_lb()
	pages = ceil(len(await ctx.qc.get_lb())/12)
	data = data[page * 12:(page + 1) * 12]
	if not len(data):
		raise bot.Exc.NotFoundError(ctx.qc.gt("Leaderboard is empty."))

	if ctx.qc.cfg.emoji_ranks:  # display as embed message
		embed = Embed(title=f"Leaderboard - page {page+1} of {pages}", colour=Colour(0x7289DA))
		# Format with uniform monospace columns
		table_lines = []
		for n in range(len(data)):
			row = data[n]
			num = str((page*12)+n+1).rjust(2)
			# Strip emojis from nickname - keep only ASCII + basic punctuation
			nick_clean = re.sub(r'[^\x00-\x7F()\[\]-]', '', row['nick'].strip())[:20].ljust(20)
			wl = f"{row['wins']}-{row['losses']}".rjust(5)
			total_games = row['wins'] + row['losses']
			wr = f"({round(row['wins'] / total_games * 100)}%)".rjust(6) if total_games > 0 else "  (0%)"
			rating = str(row['rating']).rjust(4)
			rank = ctx.qc.rating_rank(row['rating'])['rank']
			table_lines.append(f"`{num} {nick_clean} {wl} {wr}`  {rank} {rating}")
		
		# Add header for left columns only
		table_lines.insert(0, f"`{'No':>2} {'Nickname':<20} {'W-L':>5} {'WR':>6}`")
		
		embed.add_field(
			name="—",
			value="\n".join(table_lines),
			inline=False
		)
		await ctx.reply(embed=embed)
		return

	# display as md table
	await ctx.reply(
		discord_table(
			["№", "Nickname", "W-L", "WR", "Rating"],
			[[
				(page * 12) + (n + 1),
				data[n]['nick'].strip()[:15],
				"{0}-{1}".format(
					data[n]['wins'],
					data[n]['losses']
				),
				"({0}%)".format(round(data[n]['wins'] / max(1, data[n]['wins'] + data[n]['losses']) * 100)),
				str(data[n]['rating']) + ctx.qc.rating_rank(data[n]['rating'])['rank']
			] for n in range(len(data))]
		)
	)


async def season_leaderboard(ctx, page: int = 1):
	"""Show top 12 players with minimum 20 games played"""
	page = (page or 1) - 1

	data = await ctx.qc.get_season_lb()
	pages = ceil(len(await ctx.qc.get_season_lb())/12)
	data = data[page * 12:(page + 1) * 12]
	if not len(data):
		raise bot.Exc.NotFoundError(ctx.qc.gt("Leaderboard is empty."))

	if ctx.qc.cfg.emoji_ranks:  # display as embed message
		embed = Embed(title=f"Season Leaderboard (20+ games) - page {page+1} of {pages}", colour=Colour(0x7289DA))
		# Format with uniform monospace columns
		table_lines = []
		for n in range(len(data)):
			row = data[n]
			num = str((page*12)+n+1).rjust(2)
			# Strip emojis from nickname - keep only ASCII + basic punctuation
			nick_clean = re.sub(r'[^\x00-\x7F()\[\]-]', '', row['nick'].strip())[:20].ljust(20)
			wl = f"{row['wins']}-{row['losses']}".rjust(5)
			total_games = row['wins'] + row['losses']
			wr = f"({round(row['wins'] / total_games * 100)}%)".rjust(6) if total_games > 0 else "  (0%)"
			rating = str(row['rating']).rjust(4)
			rank = ctx.qc.rating_rank(row['rating'])['rank']
			table_lines.append(f"`{num} {nick_clean} {wl} {wr}`  {rank} {rating}")
		
		# Add header for left columns only
		table_lines.insert(0, f"`{'No':>2} {'Nickname':<20} {'W-L':>5} {'WR':>6}`")
		
		embed.add_field(
			name="—",
			value="\n".join(table_lines),
			inline=False
		)
		await ctx.reply(embed=embed)
		return

	# display as md table
	await ctx.reply(
		discord_table(
			["№", "Nickname", "W-L", "WR", "Rating"],
			[[
				(page * 12) + (n + 1),
				data[n]['nick'].strip()[:15],
				"{0}-{1}".format(
					data[n]['wins'],
					data[n]['losses']
				),
				"({0}%)".format(round(data[n]['wins'] / max(1, data[n]['wins'] + data[n]['losses']) * 100)),
				str(data[n]['rating']) + ctx.qc.rating_rank(data[n]['rating'])['rank']
			] for n in range(len(data))]
		)
	)
