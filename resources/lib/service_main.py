# -*- coding: utf-8 -*-
"""
    Service entry point: SponsorBlock skipper and the logo option, alongside
    the engine service.

    SPDX-License-Identifier: GPL-2.0-only
"""

from leanback import migrate
from leanback.brand import BrandMonitor
from leanback.sponsorblock import SponsorBlockPlayer
from youtube_plugin.kodion import service_runner

# Before the engine reads its settings.
migrate.run()

# Kept referenced for the lifetime of the service so Kodi keeps delivering
# player callbacks to it; it runs its own polling thread while playing.
_sponsorblock = SponsorBlockPlayer()
# Same for settings callbacks: keeps the chosen logo option applied.
_brand = BrandMonitor()

service_runner.run()

_sponsorblock.shutdown()
