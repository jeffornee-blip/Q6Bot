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

# Debug: Show we started
print("DEBUG START", flush=True)
print("DEBUG IMPORTS COMPLETE", flush=True)

# Startup timeout - fail if startup takes too long
startup_timeout = 30  # seconds
startup_start_time = time.time()

def check_startup_timeout():
	elapsed = time.time() - startup_start_time
	if elapsed > startup_timeout:
		print(f"[ERROR] Startup timeout! Exceeded {startup_timeout} seconds", flush=True)
		sys.exit(1)

print("=" * 60)
print("PUBobot2 Starting...")
print("=" * 60)
print("[STARTUP] Output buffering: ENABLED - Use PYTHONUNBUFFERED=1 for real-time logs")
sys.stdout.flush()

# Check environment variables before loading anything
print("\n[STARTUP] Checking environment variables...")
sys.stdout.flush()
check_startup_timeout()
required_vars = ['DC_BOT_TOKEN', 'DATABASE_URL']
missing_vars = []
for var in required_vars:
	if os.getenv(var):
		print(f"✓ {var} is set")
	else:
		print(f"✗ {var} is NOT set")
		missing_vars.append(var)
	sys.stdout.flush()

if missing_vars:
	print(f"\n[ERROR] Missing required environment variables: {', '.join(missing_vars)}")
	print("Cannot start bot without these variables!")
	sys.stdout.flush()
	sys.exit(1)

print("\n[STARTUP] Loading bot core modules...")
sys.stdout.flush()
check_startup_timeout()
try:
	# Load bot core - step by step with debugging
	print("[STARTUP] Loading config...")
	sys.stdout.flush()
	check_startup_timeout()
	from core import config
	print("[STARTUP] ✓ config loaded")
	sys.stdout.flush()
	
	print("[STARTUP] Loading console...")
	sys.stdout.flush()
	check_startup_timeout()
	from core import console
	print("[STARTUP] ✓ console loaded")
	sys.stdout.flush()
	
	print("[STARTUP] Loading database...")
	sys.stdout.flush()
	check_startup_timeout()
	from core import database
	print("[STARTUP] ✓ database loaded")
	sys.stdout.flush()
	
	print("[STARTUP] Loading locales...")
	sys.stdout.flush()
	check_startup_timeout()
	from core import locales
	print("[STARTUP] ✓ locales loaded")
	sys.stdout.flush()
	
	print("[STARTUP] Loading cfg_factory...")
	sys.stdout.flush()
	check_startup_timeout()
	from core import cfg_factory
	print("[STARTUP] ✓ cfg_factory loaded")
	sys.stdout.flush()
	
	print("[STARTUP] Loading Discord client...")
	sys.stdout.flush()
	check_startup_timeout()
	from core.client import dc
	print("[STARTUP] ✓ Discord client loaded")
	sys.stdout.flush()
	
	print("[STARTUP] ✓ Core modules loaded")
	sys.stdout.flush()
except Exception as e:
	print(f"[ERROR] Failed to load core modules: {e}")
	traceback.print_exc()
	sys.stdout.flush()
	sys.exit(1)

print("[STARTUP] Connecting to database...")
sys.stdout.flush()
check_startup_timeout()
loop = asyncio.get_event_loop()
connection_attempts = 0
max_attempts = 3
while connection_attempts < max_attempts:
	connection_attempts += 1
	try:
		print(f"[STARTUP] Database connection attempt {connection_attempts}/{max_attempts}...")
		sys.stdout.flush()
		check_startup_timeout()
		loop.run_until_complete(database.db.connect())
		print("[STARTUP] ✓ Database connected")
		sys.stdout.flush()
		break
	except asyncio.TimeoutError:
		print(f"[WARNING] Database connection timeout on attempt {connection_attempts}/{max_attempts}")
		sys.stdout.flush()
		if connection_attempts >= max_attempts:
			print(f"[ERROR] Failed to connect to database after {max_attempts} attempts: Timeout")
			print(f"[ERROR] DATABASE_URL: {os.getenv('DATABASE_URL')}")
			sys.stdout.flush()
			sys.exit(1)
	except Exception as e:
		print(f"[WARNING] Database connection error on attempt {connection_attempts}/{max_attempts}: {e}")
		sys.stdout.flush()
		if connection_attempts >= max_attempts:
			print(f"[ERROR] Failed to connect to database: {e}")
			print(f"[ERROR] DATABASE_URL: {os.getenv('DATABASE_URL')}")
			traceback.print_exc()
			sys.stdout.flush()
			sys.exit(1)
	
	if connection_attempts < max_attempts:
		print("[STARTUP] Retrying in 2 seconds...")
		sys.stdout.flush()
		time.sleep(2)

print("[STARTUP] Loading bot...")
sys.stdout.flush()
check_startup_timeout()
try:
	# Load bot
	print("[STARTUP] Importing bot module...")
	sys.stdout.flush()
	import bot
	print("[STARTUP] ✓ Bot loaded")
	sys.stdout.flush()
except Exception as e:
	print(f"[ERROR] Failed to load bot: {e}")
	traceback.print_exc()
	sys.stdout.flush()
	sys.exit(1)

# Load web server
print("[STARTUP] Checking web server configuration...")
check_startup_timeout()
sys.stdout.flush()
if config.cfg.WS_ENABLE:
	print("[STARTUP] Web server enabled, loading...")
	sys.stdout.flush()
	check_startup_timeout()
	try:
		from webui import webserver
		print("[STARTUP] ✓ Web server loaded")
		sys.stdout.flush()
	except Exception as e:
		print(f"[WARNING] Failed to load web server: {e}")
		sys.stdout.flush()
		webserver = False
else:
	print("[STARTUP] Web server disabled")
	sys.stdout.flush()
	webserver = False

check_startup_timeout()
log = console.log
log.info("=" * 60)
log.info("PUBobot2 Started Successfully")
log.info("=" * 60)
print("[STARTUP] ✓ All startup checks complete. Bot is starting Discord connection...")
print(f"[STARTUP] Startup completed in {time.time() - startup_start_time:.2f} seconds")
sys.stdout.flush()
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
# This must be run after the bot is ready and guilds are loaded
async def force_update_after_ready():
    await dc.wait_until_ready()
    await bot.force_update.force_update_all_rating_roles()
loop.create_task(force_update_after_ready())

log.info("Connecting to discord...")
loop.run_forever()
