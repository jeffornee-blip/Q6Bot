#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Bulletproof startup with hard timeout to prevent hanging forever
"""

import sys
import os

# FORCE unbuffered output at Python level IMMEDIATELY
try:
    sys.stdout = os.fdopen(sys.stdout.fileno(), 'w', 1)
    sys.stderr = os.fdopen(sys.stderr.fileno(), 'w', 1)
except:
    pass  # If this fails, continue anyway

import signal

# Write immediately to both stdout and stderr
msg = "=== PYTHON STARTUP ==="
print(msg, flush=True)
sys.stderr.write(msg + '\n')
sys.stderr.flush()

# HARD TIMEOUT: Exit after 30 seconds no matter what
def timeout_exit(sig, frame):
    print('TIMEOUT: Startup exceeded 30 seconds - exiting', flush=True)
    try:
        with open('pubobot_timeout.txt', 'w') as f:
            f.write('Startup timed out after 30 seconds\n')
    except:
        pass
    sys.exit(1)

signal.signal(signal.SIGALRM, timeout_exit)
signal.alarm(30)

# ONE: Write to current directory immediately
try:
    with open('pubobot_startup.txt', 'w') as f:
        f.write('Python process started\n')
        f.write(f'CWD: {os.getcwd()}\n')
        f.write(f'Python: {sys.version}\n')
    print("Startup file written", flush=True)
except Exception as e:
    print(f'Cannot write to current dir: {e}', flush=True)
    sys.stderr.write(f'Cannot write to current dir: {e}\n')

# TWO: Try to import and run the bot - catch ANY error
try:
    # Import all requirements first
    print('Importing sys modules...', flush=True)
    import asyncio
    import time
    import traceback
    import queue
    from asyncio import sleep as asleep
    from asyncio import iscoroutine
    
    print('Standard imports OK', flush=True)
    
    # Now import bot modules
    print('Importing core modules...', flush=True)
    from core import config, console, database, locales, cfg_factory
    from core.client import dc
    
    print('Core modules OK', flush=True)
    
    # Check env variables
    print('Checking environment...', flush=True)
    if not os.getenv('DC_BOT_TOKEN') or not os.getenv('DATABASE_URL'):
        print('Missing required environment variables', flush=True)
        signal.alarm(0)
        sys.exit(1)
    
    print('Environment OK', flush=True)
    
    # Connect database with timeout
    print('Connecting to database...', flush=True)
    loop = asyncio.get_event_loop()
    loop.run_until_complete(asyncio.wait_for(database.db.connect(), timeout=10))
    print('Database connected', flush=True)
    
    # Import bot
    print('Importing bot module...', flush=True)
    import bot
    print('Bot module loaded', flush=True)
    
    # Check webserver
    print('Checking webserver...', flush=True)
    if config.cfg.WS_ENABLE:
        try:
            from webui import webserver
            print('Webserver loaded', flush=True)
        except:
            print('Webserver load failed (continuing)', flush=True)
            webserver = False
    else:
        print('Webserver disabled', flush=True)
        webserver = False
    
    print('Startup complete', flush=True)
    signal.alarm(0)  # Cancel timeout
    log = console.log
    log.info('PUBobot2 Started')

except Exception as e:
    signal.alarm(0)  # Cancel timeout
    err_msg = f'Startup failed: {e}\n{traceback.format_exc()}'
    print(err_msg, flush=True)
    sys.stderr.write(err_msg + '\n')
    sys.stderr.flush()
    
    # Write to file
    try:
        with open('pubobot_error.txt', 'w') as f:
            f.write(err_msg)
    except:
        pass
    
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
