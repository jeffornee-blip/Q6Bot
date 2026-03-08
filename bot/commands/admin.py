__all__ = [
	'noadds', 'noadd', 'forgive', 'rating_seed', 'rating_penality', 'rating_hide',
	'rating_reset', 'rating_snap', 'stats_reset', 'stats_reset_player', 'stats_replace_player',
	'phrases_add', 'phrases_clear', 'undo_match', 'force_checkin', 'captain_score'
]

from time import time
from datetime import timedelta
from nextcord import Member

from core.utils import seconds_to_str, get_nick
from core.database import db

import bot


async def noadds(ctx):
	data = await bot.noadds.get_noadds(ctx)
	now = int(time())
	s = "```markdown\n"
	s += ctx.qc.gt(" ID | Prisoner | Left | Reason")
	s += "\n----------------------------------------\n"
	if len(data):
		s += "\n".join((
			f" {i['id']} | {i['name']} | {seconds_to_str(max(0, (i['at'] + i['duration']) - now))} | {i['reason'] or '-'}"
			for i in data
		))
	else:
		s += ctx.qc.gt("Noadds are empty.")
	await ctx.reply(s + "\n```")


async def noadd(ctx, player: Member, duration: timedelta, reason: str = None):
	ctx.check_perms(ctx.Perms.MODERATOR)
	if not duration:
		duration = timedelta(hours=2)
	if duration > timedelta(days=365*100):
		raise bot.Exc.ValueError(ctx.qc.gt("Specified duration time is too long."))
	await bot.noadds.noadd(
		ctx=ctx, member=player, duration=int(duration.total_seconds()), moderator=ctx.author, reason=reason
	)
	await ctx.success(ctx.qc.gt("Banned **{member}** for `{duration}`.").format(
		member=get_nick(player),
		duration=duration.__str__()
	))


async def forgive(ctx, player: Member):
	ctx.check_perms(ctx.Perms.MODERATOR)
	if await bot.noadds.forgive(ctx=ctx, member=player, moderator=ctx.author):
		await ctx.success(ctx.qc.gt("Done."))
	else:
		raise bot.Exc.NotFoundError(ctx.qc.gt("Specified member is not banned."))


async def rating_seed(ctx, player: str, rating: int, deviation: int = None):
	ctx.check_perms(ctx.Perms.MODERATOR)
	if (player := await ctx.get_member(player)) is None:
		raise bot.Exc.SyntaxError(f"Specified member not found on the server.")
	if not 0 < rating < 10000 or not 0 < (deviation or 1) < 3000:
		raise bot.Exc.ValueError("Bad rating or deviation value.")

	await ctx.qc.rating.set_rating(player, rating=rating, deviation=deviation, reason="manual seeding")
	await ctx.qc.update_rating_roles(player)
	await ctx.success(ctx.qc.gt("Done."))


async def rating_penality(ctx, player: str, penality: int, reason: str = None):
	ctx.check_perms(ctx.Perms.MODERATOR)
	if (player := await ctx.get_member(player)) is None:
		raise bot.Exc.SyntaxError(f"Specified member not found on the server.")
	if abs(penality) > 10000:
		raise ValueError("Bad penality value.")
	reason = "penality: " + reason if reason else "penality by a moderator"

	await ctx.qc.rating.set_rating(player, penality=penality, reason=reason)
	await ctx.qc.update_rating_roles(player)
	await ctx.success(ctx.qc.gt("Done."))


async def rating_hide(ctx, player: str, hide: bool = True):
	ctx.check_perms(ctx.Perms.MODERATOR)
	if (player := await ctx.get_member(player)) is None:
		raise bot.Exc.SyntaxError(f"Specified member not found on the server.")
	await ctx.qc.rating.hide_player(player.id, hide=hide)
	await ctx.success(ctx.qc.gt("Done."))


async def rating_reset(ctx):
	ctx.check_perms(ctx.Perms.ADMIN)
	await ctx.qc.rating.reset()
	await ctx.success(ctx.qc.gt("Done."))


async def rating_snap(ctx):
	ctx.check_perms(ctx.Perms.ADMIN)
	await ctx.qc.rating.snap_ratings(ctx.qc._ranks_table)
	await ctx.success(ctx.qc.gt("Done."))


async def stats_reset(ctx):
	ctx.check_perms(ctx.Perms.ADMIN)
	await bot.stats.reset_channel(ctx.qc.id)
	await ctx.success(ctx.qc.gt("Done."))


async def stats_reset_player(ctx, player: str):
	ctx.check_perms(ctx.Perms.MODERATOR)
	if (player := await ctx.get_member(player)) is None:
		raise bot.Exc.SyntaxError(f"Specified member not found on the server.")

	await bot.stats.reset_player(ctx.qc.id, player.id)
	await ctx.success(ctx.qc.gt("Done."))


async def stats_replace_player(ctx, player1: str, player2: str):
	ctx.check_perms(ctx.Perms.ADMIN)
	if (player1 := await ctx.get_member(player1)) is None:
		raise bot.Exc.SyntaxError(f"Specified member not found on the server.")
	if (player2 := await ctx.get_member(player2)) is None:
		raise bot.Exc.SyntaxError(f"Specified member not found on the server.")

	await bot.stats.replace_player(ctx.qc.id, player1.id, player2.id, get_nick(player2))
	await ctx.success(ctx.qc.gt("Done."))


async def phrases_add(ctx, player: Member, phrase: str):
	ctx.check_perms(ctx.Perms.MODERATOR)
	await bot.noadds.phrases_add(ctx, player, phrase)
	await ctx.success(ctx.qc.gt("Done."))


async def phrases_clear(ctx, player: Member):
	ctx.check_perms(ctx.Perms.MODERATOR)
	await bot.noadds.phrases_clear(ctx, member=player)
	await ctx.success(ctx.qc.gt("Done."))


async def undo_match(ctx, match_id: int):
	ctx.check_perms(ctx.Perms.MODERATOR)

	result = await bot.stats.undo_match(ctx, match_id)
	if result:
		await ctx.success(ctx.qc.gt("Done."))
	else:
		raise bot.Exc.NotFoundError(ctx.qc.gt("Could not find match with specified id."))


async def force_checkin(ctx):
	""" Force all players in check-in stage to check in """
	ctx.check_perms(ctx.Perms.ADMIN)
	
	# Find the active match in this channel that is in check-in stage
	match = None
	for m in bot.active_matches:
		if m.qc == ctx.qc and m.state == m.CHECK_IN:
			match = m
			break
	
	if not match:
		raise bot.Exc.NotFoundError(ctx.qc.gt("No match in check-in stage found."))
	
	# Force all players to check in
	for player in match.players:
		match.check_in.ready_players.add(player)
	
	# Refresh the check-in, which will auto-finish if all are ready
	await match.check_in.refresh(ctx)
	await ctx.success(ctx.qc.gt("All players have been forced to check in."))


async def captain_score(ctx):
	"""Display captain scoring logic for the current active match in this channel."""
	ctx.check_perms(ctx.Perms.ADMIN)
	
	# Find the active match in this channel
	match = None
	for m in bot.active_matches:
		if m.qc == ctx.qc:
			match = m
			break
	
	if not match:
		raise bot.Exc.NotFoundError(ctx.qc.gt("No active match found in this channel."))
	
	# Get recent captains data from the database (for penalty calculation)
	recent_captains = {}
	if match.cfg['pick_captains'] == "smart":
		try:
			recent_captains_data = await db.select(
				('user_id',), 'qc_player_matches',
				where={'channel_id': ctx.qc.id, 'is_captain': 1},
				order_by='match_id DESC',
				limit=6
			)
			for m in recent_captains_data:
				user_id = m['user_id']
				recent_captains[user_id] = recent_captains.get(user_id, 0) + 1
		except:
			pass
	
	# Collect all captain pair scores
	pair_scores = []
	
	for i, p1 in enumerate(match.players):
		for p2 in match.players[i+1:]:
			# Calculate individual scoring components
			
			# Factor 1: Captain role bonus
			has_captain_role_p1 = match.cfg['captains_role_id'] in [r.id for r in p1.roles] if match.cfg['captains_role_id'] else False
			has_captain_role_p2 = match.cfg['captains_role_id'] in [r.id for r in p2.roles] if match.cfg['captains_role_id'] else False
			captain_count = sum([has_captain_role_p1, has_captain_role_p2])
			captain_bonus = 1000 if captain_count == 2 else (300 if captain_count == 1 else 0)
			
			# Factor 2: MMR difference similarity
			mmr_diff = abs(match.ratings[p1.id] - match.ratings[p2.id])
			mmr_similarity = max(0, 300 - (mmr_diff * 3 / 10))  # 300 at 0 diff, 0 at 1000 diff
			
			# Factor 3: Quidditch role bonus
			def get_quidditch_role(member):
				role_names = [r.name.lower() for r in member.roles]
				for role in ['keeper', 'seeker', 'beater', 'chaser', 'flex']:
					if role in role_names:
						return role
				return 'chaser'
			
			def get_quidditch_role_bonus(role1, role2):
				if role1 == role2:
					return 300
				if 'flex' in (role1, role2):
					other_role = role2 if role1 == 'flex' else role1
					if other_role in ['keeper', 'seeker', 'beater']:
						return 200
				return 0
			
			role1 = get_quidditch_role(p1)
			role2 = get_quidditch_role(p2)
			role_bonus = get_quidditch_role_bonus(role1, role2)
			
			# Factor 4: Recent captains penalty (-300 per appearance)
			recent_penalty = 0
			if p1.id in recent_captains:
				recent_penalty -= 300 * recent_captains[p1.id]
			if p2.id in recent_captains:
				recent_penalty -= 300 * recent_captains[p2.id]
			
			# Total score
			total_score = captain_bonus + mmr_similarity + role_bonus + recent_penalty
			
			pair_scores.append({
				'p1': p1,
				'p2': p2,
				'p1_mmr': match.ratings[p1.id],
				'p2_mmr': match.ratings[p2.id],
				'p1_role': role1,
				'p2_role': role2,
				'captain_bonus': captain_bonus,
				'mmr_similarity': int(mmr_similarity),
				'role_bonus': role_bonus,
				'recent_penalty': recent_penalty,
				'total_score': int(total_score)
			})
	
	# Sort by total score descending
	pair_scores.sort(key=lambda x: x['total_score'], reverse=True)
	
	if not pair_scores:
		await ctx.reply(ctx.qc.gt("No players in this match."))
		return
	
	# Get top 10 pairs
	top_pairs = pair_scores[:10]
	
	# Define column widths for consistent alignment
	col_players = 28
	col_mmr = 14
	col_mmr_bonus = 8
	col_roles = 18
	col_role_bonus = 8
	col_captain_bonus = 10
	col_recent_penalty = 10
	col_total = 8
	
	# Create header and separator
	header = f"{'Players':<{col_players}} {'MMR':<{col_mmr}} {'MMR+':<{col_mmr_bonus}} {'Roles':<{col_roles}} {'Role+':<{col_role_bonus}} {'Captain+':<{col_captain_bonus}} {'Recent-':<{col_recent_penalty}} {'TOTAL':<{col_total}}"
	total_width = col_players + col_mmr + col_mmr_bonus + col_roles + col_role_bonus + col_captain_bonus + col_recent_penalty + col_total + 7  # +7 for spaces between columns
	separator = "─" * total_width
	
	lines = [header, separator]
	
	for score_data in top_pairs:
		p1_nick = get_nick(score_data['p1'])[:12]
		p2_nick = get_nick(score_data['p2'])[:12]
		players_str = f"{p1_nick}/{p2_nick}"
		
		mmr_str = f"{score_data['p1_mmr']}/{score_data['p2_mmr']}"
		mmr_bonus_str = f"+{score_data['mmr_similarity']}"
		
		roles_str = f"{score_data['p1_role']}/{score_data['p2_role']}"
		role_bonus_str = f"+{score_data['role_bonus']}"
		
		captain_bonus_str = f"+{score_data['captain_bonus']}"
		recent_penalty_str = f"{score_data['recent_penalty']}"
		total_str = f"{score_data['total_score']}"
		
		line = f"{players_str:<{col_players}} {mmr_str:<{col_mmr}} {mmr_bonus_str:<{col_mmr_bonus}} {roles_str:<{col_roles}} {role_bonus_str:<{col_role_bonus}} {captain_bonus_str:<{col_captain_bonus}} {recent_penalty_str:<{col_recent_penalty}} {total_str:<{col_total}}"
		lines.append(line)
	
	# Send as code block via DM to the admin
	table_output = "```\n" + "\n".join(lines) + "\n```"
	
	try:
		await ctx.author.send(table_output)
		await ctx.ignore(ctx.qc.gt("Captain score table has been sent to your DMs."))
	except Exception as e:
		raise bot.Exc.PermissionError(ctx.qc.gt("Could not send DM. Please ensure your DMs are open."))
