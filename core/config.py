# -*- coding: utf-8 -*-
import os
from importlib.machinery import SourceFileLoader


class Config:
	"""Configuration class that loads from environment variables or config.cfg file"""
	
	def __init__(self):
		# Try loading from config.cfg first (for local development)
		cfg_file = None
		try:
			cfg_file = SourceFileLoader('cfg', 'config.cfg').load_module()
		except Exception:
			pass
		
		# Discord Configuration
		self.DC_BOT_TOKEN = os.getenv('DC_BOT_TOKEN') or (cfg_file.DC_BOT_TOKEN if cfg_file else None)
		self.DC_CLIENT_ID = int(os.getenv('DC_CLIENT_ID', cfg_file.DC_CLIENT_ID if cfg_file else 0))
		self.DC_CLIENT_SECRET = os.getenv('DC_CLIENT_SECRET', cfg_file.DC_CLIENT_SECRET if cfg_file else '')
		self.DC_INVITE_LINK = os.getenv('DC_INVITE_LINK', cfg_file.DC_INVITE_LINK if cfg_file else '')
		self.DC_OWNER_ID = int(os.getenv('DC_OWNER_ID', cfg_file.DC_OWNER_ID if cfg_file else 0))
		self.DC_SLASH_SERVERS = os.getenv('DC_SLASH_SERVERS', 
			str(cfg_file.DC_SLASH_SERVERS) if cfg_file else '[]')
		if isinstance(self.DC_SLASH_SERVERS, str):
			import json
			try:
				self.DC_SLASH_SERVERS = json.loads(self.DC_SLASH_SERVERS)
			except:
				self.DC_SLASH_SERVERS = []
		
		# Database Configuration
		self.DB_URI = os.getenv('DATABASE_URL') or (cfg_file.DB_URI if cfg_file else None)
		
		# Logging Configuration
		self.LOG_LEVEL = os.getenv('LOG_LEVEL', cfg_file.LOG_LEVEL if cfg_file else 'INFO')
		
		# Help and Commands
		self.COMMANDS_URL = os.getenv('COMMANDS_URL', 
			cfg_file.COMMANDS_URL if cfg_file else 'https://github.com/Leshaka/PUBobot2/blob/main/COMMANDS.md#avaible-commands')
		self.HELP = os.getenv('HELP', 
			cfg_file.HELP if cfg_file else 'PUBobot2 is a discord bot for pickup games organisation.')
		self.STATUS = os.getenv('STATUS', cfg_file.STATUS if cfg_file else '')
		
		# Web Server Configuration
		self.WS_ENABLE = os.getenv('WS_ENABLE', 'false').lower() == 'true' or (cfg_file.WS_ENABLE if cfg_file else False)
		self.WS_HOST = os.getenv('WS_HOST', cfg_file.WS_HOST if cfg_file else '0.0.0.0')
		self.WS_PORT = int(os.getenv('WS_PORT', cfg_file.WS_PORT if cfg_file else 443))
		self.WS_OAUTH_REDIRECT_URL = os.getenv('WS_OAUTH_REDIRECT_URL', cfg_file.WS_OAUTH_REDIRECT_URL if cfg_file else '')
		self.WS_ROOT_URL = os.getenv('WS_ROOT_URL', cfg_file.WS_ROOT_URL if cfg_file else '')
		self.WS_SSL_CERT_FILE = os.getenv('WS_SSL_CERT_FILE', cfg_file.WS_SSL_CERT_FILE if cfg_file else '')
		self.WS_SSL_KEY_FILE = os.getenv('WS_SSL_KEY_FILE', cfg_file.WS_SSL_KEY_FILE if cfg_file else '')
		
		# Validate critical config
		if not self.DC_BOT_TOKEN:
			raise ValueError("DC_BOT_TOKEN not set! Set it via environment variable or config.cfg")
		# DB_URI is optional during initialization - will be required at connect time
		if not self.DB_URI:
			import sys
			# Only warn, don't raise - database may not be needed during build phase
			if '--require-db' in sys.argv:
				raise ValueError("DB_URI/DATABASE_URL not set! Set it via environment variable or config.cfg")


cfg = Config()

try:
	with open('.version', 'r') as f:
		__version__ = f.read()
except Exception:
	__version__ = "unknown"
