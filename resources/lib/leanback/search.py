# -*- coding: utf-8 -*-
"""
    YouTube TV's search screen: on-screen keyboard and suggestions.

    The keyboard is an 8 x 4 grid like YouTube TV's (seven characters a row
    plus a function column), with a letters page and a numbers/symbols page.
    Suggestions come from YouTube's own autocomplete, which needs no key;
    with nothing typed the column shows recent searches instead.

    SPDX-License-Identifier: GPL-2.0-only
"""

import json
import threading
from urllib.parse import urlencode
from urllib.request import Request, urlopen

import xbmc
import xbmcgui

from . import ADDON_ID

MEDIA = 'special://home/addons/{}/resources/skins/Default/media/'.format(
    ADDON_ID)
ICON_BACKSPACE = MEDIA + 'icon_backspace.png'
ICON_HISTORY = MEDIA + 'icon_history.png'
ICON_SEARCH = MEDIA + 'icon_search.png'

BACKSPACE = 'backspace'
MODE = 'mode'

# Rows of seven characters plus one function key; '' leaves a cell empty.
# Lower case, as typed (YouTube TV shows capitals but types lower case).
LETTERS = (
    'abcdefg', BACKSPACE,
    'hijklmn', MODE,
    'opqrstu', '',
    "vwxyz-'", '',
)
SYMBOLS = (
    '1234567', BACKSPACE,
    '890.,?!', MODE,
    '@#&()/:', '',
    '"_+=*%$', '',
)
MODE_LABELS = {'letters': '&123', 'symbols': 'ABC'}

SUGGEST_URL = 'https://suggestqueries.google.com/complete/search'
SUGGEST_COUNT = 5
# Typing pause before suggestions and results refresh.
DEBOUNCE = 0.6


def key_items(mode):
    layout = LETTERS if mode == 'letters' else SYMBOLS
    items = []
    for index in range(0, len(layout), 2):
        for char in layout[index]:
            item = xbmcgui.ListItem(char)
            item.setProperty('key', char)
            items.append(item)
        function = layout[index + 1]
        item = xbmcgui.ListItem()
        if function == BACKSPACE:
            item.setArt({'icon': ICON_BACKSPACE})
        elif function == MODE:
            item.setLabel(MODE_LABELS[mode])
        item.setProperty('key', function)
        items.append(item)
    return items


def suggestion_items(queries, history=False):
    items = []
    for query in queries[:SUGGEST_COUNT]:
        item = xbmcgui.ListItem(query)
        item.setArt({'icon': ICON_HISTORY if history else ICON_SEARCH})
        item.setProperty('query', query)
        items.append(item)
    return items


def fetch_suggestions(query, language='en'):
    """YouTube's autocomplete for the query; [] when it can't be reached."""
    url = '{}?{}'.format(SUGGEST_URL, urlencode({
        'client': 'firefox', 'ds': 'yt', 'hl': language, 'q': query}))
    try:
        request = Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        with urlopen(request, timeout=4) as response:
            data = json.loads(response.read().decode('utf-8', 'replace'))
        return [text for text in data[1] if isinstance(text, str)]
    except Exception as exc:  # pylint: disable=broad-except
        xbmc.log('[{}] suggestions failed: {!r}'.format(ADDON_ID, exc),
                 xbmc.LOGDEBUG)
        return []


class Debouncer(object):
    """Runs the callback once typing has paused for DEBOUNCE seconds."""

    def __init__(self, callback):
        self._callback = callback
        self._timer = None
        self._lock = threading.Lock()

    def trigger(self, *args):
        with self._lock:
            if self._timer:
                self._timer.cancel()
            self._timer = threading.Timer(DEBOUNCE, self._callback, args)
            self._timer.daemon = True
            self._timer.start()

    def cancel(self):
        with self._lock:
            if self._timer:
                self._timer.cancel()
                self._timer = None
