#!/usr/bin/env python3
# -*- coding: utf-8 -*-

# ============================================================================
# DIAGNOSTIC MODE - writes to multiple outputs to debug Railway deployment
# ============================================================================

import sys
import os

# Create a comprehensive startup trace file
TRACE_FILE = "startup.trace"

def trace(msg):
    """Write message to our trace file"""
    try:
        with open(TRACE_FILE, 'a') as f:
            f.write(msg + "\n")
            f.flush()
    except:
        pass

# Start tracing immediately
trace("=== PUBOBOT2 STARTUP TRACE ===")
trace(f"Python version: {sys.version}")
trace(f"Executable: {sys.executable}")
trace(f"Working directory: {os.getcwd()}")
trace("")

# Also write to actual stdout/stderr
print("PUBOBOT2: Starting", flush=True)
sys.stderr.write("PUBOBOT2: Starting\n")
sys.stderr.flush()

# Now do the actual imports
try:
    trace("Importing core modules...")
    import time
    import signal
    import asyncio
    import traceback
    import queue
    from asyncio import sleep as asleep
    from asyncio import iscoroutine
    trace("Core imports complete")
    
    # WRITE TO FILE BEFORE LOADING BOT MODULES
    trace("Starting config loading...")
except Exception as e:
    trace(f"ERROR during imports: {e}")
    trace(traceback.format_exc())
    raise

# Rest of the original startup code begins...
log_file = None
try:
    log_file = open('/tmp/pubobot.log', 'w')
    log_file.write("=== PUBobot2 Startup Log ===\n")
    log_file.flush()
except:
    try:
        log_file = open('pubobot_startup.log', 'w')
        log_file.write("=== PUBobot2 Startup Log ===\n")
        log_file.flush()
    except:
        log_file = None

def log_msg(msg):
	"""Write to all available output streams"""
	import datetime
	timestamp = datetime.datetime.now().strftime("%H:%M:%S.%f")[:-3]
	formatted_msg = f"[{timestamp}] {msg}"
	print(formatted_msg, flush=True)
	sys.stderr.write(formatted_msg + "\n")
	sys.stderr.flush()
	if log_file:
		log_file.write(formatted_msg + "\n")
		log_file.flush()
	trace(formatted_msg)

log_msg("PYTHON_PROCESS_STARTED")

print("PYTHON_STARTED", flush=True)
sys.stderr.write("PYTHON_STARTED_STDERR\n")
sys.stderr.flush()

try:
	log_msg("IMPORTS_COMPLETE")
	
	# IMMEDIATE STARTUP DEBUG - write to multiple outputs to ensure we see something
	try:
		with open('/tmp/pubobot_startup.log', 'w') as f:
			f.write("SCRIPT STARTED\n")
	except:
		pass
	
	log_msg("PUBOBOT2: Script started and ready")
	
	log_msg("=" * 60)
	log_msg("PUBobot2 Starting...")
	log_msg("=" * 60)
	
	# Check environment variables before loading anything
	log_msg("\n[STARTUP] Checking environment variables...")
	required_vars = ['DC_BOT_TOKEN', 'DATABASE_URL']
	missing_vars = []
	for var in required_vars:
		if os.getenv(var):
			log_msg(f"✓ {var} is set")
		else:
			log_msg(f"✗ {var} is NOT set")
			missing_vars.append(var)
	
	if missing_vars:
		log_msg(f"\n[ERROR] Missing required environment variables: {', '.join(missing_vars)}")
		log_msg("Cannot start bot without these variables!")
		sys.exit(1)
	
	log_msg("\n[STARTUP] Loading bot core modules...")
	try:
		log_msg("[STARTUP] Loading config...")
		from core import config
		log_msg("[STARTUP] ✓ config loaded")
		
		log_msg("[STARTUP] Loading console...")
		from core import console
		log_msg("[STARTUP] ✓ console loaded")
		
		log_msg("[STARTUP] Loading database...")
		from core import database
		log_msg("[STARTUP] ✓ database loaded")
		
		log_msg("[STARTUP] Loading locales...")
		from core import locales
		log_msg("[STARTUP] ✓ locales loaded")
		
		log_msg("[STARTUP] Loading cfg_factory...")
		from core import cfg_factory
		log_msg("[STARTUP] ✓ cfg_factory loaded")
		
		log_msg("[STARTUP] Loading Discord client...")
		from core.client import dc
		log_msg("[STARTUP] ✓ Discord client loaded")
		
		log_msg("[STARTUP] ✓ Core modules loaded")
		
		log_msg("[STARTUP] Connecting to database...")
		loop = asyncio.get_event_loop()
		connection_attempts = 0
		max_attempts = 3
		while connection_attempts < max_attempts:
			connection_attempts += 1
			try:
				log_msg(f"[STARTUP] Database connection attempt {connection_attempts}/{max_attempts}...")
				loop.run_until_complete(database.db.connect())
				log_msg("[STARTUP] ✓ Database connected")
				break
			except asyncio.TimeoutError:
				log_msg(f"[WARNING] Database connection timeout on attempt {connection_attempts}/{max_attempts}")
				if connection_attempts >= max_attempts:
					log_msg(f"[ERROR] Failed to connect to database after {max_attempts} attempts: Timeout")
					log_msg(f"[ERROR] DATABASE_URL: {os.getenv('DATABASE_URL')}")
					sys.exit(1)
			except Exception as e:
				log_msg(f"[WARNING] Database connection error on attempt {connection_attempts}/{max_attempts}: {e}")
				if connection_attempts >= max_attempts:
					log_msg(f"[ERROR] Failed to connect to database: {e}")
					log_msg(f"[ERROR] DATABASE_URL: {os.getenv('DATABASE_URL')}")
					raise
			
			if connection_attempts < max_attempts:
				log_msg("[STARTUP] Retrying in 2 seconds...")
				time.sleep(2)
		
		log_msg("[STARTUP] Loading bot...")
		log_msg("[STARTUP] Importing bot module...")
		import bot
		log_msg("[STARTUP] ✓ Bot loaded")
		
		# Load web server
		log_msg("[STARTUP] Checking web server configuration...")
		if config.cfg.WS_ENABLE:
			log_msg("[STARTUP] Web server enabled, loading...")
			try:
				from webui import webserver
				log_msg("[STARTUP] ✓ Web server loaded")
			except Exception as e:
				log_msg(f"[WARNING] Failed to load web server: {e}")
				webserver = False
		else:
			log_msg("[STARTUP] Web server disabled")
			webserver = False
		
		log = console.log
		log.info("=" * 60)
		log.info("PUBobot2 Started Successfully")
		log.info("=" * 60)
		log_msg("[STARTUP] ✓ All startup checks complete. Bot is starting Discord connection...")
		if log_file:
			log_file.close()
			log_file = None
	
	except Exception as e:
		log_msg(f"[ERROR] Failed during startup: {e}")
		log_msg(traceback.format_exc())
		sys.exit(1)

except Exception as e:
	# Catch ANYTHING that happens before the normal error handling
	msg = f"CRITICAL ERROR: {e}\n{traceback.format_exc()}"
	print(msg, flush=True)
	sys.stderr.write(msg + "\n")
	sys.stderr.flush()
	if log_file:
		log_file.write(msg + "\n")
		log_file.flush()
		log_file.close()
	trace(msg)
	sys.exit(1)

# Now setup signal handlers and event loop
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
