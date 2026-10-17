# -*- coding: utf-8 -*-
"""
    Opening and closing the TV interface the way a TV app does.

    Kodi runs an add-on opened from Video add-ons (or Program add-ons) on top
    of that list: the list stays on screen while Python starts and the main
    window's large XML loads. And a Python window, when it closes, re-opens
    the window that was active when it was shown: here the Videos window,
    which can come back at its root instead of the list. Opened from a
    home-menu entry (Bald's, or Favourites) that window is Home, so none of
    this shows.

    - A small splash window with the CoreTube backdrop opens as soon as the
      script runs and stays underneath the main window. It covers the load,
      and on leaving it's what the main window falls back to for a moment.
    - Opened from a list, leaving then goes on to Home instead of back to
      that list (a setting).
    - Opened from a list, CoreTube offers once to add itself to Favourites,
      which most skins show on their home screen.

    The splash is a window, not a dialog: Kodi counts a script's dialog as
    modal and then refuses to open any window, the main one included.

    Kept to Kodi's own modules so it can run before the window's imports.

    SPDX-License-Identifier: GPL-2.0-only
"""

import json
import os
import threading

import xbmc
import xbmcgui
import xbmcvfs

from . import ADDON_ID, addon, localize, setting_bool

SPLASH_XML = 'script-coretube-splash.xml'
WINDOW_HOME = 10000
# Kodi screens that list add-ons: Programs, Videos, the add-on browser,
# Favourites. Opened from anywhere else (Home, a skin's own menu, a widget)
# CoreTube changes nothing about where it returns to.
LIST_WINDOWS = (10001, 10025, 10040, 10060)
OFFER_MARKER = 'special://profile/addon_data/{}/favourite-offer.txt'.format(
    ADDON_ID)
# Ask once the home rows have had time to arrive, not over the splash.
OFFER_DELAY_SECONDS = 4


def _log(msg, level=xbmc.LOGINFO):
    xbmc.log('[{}] launch: {}'.format(ADDON_ID, msg), level)


def _rpc(method, params=None):
    try:
        response = json.loads(xbmc.executeJSONRPC(json.dumps({
            'jsonrpc': '2.0', 'id': 1, 'method': method,
            'params': params or {}})))
    except ValueError:
        return None
    return response.get('result')


class Launch(object):
    """Where CoreTube was opened from, and the splash while it loads."""

    def __init__(self):
        self.origin = xbmcgui.getCurrentWindowId()
        self.from_list = self.origin in LIST_WINDOWS
        self._splash = None

    def start(self):
        """Call first thing, before the main window's imports."""
        if not setting_bool('leanback.launch.splash'):
            return
        try:
            self._splash = xbmcgui.WindowXML(
                SPLASH_XML, addon().getAddonInfo('path'), 'Default', '1080i')
            self._splash.show()
        except RuntimeError as exc:
            self._splash = None
            _log('splash failed: {}'.format(exc), xbmc.LOGWARNING)

    def finish(self):
        """The main window has closed. Kodi has fallen back to the splash
        (or, without it, to where CoreTube was opened from)."""
        splash, self._splash = self._splash, None
        if (self.from_list and setting_bool('leanback.launch.exit_home')
                and not xbmc.Monitor().abortRequested()):
            # Over the splash, so the list never shows again. Wait for it,
            # so the splash below is no longer the active window when it's
            # closed and doesn't re-open the list itself.
            xbmc.executebuiltin('ActivateWindow(Home)', True)
            _log('opened from window {}; left to Home'.format(self.origin))
        if splash is not None:
            splash.close()
            del splash

    def offer_favourite(self, still_open):
        """Opened from a list: offer once to add CoreTube to Favourites.

        still_open() tells whether the main window is still up; the question
        is skipped if CoreTube was left (or a video started) meanwhile."""
        if not self.from_list or _offered():
            return

        def ask():
            if (xbmc.Monitor().waitForAbort(OFFER_DELAY_SECONDS)
                    or not still_open()
                    or xbmc.getCondVisibility('Player.HasMedia')):
                return
            if _is_favourite():
                _mark_offered()
                return
            _mark_offered()
            if not xbmcgui.Dialog().yesno(localize(39140), localize(39141)):
                return
            result = _rpc('Favourites.AddFavourite', {
                'title': addon().getAddonInfo('name'),
                'type': 'script',
                'path': ADDON_ID,
                'thumbnail': 'special://home/addons/{}/resources/brand/'
                             'icon.png'.format(ADDON_ID),
            })
            _log('added to Favourites: {}'.format(result))

        thread = threading.Thread(target=ask, name='coretube-favourite')
        thread.daemon = True
        thread.start()


def _is_favourite():
    result = _rpc('Favourites.GetFavourites', {'properties': ['path']}) or {}
    return any(fav.get('type') == 'script' and fav.get('path') == ADDON_ID
               for fav in result.get('favourites') or ())


def _offered():
    return os.path.exists(xbmcvfs.translatePath(OFFER_MARKER))


def _mark_offered():
    path = xbmcvfs.translatePath(OFFER_MARKER)
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, 'w', encoding='utf-8') as f:
            f.write('asked\n')
    except OSError as exc:
        _log('could not record the Favourites offer: {}'.format(exc),
             xbmc.LOGWARNING)
