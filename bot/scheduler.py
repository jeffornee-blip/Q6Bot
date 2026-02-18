# -*- coding: utf-8 -*-
import time
from datetime import datetime
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

	async def think(self, frame_time):
		"""Called every ~1 second from the main event loop"""
		if not self.countdown_channel_id:
			return

		current_minute = datetime.now().minute
		current_second = datetime.now().second

		# At the 32-minute mark, start countdown (only once per hour)
		if current_minute == 32 and current_second < 2:
			if self.last_triggered_minute != 32:
				await self.start_countdown()
				self.last_triggered_minute = 32
		else:
			# Reset trigger for next hour
			if self.last_triggered_minute == 32:
				self.last_triggered_minute = None

		# Update countdown every 30 seconds if active
		if self.countdown_message and self.countdown_end_time:
			time_remaining = self.countdown_end_time - frame_time
			if time_remaining > 0:
				# Only update approximately every 30 seconds
				if not hasattr(self, '_last_update_time'):
					self._last_update_time = frame_time
				if frame_time - self._last_update_time >= 30:
					await self.update_countdown(time_remaining)
					self._last_update_time = frame_time
			else:
				await self.end_countdown()

	async def start_countdown(self):
		"""Send initial countdown message at :32"""
		channel = dc.get_channel(self.countdown_channel_id)
		if not channel:
			log.error(f"Could not find countdown channel with ID {self.countdown_channel_id}")
			return

		try:
			self.countdown_end_time = time.time() + (10 * 60)  # 10 minutes
			message = await channel.send("🔔 **10-Minute Countdown Starts!** 🔔\n⏱️ 10:00 remaining")
			self.countdown_message = message
			log.info(f"Countdown started in channel {channel.name} (#{self.countdown_channel_id})")
		except Exception as e:
			log.error(f"Failed to send countdown message: {e}")

	async def update_countdown(self, seconds_remaining):
		"""Update countdown message"""
		if not self.countdown_message:
			return

		minutes = int(seconds_remaining) // 60
		seconds = int(seconds_remaining) % 60

		try:
			await self.countdown_message.edit(
				content=f"🔔 **Countdown** 🔔\n⏱️ {minutes}:{seconds:02d} remaining"
			)
		except Exception as e:
			log.error(f"Failed to update countdown: {e}")
			self.countdown_message = None

	async def end_countdown(self):
		"""Called when countdown expires"""
		if self.countdown_message:
			try:
				await self.countdown_message.edit(content="✅ **Countdown Complete!**")
				log.info("Countdown completed")
			except Exception as e:
				log.error(f"Failed to finalize countdown: {e}")
		self.countdown_message = None
		self.countdown_end_time = None


scheduler = Scheduler()
