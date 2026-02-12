#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import time
import signal
import asyncio
import traceback
import queue
import sys
import os
from asyncio import sleep as asleep
from asyncio import iscoroutine

print("=" * 60)
print("PUBobot2 Starting...")
print("=" * 60)

# Check environment variables before loading anything
print("\n[STARTUP] Checking environment variables...")
required_vars = ['DC_BOT_TOKEN', 'DATABASE_URL']
missing_vars = []
for var in required_vars:
	if os.getenv(var):
		print(f"✓ {var} is set")
	else:
		print(f"✗ {var} is NOT set")
		missing_vars.append(var)

if missing_vars:
	print(f"\n[ERROR] Missing required environment variables: {', '.join(missing_vars)}")
	print("Cannot start bot without these variables!")
	sys.exit(1)

print("\n[STARTUP] Loading bot core modules...")
try:
	# Load bot core
	from core import config, console, database, locales, cfg_factory
	from core.client import dc
	print("[STARTUP] ✓ Core modules loaded")
except Exception as e:
	print(f"[ERROR] Failed to load core modules: {e}")
	traceback.print_exc()
	sys.exit(1)

print("[STARTUP] Connecting to database...")
loop = asyncio.get_event_loop()
try:
	loop.run_until_complete(database.db.connect())
	print("[STARTUP] ✓ Database connected")
except Exception as e:
	print(f"[ERROR] Failed to connect to database: {e}")
	print(f"[ERROR] DATABASE_URL: {os.getenv('DATABASE_URL')}")
	traceback.print_exc()
	sys.exit(1)

print("[STARTUP] Loading bot...")
try:
	# Load bot
	import bot
	print("[STARTUP] ✓ Bot loaded")
except Exception as e:
	print(f"[ERROR] Failed to load bot: {e}")
	traceback.print_exc()
	sys.exit(1)

# Load web server
print("[STARTUP] Checking web server configuration...")
if config.cfg.WS_ENABLE:
	print("[STARTUP] Web server enabled, loading...")
	try:
		from webui import webserver
		print("[STARTUP] ✓ Web server loaded")
	except Exception as e:
		print(f"[WARNING] Failed to load web server: {e}")
		webserver = False
else:
	print("[STARTUP] Web server disabled")
	webserver = False

log = console.log
log.info("=" * 60)
log.info("PUBobot2 Started Successfully")
log.info("=" * 60)
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
async def think():
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
	await database.db.close()
	if webserver:
		log.info("Closing web server.")
		webserver.srv.close()
		await webserver.srv.wait_closed()
	log.info("Closing log.")
	log.close()
	print("Exit now.")
	loop.stop()

# Login to discord
loop = asyncio.get_event_loop()
loop.create_task(think())
loop.create_task(dc.start(config.cfg.DC_BOT_TOKEN))

# At the end of startup, force update all rating roles
loop.create_task(bot.force_update.force_update_all_rating_roles())

log.info("Connecting to discord...")
loop.run_forever()
