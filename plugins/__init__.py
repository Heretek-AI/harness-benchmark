"""Re-export the loader so ``from plugins import PluginLoader`` works."""
from plugins.loader import PluginLoader, PluginSpec

__all__ = ["PluginLoader", "PluginSpec"]