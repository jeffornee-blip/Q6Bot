#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Bulletproof startup that writes diagnostics to multiple files
"""

import sys
import os

# ONE: Write to current directory immediately
try:
    with open('pubobot_startup.txt', 'w') as f:
        f.write('Python process started\n')
        f.write(f'CWD: {os.getcwd()}\n')
        f.write(f'Python: {sys.version}\n')
except Exception as e:
    sys.stderr.write(f'Cannot write to current dir: {e}\n')

# TWO: Try to import and run the bot - catch ANY error
try:
    # Import all requirements first
    import asyncio
    import signal
    import time
    import traceback
    import queue
    from asyncio import sleep as asleep
    from asyncio import iscoroutine
    
    print('Standard imports OK', flush=True)
    
    # Now import bot modules
    from core import config, console, database, locales, cfg_factory
    from core.client import dc
    
    print('Core modules OK', flush=True)
    
    # Check env variables
    if not os.getenv('DC_BOT_TOKEN') or not os.getenv('DATABASE_URL'):
        print('Missing required environment variables', flush=True)
        sys.exit(1)
    
    print('Environment OK', flush=True)
    
    # Connect database
    loop = asyncio.get_event_loop()
    loop.run_until_complete(database.db.connect())
    print('Database connected', flush=True)
    
    # Import bot
    import bot
    print('Bot module loaded', flush=True)
    
    # Check webserver
    if config.cfg.WS_ENABLE:
        try:
            from webui import webserver
            print('Webserver loaded', flush=True)
        except:
            print('Webserver load failed', flush=True)
            webserver = False
    else:
        webserver = False
    
    print('Startup complete', flush=True)
    log = console.log
    log.info('PUBobot2 Started')

except Exception as e:
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
