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

import re
import threading
from urllib.parse import parse_qs, quote_plus, urlsplit

import xbmc
import xbmcgui

from . import ADDON_ID, HINT_PROPERTY, PLUGIN, addon, localize, setting_bool
from . import brand
from . import search
from .loader import RowLoader

XML_FILE = 'script-coretube-main.xml'

NAV_LIST = 9000
ROWS_GROUP = 100
ROW_IDS = tuple(range(101, 111))
GRID = 200
SEARCH_BAR = 300
# Search view (see search.py): keyboard, Space/Clear/Search, suggestions,
# results shelf.
KEYS = 400
KEY_ACTIONS = 401
SUGGESTIONS = 402
RESULTS = 403
# Channel page tabs above its grid: the channel's own (YouTube names and
# orders them), opening on the first, normally Home.
TABS = 210
# The open tab's sort chips (Latest / Popular / Oldest, or YouTube's
# filters for that channel), under the tabs.
SORTS = 211
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
PATH_CHANNEL_TAB = (PLUGIN + '/leanback/channeltab/{tab}/'
                    '?channel_id={channel_id}&item_name={name}')
PATH_CHANNEL_SORT = '&order={}'
# The signed-in account's own lists, read with its sign-in instead of a key.
PATH_KEYLESS_MINE = PLUGIN + '/leanback/mine/{}/'
# The account's YouTube watch history, from every device it's signed in on.
PATH_ACCOUNT_HISTORY = PATH_KEYLESS_MINE.format('history')
# Its unfinished videos: "Continue watching" across devices.
PATH_ACCOUNT_CONTINUE = PATH_KEYLESS_MINE.format('continue')


def continue_path(signed_in):
    """The "Continue watching" row. Signed in, with playback reported to
    the account (so this box's videos are in its history too), it's the
    account's unfinished videos from every device; otherwise this box's own
    playback history."""
    if signed_in:
        try:
            if addon().getSetting('kodion.history.remote') == 'true':
                return PATH_ACCOUNT_CONTINUE
        except RuntimeError:
            pass
    return PATH_HISTORY


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


def reload_service_sign_in():
    """Have the engine's service pick up a new sign-in (or sign-out).

    The service reads the account's tokens once, when Kodi starts, and
    reports playback to YouTube's watch history with them. Without this,
    after a first sign-in every report was skipped ("Invalid or disabled
    client") until Kodi was restarted. The engine's own user-switching
    actions send the same notification."""
    try:
        from youtube_plugin.kodion.constants import RELOAD_ACCESS_MANAGER
        from youtube_plugin.kodion.context import XbmcContext

        XbmcContext.send_notification(RELOAD_ACCESS_MANAGER)
    except Exception as exc:  # pylint: disable=broad-except
        xbmc.log('[{}] sign-in reload for the service failed: {}'.format(
            ADDON_ID, exc), xbmc.LOGWARNING)


def underline_width(title):
    """Width of the open tab's underline: the title's width in the tab font
    (Bald's DM Sans Medium 30), estimated per character and snapped to the
    widths the skin provides (40-200 in steps of 20)."""
    width = sum(22 if char.isupper() else 9 if char in 'ijlt ' else 17
                for char in title)
    return max(40, min(200, int(round(width / 20.0)) * 20))


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
        # (control id, list position) to go back to after a video.
        self._return_focus = None
        self._loader = RowLoader()
        # Path each list currently holds (or is loading), the page that
        # continues it, and the lists fetching that page right now.
        self._paths = {}
        self._next_pages = {}
        self._paging = set()
        self._query = ''
        self._key_mode = 'letters'
        self._typing = search.Debouncer(self._refresh_search)
        # leanback/launch.py: the start-up splash, and where we came from.
        self.launch = None

    # -- lifecycle --------------------------------------------------------

    def onInit(self):
        # onInit runs again whenever we come back from fullscreen video.
        self.setProperty('logo', brand.current())
        # The window's fonts are Bald's; any other skin falls back to its
        # font13, so the badges switch to their larger sizes (gen_skin.py).
        self.setProperty('fonts', '' if xbmc.getSkinDir() == 'skin.bald'
                         else 'fallback')
        if not self._nav_ready:
            self._signed_in = is_signed_in()
            self._has_key = has_api_key()
            self._build_nav()
            self._nav_ready = True
            self._push({'type': 'rows', 'nav': NAV_HOME,
                        'rows': self._home_rows()})
            if self.launch:
                self.launch.offer_favourite(lambda: xbmc.getCondVisibility(
                    'Window.IsActive({})'.format(XML_FILE)))
        elif not self._restore_focus():
            self._show(self._views[-1])

    def _restore_focus(self):
        """Back from a video: return to the tile that was played, without
        redrawing the view. False when there is nothing to return to."""
        if not self._return_focus:
            return False
        focus_id, position = self._return_focus
        self._return_focus = None
        if not xbmc.getCondVisibility(
                'Integer.IsGreater(Container({}).NumItems,0)'.format(focus_id)):
            return False
        self.setFocusId(focus_id)
        if position >= 0:
            self.getControl(focus_id).selectItem(position)
        return True

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
            rows.append((39016, continue_path(self._signed_in)))
            if self._signed_in:
                rows.append((39135, PATH_ACCOUNT_HISTORY))
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
            rows.append((39016, continue_path(self._signed_in)))
            if self._signed_in:
                rows.append((39135, PATH_ACCOUNT_HISTORY))
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
        rows = [(39114, PATH_HISTORY)]
        if self._signed_in:
            rows.append((39135, PATH_ACCOUNT_HISTORY))
        rows.append((39015, PATH_WATCH_LATER))
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
        elif view['type'] == 'channel':
            self._show_channel(view)
            return
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

    # -- channel page -------------------------------------------------------

    def _open_channel(self, channel_id, name=''):
        self._push({'type': 'channel', 'channel_id': channel_id,
                    'title': re.sub(r'\[/?[A-Z]+\]', '', name or ''),
                    'tab': None, 'focus_content': True})

    def _show_channel(self, view):
        """The header and tabs come first (they say which tabs exist);
        the open tab's grid follows."""
        self._loader.cancel()
        self._paging.clear()
        if view.get('header') is not None:
            self._show_channel_tab(view)
            return
        self._set_channel_header(view, {})
        self.getControl(TABS).reset()
        self._tab_keys = ()
        self.setProperty('grid.loading', 'true')
        self.getControl(GRID).reset()
        self._paths.pop(GRID, None)

        def fetch():
            view['header'] = (self._loader.engine.channel_header(
                view['channel_id']) or {})
            if not (self._views and self._views[-1] is view):
                return
            try:
                self._show_channel_tab(view)
            except Exception as exc:  # pylint: disable=broad-except
                # Never leave the page loading: show it empty instead.
                xbmc.log('[{}] channel page failed: {!r}'.format(
                    ADDON_ID, exc), xbmc.LOGWARNING)
                self.clearProperty('grid.loading')
        threading.Thread(target=fetch, daemon=True).start()

    def _show_channel_tab(self, view):
        header = view['header']
        tabs = [tab for tab in header.get('tabs') or ()
                if isinstance(tab, dict)] or [{'key': 'videos',
                                               'title': 'Videos'}]
        header['tabs'] = tabs
        if view['tab'] not in [tab['key'] for tab in tabs]:
            view['tab'] = tabs[0]['key']
        self._set_channel_header(view, header)
        path = PATH_CHANNEL_TAB.format(
            tab=view['tab'], channel_id=view['channel_id'],
            name=quote_plus(view.get('title') or ''))
        if view.get('sort'):
            path += PATH_CHANNEL_SORT.format(view['sort'])
        self._fill(GRID, path, 'grid.loading')
        self._show_sorts(view)
        if view.pop('focus_content', False):
            # The tabs show at once; the videos take focus on arrival.
            self.setFocusId(TABS)
            self._focus_when_filled(GRID, start_focus=TABS)

    def _set_channel_header(self, view, header):
        header = header or {}
        name = header.get('title') or view.get('title') or ''
        if header.get('title'):
            view['title'] = header['title']
        for key, value in (('name', name),
                           ('handle', header.get('handle')),
                           ('stats', header.get('stats')),
                           ('avatar', header.get('avatar')),
                           ('banner', header.get('banner'))):
            if value:
                self.setProperty('channel.' + key, value)
            else:
                self.clearProperty('channel.' + key)
        # The list is only rebuilt for another channel's set of tabs, never
        # under the focus when switching tabs; only the open tab's marker
        # moves.
        entries = header.get('tabs') or ()
        keys = tuple(tab['key'] for tab in entries)
        tabs = self.getControl(TABS)
        if keys != getattr(self, '_tab_keys', ()):
            self._tab_keys = keys
            tabs.reset()
            for tab in entries:
                item = xbmcgui.ListItem(tab['title'])
                item.setProperty('tab', tab['key'])
                item.setProperty('ulw', str(underline_width(tab['title'])))
                tabs.addItem(item)
        for index, key in enumerate(keys):
            tabs.getListItem(index).setProperty(
                'selected', 'true' if key == view['tab'] else '')

    def _show_sorts(self, view):
        """The open tab's sort chips, fetched once per tab in the
        background; the row stays hidden for tabs without any."""
        key = (view['channel_id'], view['tab'])
        sorts = view.setdefault('sorts', {})
        if key[1] in sorts:
            self._set_sorts(view, sorts[key[1]])
            return
        self.clearProperty('channel.sorts')

        def fetch():
            chips = self._loader.engine.channel_sorts(*key)
            sorts[key[1]] = chips
            if (self._views and self._views[-1] is view
                    and view['tab'] == key[1]):
                self._set_sorts(view, chips)
        threading.Thread(target=fetch, daemon=True).start()

    def _set_sorts(self, view, chips):
        control = self.getControl(SORTS)
        keys = tuple(chip['key'] for chip in chips)
        if keys != getattr(self, '_sort_keys', ()):
            self._sort_keys = keys
            control.reset()
            for chip in chips:
                item = xbmcgui.ListItem(chip['title'])
                item.setProperty('sort', chip['key'])
                control.addItem(item)
        current = view.get('sort') or next(
            (chip['key'] for chip in chips if chip['selected']), None)
        for index, key in enumerate(keys):
            control.getListItem(index).setProperty(
                'selected', 'true' if key == current else '')
        if chips:
            self.setProperty('channel.sorts', 'true')
        else:
            self.clearProperty('channel.sorts')

    def _on_sort(self):
        view = self._views[-1]
        sort = self.getControl(SORTS).getSelectedItem().getProperty('sort')
        if view.get('type') != 'channel' or not sort:
            return
        chips = view.get('sorts', {}).get(view['tab']) or ()
        default = next((chip['key'] for chip in chips if chip['selected']),
                       None)
        current = view.get('sort') or default
        if sort == current:
            return
        # The default chip is the tab's own listing, with no order.
        view['sort'] = None if sort == default else sort
        self._loader.cancel()
        self._paging.clear()
        self._show_channel_tab(view)

    def _on_tab(self):
        view = self._views[-1]
        tab = self.getControl(TABS).getSelectedItem().getProperty('tab')
        if view.get('type') != 'channel' or not tab or tab == view['tab']:
            return
        view['tab'] = tab
        view['sort'] = None
        self._loader.cancel()
        self._paging.clear()
        self._show_channel_tab(view)

    # -- search -------------------------------------------------------------

    def _show_search(self):
        keys = self.getControl(KEYS)
        if not keys.size():
            keys.addItems(search.key_items(self._key_mode))
            actions = self.getControl(KEY_ACTIONS)
            for label, action in ((39120, 'space'), (39121, 'clear'),
                                  (39100, 'search')):
                # Capitals in bold, as YouTube TV labels these buttons.
                item = xbmcgui.ListItem('[B]{}[/B]'.format(
                    localize(label).upper()))
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
            # Relabel the keys in place: emptying the focused panel with
            # reset() made Kodi move focus away, onto the rail.
            keys = self.getControl(KEYS)
            for index, item in enumerate(search.key_items(self._key_mode)):
                key = keys.getListItem(index)
                key.setLabel(item.getLabel())
                key.setProperty('key', item.getProperty('key'))
                key.setArt({'icon': item.getArt('icon')})
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

        self._loader.load(path, done, owner=control_id)

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

        self._loader.load(next_path, done, owner=control_id)

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

    def _focus_when_filled(self, focus, start_focus=None):
        """Containers fill asynchronously; focus once something has items.
        start_focus: the control focus was just sent to, which Kodi may not
        report yet."""
        waiting_on = {self.getFocusId(), start_focus or self.getFocusId()}
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
                    or self.getFocusId() not in waiting_on):
                return
        # Nothing arrived. Don't leave focus on a list of the previous view,
        # now hidden, where key presses would still act.
        if not xbmc.getCondVisibility(
                'Control.IsVisible({})'.format(self.getFocusId())):
            self.setFocusId(NAV_LIST)

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
        elif control_id == TABS:
            # Coming up from the videos lands on the open tab, as on YouTube.
            view = self._views[-1] if self._views else {}
            keys = getattr(self, '_tab_keys', ())
            if view.get('type') == 'channel' and view.get('tab') in keys:
                self.getControl(TABS).selectItem(keys.index(view['tab']))
        elif control_id == SORTS:
            # Likewise onto the open sort chip.
            control = self.getControl(SORTS)
            for index in range(control.size()):
                if control.getListItem(index).getProperty('selected'):
                    control.selectItem(index)
                    break

    def onClick(self, control_id):
        if control_id == SEARCH_BAR:
            self._on_nav(NAV_SEARCH)
        elif control_id == KEYS:
            self._on_key()
        elif control_id == KEY_ACTIONS:
            self._on_key_action()
        elif control_id == TABS:
            self._on_tab()
        elif control_id == SORTS:
            self._on_sort()
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
            if self._signed_in:
                # Ask here rather than in the engine: its Yes/No, opened from
                # a plugin call, can come up with nothing focused, and then
                # the remote can't answer it.
                if not xbmcgui.Dialog().yesno(localize(39105),
                                              xbmc.getLocalizedString(750)):
                    return
                path = '{}/sign/out/?confirmed=true'.format(PLUGIN)
            else:
                path = '{}/sign/in/'.format(PLUGIN)
            xbmc.executebuiltin('RunPlugin({})'.format(path), True)
            signed_in = is_signed_in()
            if signed_in != self._signed_in:
                reload_service_sign_in()
            self._signed_in = signed_in
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
            parts = urlsplit(path)
            if parts.path.rstrip('/').endswith('/leanback/channel'):
                params = parse_qs(parts.query)
                self._open_channel(
                    (params.get('channel_id') or [''])[0],
                    (params.get('item_name') or [''])[0]
                    or self._item_info(control_id, 'Label'))
                return
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
            # This box's own position beats the account's (YouTube history
            # tiles carry the account's in their path).
            if position:
                path = re.sub(r'[?&]seek=[^&]*', '', path)
                path = '{}{}seek={}'.format(path, '&' if '?' in path else '?',
                                            int(position))
        focus_id = self.getFocusId()
        try:
            selected = self.getControl(focus_id).getSelectedPosition()
        except (RuntimeError, TypeError, AttributeError):
            selected = -1
        self._return_focus = (focus_id, selected)
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
        if channel_id and self._has_key:
            options.append((localize(39109), lambda: self._open_grid(
                channel or localize(39109), channel_path)))
        elif channel_id:
            options.append((localize(39109), lambda: self._open_channel(
                channel_id, channel)))
        if not options:
            return
        choice = xbmcgui.Dialog().contextmenu([label for label, _ in options])
        if choice >= 0:
            options[choice][1]()


def run(launch=None):
    window = MainWindow(XML_FILE, addon().getAddonInfo('path'),
                        'Default', '1080i')
    window.launch = launch
    try:
        window.doModal()
    finally:
        if launch:
            launch.finish()
    window._typing.cancel()  # pylint: disable=protected-access
    window._loader.shutdown()  # pylint: disable=protected-access
    del window
