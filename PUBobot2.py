#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""PUBobot2 - Discord bot for pickup games"""

import sys
import os

# FIRST: Check if we're in build mode BEFORE importing anything else
# This prevents any blocking operations during the build verification phase
_BUILD_MODE = not os.getenv('DATABASE_URL')
if _BUILD_MODE:
	print("BUILD_MODE: No DATABASE_URL - performing verification-only startup")
	sys.exit(0)

# Now safe to import everything
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
original_SIGTERM_handler = signal.getsignal(signal.SIGTERM)

def shutdown_handler(sig, frame):
	log.info(f"=== SHUTDOWN SIGNAL {sig} RECEIVED - SAVING STATE ===")
	try:
		# Get the running event loop and save state
		try:
			loop = asyncio.get_running_loop()
			loop.run_until_complete(bot.save_state_async())
		except RuntimeError:
			# No running loop, try to run in a new loop
			asyncio.run(bot.save_state_async())
		log.info("State save complete")
		# Give time for database flush
		time.sleep(1)
	except Exception as e:
		log.error(f"Failed to save state during shutdown: {e}")
		import traceback
		traceback.print_exc()
	finally:
		log.info("Terminating...")
		console.terminate()
		signal.signal(signal.SIGINT, original_SIGINT_handler)
		signal.signal(signal.SIGTERM, original_SIGTERM_handler)

signal.signal(signal.SIGINT, shutdown_handler)
signal.signal(signal.SIGTERM, shutdown_handler)

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
	# Connect to database at startup with retries
	db_connected = False
	db = database.get_db()
	for attempt in range(1, 4):
		try:
			log.info(f"Database connection attempt {attempt}/3...")
			await asyncio.wait_for(db.connect(), timeout=30)
			db_connected = True
			log.info("Database connected successfully")
			break
		except Exception as e:
			log.error(f"Database connection attempt {attempt} failed: {e}")
			if attempt < 3:
				await asleep(5)

	if not db_connected:
		log.error("All database connection attempts failed. Cannot start without database.")
		console.terminate()
		loop.stop()
		return

	# Initialize factory tables after database connection
	try:
		await bot.initialize_factories()
	except Exception as e:
		log.error(f"Error initializing factories: {e}\n{traceback.format_exc()}")
		raise
	
	for task in dc.events['on_init']:
		try:
			await task()
		except Exception as e:
			log.error(f"Error running init task from {task.__module__}: {e}\n{traceback.format_exc()}")

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

	if db_connected:
		log.info("Closing db.")
		try:
			await asyncio.wait_for(database.get_db().close(), timeout=10)
		except asyncio.TimeoutError:
			log.error("Database close operation timed out")
		except Exception as e:
			log.error(f"Error closing database: {e}")
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
	# At this point, DATABASE_URL is guaranteed to be set (or we wouldn't reach here)
	log.info('PUBobot2 Starting')
	log.info("Connecting to discord...")
	
	# Get or create event loop
	loop = asyncio.get_event_loop()
	
	loop.create_task(think(loop))
	loop.create_task(dc.start(cfg.DC_BOT_TOKEN))
	loop.create_task(force_update_after_ready())
	
	try:
		loop.run_forever()
	except KeyboardInterrupt:
		log.info("Received shutdown signal")
	finally:
		loop.close()

