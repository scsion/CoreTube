# -*- coding: utf-8 -*-
"""
    Plugin entry point.

    Runs the forked engine's plugin, with the leanback window's own keyless
    routes (/leanback/...) registered on its router first. The engine's
    plugin.py stays an untouched upstream copy.

    SPDX-License-Identifier: GPL-2.0-only
"""

from leanback import routes  # noqa: F401 - registers the /leanback/ paths
from youtube_plugin.kodion import plugin_runner

plugin_runner.run()
