import gettext
from os import listdir
from pathlib import Path

locales = dict()

# Try to load compiled translations if available
compiled_dir = Path("locales/compiled")
if compiled_dir.exists():
	for locale_name in listdir(compiled_dir):
		# Skip files like .keep
		if locale_name.startswith('.'):
			continue
		try:
			t = gettext.translation("all", localedir="locales/compiled", languages=[locale_name])
			t.install()
			locales[t.gettext("_lang")] = t.gettext
		except Exception as e:
			# Log but don't fail if a translation can't be loaded
			print(f"Warning: Could not load translation for '{locale_name}': {e}")

# Add default translation
t = gettext.NullTranslations()
t.install()
locales["en"] = t.gettext