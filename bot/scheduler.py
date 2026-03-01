# -*- coding: utf-8 -*-
import time
import asyncio
from datetime import datetime
from nextcord import Embed, Color
from core.client import dc
from core.console import log
from . import main as bot_main


class Scheduler:
	"""
	Handles scheduled tasks like hourly countdowns.
	Configure by setting the channel ID: scheduler.countdown_channel_id = YOUR_CHANNEL_ID
	"""

	def __init__(self):
		self.countdown_channel_id = None  # Set this to your Discord channel ID
		self.countdown_message = None
		self.safe_to_queue_message = None
		self.countdown_active = False  # Track if we're in the countdown period
		self.last_alert_resend_time = 0  # Track when alert was last resent
		self.last_triggered_minute = None
		self.timer_task = None
		self.state_save_task = None  # Task for periodic state saving

	def start(self):
		"""Start the dedicated timer task and state save task"""
		if self.timer_task is None or self.timer_task.done():
			self.timer_task = asyncio.create_task(self._timer_loop())
			log.info("Countdown scheduler timer started")
		
		if self.state_save_task is None or self.state_save_task.done():
			self.state_save_task = asyncio.create_task(self._state_save_loop())
			log.info("Periodic state save task started")

	async def _timer_loop(self):
		"""Dedicated task that triggers at exact :33 mark to start countdown and :42 to end"""
		while True:
			try:
				now = datetime.now()
				current_minute = now.minute
				
				# Check if we need to start countdown at :33
				if current_minute == 33:
					if not self.countdown_active:
						await self.start_countdown()
				# Check if we need to end countdown at :42
				elif current_minute == 42:
					if self.countdown_active:
						await self.end_countdown()
				
				# Sleep for 10 seconds and check again
				await asyncio.sleep(10)
				
			except Exception as e:
				log.error(f"Error in countdown timer loop: {e}")
				# Wait 30 seconds before retrying
				await asyncio.sleep(30)

	async def _state_save_loop(self):
		"""Periodic task that saves bot state every 30 seconds"""
		while True:
			try:
				# Sleep 30 seconds between saves
				await asyncio.sleep(30)
				# Save state without blocking
				bot_main.save_state()
			except Exception as e:
				log.error(f"Error in state save loop: {e}")
				# Continue trying even if save fails
				await asyncio.sleep(30)

	async def think(self, frame_time):
		"""Called every ~1 second from the main event loop"""
		# Currently unused - countdown messages are now managed by timer and message events
		pass

	async def start_countdown(self):
		"""Send the 41 Alert at :33"""
		if not self.countdown_channel_id:
			return
		
		# Delete previous safe to queue message if it exists
		if self.safe_to_queue_message:
			try:
				await self.safe_to_queue_message.delete()
				log.info("Deleted previous safe to queue message")
			except Exception as e:
				log.error(f"Failed to delete previous safe to queue message: {e}")
			self.safe_to_queue_message = None
			
		channel = dc.get_channel(self.countdown_channel_id)
		if not channel:
			log.error(f"Could not find countdown channel with ID {self.countdown_channel_id}")
			return

		try:
			self.countdown_active = True
			self.last_alert_resend_time = time.time()
			embed = Embed(
				title="⚠️ 41 Alert - DO NOT QUEUE ⚠️",
				color=Color.orange()
			)
			message = await channel.send(embed=embed)
			self.countdown_message = message
			log.info(f"41 Alert started in channel {channel.name} (#{self.countdown_channel_id})")
		except Exception as e:
			log.error(f"Failed to send countdown message: {e}")

	async def resend_alert_if_active(self):
		"""Resend the 41 Alert to keep it at the bottom if countdown is active"""
		if not self.countdown_active or not self.countdown_channel_id:
			return

		# Check if 30 seconds have passed since last resend
		current_time = time.time()
		if current_time - self.last_alert_resend_time < 30:
			return

		channel = dc.get_channel(self.countdown_channel_id)
		if not channel:
			return

		try:
			# Delete old message if it exists
			if self.countdown_message:
				try:
					await self.countdown_message.delete()
				except Exception as e:
					log.error(f"Failed to delete old countdown message: {e}")
			
			# Send new message to keep it at bottom
			embed = Embed(
				title="⚠️ 41 Alert - DO NOT QUEUE ⚠️",
				color=Color.orange()
			)
			message = await channel.send(embed=embed)
			self.countdown_message = message
			self.last_alert_resend_time = current_time
		except Exception as e:
			log.error(f"Failed to resend countdown alert: {e}")

	async def end_countdown(self):
		"""Called at :42 to end the countdown and send safe to queue message"""
		self.countdown_active = False
		
		# Delete the countdown message if it exists
		if self.countdown_message:
			try:
				await self.countdown_message.delete()
				log.info("Deleted countdown message")
			except Exception as e:
				log.error(f"Failed to delete countdown message: {e}")
			self.countdown_message = None
		
		# Send safe to queue message
		await self.send_safe_to_queue_message()

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
			message = await channel.send(embed=embed)
			self.safe_to_queue_message = message
			log.info("Safe to queue message sent")
		except Exception as e:
			log.error(f"Failed to send safe to queue message: {e}")


scheduler = Scheduler()
