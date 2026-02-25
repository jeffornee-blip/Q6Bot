# -*- coding: utf-8 -*-
from importlib import import_module
from core.config import cfg

_db = None

def get_db():
	"""Lazy-load database connection"""
	global _db
	if _db is None:
		if not cfg.DB_URI:
			raise ValueError("DATABASE_URL not set! Cannot initialize database connection. Set it via environment variable or config.cfg")
		db_type, db_address = cfg.DB_URI.split("://", 1)
		adapter = import_module('core.DBAdapters.' + db_type)
		_db = adapter.Adapter(db_address)
	return _db

# For compatibility with existing code
class DatabaseProxy:
	def __getattr__(self, name):
		return getattr(get_db(), name)
	def __await__(self):
		return get_db().__await__()

db = DatabaseProxy()
