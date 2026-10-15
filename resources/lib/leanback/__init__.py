# -*- coding: utf-8 -*-
"""
    Leanback TV interface for the forked YouTube engine.

    SPDX-License-Identifier: GPL-2.0-only
"""

import xbmcaddon

ADDON_ID = 'script.coretube'
PLUGIN = 'plugin://' + ADDON_ID
# Home window property the GUI sets just before it starts playback, so the
# SponsorBlock service knows the video id even if the player item lacks it.
HINT_PROPERTY = ADDON_ID + '-leanback_video_id'


def addon():
    # A fresh instance each time so setting changes are picked up.
    return xbmcaddon.Addon(ADDON_ID)


def localize(string_id):
    return addon().getLocalizedString(string_id)


def setting_bool(setting_id):
    try:
        return addon().getSettingBool(setting_id)
    except (RuntimeError, TypeError):
        return False
