# -*- coding: utf-8 -*-
"""
    Loads rows inside the window instead of through Kodi's plugin calls.

    A <content> container makes Kodi start a fresh plugin run, with a new
    Python interpreter and engine start-up, for every row, one after another.
    That alone took 4-7 s for a home screen. Here the window runs the same
    engine route for each row in a worker thread and converts the engine's
    items with the engine's own listitem code, so rows look exactly like
    plugin listings but arrive together, usually within a second or two.

    SPDX-License-Identifier: GPL-2.0-only
"""

import threading
import time
from concurrent.futures import ThreadPoolExecutor

import xbmc

from . import ADDON_ID

# Rows of local lists (history, watch later) change with every video played.
_UNCACHED = ('/kodion/',)
CACHE_SECONDS = 10 * 60
WORKERS = 6


def _log(message, level=xbmc.LOGDEBUG):
    xbmc.log('[{}] loader: {}'.format(ADDON_ID, message), level)


class Engine(object):
    """The engine's provider and a context to clone per request, built on
    first use so opening the window isn't held up by the imports."""

    def __init__(self):
        self._lock = threading.Lock()
        self._ready = False

    def _init(self):
        with self._lock:
            if self._ready:
                return
            from youtube_plugin.kodion.context import XbmcContext
            from youtube_plugin.kodion.items.xbmc import xbmc_items
            from youtube_plugin.youtube import Provider

            from . import routes  # noqa: F401 - registers /leanback/ paths

            self.context = XbmcContext()
            self.provider = Provider()
            # Build the client here, once: the parallel rows would otherwise
            # each build (and sign in) their own.
            self.provider.get_client(self.context)
            self.converters = {
                'AudioItem': xbmc_items.media_listitem,
                'VideoItem': xbmc_items.media_listitem,
                'DirectoryItem': xbmc_items.directory_listitem,
                'NextPageItem': xbmc_items.directory_listitem,
                'WatchLaterItem': xbmc_items.directory_listitem,
                'BookmarkItem': xbmc_items.directory_listitem,
            }
            self._ready = True

    def resume_point(self, video_id, min_seconds, max_percent):
        """Seconds to resume a video from, per the engine's watch history;
        0 when it wasn't started, or was nearly finished."""
        try:
            self._init()
            history = self.context.get_playback_history()
            data = (history.get_items([video_id]) or {}).get(video_id) or {}
            played = float(data.get('played_time') or 0)
            percent = float(data.get('played_percent') or 0)
        except Exception as exc:  # pylint: disable=broad-except
            _log('resume point of {} failed: {!r}'.format(video_id, exc),
                 xbmc.LOGWARNING)
            return 0
        return played if played >= min_seconds and percent < max_percent \
            else 0

    def channel_header(self, channel_id):
        """Header info for a channel page (see innertube.channel_header),
        cached for a few hours; None when it can't be fetched."""
        try:
            self._init()
            from . import innertube
            cache = self.context.get_function_cache()
            return cache.run(innertube.channel_header, 6 * cache.ONE_HOUR,
                             self.provider.get_client(self.context),
                             channel_id, _scope=cache.SCOPE_BUILTINS)
        except Exception as exc:  # pylint: disable=broad-except
            _log('channel header of {} failed: {!r}'.format(channel_id, exc),
                 xbmc.LOGWARNING)
            return None

    def channel_sorts(self, channel_id, tab):
        """Sort chips for a channel tab (innertube.channel_sorts), cached
        for an hour; [] when there are none or they can't be fetched."""
        try:
            self._init()
            from . import innertube
            cache = self.context.get_function_cache()
            return cache.run(innertube.channel_sorts, cache.ONE_HOUR,
                             self.provider.get_client(self.context),
                             channel_id, tab,
                             _scope=cache.SCOPE_BUILTINS) or []
        except Exception as exc:  # pylint: disable=broad-except
            _log('sorts of {}/{} failed: {!r}'.format(channel_id, tab, exc),
                 xbmc.LOGWARNING)
            return []

    def recent_searches(self):
        """The engine's search history, newest first (shared with its own
        search pages)."""
        try:
            self._init()
            items = self.context.get_search_history().get_items() or ()
            return [item['q'] for item in items
                    if isinstance(item, dict) and item.get('q')]
        except Exception as exc:  # pylint: disable=broad-except
            _log('search history failed: {!r}'.format(exc), xbmc.LOGWARNING)
            return []

    def add_search(self, query):
        try:
            self._init()
            self.context.get_search_history().add_item(query)
        except Exception as exc:  # pylint: disable=broad-except
            _log('saving search failed: {!r}'.format(exc), xbmc.LOGWARNING)

    def listing(self, uri):
        """Run the engine route for a plugin:// URI; returns ListItems."""
        self._init()
        path, params = self.context.parse_uri(uri)
        context = self.context.clone(new_path=path, new_params=params)
        result = self.provider.navigate(context)
        items = result[0] if isinstance(result, tuple) else result
        if not isinstance(items, (list, tuple)):
            return []
        show_fanart = False
        listitems = []
        for item in items:
            convert = self.converters.get(item.__class__.__name__)
            if not convert:
                continue
            if (convert.__name__ == 'directory_listitem'
                    and not getattr(item, 'available', True)):
                continue
            _, listitem, is_folder = convert(context, item,
                                             show_fanart=show_fanart)
            listitem.setIsFolder(is_folder)
            if getattr(item, 'live', False):
                listitem.setProperty('live', 'true')
            listitems.append(listitem)
        return listitems


class RowLoader(object):
    """Fills list controls from plugin:// URIs in the background."""

    def __init__(self):
        self.engine = Engine()
        self._pool = ThreadPoolExecutor(max_workers=WORKERS)
        self._cache = {}
        self._generation = 0
        self._lock = threading.Lock()

    def cached(self, uri):
        entry = self._cache.get(uri)
        if entry and time.time() - entry[0] < CACHE_SECONDS:
            return entry[1]
        return None

    def cancel(self):
        """Results of requests made before this are dropped."""
        with self._lock:
            self._generation += 1

    def load(self, uri, done):
        """Calls done(listitems) from a worker thread, unless cancelled."""
        with self._lock:
            generation = self._generation
        hit = None if uri.startswith(tuple(
            'plugin://{}{}'.format(ADDON_ID, p) for p in _UNCACHED)) else \
            self.cached(uri)
        if hit is not None:
            done(hit)
            return
        self._pool.submit(self._run, uri, done, generation)

    def _run(self, uri, done, generation):
        started = time.time()
        try:
            listitems = self.engine.listing(uri)
        except Exception as exc:  # pylint: disable=broad-except
            _log('{} failed: {!r}'.format(uri, exc), xbmc.LOGWARNING)
            listitems = []
        _log('{} -> {} items in {:.2f}s'.format(
            uri, len(listitems), time.time() - started), xbmc.LOGINFO)
        if listitems:
            self._cache[uri] = (time.time(), listitems)
        with self._lock:
            if generation != self._generation:
                return
        done(listitems)

    def shutdown(self):
        self.cancel()
        self._pool.shutdown(wait=False)
