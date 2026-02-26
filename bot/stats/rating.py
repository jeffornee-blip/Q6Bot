# -*- coding: utf-8 -*-
import glicko2
import trueskill
import time

from core.database import db
from core.utils import find, get_nick

from bot.stats import stats


class BaseRating:

	table = "qc_players"

	def __init__(
			self, channel_id, init_rp=1500, init_deviation=300, min_deviation=None, scale=100,
			loss_scale=100, win_scale=100, draw_bonus=0, ws_boost=False, ls_boost=False
	):
		self.channel_id = channel_id
		self.init_rp = init_rp
		self.init_deviation = init_deviation
		self.min_deviation = min_deviation or 0
		self.scale = (scale or 100)/100.0
		self.win_scale = (win_scale or 100)/100.0
		self.loss_scale = (loss_scale or 100)/100.0
		self.draw_bonus = (draw_bonus or 0)/100.0
		self.ws_boost = ws_boost
		self.ls_boost = ls_boost

	def _scale_win(self, r_change):
		return r_change * self.win_scale

	def _scale_loss(self, r_change):
		return r_change * self.loss_scale

	def _scale_draw(self, r_change):
		return r_change + (abs(r_change) * self.draw_bonus)

	def _scale_changes(self, player, r_change, d_change, score):
		p = player.copy()

		if score == -1:
			r_change = self._scale_loss(r_change) * self.scale
			p['losses'] += 1
			p['streak'] = -1 if p['streak'] >= 0 else p['streak'] - 1
			if self.ls_boost and p['streak'] < -2:
				r_change = r_change * (min(abs(p['streak']), 6) / 2)
		elif score == 0:
			r_change = self._scale_draw(r_change) * self.scale
			p['draws'] += 1
			p['streak'] = 0
		elif score == 1:
			r_change = self._scale_win(r_change) * self.scale
			p['wins'] += 1
			p['streak'] = 1 if p['streak'] <= 0 else p['streak'] + 1
			if self.ws_boost and p['streak'] > 2:
				r_change = r_change * (min(p['streak'], 6) / 2)

		p['rating'] = max(0, round(p['rating'] + r_change))
		p['deviation'] = max(self.min_deviation, round(p['deviation'] + d_change))
		return p

	async def get_players(self, user_ids):
		""" Return rating or initial rating for each member """
		data = await db.select(
			['user_id', 'rating', 'deviation', 'channel_id', 'wins', 'losses', 'draws', 'streak'], self.table,
			where={'channel_id': self.channel_id}
		)
		results = []
		for user_id in user_ids:
			if d := find(lambda p: p['user_id'] == user_id, data):
				if d['rating'] is None:
					d['rating'] = self.init_rp
					d['deviation'] = self.init_deviation
				else:
					d['deviation'] = min(self.init_deviation, d['deviation'])
			else:
				d = dict(
					channel_id=self.channel_id, user_id=user_id, rating=self.init_rp,
					deviation=self.init_deviation, wins=0, losses=0, draws=0
				)
			results.append(d)
		return results

	async def set_rating(self, member, rating=None, deviation=None, penality=0, reason=None):
		old = await db.select_one(
			('rating', 'deviation'), self.table,
			where=dict(channel_id=self.channel_id, user_id=member.id)
		)

		if not old:
			rating = max(1, rating - penality if rating else self.init_rp - penality)
			await db.insert(
				self.table,
				dict(
					channel_id=self.channel_id, nick=get_nick(member), user_id=member.id,
					rating=rating, deviation=deviation or self.init_deviation
				)
			)
			old = dict(rating=self.init_rp, deviation=self.init_deviation)
		else:
			rating = max(1, rating - penality if rating else old['rating'] - penality)
			old['rating'] = old['rating'] or self.init_rp
			old['deviation'] = old['deviation'] or self.init_deviation
			await db.update(
					self.table,
					dict(rating=rating, deviation=deviation or old['deviation']),
					keys=dict(channel_id=self.channel_id, user_id=member.id)
				)

		await db.insert(
			"qc_rating_history",
			dict(
				channel_id=self.channel_id, user_id=member.id, at=int(time.time()), rating_before=old['rating'],
				deviation_before=old['deviation'], rating_change=rating-old['rating'],
				deviation_change=deviation-old['deviation'] if deviation else 0,
				match_id=None, reason=reason
			)
		)

	async def hide_player(self, user_id, hide=True):
		await db.update(self.table, dict(is_hidden=hide), keys=dict(channel_id=self.channel_id, user_id=user_id))

	async def snap_ratings(self, ranks_table):
		ranks = [i['rating'] for i in ranks_table if i['rating'] != 0]
		lowest = min(ranks)
		data = await db.select(('*',), self.table, where=dict(channel_id=self.channel_id))
		history = []
		now = int(time.time())
		for p in (p for p in data if p['rating'] is not None):
			new_rating = max([i for i in ranks if i <= p['rating']] + [lowest])
			history.append(dict(
				user_id=p['user_id'],
				channel_id=self.channel_id,
				at=now,
				rating_before=p['rating'],
				rating_change=new_rating - p['rating'],
				deviation_before=p['deviation'],
				deviation_change=0,
				match_id=None,
				reason="ratings snap"
			))
			p['rating'] = new_rating
		await db.insert_many(self.table, data, on_dublicate='replace')
		await db.insert_many('qc_rating_history', history)

	async def apply_decay(self, rating, deviation, ranks_table):
		""" Apply weekly rating and deviation decay """
		now = int(time.time())
		ranks = [i['rating'] for i in ranks_table if i['rating'] != 0]
		data = await stats.last_games(self.channel_id)
		history = []
		to_update = []
		for p in data:
			if None in (p['rating'], p['deviation'], p['at']):
				continue

			new_deviation = min((self.init_deviation, p['deviation'] + deviation))

			min_rating = max([i for i in ranks if i <= p['rating']]+[0])
			if min_rating != 0 and p['at'] < (now-(60*60*24*7)):
				new_rating = max((min_rating, p['rating']-rating))
			else:
				new_rating = p['rating']

			if new_rating != p['rating'] or new_deviation != p['deviation']:
				history.append(dict(
					user_id=p['user_id'],
					channel_id=self.channel_id,
					at=now,
					rating_before=p['rating'],
					rating_change=new_rating-p['rating'],
					deviation_before=p['deviation'],
					deviation_change=new_deviation-p['deviation'],
					match_id=None,
					reason="inactivity rating decay"
				))
				p.pop('at')
				p['deviation'] = new_deviation
				p['rating'] = new_rating
				to_update.append(p)

		if len(history):
			await db.insert_many('qc_rating_history', history)
			await db.insert_many(self.table, to_update, on_dublicate='replace')

	async def reset(self):
		data = await db.select(('user_id', 'rating', 'deviation'), self.table, where=dict(channel_id=self.channel_id))
		history = []
		now = int(time.time())

		for p in data:
			if p['rating'] is not None and (p['rating'] != self.init_rp or p['deviation'] != self.init_deviation):
				history.append(dict(
					user_id=p['user_id'],
					channel_id=self.channel_id,
					at=now,
					rating_before=p['rating'],
					rating_change=self.init_rp-p['rating'],
					deviation_before=p['deviation'],
					deviation_change=self.init_deviation-p['deviation'],
					match_id=None,
					reason="ratings reset"
				))

		await db.update(
			self.table, dict(rating=None, deviation=None), keys=dict(channel_id=self.channel_id)
		)
		if len(history):
			await db.insert_many('qc_rating_history', history)


class FlatRating(BaseRating):

	def __init__(self, **kwargs):
		super().__init__(**kwargs)

	def _scale_draw(self, r_change):
		return 10 * self.draw_bonus

	def rate(self, winners, losers, draw=False, winner_meta=None, loser_meta=None):
		r1, r2 = [], []
		if not draw:
			for p in winners:
				new = self._scale_changes(p, 10, 0, 1)
				r1.append(new)

			for p in losers:
				new = self._scale_changes(p, -10, 0, -1)
				r2.append(new)
		else:
			r1 = [self._scale_changes(p, 0, 0, 0) for p in winners]
			r2 = [self._scale_changes(p, 0, 0, 0) for p in losers]

		return [r1, r2]


class Glicko2Rating(BaseRating):

	def __init__(self, **kwargs):
		super().__init__(**kwargs)

	def rate(self, winners, losers, draw=False, winner_meta=None, loser_meta=None):
		score_w = 0.5 if draw else 1
		score_l = 0.5 if draw else 0
		r1, r2 = [], []
		print("Scores:")
		print(score_l, score_w)

		avg_w = [
			[int(sum((p['rating'] for p in winners)) / len(winners))],  # average rating
			[int(sum((p['deviation'] for p in winners)) / len(winners))],  # average deviation
			[score_l]
		]
		avg_l = [
			[int(sum((p['rating'] for p in losers)) / len(losers))],  # average rating
			[int(sum((p['deviation'] for p in losers)) / len(losers))],  # average deviation
			[score_w]
		]

		po = glicko2.Player()
		for p in winners:
			po.setRating(avg_w[0][0])
			po.setRd(p['deviation'])
			po.update_player(*avg_l)
			new = self._scale_changes(p, po.getRating() - avg_w[0][0], po.getRd() - p['deviation'], 0 if draw else 1)
			r1.append(new)

		for p in losers:
			po.setRating(avg_l[0][0])
			po.setRd(p['deviation'])
			po.update_player(*avg_w)
			new = self._scale_changes(p, po.getRating() - avg_l[0][0], po.getRd() - p['deviation'], 0 if draw else -1)
			r2.append(new)

		return [r1, r2]


class TrueSkillRating(BaseRating):

	def __init__(self, **kwargs):
		super().__init__(**kwargs)
		self.ts = trueskill.TrueSkill(
			mu=self.init_rp, sigma=self.init_deviation,
			beta=int(self.init_deviation/2), tau=int(self.init_deviation/100)
		)

	def rate(self, winners, losers, draw=False, winner_meta=None, loser_meta=None):
		g1 = [self.ts.create_rating(mu=p['rating'], sigma=p['deviation']) for p in winners]
		g2 = [self.ts.create_rating(mu=p['rating'], sigma=p['deviation']) for p in losers]
		r1, r2 = [], []

		ranks = [0, 0] if draw else [0, 1]
		g1, g2 = (list(i) for i in self.ts.rate((g1, g2), ranks=ranks))

		for p in winners:
			res = g1.pop(0)
			new = self._scale_changes(p, res.mu - p['rating'], res.sigma - p['deviation'], 0 if draw else 1)
			r1.append(new)

		for p in losers:
			res = g2.pop(0)
			new = self._scale_changes(p, res.mu - p['rating'], res.sigma - p['deviation'], 0 if draw else -1)
			r2.append(new)

		return [r1, r2]


class Quidditch6v6Rating(BaseRating):
	"""
	Competitive Quidditch 6v6 rating system with draft position and captain weighting.
	Draft picks: 1st=1.3x, 2nd=1.2x, 3rd=1.15x, 4th=1.1x, 5th=1.0x
	Captains: +1.15x multiplier
	"""

	DRAFT_MULTIPLIERS = [1.3, 1.2, 1.2, 1.15, 1.125, 1.1, 1.075, 1.05, 1.0, 1.0]  # For picks 0-9 (0-indexed)

	CAPTAIN_MULTIPLIER = 1.15
	MIN_GAIN = 10
	MIN_LOSS = 10
	K_FACTOR = 48

	def __init__(self, **kwargs):
		super().__init__(**kwargs)

	def _get_draft_multiplier(self, draft_position):
		"""Get draft multiplier based on pick position (0-indexed)"""
		if draft_position < 0 or draft_position >= len(self.DRAFT_MULTIPLIERS):
			return 1.0
		return self.DRAFT_MULTIPLIERS[draft_position]

	def _get_team_differential_multiplier(self, team_avg_rating, opponent_avg_rating, is_winner):
		"""Calculate multiplier based on team strength difference (capped at 1.5)"""
		diff = (team_avg_rating - opponent_avg_rating) / 200
		
		if is_winner:
			# Winners: less gain if favored, more if underdogs
			multiplier = 0.8 + max(0.2, min(1.5, 1 + diff))
		else:
			# Losers: more loss if favored, less if underdogs
			multiplier = 0.8 + max(0.2, min(1.5, 1 - diff))
		
		return multiplier

	def _get_streak_multiplier(self, streak, is_win):
		"""Get streak multiplier based on consecutive wins/losses
		
		Only applies multiplier if the outcome continues the streak.
		If streak is broken (e.g., win on losing streak), no multiplier.
		"""
		if streak is None:
			return 1.0
		
		# Only apply multiplier if outcome continues the streak direction
		if streak > 0 and not is_win:  # Winning streak broken by a loss
			return 1.0
		if streak < 0 and is_win:  # Losing streak broken by a win
			return 1.0
		if streak == 0:  # No active streak
			return 1.0
		
		# Streak continues - apply multiplier
		abs_streak = abs(streak)
		
		if abs_streak >= 5:
			return 1.3
		elif abs_streak >= 4:
			return 1.2
		elif abs_streak >= 3:
			return 1.1
		else:
			return 1.0

	def _calculate_expected_score(self, player_rating, opponent_avg_rating):
		"""Calculate expected win probability using Elo formula"""
		return 1 / (1 + 10 ** ((opponent_avg_rating - player_rating) / 400))

	def rate(self, winners, losers, draw=False, winner_meta=None, loser_meta=None):
		"""
		Rate teams with Quidditch weighting.
		
		Args:
			winners: List of winner player dicts
			losers: List of loser player dicts
			draw: Bool if game was a draw
			winner_meta: Dict with 'members' (Discord members), 'draft_positions', 'captains'
			loser_meta: Dict with 'members' (Discord members), 'draft_positions', 'captains'
		"""
		winner_meta = winner_meta or {'members': {}, 'draft_positions': {}, 'captains': set()}
		loser_meta = loser_meta or {'members': {}, 'draft_positions': {}, 'captains': set()}
		
		# Calculate team average ratings
		winner_avg = sum(p['rating'] for p in winners) / len(winners) if winners else self.init_rp
		loser_avg = sum(p['rating'] for p in losers) / len(losers) if losers else self.init_rp
		
		r1, r2 = [], []
		
		# Process winners
		for p in winners:
			# Score: 1 for win, 0.5 for draw, 0 for loss
			actual_score = 0.5 if draw else 1
			# Use team average vs team average for team games (not individual vs opponent)
			expected_score = self._calculate_expected_score(winner_avg, loser_avg)
			
			# Base change
			base_change = self.K_FACTOR * (actual_score - expected_score)
			
			# Apply multipliers
			draft_pos = winner_meta['draft_positions'].get(p['user_id'], 4)  # Default to 5th pick
			draft_mult = self._get_draft_multiplier(draft_pos)
			
			captain_mult = self.CAPTAIN_MULTIPLIER if p['user_id'] in winner_meta['captains'] else 1.0
			
			team_diff_mult = self._get_team_differential_multiplier(winner_avg, loser_avg, is_winner=True)
			
			streak_mult = self._get_streak_multiplier(p.get('streak', 0), is_win=True)
			
			# Final rating change
			r_change = base_change * draft_mult * captain_mult * team_diff_mult * streak_mult
			
			# Apply minimum gain
			r_change = max(self.MIN_GAIN, r_change)
			
			new = self._scale_changes(p, r_change, 0, 0 if draw else 1)
			r1.append(new)
		
		# Process losers
		for p in losers:
			# Score: 0.5 for draw, 0 for loss
			actual_score = 0.5 if draw else 0
			# Use team average vs team average for team games (not individual vs opponent)
			expected_score = self._calculate_expected_score(loser_avg, winner_avg)
			
			# Base change
			base_change = self.K_FACTOR * (actual_score - expected_score)
			
			# Apply multipliers
			draft_pos = loser_meta['draft_positions'].get(p['user_id'], 4)  # Default to 5th pick
			draft_mult = self._get_draft_multiplier(draft_pos)
			
			captain_mult = self.CAPTAIN_MULTIPLIER if p['user_id'] in loser_meta['captains'] else 1.0
			
			team_diff_mult = self._get_team_differential_multiplier(loser_avg, winner_avg, is_winner=False)
			
			streak_mult = self._get_streak_multiplier(p.get('streak', 0), is_win=False)
			
			# Final rating change
			r_change = base_change * draft_mult * captain_mult * team_diff_mult * streak_mult
			
			# Apply minimum loss (more negative)
			r_change = min(-self.MIN_LOSS, r_change)
			
			new = self._scale_changes(p, r_change, 0, 0 if draw else -1)
			r2.append(new)
		
		return [r1, r2]
