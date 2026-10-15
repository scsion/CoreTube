# -*- coding: utf-8 -*-
"""
    Leanback TV interface.

    Every row and grid shows a plugin:// listing of the forked engine, filled
    by this window itself (loader.py), which runs the engine routes in worker
    threads: much faster than one plugin run per row, and selecting an item
    reaches this window instead of Kodi's own handling (which would open its
    Videos window or info dialog). Lists continue endlessly: a listing's
    "next page" item is kept back and its page appended as the end nears.
    Playback goes through the engine's /play/ path, resuming without asking.

    SPDX-License-Identifier: GPL-2.0-only
"""

from urllib.parse import quote_plus

import xbmc
import xbmcgui

from . import ADDON_ID, HINT_PROPERTY, PLUGIN, addon, localize, setting_bool
from . import brand
from . import search
from .loader import RowLoader

XML_FILE = 'script-youtube-leanback-main.xml'

NAV_LIST = 9000
ROWS_GROUP = 100
ROW_IDS = tuple(range(101, 109))
GRID = 200
SEARCH_BAR = 300
# Search view (see search.py): keyboard, Space/Clear/Search, suggestions,
# results shelf.
KEYS = 400
KEY_ACTIONS = 401
SUGGESTIONS = 402
RESULTS = 403
CONTENT_IDS = ROW_IDS + (GRID, RESULTS)

FOCUS_WAIT_STEPS = 50
# Load the next page once the selection is this close to the end of a list.
LOAD_AHEAD = 12
# Resume a video watched for longer than this, unless it was nearly done.
RESUME_MIN_SECONDS = 10
RESUME_MAX_PERCENT = 95

ACTION_MOVE_LEFT, ACTION_MOVE_RIGHT, ACTION_MOVE_UP, ACTION_MOVE_DOWN = (
    1, 2, 3, 4)
MOVES = (ACTION_MOVE_LEFT, ACTION_MOVE_RIGHT, ACTION_MOVE_UP,
         ACTION_MOVE_DOWN)
ACTION_PREVIOUS_MENU = 10
ACTION_NAV_BACK = 92
ACTION_CONTEXT_MENU = 117
ACTION_MENU = 163

NAV_SEARCH = 'search'
NAV_HOME = 'home'
NAV_SUBSCRIPTIONS = 'subscriptions'
NAV_LIBRARY = 'library'
NAV_ACCOUNT = 'account'
NAV_SETTINGS = 'settings'

PATH_TRENDING = PLUGIN + '/special/popular_right_now/'
PATH_RECOMMENDED = PLUGIN + '/special/recommendations/'
PATH_SUBSCRIPTIONS = PLUGIN + '/special/my_subscriptions/'
PATH_LIVE = PLUGIN + '/special/live/'
PATH_WATCH_LATER = PLUGIN + '/kodion/watch_later/list/'
PATH_HISTORY = PLUGIN + '/kodion/playback_history/list/'
PATH_LIKED = PLUGIN + '/channel/mine/playlist/LL/'
PATH_MY_PLAYLISTS = PLUGIN + '/channel/mine/playlists/'
PATH_SAVED_PLAYLISTS = PLUGIN + '/special/saved_playlists/'
PATH_SEARCH = PLUGIN + '/kodion/search/query/?q={}'
PATH_RELATED = PLUGIN + '/special/related_videos/?video_id={}'
PATH_CHANNEL = PLUGIN + '/channel/{}/'

# Keyless equivalents served by leanback/routes.py straight from InnerTube.
PATH_KEYLESS_FEED = PLUGIN + '/leanback/feed/{}/'
PATH_KEYLESS_SEARCH = PLUGIN + '/leanback/search/?q={}'
PATH_KEYLESS_RELATED = PLUGIN + '/leanback/related/?video_id={}'
PATH_KEYLESS_CHANNEL = PLUGIN + '/leanback/channel/?channel_id={}&item_name={}'
# The signed-in account's own lists, read with its sign-in instead of a key.
PATH_KEYLESS_MINE = PLUGIN + '/leanback/mine/{}/'


def has_api_key():
    """The engine's own listings need a user key for the Data API v3.
    Without one the window switches to its keyless InnerTube routes."""
    try:
        return bool(addon().getSetting('youtube.api.key').strip())
    except RuntimeError:
        return False


def is_signed_in():
    """Ask the engine's access manager whether a YouTube account is linked."""
    try:
        from youtube_plugin.kodion.context import XbmcContext

        access_manager = XbmcContext().get_access_manager()
        _, num_tokens = access_manager.get_refresh_tokens()
        return num_tokens > 0
    except Exception as exc:  # pylint: disable=broad-except
        xbmc.log('[{}] sign-in check failed: {}'.format(ADDON_ID, exc),
                 xbmc.LOGWARNING)
        return False


def without_empty_local_lists(rows):
    """Drop the history / watch later rows while those lists are empty.

    Rows can't hide themselves when empty (see tools/gen_skin.py), and these
    two are cheap to check because the engine keeps them locally."""
    try:
        from youtube_plugin.kodion.context import XbmcContext

        context = XbmcContext()
        empty = set()
        if not context.get_playback_history().get_items(limit=1):
            empty.add(PATH_HISTORY)
        if not context.get_watch_later_list().get_items():
            empty.add(PATH_WATCH_LATER)
    except Exception as exc:  # pylint: disable=broad-except
        xbmc.log('[{}] local list check failed: {}'.format(ADDON_ID, exc),
                 xbmc.LOGWARNING)
        return rows
    return [(label, path) for label, path in rows if path not in empty]


class MainWindow(xbmcgui.WindowXML):
    def __init__(self, *args, **kwargs):
        super(MainWindow, self).__init__(*args, **kwargs)
        self._views = []
        self._signed_in = False
        self._has_key = False
        self._nav_ready = False
        self._loader = RowLoader()
        # Path each list currently holds (or is loading), the page that
        # continues it, and the lists fetching that page right now.
        self._paths = {}
        self._next_pages = {}
        self._paging = set()
        self._query = ''
        self._key_mode = 'letters'
        self._typing = search.Debouncer(self._refresh_search)

    # -- lifecycle --------------------------------------------------------

    def onInit(self):
        # onInit runs again whenever we come back from fullscreen video.
        self.setProperty('logo', brand.current())
        if not self._nav_ready:
            self._signed_in = is_signed_in()
            self._has_key = has_api_key()
            self._build_nav()
            self._nav_ready = True
            self._push({'type': 'rows', 'nav': NAV_HOME,
                        'rows': self._home_rows()})
        else:
            self._show(self._views[-1])

    def _build_nav(self):
        nav = self.getControl(NAV_LIST)
        nav.reset()
        # White line icons drawn by tools/gen_textures.py.
        media = ('special://home/addons/{}/resources/skins/Default/media/'
                 .format(ADDON_ID))
        entries = (
            (NAV_SEARCH, 39100, 'icon_search.png'),
            (NAV_HOME, 39101, 'icon_home.png'),
            (NAV_SUBSCRIPTIONS, 39102, 'icon_subscriptions.png'),
            (NAV_LIBRARY, 39103, 'icon_library.png'),
            (NAV_ACCOUNT, 39105 if self._signed_in else 39104,
             'icon_account.png'),
            (NAV_SETTINGS, 39106, 'icon_settings.png'),
        )
        for key, label, icon in entries:
            item = xbmcgui.ListItem(localize(label))
            item.setArt({'icon': media + icon})
            item.setProperty('nav', key)
            nav.addItem(item)
        nav.selectItem(1)

    # -- views ------------------------------------------------------------

    def _open_settings(self):
        addon().openSettings()
        self.setProperty('logo', brand.current())
        self._has_key = has_api_key()
        if self._views and self._views[-1].get('nav') == NAV_HOME:
            self._reset_to({'type': 'rows', 'nav': NAV_HOME,
                            'rows': self._home_rows()})

    def _home_rows(self):
        if not self._has_key:
            return self._keyless_home_rows()
        rows = []
        if setting_bool('leanback.home.subscriptions') and self._signed_in:
            rows.append((39013, PATH_SUBSCRIPTIONS))
        if setting_bool('leanback.home.recommendations'):
            rows.append((39012, PATH_RECOMMENDED))
        if setting_bool('leanback.home.history'):
            rows.append((39016, PATH_HISTORY))
        if setting_bool('leanback.home.trending'):
            rows.append((39011, PATH_TRENDING))
        if setting_bool('leanback.home.live'):
            rows.append((39014, PATH_LIVE))
        if setting_bool('leanback.home.watch_later'):
            rows.append((39015, PATH_WATCH_LATER))
        return rows

    def _keyless_home_rows(self):
        rows = []
        feed = PATH_KEYLESS_FEED.format
        if setting_bool('leanback.home.subscriptions') and self._signed_in:
            rows.append((39013, PATH_KEYLESS_MINE.format('subscriptions')))
        if setting_bool('leanback.home.recommendations'):
            rows.append((39012, feed('recommended')))
        if setting_bool('leanback.home.trending'):
            rows.append((39011, feed('trending')))
        if setting_bool('leanback.home.history'):
            rows.append((39016, PATH_HISTORY))
        if setting_bool('leanback.home.live'):
            rows.append((39014, feed('live')))
        if setting_bool('leanback.home.trending'):
            # YouTube's Explore destinations stand in for the gone
            # Trending page and for the v3 category charts.
            rows += [(39017, feed('news')),
                     (39018, feed('sports')),
                     (39019, feed('gaming'))]
        if setting_bool('leanback.home.watch_later'):
            rows.append((39015, PATH_WATCH_LATER))
        return rows

    def _library_rows(self):
        rows = [(39114, PATH_HISTORY), (39015, PATH_WATCH_LATER)]
        if self._signed_in and self._has_key:
            rows += [(39115, PATH_LIKED),
                     (39116, PATH_MY_PLAYLISTS),
                     (39117, PATH_SAVED_PLAYLISTS)]
        elif self._signed_in:
            mine = PATH_KEYLESS_MINE.format
            rows += [(39115, mine('liked')),
                     (39116, mine('playlists')),
                     (39117, mine('saved_playlists'))]
        return rows

    def _push(self, view):
        self._views.append(view)
        self._show(view)

    def _pop(self):
        if len(self._views) <= 1:
            return False
        self._views.pop()
        self._show(self._views[-1])
        return True

    def _reset_to(self, view):
        self._views = [view]
        self._show(view)

    def _show(self, view):
        self.setProperty('view', view['type'])
        if view.get('nav'):
            self.setProperty('section', view['nav'])
        if view['type'] == 'rows':
            # Re-checked on every show, so history appears after the first
            # video without rebuilding the view.
            rows = without_empty_local_lists(view['rows'])
            self._loader.cancel()
            self._paging.clear()
            self.setProperty('focusrow', '1')
            # The first home shelf gets YouTube TV's big tiles.
            self.setProperty('row1.large',
                             'true' if view.get('nav') == NAV_HOME else '')
            for index, row_id in enumerate(ROW_IDS):
                prefix = 'row{}.'.format(index + 1)
                if index < len(rows):
                    label, path = rows[index]
                    self.setProperty(prefix + 'label', localize(label))
                    self.setProperty(prefix + 'path', path)
                    self._fill(row_id, path, prefix + 'loading',
                               on_empty=lambda p=prefix: self.clearProperty(
                                   p + 'path'))
                else:
                    self.clearProperty(prefix + 'label')
                    self.clearProperty(prefix + 'path')
                    self.clearProperty(prefix + 'loading')
                    self._paths.pop(row_id, None)
                    self.getControl(row_id).reset()
            focus = ROWS_GROUP
        elif view['type'] == 'search':
            self._show_search()
            if view.get('focus_content'):
                self.setFocusId(KEYS)
            return
        else:
            self._loader.cancel()
            self._paging.clear()
            self.setProperty('grid.title', view['title'])
            self._fill(GRID, view['path'], 'grid.loading')
            focus = GRID
        if self.getFocusId() != NAV_LIST or view.get('focus_content'):
            self._focus_when_filled(focus)

    # -- search -------------------------------------------------------------

    def _show_search(self):
        keys = self.getControl(KEYS)
        if not keys.size():
            keys.addItems(search.key_items(self._key_mode))
            actions = self.getControl(KEY_ACTIONS)
            for label, action in ((39120, 'space'), (39121, 'clear'),
                                  (39100, 'search')):
                item = xbmcgui.ListItem(localize(label))
                item.setProperty('action', action)
                actions.addItem(item)
        self._set_query(self._query, refresh_now=True)

    def _set_query(self, query, refresh_now=False):
        self._query = query
        if query:
            self.setProperty('search.query', query)
        else:
            self.clearProperty('search.query')
        if refresh_now:
            self._typing.cancel()
            self._refresh_search(query)
        else:
            self._typing.trigger(query)

    def _refresh_search(self, query):
        """Suggestions and results for what's typed, once typing pauses."""
        if query != self._query:
            return
        if query:
            suggestions = search.suggestion_items(search.fetch_suggestions(
                query, xbmc.getLanguage(xbmc.ISO_639_1) or 'en'))
        else:
            suggestions = search.suggestion_items(
                self._loader.engine.recent_searches(), history=True)
        if query != self._query:
            return
        control = self.getControl(SUGGESTIONS)
        control.reset()
        control.addItems(suggestions)
        if query:
            self.setProperty('search.title', localize(39123).format(query))
            path = PATH_SEARCH if self._has_key else PATH_KEYLESS_SEARCH
            self._fill(RESULTS, path.format(quote_plus(query)),
                       'search.loading')
        else:
            self.clearProperty('search.title')
            self.clearProperty('search.loading')
            self._paths.pop(RESULTS, None)
            self.getControl(RESULTS).reset()

    def _on_key(self):
        key = self.getControl(KEYS).getSelectedItem().getProperty('key')
        if not key:
            return
        if key == search.BACKSPACE:
            self._set_query(self._query[:-1])
        elif key == search.MODE:
            self._key_mode = ('symbols' if self._key_mode == 'letters'
                              else 'letters')
            keys = self.getControl(KEYS)
            position = keys.getSelectedPosition()
            keys.reset()
            keys.addItems(search.key_items(self._key_mode))
            keys.selectItem(position)
        else:
            # Typed in lower case, like YouTube TV, whatever the key shows.
            self._set_query(self._query + key.lower())

    def _on_key_action(self):
        action = self.getControl(KEY_ACTIONS).getSelectedItem().getProperty(
            'action')
        if action == 'space':
            if self._query and not self._query.endswith(' '):
                self._set_query(self._query + ' ')
        elif action == 'clear':
            self._set_query('')
        elif action == 'search' and self._query.strip():
            self._loader.engine.add_search(self._query.strip())
            self._set_query(self._query.strip(), refresh_now=True)
            self.setFocusId(RESULTS)

    def _on_suggestion(self):
        query = self.getControl(SUGGESTIONS).getSelectedItem().getProperty(
            'query')
        if query:
            self._loader.engine.add_search(query)
            self._set_query(query, refresh_now=True)
            self.setFocusId(RESULTS)

    def _fill(self, control_id, path, loading_property, on_empty=None):
        control = self.getControl(control_id)
        # Coming back to a view keeps loaded lists (and their scroll
        # position), except local lists that playback just changed.
        if (self._paths.get(control_id) == path and control.size()
                and '/kodion/' not in path):
            self.clearProperty(loading_property)
            return
        self._paths[control_id] = path
        self._next_pages.pop(control_id, None)
        control.reset()
        self.setProperty(loading_property, 'true')

        def done(listitems):
            if self._paths.get(control_id) != path:
                return
            listitems = self._keep_next_page(control_id, listitems)
            control.reset()
            control.addItems(listitems)
            self.clearProperty(loading_property)
            if not listitems and on_empty:
                on_empty()

        self._loader.load(path, done)

    def _keep_next_page(self, control_id, listitems):
        """Hold back a listing's trailing "next page" item: its page is
        appended when the selection gets close to the end instead."""
        # Next-page items are folders marked specialSort=bottom, and all of
        # them carry the continuation as page_token.
        last = listitems[-1] if listitems else None
        if last and not last.getProperty('video_id') and (
                last.getProperty('specialSort') == 'bottom'
                or 'page_token=' in last.getPath()):
            self._next_pages[control_id] = listitems[-1].getPath()
            return listitems[:-1]
        self._next_pages.pop(control_id, None)
        return listitems

    def _load_more(self, control_id):
        next_path = self._next_pages.get(control_id)
        if not next_path or control_id in self._paging:
            return
        control = self.getControl(control_id)
        if control.getSelectedPosition() < control.size() - LOAD_AHEAD:
            return
        self._paging.add(control_id)
        path = self._paths.get(control_id)

        def done(listitems):
            self._paging.discard(control_id)
            if self._paths.get(control_id) != path:
                return
            # Kodi moves the selection back towards the top when items are
            # added, so put it back where the user is.
            position = control.getSelectedPosition()
            control.addItems(self._keep_next_page(control_id, listitems))
            control.selectItem(position)

        self._loader.load(next_path, done)

    def _first_filled_row(self, wait_for_loading=False):
        """The topmost shelf with items. With wait_for_loading, None while a
        shelf above it is still loading, so startup focus lands on the top
        shelf even when a lower one arrives first."""
        for index, row_id in enumerate(ROW_IDS):
            if xbmc.getCondVisibility(
                    'Integer.IsGreater(Container({}).NumItems,0)'
                    .format(row_id)):
                return row_id
            if wait_for_loading and self.getProperty(
                    'row{}.loading'.format(index + 1)) == 'true':
                return None
        return None

    def _focus_when_filled(self, focus):
        """Containers fill asynchronously; focus once something has items."""
        start_focus = self.getFocusId()
        monitor = xbmc.Monitor()
        for _ in range(FOCUS_WAIT_STEPS):
            if focus == ROWS_GROUP:
                target = self._first_filled_row(wait_for_loading=True)
            elif xbmc.getCondVisibility(
                    'Integer.IsGreater(Container({}).NumItems,0)'
                    .format(GRID)):
                target = GRID
            else:
                target = None
            if target:
                self.setFocusId(target)
                return
            # Stop waiting if the user moved on in the meantime.
            if (monitor.waitForAbort(0.1)
                    or self.getFocusId() != start_focus):
                return

    def _open_grid(self, title, path, nav=None):
        view = {'type': 'grid', 'title': title, 'path': path,
                'focus_content': True}
        if nav:
            view['nav'] = nav
            self._reset_to(view)
        else:
            self._push(view)

    # -- input ------------------------------------------------------------

    def onFocus(self, control_id):
        # Drives the skin's scroll: the focused shelf slides to the top.
        if control_id in ROW_IDS:
            self.setProperty('focusrow', str(ROW_IDS.index(control_id) + 1))
        elif control_id == SEARCH_BAR:
            self.setProperty('focusrow', '1')

    def onClick(self, control_id):
        if control_id == SEARCH_BAR:
            self._on_nav(NAV_SEARCH)
        elif control_id == KEYS:
            self._on_key()
        elif control_id == KEY_ACTIONS:
            self._on_key_action()
        elif control_id == SUGGESTIONS:
            self._on_suggestion()
        elif control_id == NAV_LIST:
            self._on_nav(self.getControl(NAV_LIST)
                         .getSelectedItem().getProperty('nav'))
        elif control_id in CONTENT_IDS:
            self._on_item(control_id)

    def onAction(self, action):
        action_id = action.getId()
        if action_id in (ACTION_NAV_BACK, ACTION_PREVIOUS_MENU):
            # Like YouTube TV: Back from a lower shelf returns to the top.
            first = self._first_filled_row()
            if self.getFocusId() in ROW_IDS and self.getFocusId() != first:
                self.setFocusId(first)
                return
            if self._pop():
                return
            if self.getFocusId() != NAV_LIST:
                self.setFocusId(NAV_LIST)
                return
            self.close()
        elif action_id in MOVES:
            if self.getFocusId() in CONTENT_IDS:
                self._load_more(self.getFocusId())
        elif action_id in (ACTION_CONTEXT_MENU, ACTION_MENU):
            if self.getFocusId() in CONTENT_IDS:
                self._context_menu(self.getFocusId())

    def _on_nav(self, key):
        if key == NAV_HOME:
            self._reset_to({'type': 'rows', 'nav': key,
                            'rows': self._home_rows(), 'focus_content': True})
        elif key == NAV_SEARCH:
            # YouTube TV's own search screen instead of Kodi's keyboard.
            self._reset_to({'type': 'search', 'nav': key,
                            'focus_content': True})
        elif key == NAV_SUBSCRIPTIONS:
            if not self._signed_in:
                xbmcgui.Dialog().notification(addon().getAddonInfo('name'),
                                              localize(39113))
                return
            self._open_grid(localize(39102),
                            PATH_SUBSCRIPTIONS if self._has_key else
                            PATH_KEYLESS_MINE.format('subscriptions'),
                            nav=key)
        elif key == NAV_LIBRARY:
            self._reset_to({'type': 'rows', 'nav': key,
                            'rows': self._library_rows(),
                            'focus_content': True})
        elif key == NAV_ACCOUNT:
            mode = 'out' if self._signed_in else 'in'
            xbmc.executebuiltin('RunPlugin({}/sign/{}/)'.format(PLUGIN, mode),
                                True)
            self._signed_in = is_signed_in()
            self._build_nav()
            self._reset_to({'type': 'rows', 'nav': NAV_HOME,
                            'rows': self._home_rows()})
        elif key == NAV_SETTINGS:
            self._open_settings()

    def _item_info(self, control_id, label):
        return xbmc.getInfoLabel(
            'Container({}).ListItem.{}'.format(control_id, label))

    def _on_item(self, control_id):
        path = self._item_info(control_id, 'FileNameAndPath')
        if not path:
            return
        if xbmc.getCondVisibility(
                'Container({}).ListItem.IsFolder'.format(control_id)):
            self._open_grid(self._item_info(control_id, 'Label'), path)
            return
        self._play(path, self._item_info(control_id, 'Property(video_id)'))

    def _play(self, path, video_id=''):
        """Play straight away. A video watched part-way resumes from where
        it stopped: the engine's seek parameter, so Kodi never asks."""
        if video_id:
            xbmcgui.Window(10000).setProperty(HINT_PROPERTY, video_id)
            position = self._loader.engine.resume_point(
                video_id, RESUME_MIN_SECONDS, RESUME_MAX_PERCENT)
            if position and 'seek=' not in path:
                path = '{}{}seek={}'.format(path, '&' if '?' in path else '?',
                                            int(position))
        xbmc.executebuiltin('PlayMedia("{}")'.format(path))

    def _context_menu(self, control_id):
        path = self._item_info(control_id, 'FileNameAndPath')
        video_id = self._item_info(control_id, 'Property(video_id)')
        channel_id = self._item_info(control_id, 'Property(channel_id)')
        channel = self._item_info(control_id, 'Artist')
        options = []
        if self._has_key:
            related_path = PATH_RELATED.format(video_id)
            channel_path = PATH_CHANNEL.format(channel_id)
        else:
            related_path = PATH_KEYLESS_RELATED.format(video_id)
            channel_path = PATH_KEYLESS_CHANNEL.format(
                channel_id, quote_plus(channel))
        if video_id:
            options.append((localize(39108),
                            lambda: self._play(path, video_id)))
            options.append((localize(39110), lambda: self._open_grid(
                localize(39110), related_path)))
        if channel_id:
            options.append((localize(39109), lambda: self._open_grid(
                channel or localize(39109), channel_path)))
        if not options:
            return
        choice = xbmcgui.Dialog().contextmenu([label for label, _ in options])
        if choice >= 0:
            options[choice][1]()


def run():
    window = MainWindow(XML_FILE, addon().getAddonInfo('path'),
                        'Default', '1080i')
    window.doModal()
    window._typing.cancel()  # pylint: disable=protected-access
    window._loader.shutdown()  # pylint: disable=protected-access
    del window
