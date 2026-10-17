# -*- coding: utf-8 -*-
"""
    Keyless plugin routes for the leanback window.

    Registered on the engine's router before it runs (see leanback_plugin.py),
    so they share its context, caches, settings and listitem conversion, and
    the items they return carry the same properties as the engine's own
    (video_id, channel_id, Artist, PublishedSince, Duration, Plot, thumb).
    The data comes from innertube.py instead of the Data API v3, so none of
    these need a personal API key:

        /leanback/feed/<name>/       trending, news, sports, gaming, live,
                                     learning, recommended
        /leanback/search/?q=
        /leanback/related/?video_id=
        /leanback/channel/?channel_id=[&item_name=<channel title>]
        /leanback/playlist/?playlist_id=
        /leanback/mine/<name>/       subscriptions, liked, playlists,
                                     saved_playlists (signed in only)

    Signed in, the recommended feed, playlists and the mine/ lists are read
    as the account through the engine's TV sign-in, which needs no key
    either.

    SPDX-License-Identifier: GPL-2.0-only
"""

import re

from youtube_plugin.kodion.abstract_provider import AbstractProvider
from youtube_plugin.kodion.constants import (
    CHANNEL_ID,
    CONTENT,
    PATHS,
    PLAYLIST_ID,
    VIDEO_ID,
)
from youtube_plugin.kodion.items import DirectoryItem, VideoItem

from . import innertube

ROOT = '/leanback'
PATH_FEED = ROOT + '/feed'
PATH_SEARCH = ROOT + '/search'
PATH_RELATED = ROOT + '/related'
PATH_CHANNEL = ROOT + '/channel'
PATH_PLAYLIST = ROOT + '/playlist'
PATH_MINE = ROOT + '/mine'

FEEDS = frozenset(innertube.DESTINATIONS) | {'trending', 'recommended'}
# The signed-in account's own lists, read with its TV sign-in.
MINE = {
    'subscriptions': innertube.subscriptions,
    'history': innertube.history,
    'liked': innertube.liked,
    'playlists': innertube.my_playlists,
    'saved_playlists': innertube.saved_playlists,
}

# Shelf contents change through the day; paged lists are only ever re-read
# when someone pages back, so they can live a little longer. The account's
# own lists change when the user acts, so they expire sooner.
FEED_CACHE = 30 * 60
PAGE_CACHE = 60 * 60
MINE_CACHE = 5 * 60
# Except the account's watch history: a video just watched on the phone
# should be there when CoreTube is opened. Short enough for that, long
# enough that rows loading together share one request.
HISTORY_CACHE = 30

# Resume a video watched on another device only between these.
ACCOUNT_RESUME_MIN = 10
ACCOUNT_RESUME_MAX_PERCENT = 95

SEPARATOR = ' • '

# Emoji and their joiners/variation selectors. Kodi's fonts have no colour
# emoji and draw them as empty boxes, so titles drop them.
_EMOJI = re.compile('[\U0001F000-\U0001FAFF☀-➿️‍'
                    '⬀-⯿\U000E0000-\U000E007F]+')


def _clean(title):
    return ' '.join(_EMOJI.sub(' ', title or '').split())


# -- item conversion --------------------------------------------------------

def _plot(data):
    stats = SEPARATOR.join(filter(None, (
        data.get('channel'), data.get('views'), data.get('published'))))
    return '\n'.join(filter(None, (stats, data.get('description'))))


def _account_resume(data):
    """(seconds watched, seconds to resume from) for a video the account
    watched part-way on any device (YouTube's red bar). A nearly finished
    video shows a full bar but starts from the beginning, as on YouTube."""
    duration, watched = data.get('duration'), data.get('watched')
    if not duration or not watched or data.get('live'):
        return 0, 0
    seconds = duration * watched // 100
    if watched >= ACCOUNT_RESUME_MAX_PERCENT or seconds < ACCOUNT_RESUME_MIN:
        return seconds, 0
    return seconds, seconds


def _video_item(context, data, play_data):
    video_id = data['id']
    watched, resume = (0, 0) if play_data else _account_resume(data)
    params = {VIDEO_ID: video_id}
    if resume:
        # The leanback window replaces this with the box's own position
        # when there is one (leanback/gui.py).
        params['seek'] = resume
    item = VideoItem(
        _clean(data.get('title')) or video_id,
        context.create_uri((PATHS.PLAY,), params),
        image=data.get('thumb'),
        plot=_plot(data),
        video_id=video_id,
        channel_id=data.get('channel_id'),
    )
    if data.get('channel'):
        item.add_artist(data['channel'])
    # Label2 under the tile, worded the way YouTube shows it:
    # "28K views • 3 years ago".
    item.set_short_details(SEPARATOR.join(filter(None, (
        data.get('views'), data.get('published')))))
    if data.get('duration'):
        item.set_duration_from_seconds(data['duration'])
    published = innertube.parse_ago(data.get('published'))
    if published:
        item.set_added_utc(published)
        item.set_aired_from_datetime(published)
    if data.get('live'):
        item.live = True
    if data.get('upcoming'):
        item.upcoming = True
    if watched:
        # Progress bar from the account; Kodi's own history wins when the
        # video was played on this box.
        item.set_start_percent(data['watched'])
        item.set_start_time(watched)
    if play_data:
        if 'play_count' in play_data:
            item.set_play_count(play_data['play_count'])
        if 'last_played' in play_data:
            item.set_last_played(play_data['last_played'])
        if not item.live:
            if 'played_percent' in play_data:
                item.set_start_percent(play_data['played_percent'])
            if 'played_time' in play_data:
                item.set_start_time(play_data['played_time'])
    return item


def _channel_item(context, data):
    return DirectoryItem(
        context.get_ui().bold(data.get('title') or data['id']),
        context.create_uri(PATH_CHANNEL, {CHANNEL_ID: data['id'],
                                          'item_name': data.get('title', '')}),
        image=data.get('thumb'),
        plot=data.get('description') or data.get('title'),
        category_label=data.get('title'),
        channel_id=data['id'],
    )


def _playlist_item(context, data):
    item = DirectoryItem(
        data.get('title') or data['id'],
        context.create_uri(PATH_PLAYLIST, {PLAYLIST_ID: data['id']}),
        image=data.get('thumb'),
        plot='\n'.join(filter(None, (data.get('channel'),
                                     data.get('description')))),
        category_label=data.get('title'),
        playlist_id=data['id'],
    )
    if data.get('channel'):
        item.add_artist(data['channel'])
    return item


def _next_page_item(context, page_token):
    params = dict(context.get_params())
    params['page_token'] = page_token
    params['page'] = (params.get('page') or 1) + 1
    return DirectoryItem(
        context.localize('page.next', params['page']),
        context.create_uri(context.get_path(), params),
        image='DefaultFolder.png',
        category_label='__inherit__',
        # The leanback grid replaces itself with "next page" items.
        special_sort='bottom',
    )


def _to_items(context, page):
    entries = page.get('items') or ()
    play_data = {}
    if context.get_settings().use_local_history():
        video_ids = [data['id'] for data in entries if data['kind'] == 'video']
        if video_ids:
            play_data = context.get_playback_history().get_items(video_ids)
    result = []
    for data in entries:
        kind = data['kind']
        if kind == 'video':
            result.append(_video_item(context, data, play_data.get(data['id'])))
        elif kind == 'channel':
            result.append(_channel_item(context, data))
        elif kind == 'playlist':
            result.append(_playlist_item(context, data))
    if page.get('next'):
        result.append(_next_page_item(context, page['next']))
    return result


def _listing(provider, context, page, category_label=None):
    if not page or not page.get('items'):
        # Kodi treats this as a failed listing: an empty row hides itself.
        return False, None
    return _to_items(context, page), {
        provider.CONTENT_TYPE: {
            'content_type': CONTENT.VIDEO_CONTENT,
            'sub_type': None,
            'category_label': category_label,
        },
    }


def _account(context, client):
    """The signed-in account's ID, or None when signed out. Authed requests
    must wait for this: signed out, the engine answers them with a sign-in
    prompt. The ID goes into cache keys, so one account's lists are never
    shown to another."""
    if not client.logged_in:
        return None
    return context.get_access_manager().get_current_user_id()


def _cached(context, seconds, func, *args, **kwargs):
    """Cache parsed pages. The engine client is reduced to its type in the
    cache key, so only the builtin arguments tell results apart."""
    function_cache = context.get_function_cache()
    return function_cache.run(
        func,
        seconds,
        *args,
        _refresh=context.refresh_requested(),
        _scope=function_cache.SCOPE_BUILTINS,
        **kwargs
    )


# -- routes -----------------------------------------------------------------

@AbstractProvider.register_path('^' + PATH_FEED + '/(?P<feed>[a-z_]+)/?$')
def on_feed(provider, context, re_match):
    name = re_match.group('feed')
    if name not in FEEDS:
        return False, None
    client = provider.get_client(context)
    if name == 'recommended':
        page = _recommended(context, client)
    elif name == 'trending':
        page = _cached(context, FEED_CACHE, innertube.trending, client)
    else:
        page = _cached(context, FEED_CACHE, innertube.destination,
                       client, name)
    return _listing(provider, context, page)


def _recommended(context, client):
    account = _account(context, client)
    if account:
        page = _cached(context, FEED_CACHE, innertube.home_feed, client,
                       account)
        if page and page.get('items'):
            return page
    seeds = ()
    if context.get_settings().use_local_history():
        seeds = tuple(context.get_playback_history().get_items(
            limit=innertube.RECOMMEND_SEEDS) or ())
    if not seeds:
        # Nothing watched yet: start from what's popular instead of leaving
        # the row empty (the trending page is usually cached already).
        trending = _cached(context, FEED_CACHE, innertube.trending, client)
        seeds = tuple(data['id'] for data in (trending or {}).get('items', ())
                      if not data.get('live'))[:innertube.RECOMMEND_SEEDS]
    if not seeds:
        return None
    # The seed list is part of the cache key: watching something new
    # refreshes the row straight away.
    return _cached(context, FEED_CACHE, innertube.recommended, client, seeds)


@AbstractProvider.register_path('^' + PATH_MINE + '/(?P<name>[a-z_]+)/?$')
def on_mine(provider, context, re_match):
    name = re_match.group('name')
    # Continue watching: the unfinished videos of the account's history,
    # from any device, read from the same (shared, cached) history page.
    unfinished = name == 'continue'
    if unfinished:
        name = 'history'
    func = MINE.get(name)
    if not func:
        return False, None
    client = provider.get_client(context)
    account = _account(context, client)
    if not account:
        return False, None
    page = _cached(context,
                   HISTORY_CACHE if name == 'history' else MINE_CACHE,
                   func, client, account, context.get_param('page_token'))
    if unfinished and page:
        page = innertube.unfinished(page)
    return _listing(provider, context, page)


@AbstractProvider.register_path('^' + PATH_SEARCH + '/?$')
def on_search(provider, context, re_match):
    query = context.get_param('q')
    if not query:
        return False, None
    page_token = context.get_param('page_token')
    page = _cached(context, PAGE_CACHE, innertube.search,
                   provider.get_client(context), query, page_token)
    return _listing(provider, context, page, category_label=query)


@AbstractProvider.register_path('^' + PATH_RELATED + '/?$')
def on_related(provider, context, re_match):
    video_id = context.get_param(VIDEO_ID)
    if not video_id:
        return False, None
    page = _cached(context, PAGE_CACHE, innertube.related,
                   provider.get_client(context), video_id,
                   context.get_param('page_token'))
    return _listing(provider, context, page)


@AbstractProvider.register_path('^' + PATH_CHANNEL + '/?$')
@AbstractProvider.register_path('^' + ROOT + '/channeltab/(?P<tab>[a-z0-9-]+)/?$')
def on_channel(provider, context, re_match):
    """A channel's videos, or one of its tabs (Home, Shorts, Live, Shows...)
    at /leanback/channeltab/<tab key>/. (Not channel/<tab>/: the engine
    reads the segment after 'channel' as a channel id.)"""
    channel_id = context.get_param(CHANNEL_ID)
    if not channel_id:
        return False, None
    page = _cached(context, PAGE_CACHE, innertube.channel_tab,
                   provider.get_client(context), channel_id,
                   re_match.groupdict().get('tab') or 'videos',
                   context.get_param('page_token'),
                   # order: the tab's sort chip (Latest, Popular...).
                   context.get_param('order'))
    if page:
        # Continuation pages don't repeat the channel name.
        name = (page.get('header_title') or page.get('title')
                or context.get_param('item_name'))
        for data in page.get('items') or ():
            if data['kind'] == 'video':
                data['channel'] = data.get('channel') or name
                data['channel_id'] = data.get('channel_id') or channel_id
    return _listing(provider, context, page,
                    category_label=context.get_param('item_name'))


@AbstractProvider.register_path('^' + PATH_PLAYLIST + '/?$')
def on_playlist(provider, context, re_match):
    playlist_id = context.get_param(PLAYLIST_ID)
    if not playlist_id:
        return False, None
    client = provider.get_client(context)
    page_token = context.get_param('page_token')
    account = _account(context, client)
    if account:
        # Signed in, private playlists (watch later, own lists) open too.
        page = _cached(context, MINE_CACHE, innertube.account_playlist,
                       client, account, playlist_id, page_token)
    else:
        page = _cached(context, PAGE_CACHE, innertube.playlist,
                       client, playlist_id, page_token)
    return _listing(provider, context, page)
