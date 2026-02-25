#!/usr/bin/env python3
# -*- coding: utf-8 -*-

# ============================================================================
# ABSOLUTE FIRST ACTION: Write to file BEFORE anything else
# ============================================================================

import sys
import os

TRACE_FILE = "startup.trace"

# Delete old trace file
try:
    os.remove(TRACE_FILE)
except:
    pass

def trace(msg, also_print=True):
    """Write message to trace file and optionally stdout"""
    try:
        with open(TRACE_FILE, 'a') as f:
            f.write(msg + "\n")
            f.flush()
        os.fsync(open(TRACE_FILE, 'r').fileno())  # Force disk sync
    except Exception as e:
        if also_print:
            print(f"TRACE ERROR: {e}", flush=True)
    
    if also_print:
        print(msg, flush=True)
        sys.stderr.write(msg + "\n")
        sys.stderr.flush()

# IMMEDIATE PROOF OF EXECUTION
trace("=" * 80)
trace("PUBOBOT2 PYTHON PROCESS STARTED", also_print=True)
trace("=" * 80)
trace(f"Python: {sys.version}")
trace(f"Executable: {sys.executable}")
trace(f"CWD: {os.getcwd()}")
trace(f"PID: {os.getpid()}")

# Add startup timeout
import signal
import time

STARTUP_TIMEOUT = 60  # 60 seconds

def timeout_handler(signum, frame):
    trace("STARTUP TIMEOUT EXCEEDED - exiting", also_print=True)
    with open(TRACE_FILE, 'a') as f:
        f.write("STARTUP TIMEOUT - bot did not complete initialization\n")
    sys.exit(1)

signal.signal(signal.SIGALRM, timeout_handler)
signal.alarm(STARTUP_TIMEOUT)

trace("Timeout set to 60 seconds")

try:
    # Now do imports
    trace("Importing standard library modules...")
    import asyncio
    import traceback
    import queue
    from asyncio import sleep as asleep
    from asyncio import iscoroutine
    trace("Standard library imports complete")
    
    # Now core modules
    trace("Importing core.config...")
    from core import config
    trace("✓ config imported")
    
    trace("Importing core.console...")
    from core import console
    trace("✓ console imported")
    
    trace("Importing core.database...")
    from core import database
    trace("✓ database imported")
    
    trace("Importing core.locales...")
    from core import locales
    trace("✓ locales imported")
    
    trace("Importing core.cfg_factory...")
    from core import cfg_factory
    trace("✓ cfg_factory imported")
    
    trace("Importing core.client...")
    from core.client import dc
    trace("✓ client imported")
    
    trace("All core modules imported successfully")
    
    # Cancel timeout alarm
    signal.alarm(0)
    
    # Setup logging
    log_file = None
    try:
        log_file = open("startup.log", 'w')
        log_file.write("=== Startup Log ===\n")
        log_file.flush()
    except:
        pass
    
    def log_msg(msg):
        trace(msg)
        if log_file:
            log_file.write(msg + "\n")
            log_file.flush()
    
    log_msg("Environment check...")
    required_vars = ['DC_BOT_TOKEN', 'DATABASE_URL']
    for var in required_vars:
        if os.getenv(var):
            log_msg(f"✓ {var} is set")
        else:
            log_msg(f"✗ {var} is NOT set")
            sys.exit(1)
    
    log_msg("Connecting to database...")
    loop = asyncio.get_event_loop()
    loop.run_until_complete(database.db.connect())
    log_msg("✓ Database connected")
    
    log_msg("Importing bot module...")
    import bot
    log_msg("✓ Bot imported")
    
    log_msg("Loading web server config...")
    if config.cfg.WS_ENABLE:
        log_msg("Web server enabled")
        try:
            from webui import webserver
            log_msg("✓ Web server loaded")
        except Exception as e:
            log_msg(f"Warning: web server load failed: {e}")
            webserver = False
    else:
        log_msg("Web server disabled")
        webserver = False
    
    log = console.log
    log.info("=" * 60)
    log.info("PUBobot2 Started Successfully")
    log.info("=" * 60)
    
    log_msg("=" * 80)
    log_msg("STARTUP COMPLETE - BOT IS READY")
    log_msg("=" * 80)
    
    if log_file:
        log_file.close()

except Exception as e:
    signal.alarm(0)  # Cancel timeout
    error_msg = f"STARTUP ERROR: {e}\n{traceback.format_exc()}"
    trace(error_msg, also_print=True)
    
    if log_file:
        log_file.write(error_msg + "\n")
        log_file.flush()
        log_file.close()
    
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
