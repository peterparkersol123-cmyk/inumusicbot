"""
Auto-loads all plugin modules at import time.
Any .py file inside a subdirectory of plugins/ is imported automatically.
"""
import importlib
import os
import logging

LOGGER = logging.getLogger("MusicBot.Plugins")

_plugin_dir = os.path.dirname(__file__)

for folder in os.listdir(_plugin_dir):
    folder_path = os.path.join(_plugin_dir, folder)
    if not os.path.isdir(folder_path) or folder.startswith("_"):
        continue
    for filename in os.listdir(folder_path):
        if filename.endswith(".py") and not filename.startswith("_"):
            module_name = f"MusicBot.plugins.{folder}.{filename[:-3]}"
            try:
                importlib.import_module(module_name)
                LOGGER.debug(f"Loaded plugin: {module_name}")
            except Exception as e:
                LOGGER.error(f"Failed to load plugin {module_name}: {e}")
