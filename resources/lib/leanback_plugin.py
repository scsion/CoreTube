# -*- coding: utf-8 -*-
"""
    Plugin entry point.

    Runs the forked engine's plugin, with the leanback window's own keyless
    routes (/leanback/...) registered on its router first. The engine's
    plugin.py stays an untouched upstream copy.

    Opening the add-on itself (its root path) lands on the plugin's top
    level, the engine's own menu. That opens the TV interface instead. This
    works from any skin and any screen: add-on lists, custom home menus,
    Favourites saved before 0.9.2 and widgets. Widgets, pickers and the
    window's own listings use the engine's routes (/kodion/..., /leanback/...)
    rather than the root, so they still get the plugin.

    Kodi activates the Programs window before running a plugin opened from
    Program add-ons or RunAddon(). Back out to Home first, as PlexMod does, so
    that window never shows before the script's splash.

    SPDX-License-Identifier: GPL-2.0-only
"""

import sys

import xbmc
import xbmcgui
import xbmcplugin

ROOT = 'plugin://script.coretube'
WINDOW_HOME = 10000


def _opened_as_addon():
    """Kodi invoked the add-on's root, not one of the engine's routes."""
    return (len(sys.argv) > 2
            and sys.argv[0].rstrip('/') == ROOT
            and not sys.argv[2].lstrip('?'))


def _ensure_home():
    """Leave the add-on list Kodi activated for this plugin before the
    script starts, so its window never shows."""
    if xbmcgui.getCurrentWindowId() == WINDOW_HOME:
        return
    xbmc.executebuiltin('Action(back)')
    xbmc.executebuiltin('Dialog.Close(all,1)')
    xbmc.executebuiltin('ActivateWindow(home)')
    monitor = xbmc.Monitor()
    for _ in range(50):
        if xbmcgui.getCurrentWindowId() == WINDOW_HOME:
            return
        if monitor.waitForAbort(0.1):
            return


if _opened_as_addon():
    _ensure_home()
    xbmcplugin.endOfDirectory(int(sys.argv[1]), succeeded=False)
    xbmc.executebuiltin('RunScript(script.coretube)')
else:
    from leanback import routes  # noqa: F401 - registers the /leanback/ paths
    from youtube_plugin.kodion import plugin_runner

    plugin_runner.run()
