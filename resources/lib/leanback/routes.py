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

    SPDX-License-Identifier: GPL-2.0-only
"""

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

FEEDS = frozenset(innertube.DESTINATIONS) | {'trending', 'recommended'}

# Shelf contents change through the day; paged lists are only ever re-read
# when someone pages back, so they can live a little longer.
FEED_CACHE = 30 * 60
PAGE_CACHE = 60 * 60

SEPARATOR = ' • '


# -- item conversion --------------------------------------------------------

def _plot(data):
    stats = SEPARATOR.join(filter(None, (
        data.get('channel'), data.get('views'), data.get('published'))))
    return '\n'.join(filter(None, (stats, data.get('description'))))


def _video_item(context, data, play_data):
    video_id = data['id']
    item = VideoItem(
        data.get('title') or video_id,
        context.create_uri((PATHS.PLAY,), {VIDEO_ID: video_id}),
        image=data.get('thumb'),
        plot=_plot(data),
        video_id=video_id,
        channel_id=data.get('channel_id'),
    )
    if data.get('channel'):
        item.add_artist(data['channel'])
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
    if client.logged_in:
        page = _cached(context, FEED_CACHE, innertube.home_feed, client)
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
def on_channel(provider, context, re_match):
    channel_id = context.get_param(CHANNEL_ID)
    if not channel_id:
        return False, None
    page = _cached(context, PAGE_CACHE, innertube.channel_videos,
                   provider.get_client(context), channel_id,
                   context.get_param('page_token'))
    if page:
        # Continuation pages don't repeat the channel name.
        name = page.get('title') or context.get_param('item_name')
        for data in page.get('items') or ():
            data['channel'] = data.get('channel') or name
    return _listing(provider, context, page,
                    category_label=context.get_param('item_name'))


@AbstractProvider.register_path('^' + PATH_PLAYLIST + '/?$')
def on_playlist(provider, context, re_match):
    playlist_id = context.get_param(PLAYLIST_ID)
    if not playlist_id:
        return False, None
    page = _cached(context, PAGE_CACHE, innertube.playlist,
                   provider.get_client(context), playlist_id,
                   context.get_param('page_token'))
    return _listing(provider, context, page)
