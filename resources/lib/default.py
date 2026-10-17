# -*- coding: utf-8 -*-
"""
    Script entry point.

    Launched without arguments it opens the leanback TV interface. The engine's
    settings.xml also calls RunScript($ID,<action>) for its maintenance and
    config actions; those carry arguments and are passed straight through.

    SPDX-License-Identifier: GPL-2.0-only
"""

import sys

if len(sys.argv) > 1 and sys.argv[1]:
    from youtube_plugin.kodion import script_actions

    script_actions.run(sys.argv)
else:
    # Before the window's imports: the splash should be up as early as
    # possible (leanback/launch.py).
    from leanback.launch import Launch

    launch = Launch()
    launch.start()

    from leanback import gui

    gui.run(launch)
