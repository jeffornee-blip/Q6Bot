#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""PUBobot2 - Discord bot for pickup games"""

import sys
import os
import asyncio
import time
import traceback
import queue
import signal
from asyncio import sleep as asleep
from asyncio import iscoroutine

# Standard imports
import bot
from core.config import cfg
from core import console
from core import database
from core.client import dc

log = console.log

# Setup signal handlers
original_SIGINT_handler = signal.getsignal(signal.SIGINT)

def ctrl_c(sig, frame):
	bot.save_state()
	console.terminate()
	signal.signal(signal.SIGINT, original_SIGINT_handler)

signal.signal(signal.SIGINT, ctrl_c)

# Run commands from user console
async def run_console():
	try:
		cmd = console.user_input_queue.get(False)
	except queue.Empty:
		return

	log.info(cmd)
	try:
		x = eval(cmd)
		if iscoroutine(x):
			log.info(await x)
		else:
			log.info(str(x))
	except Exception as e:
		log.error("CONSOLE| ERROR: "+str(e))

# Background processes loop
async def think(loop):
	# Connect to database at startup
	await database.get_db().connect()
	
	for task in dc.events['on_init']:
		await task()

	# Loop runs roughly every 1 second
	while console.alive:
		frame_time = time.time()
		await run_console()
		for task in dc.events['on_think']:
			try:
				await task(frame_time)
			except Exception as e:
				log.error('Error running background task from {}: {}\n{}'.format(task.__module__, str(e), traceback.format_exc()))
		await asleep(1)

	# Exit signal received
	for task in dc.events['on_exit']:
		try:
			await task()
		except Exception as e:
			log.error('Error running exit task from {}: {}\n{}'.format(task.__module__, str(e), traceback.format_exc()))

	log.info("Waiting for connection to close...")
	await dc.close()

	log.info("Closing db.")
	await database.get_db().close()
	log.info("Closing log.")
	log.close()
	print("Exit now.")
	loop.stop()

# At the end of startup, force update all rating roles
# This must be run after the bot is ready and guilds are loaded
async def force_update_after_ready():
    await dc.wait_until_ready()
    await bot.force_update.force_update_all_rating_roles()

if __name__ == "__main__":
	# Get or create event loop
	loop = asyncio.get_event_loop()
	
	# Login to discord
	log.info('PUBobot2 Starting')
	log.info("Connecting to discord...")
	
	loop.create_task(think(loop))
	loop.create_task(dc.start(cfg.DC_BOT_TOKEN))
	loop.create_task(force_update_after_ready())
	
	try:
		loop.run_forever()
	except KeyboardInterrupt:
		log.info("Received shutdown signal")
	finally:
		loop.close()

