# -*- coding: utf-8 -*-
"""
    Plugin entry point.

    Runs the forked engine's plugin, with the leanback window's own keyless
    routes (/leanback/...) registered on its router first. The engine's
    plugin.py stays an untouched upstream copy.

    Opening the add-on itself from Kodi's video add-ons lands on the plugin's
    top level, the engine's own menu. That opens the TV interface instead;
    widgets, pickers and the window's own listings never browse it from the
    Videos screen, so they still get the plugin.

    SPDX-License-Identifier: GPL-2.0-only
"""

import sys

import xbmc
import xbmcplugin

ROOT = 'plugin://script.youtube.leanback'


def _opened_from_video_addons():
    return (len(sys.argv) > 2
            and sys.argv[0].rstrip('/') == ROOT
            and not sys.argv[2].lstrip('?')
            # Kodi's busy spinner is up while it loads this, so no check for
            # dialogs: pickers browse from elsewhere, not the Videos screen.
            and xbmc.getCondVisibility('Window.IsActive(videos)'))


if _opened_from_video_addons():
    xbmcplugin.endOfDirectory(int(sys.argv[1]), succeeded=False)
    xbmc.executebuiltin('RunScript(script.youtube.leanback)')
else:
    from leanback import routes  # noqa: F401 - registers the /leanback/ paths
    from youtube_plugin.kodion import plugin_runner

    plugin_runner.run()
