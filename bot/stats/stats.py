# -*- coding: utf-8 -*-
import time
import datetime
import asyncio
import bot
from core.console import log
from core.database import db
from core.utils import iter_to_dict, find, get_nick

# All database table definitions are deferred to initialization
# to avoid blocking at module import time

async def ensure_tables():
	"""Initialize all database tables needed for stats module"""
	
	await db.ensure_table(dict(
		tname="players",
		columns=[
			dict(cname="user_id", ctype=db.types.int),
			dict(cname="name", ctype=db.types.str),
			dict(cname="allow_dm", ctype=db.types.bool),
			dict(cname="expire", ctype=db.types.int)
		],
		primary_keys=["user_id"]
	))

	await db.ensure_table(dict(
		tname="qc_players",
		columns=[
			dict(cname="channel_id", ctype=db.types.int),
			dict(cname="user_id", ctype=db.types.int),
			dict(cname="nick", ctype=db.types.str),
			dict(cname="is_hidden", ctype=db.types.bool, default=0),
			dict(cname="rating", ctype=db.types.int),
			dict(cname="deviation", ctype=db.types.int),
			dict(cname="wins", ctype=db.types.int, notnull=True, default=0),
			dict(cname="losses", ctype=db.types.int, notnull=True, default=0),
			dict(cname="draws", ctype=db.types.int, notnull=True, default=0),
			dict(cname="streak", ctype=db.types.int, notnull=True, default=0),
			dict(cname="last_ranked_match_at", ctype=db.types.int, notnull=False)
		],
		primary_keys=["user_id", "channel_id"]
	))

	await db.ensure_table(dict(
		tname="qc_rating_history",
		columns=[
			dict(cname="id", ctype=db.types.int, autoincrement=True),
			dict(cname="channel_id", ctype=db.types.int),
			dict(cname="user_id", ctype=db.types.int),
			dict(cname="at", ctype=db.types.int),
			dict(cname="rating_before", ctype=db.types.int),
			dict(cname="rating_change", ctype=db.types.int),
			dict(cname="deviation_before", ctype=db.types.int),
			dict(cname="deviation_change", ctype=db.types.int),
			dict(cname="match_id", ctype=db.types.int),
			dict(cname="reason", ctype=db.types.str)
		],
		primary_keys=["id"]
	))

	await db.ensure_table(dict(
		tname="qc_matches",
		columns=[
			dict(cname="match_id", ctype=db.types.int),
			dict(cname="channel_id", ctype=db.types.int),
			dict(cname="queue_id", ctype=db.types.int),
			dict(cname="queue_name", ctype=db.types.str),
			dict(cname="at", ctype=db.types.int),
			dict(cname="alpha_name", ctype=db.types.str),
			dict(cname="beta_name", ctype=db.types.str),
			dict(cname="ranked", ctype=db.types.bool),
			dict(cname="winner", ctype=db.types.bool),
			dict(cname="alpha_score", ctype=db.types.int),
			dict(cname="beta_score", ctype=db.types.int),
			dict(cname="maps", ctype=db.types.str)
		],
		primary_keys=["match_id"]
	))

	await db.ensure_table(dict(
		tname="qc_match_id_counter",
		columns=[
			dict(cname="next_id", ctype=db.types.int)
		]
	))

	await db.ensure_table(dict(
		tname="qc_player_matches",
		columns=[
			dict(cname="match_id", ctype=db.types.int),
			dict(cname="channel_id", ctype=db.types.int),
			dict(cname="user_id", ctype=db.types.int),
			dict(cname="nick", ctype=db.types.str),
			dict(cname="team", ctype=db.types.bool)
		],
		primary_keys=["match_id", "user_id"]
	))

	await db.ensure_table(dict(
		tname="disabled_guilds",
		columns=[
			dict(cname="guild_id", ctype=db.types.int)
		],
		primary_keys=["guild_id"]
	))


async def check_match_id_counter():
	"""
	Set to current max match_id+1 if not persist or less
	"""
	m = await db.select_one(('match_id',), 'qc_matches', order_by='match_id', limit=1)
	next_known_match = m['match_id']+1 if m else 0
	counter = await db.select_one(('next_id',), 'qc_match_id_counter')
	if counter is None:
		await db.insert('qc_match_id_counter', dict(next_id=next_known_match))
	elif next_known_match > counter['next_id']:
		await db.update('qc_match_id_counter', dict(next_id=next_known_match))


async def next_match():
	""" Increase match_id counter, return current match_id """
	counter = await db.select_one(('next_id',), 'qc_match_id_counter')
	await db.update('qc_match_id_counter', dict(next_id=counter['next_id']+1))
	log.debug(f"Current match_id is {counter['next_id']}")
	return counter['next_id']


async def register_match_unranked(ctx, m):
	await db.insert('qc_matches', dict(
		match_id=m.id, channel_id=m.qc.id, queue_id=m.queue.cfg.p_key, queue_name=m.queue.name,
		alpha_name=m.teams[0].name, beta_name=m.teams[1].name,
		at=int(time.time()), ranked=0, winner=None, maps="\n".join(m.maps)
	))

	await db.insert_many('qc_players', (
		dict(channel_id=m.qc.id, user_id=p.id)
		for p in m.players
	), on_dublicate="ignore")

	for p in m.players:
		nick = get_nick(p)
		await db.update(
			"qc_players",
			dict(nick=nick),
			keys=dict(channel_id=m.qc.id, user_id=p.id)
		)

		if p in m.teams[0]:
			team = 0
		elif p in m.teams[1]:
			team = 1
		else:
			team = None

		await db.insert(
			'qc_player_matches',
			dict(match_id=m.id, channel_id=m.qc.id, user_id=p.id, nick=nick, team=team)
		)


async def register_match_ranked(ctx, m):
	now = int(time.time())

	await db.insert('qc_matches', dict(
		match_id=m.id, channel_id=m.qc.id, queue_id=m.queue.cfg.p_key, queue_name=m.queue.name,
		alpha_name=m.teams[0].name, beta_name=m.teams[1].name,
		at=now, ranked=1, winner=m.winner,
		alpha_score=m.scores[0], beta_score=m.scores[1], maps="\n".join(m.maps)
	))

	for channel_id in {m.qc.id, m.qc.rating.channel_id}:
		await db.insert_many('qc_players', (
			dict(channel_id=channel_id, user_id=p.id, nick=get_nick(p))
			for p in m.players
		), on_dublicate="ignore")

	results = [[
		await m.qc.rating.get_players((p.id for p in m.teams[0])),
		await m.qc.rating.get_players((p.id for p in m.teams[1])),
	]]

	# Handle "In Progress" substitutions for rating calculation
	# For subs marked as "In Progress" who lose, the original player takes the MMR loss
	alpha_ids = [p.id for p in m.teams[0]]
	beta_ids = [p.id for p in m.teams[1]]
	in_progress_subs_by_team = {0: {}, 1: {}}  # {team_idx: {current_player_id: original_player_id}}
	
	if m.id in bot.sub_tracking:
		losing_team_idx = None if m.winner is None else (1 if m.winner == 0 else 0)
		
		if losing_team_idx is not None:
			for sub_id, (original_id, status) in bot.sub_tracking[m.id].items():
				if status == "In Progress":
					# Find which team has this sub and if it's the losing team
					if sub_id in alpha_ids and losing_team_idx == 0:
						in_progress_subs_by_team[0][sub_id] = original_id
						alpha_ids[alpha_ids.index(sub_id)] = original_id
					elif sub_id in beta_ids and losing_team_idx == 1:
						in_progress_subs_by_team[1][sub_id] = original_id
						beta_ids[beta_ids.index(sub_id)] = original_id

	# Build metadata for rating system
	captains_set = {c.id for c in m.captains} if hasattr(m, 'captains') else set()
	alpha_meta = {
		'members': {p.id: p for p in m.teams[0]},
		'draft_positions': m.draft_positions if hasattr(m, 'draft_positions') else {},
		'captains': {c.id for c in m.captains if c in m.teams[0]} if hasattr(m, 'captains') else set()
	}
	beta_meta = {
		'members': {p.id: p for p in m.teams[1]},
		'draft_positions': m.draft_positions if hasattr(m, 'draft_positions') else {},
		'captains': {c.id for c in m.captains if c in m.teams[1]} if hasattr(m, 'captains') else set()
	}

	# Get ratings for the teams used in calculation (may include original players for In Progress subs)
	alpha_ratings = await m.qc.rating.get_players(alpha_ids)
	beta_ratings = await m.qc.rating.get_players(beta_ids)

	if m.winner is None:  # draw
		after = m.qc.rating.rate(winners=alpha_ratings, losers=beta_ratings, draw=True, winner_meta=alpha_meta, loser_meta=beta_meta)
		results.append(after)
	else:  # Determine winner based on final match outcome
		if m.winner == 0:
			# Team 0 (alpha) won
			after = m.qc.rating.rate(winners=alpha_ratings, losers=beta_ratings, draw=False, winner_meta=alpha_meta, loser_meta=beta_meta)
		else:
			# Team 1 (beta) won  
			after = m.qc.rating.rate(winners=beta_ratings, losers=alpha_ratings, draw=False, winner_meta=beta_meta, loser_meta=alpha_meta)
			after = after[::-1]  # Swap back to standard team order
		results.append(after)

	after = iter_to_dict((*results[-1][0], *results[-1][1]), key='user_id')
	before = iter_to_dict((*results[0][0], *results[0][1]), key='user_id')

	# For In Progress subs on losing team, add their unchanged rating to the after dict for embed display
	# Also ensure we have before data for all current match players
	for p in m.players:
		if p.id not in before:
			# Get the before data for this player in case it's missing
			player_ratings = await m.qc.rating.get_players((p.id,))
			if player_ratings:
				before[p.id] = player_ratings[0]
		
		# Check if this player is an In Progress sub on losing team
		if m.id in bot.sub_tracking and p.id in bot.sub_tracking[m.id]:
			original_id, status = bot.sub_tracking[m.id][p.id]
			if status == "In Progress":
				losing_team_idx = None if m.winner is None else (1 if m.winner == 0 else 0)
				team_idx = 0 if p in m.teams[0] else 1
				if team_idx == losing_team_idx:
					# This is an In Progress sub on losing team - they keep their unchanged rating in the embed
					if p.id not in after:
						after[p.id] = before[p.id]

	# Process all match players
	for p in m.players:
		nick = get_nick(p)
		team = 0 if p in m.teams[0] else 1

		# Check if this player was a sub with In Progress status on the losing team
		is_in_progress_sub = False
		original_id = None
		if m.id in bot.sub_tracking and p.id in bot.sub_tracking[m.id]:
			original_id, status = bot.sub_tracking[m.id][p.id]
			if status == "In Progress":
				# Determine if this was the losing team
				losing_team_idx = None if m.winner is None else (1 if m.winner == 0 else 0)
				if team == losing_team_idx:
					is_in_progress_sub = True

		# For In Progress subs on losing team: keep their rating unchanged
		if is_in_progress_sub:
			current_rating = before[p.id]['rating']
			await db.update(
				"qc_players",
				dict(
					nick=nick,
					rating=current_rating,
					deviation=before[p.id]['deviation'],
					wins=before[p.id]['wins'],
					losses=before[p.id]['losses'],
					draws=before[p.id]['draws'],
					streak=before[p.id]['streak'],
					last_ranked_match_at=now,
				),
				keys=dict(channel_id=m.qc.rating.channel_id, user_id=p.id)
			)
			rating_change = 0
		else:
			# Normal flow: apply calculated rating change
			rating_data = after.get(p.id, before[p.id])
			await db.update(
				"qc_players",
				dict(
					nick=nick,
					rating=rating_data['rating'],
					deviation=rating_data['deviation'],
					wins=rating_data['wins'],
					losses=rating_data['losses'],
					draws=rating_data['draws'],
					streak=rating_data['streak'],
					last_ranked_match_at=now,
				),
				keys=dict(channel_id=m.qc.rating.channel_id, user_id=p.id)
			)
			rating_change = rating_data['rating'] - before[p.id]['rating']

		await db.insert(
			'qc_player_matches',
			dict(match_id=m.id, channel_id=m.qc.id, user_id=p.id, nick=nick, team=team)
		)
		
		await db.insert('qc_rating_history', dict(
			channel_id=m.qc.rating.channel_id,
			user_id=p.id,
			at=now,
			rating_before=before[p.id]['rating'],
			rating_change=rating_change,
			deviation_before=before[p.id]['deviation'],
			deviation_change=0 if is_in_progress_sub else (after.get(p.id, before[p.id])['deviation']-before[p.id]['deviation']),
			match_id=m.id,
			reason=m.queue.name
		))
		
		# Also update the original player's rating if this was an In Progress sub applying loss to them
		if is_in_progress_sub and original_id and original_id in after:
			original_before = before[original_id]
			original_after = after[original_id]
			
			await db.update(
				"qc_players",
				dict(
					nick=get_nick(p),
					rating=original_after['rating'],
					deviation=original_after['deviation'],
					wins=original_after['wins'],
					losses=original_after['losses'],
					draws=original_after['draws'],
					streak=original_after['streak'],
					last_ranked_match_at=now,
				),
				keys=dict(channel_id=m.qc.rating.channel_id, user_id=original_id)
			)
			
			await db.insert('qc_rating_history', dict(
				channel_id=m.qc.rating.channel_id,
				user_id=original_id,
				at=now,
				rating_before=original_before['rating'],
				rating_change=original_after['rating']-original_before['rating'],
				deviation_before=original_before['deviation'],
				deviation_change=original_after['deviation']-original_before['deviation'],
				match_id=m.id,
				reason=f"{m.queue.name} (substitute)"
			))

	await m.qc.update_rating_roles(*m.players)
	await m.print_rating_results(ctx, before, after)


async def undo_match(ctx, match_id):
	match = await db.select_one(('ranked', 'winner'), 'qc_matches', where=dict(match_id=match_id, channel_id=ctx.qc.id))
	if not match:
		return False

	if match['ranked']:
		p_matches = await db.select(('user_id', 'team'), 'qc_player_matches', where=dict(match_id=match_id))
		p_history = iter_to_dict(
			await db.select(
				('user_id', 'rating_change', 'deviation_change'), 'qc_rating_history', where=dict(match_id=match_id)
			), key='user_id'
		)
		stats = iter_to_dict(
			await ctx.qc.rating.get_players((p['user_id'] for p in p_matches)), key='user_id'
		)

		for p in p_matches:
			new = stats[p['user_id']]
			changes = p_history[p['user_id']]

			print(match['winner'])
			if match['winner'] is None:
				new['draws'] = max((new['draws'] - 1, 0))
			elif match['winner'] == p['team']:
				new['wins'] = max((new['wins'] - 1, 0))
			else:
				new['losses'] = max((new['losses'] - 1, 0))

			new['rating'] = max((new['rating']-changes['rating_change'], 0))
			new['deviation'] = max((new['deviation']-changes['deviation_change'], 0))

			await db.update("qc_players", new, keys=dict(channel_id=ctx.qc.rating.channel_id, user_id=p['user_id']))
		await db.delete("qc_rating_history", where=dict(match_id=match_id))
		members = (ctx.channel.guild.get_member(p['user_id']) for p in p_matches)
		await ctx.qc.update_rating_roles(*(m for m in members if m is not None))

	await db.delete('qc_player_matches', where=dict(match_id=match_id))
	await db.delete('qc_matches', where=dict(match_id=match_id))
	return True


async def reset_channel(channel_id):
	where = {'channel_id': channel_id}
	await db.delete("qc_players", where=where)
	await db.delete("qc_rating_history", where=where)
	await db.delete("qc_matches", where=where)
	await db.delete("qc_player_matches", where=where)


async def reset_player(channel_id, user_id):
	where = {'channel_id': channel_id, 'user_id': user_id}
	await db.delete("qc_players", where=where)
	await db.delete("qc_rating_history", where=where)
	await db.delete("qc_player_matches", where=where)


async def replace_player(channel_id, user_id1, user_id2, new_nick):
	await db.delete("qc_players", {'channel_id': channel_id, 'user_id': user_id2})
	where = {'channel_id': channel_id, 'user_id': user_id1}
	await db.update("qc_players", {'user_id': user_id2, 'nick': new_nick}, where)
	await db.update("qc_rating_history", {'user_id': user_id2}, where)
	await db.update("qc_player_matches", {'user_id': user_id2}, where)


async def qc_stats(channel_id):
	data = await db.fetchall(
		"SELECT `queue_name`, COUNT(*) as count FROM `qc_matches` WHERE `channel_id`=%s " +
		"GROUP BY `queue_name` ORDER BY count DESC",
		(channel_id,)
	)
	stats = dict(total=sum((i['count'] for i in data)))
	stats['queues'] = data
	return stats


async def user_stats(channel_id, user_id):
	data = await db.fetchall(
		"SELECT `queue_name`, COUNT(*) as count FROM `qc_player_matches` AS pm " +
		"JOIN `qc_matches` AS m ON pm.match_id=m.match_id " +
		"WHERE pm.channel_id=%s AND user_id=%s " +
		"GROUP BY m.queue_name ORDER BY count DESC",
		(channel_id, user_id)
	)
	stats = dict(total=sum((i['count'] for i in data)))
	stats['queues'] = data
	return stats


async def top(channel_id, time_gap=None):
	total = await db.fetchone(
		"SELECT COUNT(*) as count FROM `qc_matches` WHERE channel_id=%s" + (f" AND at>{time_gap} " if time_gap else ""),
		(channel_id, )
	)

	data = await db.fetchall(
		"SELECT p.nick as nick, COUNT(*) as count FROM `qc_player_matches` AS pm " +
		"JOIN `qc_players` AS p ON pm.user_id=p.user_id AND pm.channel_id=p.channel_id " +
		"JOIN `qc_matches` AS m ON pm.match_id=m.match_id " +
		"WHERE pm.channel_id=%s " +
		(f"AND m.at>{time_gap} " if time_gap else "") +
		"GROUP BY p.user_id ORDER BY count DESC LIMIT 10",
		(channel_id, )
	)
	stats = dict(total=total['count'])
	stats['players'] = data
	return stats


async def last_games(channel_id):
	#  get last played ranked match for all players
	data = await db.fetchall(
		"SELECT tmp.at, p.* " +
		"FROM `qc_players` AS p " +
		"LEFT JOIN (" +
		"  SELECT MAX(h.at) AS at, h.user_id FROM `qc_rating_history` AS h" +
		"    WHERE h.channel_id=%s AND h.match_id IS NOT NULL" +
		"    GROUP BY h.user_id" +
		") AS tmp ON p.user_id=tmp.user_id " +
		"WHERE p.channel_id=%s",
		(channel_id, channel_id)
	)
	return data


class StatsJobs:

	def __init__(self):
		self.next_decay_at = int(self.next_monday().timestamp())

	@staticmethod
	def next_monday():
		d = datetime.datetime.today().replace(hour=0, minute=0, second=0, microsecond=0)
		d += datetime.timedelta(days=1)
		while d.weekday() != 0:  # 0 for monday
			d += datetime.timedelta(days=1)
		return d

	@staticmethod
	def tomorrow():
		d = datetime.datetime.today().replace(hour=0, minute=0, second=0, microsecond=0)
		d += datetime.timedelta(days=1)
		return d

	@staticmethod
	async def apply_rating_decays():
		log.info("--- Applying weekly deviation decays ---")
		for qc in bot.queue_channels.values():
			await qc.apply_rating_decay()
			await asyncio.sleep(1)

	async def think(self, frame_time):
		if frame_time > self.next_decay_at:
			self.next_decay_at = int(self.next_monday().timestamp())
			asyncio.create_task(self.apply_rating_decays())


jobs = StatsJobs()
