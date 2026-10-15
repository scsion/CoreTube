# -*- coding: utf-8 -*-
"""
    Service entry point: SponsorBlock skipper alongside the engine service.

    SPDX-License-Identifier: GPL-2.0-only
"""

from leanback.sponsorblock import SponsorBlockPlayer
from youtube_plugin.kodion import service_runner

# Kept referenced for the lifetime of the service so Kodi keeps delivering
# player callbacks to it; it runs its own polling thread while playing.
_sponsorblock = SponsorBlockPlayer()

service_runner.run()

_sponsorblock.shutdown()
