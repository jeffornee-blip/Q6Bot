#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Minimal startup - import only what's necessary
"""

import sys
import os
import signal

# FORCE unbuffered output at Python level IMMEDIATELY
try:
    sys.stdout = os.fdopen(sys.stdout.fileno(), 'w', 1)
    sys.stderr = os.fdopen(sys.stderr.fileno(), 'w', 1)
except:
    pass

print("STARTUP_BEGIN", flush=True)
sys.stderr.write("STARTUP_BEGIN\n")
sys.stderr.flush()

# Timeout after 30 seconds
def timeout_exit(sig, frame):
    msg = "TIMEOUT: Startup exceeded 30 seconds"
    print(msg, flush=True)
    sys.stderr.write(msg + '\n')
    sys.stderr.flush()
    sys.exit(1)

signal.signal(signal.SIGALRM, timeout_exit)
signal.alarm(30)

try:
    # Check environment
    print("CHECK_ENV", flush=True)
    if not os.getenv('DC_BOT_TOKEN'):
        raise ValueError("DC_BOT_TOKEN not set")
    if not os.getenv('DATABASE_URL'):
        raise ValueError("DATABASE_URL not set")
    
    print("ENV_OK", flush=True)
    
    # Minimal imports
    print("IMPORT_ASYNCIO", flush=True)
    import asyncio
    
    print("IMPORT_CORE_CONFIG", flush=True)
    from core.config import cfg
    
    print("CONFIG_OK", flush=True)
    
    print("IMPORT_CORE_CONSOLE", flush=True)
    from core import console
    
    print("CONSOLE_OK", flush=True)
    
    print("IMPORT_CORE_DATABASE", flush=True)
    from core import database
    
    print("DATABASE_OK", flush=True)
    
    print("CONNECTING_DB", flush=True)
    loop = asyncio.get_event_loop()
    loop.run_until_complete(asyncio.wait_for(database.db.connect(), timeout=10))
    
    print("DB_CONNECTED", flush=True)
    
    print("IMPORT_BOT", flush=True)
    import bot
    
    print("BOT_OK", flush=True)
    
    print("STARTUP_COMPLETE", flush=True)
    signal.alarm(0)  # Cancel timeout
    log = console.log
    log.info('PUBobot2 Started')

except Exception as e:
    signal.alarm(0)
    import traceback
    err_msg = f"ERROR: {e}\n{traceback.format_exc()}"
    print(err_msg, flush=True)
    sys.stderr.write(err_msg + "\n")
    sys.stderr.flush()
    sys.exit(1)

# Now setup signal handlers and event loop
import time
import traceback
import queue
from asyncio import sleep as asleep
from asyncio import iscoroutine

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
	log.info("Closing log.")
	log.close()
	print("Exit now.")
	loop.stop()

# Import what we need for the event loop
from core.client import dc
from core.config import cfg

# Login to discord
print("Starting event loop...", flush=True)
loop.create_task(think())
loop.create_task(dc.start(cfg.DC_BOT_TOKEN))

# At the end of startup, force update all rating roles
# This must be run after the bot is ready and guilds are loaded
async def force_update_after_ready():
    await dc.wait_until_ready()
    await bot.force_update.force_update_all_rating_roles()

loop.create_task(force_update_after_ready())

log.info("Connecting to discord...")
print("Running event loop...", flush=True)
sys.stdout.flush()
loop.run_forever()
