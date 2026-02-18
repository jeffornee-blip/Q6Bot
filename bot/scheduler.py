# -*- coding: utf-8 -*-
import time
import asyncio
from datetime import datetime
from nextcord import Embed, Color
from core.client import dc
from core.console import log


class Scheduler:
	"""
	Handles scheduled tasks like hourly countdowns.
	Configure by setting the channel ID: scheduler.countdown_channel_id = YOUR_CHANNEL_ID
	"""

	def __init__(self):
		self.countdown_channel_id = None  # Set this to your Discord channel ID
		self.countdown_message = None
		self.countdown_end_time = None
		self.last_triggered_minute = None
		self.timer_task = None

	def start(self):
		"""Start the dedicated timer task"""
		if self.timer_task is None or self.timer_task.done():
			self.timer_task = asyncio.create_task(self._timer_loop())
			log.info("Countdown scheduler timer started")

	async def _timer_loop(self):
		"""Dedicated task that triggers at exact :32 mark every hour"""
		while True:
			try:
				# Calculate seconds until next :32 mark
				now = datetime.now()
				target_minute = 32
				
				# If we're at or past :32, target the next hour's :32
				if now.minute >= target_minute:
					# Calculate seconds until next hour's :32
					seconds_until_next_hour = 60 - now.second + (59 - now.minute) * 60
					sleep_seconds = seconds_until_next_hour + (target_minute * 60)
				else:
					# Calculate seconds until this hour's :32
					minutes_left = target_minute - now.minute
					seconds_left = minutes_left * 60 - now.second
					sleep_seconds = seconds_left
				
				log.info(f"Countdown timer waiting {sleep_seconds}s until next :32 mark")
				await asyncio.sleep(sleep_seconds)
				
				# Trigger the countdown
				await self.start_countdown()
				
			except Exception as e:
				log.error(f"Error in countdown timer loop: {e}")
				# Wait 30 seconds before retrying
				await asyncio.sleep(30)

	async def think(self, frame_time):
		"""Called every ~1 second from the main event loop"""
		if not self.countdown_channel_id:
			return

		# Update countdown every 10 seconds if active
		if self.countdown_message and self.countdown_end_time:
			time_remaining = self.countdown_end_time - frame_time
			if time_remaining > 0:
				# Only update approximately every 10 seconds
				if not hasattr(self, '_last_update_time'):
					self._last_update_time = frame_time
				if frame_time - self._last_update_time >= 10:
					await self.update_countdown(time_remaining)
					self._last_update_time = frame_time
			else:
				await self.end_countdown()

	async def start_countdown(self):
		"""Send initial countdown message at :32"""
		if not self.countdown_channel_id:
			return
			
		channel = dc.get_channel(self.countdown_channel_id)
		if not channel:
			log.error(f"Could not find countdown channel with ID {self.countdown_channel_id}")
			return

		try:
			self.countdown_end_time = time.time() + (10 * 60)  # 10 minutes
			embed = Embed(
				title="⚠️ 41 Alert - DO NOT QUEUE ⚠️",
				description="Time Remaining: 10:00",
				color=Color.orange()
			)
			message = await channel.send(embed=embed)
			self.countdown_message = message
			log.info(f"Countdown started in channel {channel.name} (#{self.countdown_channel_id})")
		except Exception as e:
			log.error(f"Failed to send countdown message: {e}")

	async def update_countdown(self, seconds_remaining):
		"""Update countdown message in place"""
		if not self.countdown_message:
			return

		minutes = int(seconds_remaining) // 60
		seconds = int(seconds_remaining) % 60

		try:
			embed = Embed(
				title="⚠️ 41 Alert - DO NOT QUEUE ⚠️",
				description=f"Time Remaining: {minutes}:{seconds:02d}",
				color=Color.orange()
			)
			await self.countdown_message.edit(embed=embed)
		except Exception as e:
			log.error(f"Failed to update countdown: {e}")
			self.countdown_message = None

	async def end_countdown(self):
		"""Called when countdown expires - update timer to 00:00 and send safe to queue message"""
		if self.countdown_message:
			try:
				embed = Embed(
					title="⚠️ 41 Alert - DO NOT QUEUE ⚠️",
					description="Time Remaining: 00:00",
					color=Color.orange()
				)
				await self.countdown_message.edit(embed=embed)
				log.info("Countdown timer ended at 00:00")
			except Exception as e:
				log.error(f"Failed to finalize countdown timer: {e}")
		
		# Send separate safe to queue message
		await self.send_safe_to_queue_message()
		
		self.countdown_message = None
		self.countdown_end_time = None

	async def send_safe_to_queue_message(self):
		"""Send the safe to queue message at :42"""
		if not self.countdown_channel_id:
			return
		
		channel = dc.get_channel(self.countdown_channel_id)
		if not channel:
			log.error(f"Could not find countdown channel with ID {self.countdown_channel_id}")
			return
		
		try:
			embed = Embed(
				title="✅ 42 Alert - Safe to Queue ✅",
				description="Good luck, Have fun!",
				color=Color.green()
			)
			await channel.send(embed=embed)
			log.info("Safe to queue message sent")
		except Exception as e:
			log.error(f"Failed to send safe to queue message: {e}")


scheduler = Scheduler()
