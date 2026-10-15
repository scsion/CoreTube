# -*- coding: utf-8 -*-
"""
    The CoreTube logo option (Settings > TV interface > Appearance).

    Each option has its own icon and backdrop in resources/brand/<option>/.
    The add-on icon (addon.xml) and anything pointing at the backdrop, such
    as a Bald home hub, use the fixed copies in resources/brand/, so applying
    an option copies its files there and drops Kodi's cached thumbnails of
    them. The window header picks its logo from the option directly.

    SPDX-License-Identifier: GPL-2.0-only
"""

import filecmp
import json
import os
import shutil

import xbmc
import xbmcvfs

from . import ADDON_ID, addon

OPTIONS = ('a', 'b')
DEFAULT = 'a'
FILES = ('icon.png', 'fanart.jpg')


def current():
    try:
        value = addon().getSetting('leanback.logo')
    except RuntimeError:
        value = ''
    return value if value in OPTIONS else DEFAULT


def _brand_dir():
    return os.path.join(
        xbmcvfs.translatePath(addon().getAddonInfo('path')),
        'resources', 'brand')


def _rpc(method, params):
    response = xbmc.executeJSONRPC(json.dumps({
        'jsonrpc': '2.0', 'id': 1, 'method': method, 'params': params}))
    return json.loads(response).get('result') or {}


def _forget_cached(names):
    """Drop Kodi's cached copies so the new pictures show up."""
    result = _rpc('Textures.GetTextures', {
        'properties': ['url'],
        'filter': {'field': 'url', 'operator': 'contains',
                   'value': ADDON_ID},
    })
    for texture in result.get('textures') or ():
        url = texture.get('url', '')
        if '%2fbrand%2f' in url.lower() and any(
                name in url for name in names):
            _rpc('Textures.RemoveTexture',
                 {'textureid': texture['textureid']})


def apply(option=None):
    """Make the option's icon and backdrop the active ones."""
    option = option or current()
    base = _brand_dir()
    changed = []
    for name in FILES:
        source = os.path.join(base, option, name)
        target = os.path.join(base, name)
        if not os.path.exists(source):
            continue
        if os.path.exists(target) and filecmp.cmp(source, target,
                                                  shallow=False):
            continue
        try:
            shutil.copyfile(source, target)
            changed.append(name)
        except OSError as exc:
            xbmc.log('[{}] logo: copying {} failed: {}'.format(
                ADDON_ID, name, exc), xbmc.LOGWARNING)
    if changed:
        _forget_cached(changed)
        xbmc.log('[{}] logo option {} applied'.format(ADDON_ID, option),
                 xbmc.LOGINFO)
    return bool(changed)


class BrandMonitor(xbmc.Monitor):
    """Applies the logo option at start-up and whenever settings change."""

    def __init__(self):
        super(BrandMonitor, self).__init__()
        apply()

    def onSettingsChanged(self):
        apply()
