# -*- coding: utf-8 -*-
"""
    Leanback TV interface.

    The window never talks to YouTube itself. Every row and grid is a skin
    container whose <content> is a plugin:// path of the forked engine, set
    through window properties. Kodi fetches and caches those listings, and
    this controller only handles navigation, playback and the context menu.

    SPDX-License-Identifier: GPL-2.0-only
"""

from urllib.parse import quote_plus

import xbmc
import xbmcgui

from . import ADDON_ID, HINT_PROPERTY, PLUGIN, addon, localize, setting_bool

XML_FILE = 'script-youtube-leanback-main.xml'

NAV_LIST = 9000
ROWS_GROUP = 100
ROW_IDS = tuple(range(101, 109))
GRID = 200
CONTENT_IDS = ROW_IDS + (GRID,)

FOCUS_WAIT_STEPS = 50

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

    # -- lifecycle --------------------------------------------------------

    def onInit(self):
        # onInit runs again whenever we come back from fullscreen video.
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
        media = 'special://home/addons/{}/resources/media/'.format(ADDON_ID)
        entries = (
            (NAV_SEARCH, 39100, 'search.png'),
            (NAV_HOME, 39101, 'home.png'),
            (NAV_SUBSCRIPTIONS, 39102, 'channels.png'),
            (NAV_LIBRARY, 39103, 'playlist.png'),
            (NAV_ACCOUNT, 39105 if self._signed_in else 39104,
             'sign_out.png' if self._signed_in else 'sign_in.png'),
            (NAV_SETTINGS, 39106, 'settings.png'),
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
        if self._signed_in:
            rows += [(39115, PATH_LIKED),
                     (39116, PATH_MY_PLAYLISTS),
                     (39117, PATH_SAVED_PLAYLISTS)]
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
        if view['type'] == 'rows':
            # Re-checked on every show, so history appears after the first
            # video without rebuilding the view.
            rows = without_empty_local_lists(view['rows'])
            for index, row_id in enumerate(ROW_IDS):
                prefix = 'row{}.'.format(index + 1)
                if index < len(rows):
                    label, path = rows[index]
                    self.setProperty(prefix + 'label', localize(label))
                    self.setProperty(prefix + 'path', path)
                else:
                    self.clearProperty(prefix + 'label')
                    self.clearProperty(prefix + 'path')
            self.clearProperty('grid.path')
            focus = ROWS_GROUP
        else:
            self.setProperty('grid.title', view['title'])
            self.setProperty('grid.path', view['path'])
            focus = GRID
        if self.getFocusId() != NAV_LIST or view.get('focus_content'):
            self._focus_when_filled(focus)

    def _focus_when_filled(self, focus):
        """Containers fill asynchronously; focus once something has items."""
        ids = ROW_IDS if focus == ROWS_GROUP else (GRID,)
        start_focus = self.getFocusId()
        monitor = xbmc.Monitor()
        for _ in range(FOCUS_WAIT_STEPS):
            if any(xbmc.getCondVisibility(
                    'Integer.IsGreater(Container({}).NumItems,0)'.format(cid))
                   for cid in ids):
                self.setFocusId(focus)
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

    def onClick(self, control_id):
        if control_id == NAV_LIST:
            self._on_nav(self.getControl(NAV_LIST)
                         .getSelectedItem().getProperty('nav'))
        elif control_id in CONTENT_IDS:
            self._on_item(control_id)

    def onAction(self, action):
        action_id = action.getId()
        if action_id in (ACTION_NAV_BACK, ACTION_PREVIOUS_MENU):
            if self._pop():
                return
            if self.getFocusId() != NAV_LIST:
                self.setFocusId(NAV_LIST)
                return
            self.close()
        elif action_id in (ACTION_CONTEXT_MENU, ACTION_MENU):
            if self.getFocusId() in CONTENT_IDS:
                self._context_menu(self.getFocusId())

    def _on_nav(self, key):
        if key == NAV_HOME:
            self._reset_to({'type': 'rows', 'nav': key,
                            'rows': self._home_rows(), 'focus_content': True})
        elif key == NAV_SEARCH:
            query = xbmcgui.Dialog().input(localize(39107))
            if query:
                path = PATH_SEARCH if self._has_key else PATH_KEYLESS_SEARCH
                self._open_grid('{}: {}'.format(localize(39100), query),
                                path.format(quote_plus(query)),
                                nav=key)
        elif key == NAV_SUBSCRIPTIONS:
            if not self._signed_in:
                xbmcgui.Dialog().notification(addon().getAddonInfo('name'),
                                              localize(39113))
                return
            self._open_grid(localize(39102), PATH_SUBSCRIPTIONS, nav=key)
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
            title = self._item_info(control_id, 'Label')
            # "Next page" inside a grid replaces the grid instead of stacking.
            if (control_id == GRID and self._item_info(
                    control_id, 'Property(specialSort)') == 'bottom'):
                view = self._views[-1]
                view['path'] = path
                self._show(view)
                return
            self._open_grid(title, path)
            return
        self._play(path, self._item_info(control_id, 'Property(video_id)'))

    def _play(self, path, video_id=''):
        if video_id:
            xbmcgui.Window(10000).setProperty(HINT_PROPERTY, video_id)
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
    del window
