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

# IMMEDIATE STARTUP DEBUG - write to multiple outputs to ensure we see something
try:
	with open('/tmp/pubobot_startup.log', 'w') as f:
		f.write("SCRIPT STARTED\n")
except:
	pass

sys.stderr.write("PUBOBOT2 STDERR: Script started\n")
sys.stderr.flush()
print("PUBOBOT2 STDOUT: Script started", flush=True)

print("=" * 60)
print("PUBobot2 Starting...")
print("=" * 60)
sys.stdout.flush()

# Check environment variables before loading anything
print("\n[STARTUP] Checking environment variables...", flush=True)
required_vars = ['DC_BOT_TOKEN', 'DATABASE_URL']
missing_vars = []
for var in required_vars:
	if os.getenv(var):
		print(f"✓ {var} is set", flush=True)
	else:
		print(f"✗ {var} is NOT set", flush=True)
		missing_vars.append(var)

if missing_vars:
	print(f"\n[ERROR] Missing required environment variables: {', '.join(missing_vars)}", flush=True)
	print("Cannot start bot without these variables!", flush=True)
	sys.exit(1)

print("\n[STARTUP] Loading bot core modules...", flush=True)
try:
	print("[STARTUP] Loading config...", flush=True)
	from core import config
	print("[STARTUP] ✓ config loaded", flush=True)
	
	print("[STARTUP] Loading console...", flush=True)
	from core import console
	print("[STARTUP] ✓ console loaded", flush=True)
	
	print("[STARTUP] Loading database...", flush=True)
	from core import database
	print("[STARTUP] ✓ database loaded", flush=True)
	
	print("[STARTUP] Loading locales...", flush=True)
	from core import locales
	print("[STARTUP] ✓ locales loaded", flush=True)
	
	print("[STARTUP] Loading cfg_factory...", flush=True)
	from core import cfg_factory
	print("[STARTUP] ✓ cfg_factory loaded", flush=True)
	
	print("[STARTUP] Loading Discord client...", flush=True)
	from core.client import dc
	print("[STARTUP] ✓ Discord client loaded", flush=True)
	
	print("[STARTUP] ✓ Core modules loaded", flush=True)
except Exception as e:
	sys.stderr.write(f"[ERROR] Failed to load core modules: {e}\n")
	sys.stderr.write(traceback.format_exc() + "\n")
	sys.stderr.flush()
	print(f"[ERROR] Failed to load core modules: {e}", flush=True)
	traceback.print_exc()
	sys.exit(1)

print("[STARTUP] Connecting to database...", flush=True)
loop = asyncio.get_event_loop()
connection_attempts = 0
max_attempts = 3
while connection_attempts < max_attempts:
	connection_attempts += 1
	try:
		print(f"[STARTUP] Database connection attempt {connection_attempts}/{max_attempts}...", flush=True)
		loop.run_until_complete(database.db.connect())
		print("[STARTUP] ✓ Database connected", flush=True)
		break
	except asyncio.TimeoutError:
		print(f"[WARNING] Database connection timeout on attempt {connection_attempts}/{max_attempts}", flush=True)
		if connection_attempts >= max_attempts:
			print(f"[ERROR] Failed to connect to database after {max_attempts} attempts: Timeout", flush=True)
			print(f"[ERROR] DATABASE_URL: {os.getenv('DATABASE_URL')}", flush=True)
			sys.exit(1)
	except Exception as e:
		print(f"[WARNING] Database connection error on attempt {connection_attempts}/{max_attempts}: {e}", flush=True)
		if connection_attempts >= max_attempts:
			print(f"[ERROR] Failed to connect to database: {e}", flush=True)
			print(f"[ERROR] DATABASE_URL: {os.getenv('DATABASE_URL')}", flush=True)
			traceback.print_exc()
			sys.exit(1)
	
	if connection_attempts < max_attempts:
		print("[STARTUP] Retrying in 2 seconds...", flush=True)
		time.sleep(2)

print("[STARTUP] Loading bot...", flush=True)
try:
	print("[STARTUP] Importing bot module...", flush=True)
	import bot
	print("[STARTUP] ✓ Bot loaded", flush=True)
except Exception as e:
	print(f"[ERROR] Failed to load bot: {e}", flush=True)
	sys.stderr.write(f"[ERROR] Failed to load bot: {e}\n")
	sys.stderr.write(traceback.format_exc() + "\n")
	sys.stderr.flush()
	traceback.print_exc()
	sys.exit(1)

# Load web server
print("[STARTUP] Checking web server configuration...", flush=True)
if config.cfg.WS_ENABLE:
	print("[STARTUP] Web server enabled, loading...", flush=True)
	try:
		from webui import webserver
		print("[STARTUP] ✓ Web server loaded", flush=True)
	except Exception as e:
		print(f"[WARNING] Failed to load web server: {e}", flush=True)
		webserver = False
else:
	print("[STARTUP] Web server disabled", flush=True)
	webserver = False

log = console.log
log.info("=" * 60)
log.info("PUBobot2 Started Successfully")
log.info("=" * 60)
print("[STARTUP] ✓ All startup checks complete. Bot is starting Discord connection...", flush=True)
sys.stderr.write("[STARTUP] Startup complete - connecting to Discord\n")
sys.stderr.flush()
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
