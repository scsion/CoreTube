# -*- coding: utf-8 -*-
"""
    Keyless listings straight from InnerTube, the private API YouTube's own
    web and TV apps use.

    The engine's listings go through the Data API v3, which needs a personal
    API key. InnerTube needs none: browse, search and next all answer
    anonymous requests. This module sends those requests through the engine's
    client (same headers, proxy and region settings as playback) and boils
    the renderer soup down to plain dicts that routes.py turns into items.

    Every page builder returns ``{'items': [...], 'next': token_or_None}``
    where each item is a dict with a 'kind' of video, channel or playlist.

    SPDX-License-Identifier: GPL-2.0-only
"""

import re
from urllib.parse import unquote
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta

try:
    from datetime import timezone
    UTC = timezone.utc
except ImportError:  # pragma: no cover - Python 2 Kodi builds
    UTC = None

# YouTube's topic destinations ("Explore"). They are ordinary channels whose
# home tab is a list of curated shelves, and unlike the personal home feed
# they are filled for anonymous visitors. The TV client returns them as
# uniform tile shelves.
DESTINATIONS = {
    'news': 'UCYfdidRxbB8Qhf0Nx7ioOYw',
    'sports': 'UCEgdi0XIXXZ-qJOFPf4JSKw',
    'gaming': 'UCOpNcN46UbXVtpKMrmU4Abg',
    'live': 'UC4R8DWoMoI7CAwX8_LjQHig',
    'learning': 'UCtFRv9O2AHqOZjjynzrv-xg',
}
# YouTube dropped its Trending page in 2025; the closest anonymous stand-in
# is the top shelves of the busiest destinations, interleaved.
TRENDING_SOURCES = ('news', 'sports', 'gaming', 'learning')
TRENDING_SHELVES = 2

# Channel tab params (protobuf, from the web app) for the Videos tab.
CHANNEL_VIDEOS_PARAMS = 'EgZ2aWRlb3PyBgQKAjoA'
# Channel tabs CoreTube doesn't show (community posts suit a phone).
SKIPPED_TABS = frozenset(('posts', 'community'))
# Known tab params, for when the channel header can't be read.
CHANNEL_TABS = {
    'videos': CHANNEL_VIDEOS_PARAMS,
    'live': 'EgdzdHJlYW1z8gYECgJ6AA==',
    'playlists': 'EglwbGF5bGlzdHPyBgoKCEIGCgIQaCIA',
}

# How many recently watched videos seed the keyless "Recommended" row.
RECOMMEND_SEEDS = 6

# Signed-in lists. A TV subscriptions page holds only a dozen videos, so a
# listing page joins a few; the library playlist grid is read whole.
HOME_PAGES = 3
SUBSCRIPTION_PAGES = 3
# History pages hold 15 videos each.
HISTORY_PAGES = 2
LIBRARY_PAGES = 10
# Every account has these two, owned by the account's own channel.
ACCOUNT_LISTS = frozenset(('LL', 'WL'))

_VIEWS_RE = re.compile(r'\b(?:views?|watching)\b', re.IGNORECASE)
_DURATION_RE = re.compile(r'^(?:(\d+):)?(\d{1,2}):(\d{2})$')
_AGO_RE = re.compile(
    r'(\d+)\s*(seconds?|secs?|minutes?|mins?|hours?|hrs?|days?|weeks?|wks?'
    r'|months?|mo|years?|yrs?|s|m|h|d|w|y)\b',
    re.IGNORECASE,
)
_AGO_SECONDS = (
    ('mo', 30 * 86400),
    ('s', 1),
    ('mi', 60),
    ('m', 60),
    ('h', 3600),
    ('d', 86400),
    ('w', 7 * 86400),
    ('y', 365 * 86400),
)

# Renderers that are never what we want and are expensive to walk.
_SKIP_KEYS = frozenset((
    'reelShelfRenderer', 'shortsLockupViewModel', 'reelItemRenderer',
    'menu', 'menuRenderer', 'onLongPressCommand', 'trackingParams',
    'horizontalCardListRenderer', 'searchPyvRenderer', 'adSlotRenderer',
    'promotedSparklesWebRenderer', 'frameworkUpdates',
))


# -- small helpers --------------------------------------------------------

def text(node):
    """Flatten any of InnerTube's text shapes to a plain string."""
    if not node:
        return ''
    if isinstance(node, str):
        return node
    if isinstance(node, dict):
        if 'simpleText' in node:
            return node['simpleText']
        if 'runs' in node:
            return ''.join(run.get('text', '') for run in node['runs'])
        if 'content' in node:
            return node['content']
    return ''


def dig(node, *path):
    for key in path:
        try:
            node = node[key]
        except (KeyError, IndexError, TypeError):
            return None
    return node


def find_first(node, key, predicate=None):
    """Depth-first search for the first value stored under ``key``."""
    stack = [node]
    while stack:
        current = stack.pop()
        if isinstance(current, dict):
            if key in current:
                value = current[key]
                if predicate is None or predicate(value):
                    return value
            stack.extend(reversed(list(current.values())))
        elif isinstance(current, list):
            stack.extend(reversed(current))
    return None


def _is_channel_id(value):
    return isinstance(value, str) and value.startswith('UC')


def channel_id_in(node):
    return find_first(node, 'browseId', _is_channel_id)


def parse_duration(value):
    match = _DURATION_RE.match((value or '').strip())
    if not match:
        return 0
    hours, minutes, seconds = match.groups()
    return int(hours or 0) * 3600 + int(minutes) * 60 + int(seconds)


def parse_ago(value):
    """'7 hours ago', '1mo ago', 'Streamed 2 days ago' -> UTC datetime."""
    if not value or 'ago' not in value.lower():
        return None
    match = _AGO_RE.search(value)
    if not match:
        return None
    amount = int(match.group(1))
    unit = match.group(2).lower()
    for prefix, seconds in _AGO_SECONDS:
        if unit.startswith(prefix):
            break
    else:
        return None
    now = datetime.now(UTC) if UTC else datetime.utcnow()
    return now - timedelta(seconds=amount * seconds)


def best_thumbnail(thumbnails, min_width=0):
    if not thumbnails:
        return ''
    best = max(thumbnails, key=lambda thumb: thumb.get('width') or 0)
    if (best.get('width') or 0) < min_width:
        return ''
    url = best.get('url') or ''
    if url.startswith('//'):
        url = 'https:' + url
    return url


def video_thumbnail(video_id, thumbnails=None, live=False):
    # Small renderer thumbnails look blurry on a TV; the standard 480px
    # image always exists.
    return best_thumbnail(thumbnails, min_width=320) or (
        'https://i.ytimg.com/vi/{}/{}.jpg'.format(
            video_id, 'hqdefault_live' if live else 'hqdefault'))


def _classify(parts, item):
    """Sort loose metadata strings into views / published / other."""
    for part in parts:
        lower = part.lower()
        if not part or part in ('•', '\xb7'):
            continue
        if _VIEWS_RE.search(part):
            item.setdefault('views', part)
        elif 'ago' in lower or lower.startswith(('streamed', 'premiere',
                                                 'scheduled')):
            item.setdefault('published', part)


def watched_percent(node):
    """How much of a video the signed-in account has watched, from the
    red bar YouTube draws on its thumbnail (any device). 0 if none."""
    value = (find_first(node, 'percentDurationWatched')
             or find_first(node, 'startPercent'))
    try:
        return max(0, min(100, int(value or 0)))
    except (TypeError, ValueError):
        return 0


def _finish_video(item, overlay_text='', overlay_style=''):
    style = (overlay_style or '').upper()
    if 'LIVE' in style or overlay_text.upper() == 'LIVE':
        item['live'] = True
    elif 'UPCOMING' in style:
        item['upcoming'] = True
    elif 'SHORTS' in style:
        return None
    elif overlay_text:
        item['duration'] = parse_duration(overlay_text)
    if item.get('views', '').lower().endswith('watching'):
        item['live'] = True
    item['thumb'] = video_thumbnail(item['id'], item.pop('_thumbs', None),
                                    item.get('live'))
    return item


# -- renderer parsers -----------------------------------------------------

def _parse_video_renderer(renderer):
    video_id = renderer.get('videoId')
    if not video_id:
        return None
    owner = (renderer.get('ownerText') or renderer.get('longBylineText')
             or renderer.get('shortBylineText'))
    item = {
        'kind': 'video',
        'id': video_id,
        'title': text(renderer.get('title')) or text(renderer.get('headline')),
        'channel': text(owner),
        'channel_id': channel_id_in(owner),
        '_thumbs': dig(renderer, 'thumbnail', 'thumbnails'),
        'description': (
            text(renderer.get('descriptionSnippet'))
            or text(dig(renderer, 'detailedMetadataSnippets', 0, 'snippetText'))
        ),
    }
    _classify((text(renderer.get('viewCountText')),
               text(renderer.get('publishedTimeText'))), item)
    if 'upcomingEventData' in renderer:
        item['upcoming'] = True
    overlay = find_first(renderer.get('thumbnailOverlays'),
                         'thumbnailOverlayTimeStatusRenderer') or {}
    length = text(renderer.get('lengthText')) or text(overlay.get('text'))
    style = overlay.get('style', '')
    for badge in renderer.get('badges') or ():
        if 'LIVE' in (dig(badge, 'metadataBadgeRenderer', 'style') or ''):
            style = 'LIVE'
    if renderer.get('lengthSeconds') and not length:
        item['duration'] = int(renderer['lengthSeconds'])
    _classify([text(run) for run in
               dig(renderer, 'videoInfo', 'runs') or ()], item)
    item['watched'] = watched_percent(renderer.get('thumbnailOverlays'))
    return _finish_video(item, length, style)


def _parse_tile(tile):
    content_type = tile.get('contentType', '')
    metadata = dig(tile, 'metadata', 'tileMetadataRenderer') or {}
    lines = metadata.get('lines')
    if not metadata.get('title'):
        # Carousel tiles keep their text in the focus command instead.
        spotlight = find_first(tile.get('onFocusCommand'),
                               'entityMetadataRenderer') or {}
        metadata = {'title': spotlight.get('title')}
        lines = spotlight.get('bylines')
    lines = [
        [line_text for line_text in (
            text(dig(entry, 'lineItemRenderer', 'text'))
            for entry in dig(line, 'lineRenderer', 'items') or ()
        ) if line_text]
        for line in lines or ()
    ]
    thumbs = dig(tile, 'header', 'tileHeaderRenderer', 'thumbnail',
                 'thumbnails')
    title = text(metadata.get('title'))
    if content_type == 'TILE_CONTENT_TYPE_VIDEO':
        video_id = (dig(tile, 'onSelectCommand', 'watchEndpoint', 'videoId')
                    or tile.get('contentId'))
        if not video_id:
            return None
        item = {
            'kind': 'video',
            'id': video_id,
            'title': title,
            'channel': ' '.join(lines[0]) if lines else '',
            'channel_id': channel_id_in(tile.get('onLongPressCommand')),
            '_thumbs': thumbs,
        }
        for line in lines[1:]:
            _classify(line, item)
        overlays = dig(tile, 'header', 'tileHeaderRenderer',
                       'thumbnailOverlays')
        overlay = find_first(overlays,
                             'thumbnailOverlayTimeStatusRenderer') or {}
        item['watched'] = watched_percent(overlays)
        return _finish_video(item, text(overlay.get('text')),
                             overlay.get('style', ''))
    if content_type == 'TILE_CONTENT_TYPE_CHANNEL':
        channel_id = (dig(tile, 'onSelectCommand', 'browseEndpoint',
                          'browseId') or tile.get('contentId'))
        if not _is_channel_id(channel_id):
            return None
        return {'kind': 'channel', 'id': channel_id, 'title': title,
                'thumb': best_thumbnail(thumbs),
                'description': ' • '.join(' '.join(l) for l in lines)}
    if content_type == 'TILE_CONTENT_TYPE_PLAYLIST':
        playlist_id = (dig(tile, 'onSelectCommand', 'watchPlaylistEndpoint',
                           'playlistId')
                       or dig(tile, 'onSelectCommand', 'watchEndpoint',
                              'playlistId')
                       or tile.get('contentId'))
        if not playlist_id:
            return None
        return {'kind': 'playlist', 'id': playlist_id, 'title': title,
                'channel': ' '.join(lines[0]) if lines else '',
                'channel_id': channel_id_in(tile.get('onLongPressCommand')),
                'thumb': best_thumbnail(thumbs)}
    return None


def _lockup_part(part):
    part_text = text(part.get('text'))
    # View counts can be a bare "246K" next to a play icon.
    label = part.get('accessibilityLabel') or ''
    if (part_text and not _VIEWS_RE.search(part_text)
            and _VIEWS_RE.search(label)):
        part_text = ' '.join((part_text, _VIEWS_RE.search(label).group(0)))
    return part_text


def _parse_lockup(lockup):
    content_type = lockup.get('contentType', '')
    content_id = lockup.get('contentId')
    if not content_id:
        return None
    metadata = dig(lockup, 'metadata', 'lockupMetadataViewModel') or {}
    rows = [
        [_lockup_part(part) for part in row.get('metadataParts') or ()]
        for row in dig(metadata, 'metadata', 'contentMetadataViewModel',
                       'metadataRows') or ()
    ]
    image = lockup.get('contentImage') or {}
    thumbs = (dig(image, 'thumbnailViewModel', 'image', 'sources')
              or dig(image, 'collectionThumbnailViewModel', 'primaryThumbnail',
                     'thumbnailViewModel', 'image', 'sources'))
    title = text(metadata.get('title'))
    channel_id = channel_id_in(metadata)
    if content_type == 'LOCKUP_CONTENT_TYPE_VIDEO':
        item = {
            'kind': 'video',
            'id': content_id,
            'title': title,
            'channel': '',
            'channel_id': channel_id,
            '_thumbs': thumbs,
        }
        for index, row in enumerate(rows):
            _classify(row, item)
            # The first row is the channel unless it is already the stats.
            if index == 0 and not ('views' in item or 'published' in item):
                item['channel'] = ' '.join(row)
        badge = find_first(image, 'thumbnailBadgeViewModel') or {}
        item['watched'] = watched_percent(image)
        return _finish_video(item, badge.get('text', ''),
                             badge.get('badgeStyle', ''))
    if content_type in ('LOCKUP_CONTENT_TYPE_PLAYLIST',
                        'LOCKUP_CONTENT_TYPE_PODCAST'):
        badge = find_first(image, 'thumbnailBadgeViewModel') or {}
        return {'kind': 'playlist', 'id': content_id, 'title': title,
                'channel': ' '.join(rows[0]) if rows else '',
                'channel_id': channel_id,
                'description': badge.get('text', ''),
                'thumb': best_thumbnail(thumbs)}
    return None


def _parse_channel_renderer(renderer):
    channel_id = renderer.get('channelId')
    if not channel_id:
        return None
    stats = [text(renderer.get('subscriberCountText')),
             text(renderer.get('videoCountText'))]
    return {
        'kind': 'channel',
        'id': channel_id,
        'title': text(renderer.get('title')),
        'thumb': best_thumbnail(dig(renderer, 'thumbnail', 'thumbnails')),
        'description': '\n'.join(filter(None, (
            ' • '.join(filter(None, stats)),
            text(renderer.get('descriptionSnippet')),
        ))),
    }


def _parse_playlist_renderer(renderer):
    playlist_id = renderer.get('playlistId')
    if not playlist_id:
        return None
    thumbs = (dig(renderer, 'thumbnails', 0, 'thumbnails')
              or dig(renderer, 'thumbnail', 'thumbnails'))
    return {
        'kind': 'playlist',
        'id': playlist_id,
        'title': text(renderer.get('title')),
        'channel': text(renderer.get('shortBylineText')
                        or renderer.get('longBylineText')),
        'description': text(renderer.get('videoCountText')),
        'thumb': best_thumbnail(thumbs),
    }


def _parse_short(lockup):
    """A Short in a channel's Shorts tab (or Home)."""
    video_id = dig(lockup, 'onTap', 'innertubeCommand', 'reelWatchEndpoint',
                   'videoId')
    if not video_id:
        return None
    meta = lockup.get('overlayMetadata') or {}
    item = {
        'kind': 'video',
        'id': video_id,
        'title': text(meta.get('primaryText')),
        'channel': '',
        'channel_id': None,
        'short': True,
        '_thumbs': dig(lockup, 'thumbnail', 'sources'),
    }
    _classify((text(meta.get('secondaryText')),), item)
    return _finish_video(item)


def _parse_show(show):
    """A channel 'Shows' card: opens like a playlist."""
    browse_id = dig(show, 'navigationEndpoint', 'browseEndpoint', 'browseId')
    if not browse_id:
        return None
    return {
        'kind': 'playlist',
        'id': browse_id[2:] if browse_id.startswith('VL') else browse_id,
        'title': text(show.get('title')),
        'thumb': best_thumbnail(dig(show, 'thumbnailRenderer',
                                    'showCustomThumbnailRenderer',
                                    'thumbnail', 'thumbnails')),
    }


PARSERS = {
    'videoRenderer': _parse_video_renderer,
    'compactVideoRenderer': _parse_video_renderer,
    'gridVideoRenderer': _parse_video_renderer,
    'playlistVideoRenderer': _parse_video_renderer,
    'tileRenderer': _parse_tile,
    'lockupViewModel': _parse_lockup,
    'channelRenderer': _parse_channel_renderer,
    'playlistRenderer': _parse_playlist_renderer,
    'gridShowRenderer': _parse_show,
}
# Only on channel pages: elsewhere Shorts stay out of the 16:9 shelves.
SHORTS_PARSERS = dict(PARSERS, shortsLockupViewModel=_parse_short)


def collect(*roots, **options):
    """Pull every known item and the first continuation token out of the
    given response subtrees, in document order. shorts=True also takes
    Shorts, which are skipped by default."""
    shorts = options.get('shorts', False)
    parsers = SHORTS_PARSERS if shorts else PARSERS
    skip = _SKIP_KEYS - {'shortsLockupViewModel', 'reelShelfRenderer'} \
        if shorts else _SKIP_KEYS
    items = []
    seen = set()
    state = {'next': None}

    def walk(node):
        if isinstance(node, list):
            for child in node:
                walk(child)
            return
        if not isinstance(node, dict):
            return
        for key, value in node.items():
            if key in skip:
                continue
            parser = parsers.get(key)
            if parser:
                try:
                    item = parser(value)
                except (KeyError, IndexError, TypeError, ValueError):
                    item = None
                if item and (item['kind'], item['id']) not in seen:
                    seen.add((item['kind'], item['id']))
                    items.append(item)
                continue
            if key == 'continuationItemRenderer':
                state['next'] = state['next'] or find_first(
                    value, 'token', lambda token: isinstance(token, str))
                continue
            if key == 'nextContinuationData':
                state['next'] = state['next'] or value.get('continuation')
                continue
            walk(value)

    for root in roots:
        walk(root)
    return {'items': items, 'next': state['next']}


def interleave(*lists):
    """Round-robin merge without duplicates."""
    merged = []
    seen = set()
    for index in range(max((len(entries) for entries in lists), default=0)):
        for entries in lists:
            if index < len(entries):
                item = entries[index]
                key = (item['kind'], item['id'])
                if key not in seen:
                    seen.add(key)
                    merged.append(item)
    return merged


# -- requests ---------------------------------------------------------------

def request(client, endpoint, client_name='web', do_auth=False, **post_data):
    """POST to /youtubei/v1/<endpoint> without an API key."""
    result = client.api_request(client_name, 'POST',
                                path=endpoint,
                                url=client.V1_API_URL,
                                post_data=post_data,
                                do_auth=do_auth,
                                cache=False,
                                notify=False)
    if not isinstance(result, dict) or 'error' in result:
        return {}
    return result


def search(client, query, page_token=None):
    if page_token:
        result = request(client, 'search', continuation=page_token)
        return collect(result.get('onResponseReceivedCommands'))
    result = request(client, 'search', query=query)
    return collect(result.get('contents'))


def related(client, video_id, page_token=None):
    if page_token:
        result = request(client, 'next', continuation=page_token)
        return collect(result.get('onResponseReceivedEndpoints'))
    result = request(client, 'next', videoId=video_id)
    return collect(dig(result, 'contents', 'twoColumnWatchNextResults',
                       'secondaryResults'))


def channel_header(client, channel_id):
    """Name, handle, counts, avatar and banner for a channel page header,
    and which of CHANNEL_TABS the channel has."""
    result = request(client, 'browse', browseId=channel_id,
                     params=CHANNEL_VIDEOS_PARAMS)
    if not result:
        return None
    header = dig(result, 'header', 'pageHeaderRenderer', 'content',
                 'pageHeaderViewModel') or {}
    meta = dig(result, 'metadata', 'channelMetadataRenderer') or {}
    rows = [[text(part.get('text')) for part in row.get('metadataParts') or ()]
            for row in dig(header, 'metadata', 'contentMetadataViewModel',
                           'metadataRows') or ()]
    parts = [part for row in rows for part in row if part]
    tabs = []
    for tab in dig(result, 'contents', 'twoColumnBrowseResultsRenderer',
                   'tabs') or ():
        # The Search tab is an expandableTabRenderer without params.
        renderer = tab.get('tabRenderer') or {}
        params = dig(renderer, 'endpoint', 'browseEndpoint', 'params')
        title = renderer.get('title')
        # Posts are left out: they suit a phone better than a TV.
        if params and title and tab_key(title) not in SKIPPED_TABS:
            tabs.append({'key': tab_key(title), 'title': title,
                         'params': unquote(params)})
    avatar = (dig(meta, 'avatar', 'thumbnails')
              or dig(header, 'image', 'decoratedAvatarViewModel', 'avatar',
                     'avatarViewModel', 'image', 'sources'))
    return {
        'title': meta.get('title') or text(dig(header, 'title',
                                               'dynamicTextViewModel',
                                               'text')),
        'handle': next((part for part in parts if part.startswith('@')), ''),
        'stats': ' \u2022 '.join(part for part in parts
                                 if not part.startswith('@')),
        'description': meta.get('description', ''),
        'avatar': best_thumbnail(avatar),
        'banner': best_thumbnail(dig(header, 'banner', 'imageBannerViewModel',
                                     'image', 'sources')),
        'tabs': tabs or [{'key': 'videos', 'title': 'Videos',
                          'params': CHANNEL_VIDEOS_PARAMS}],
    }


def tab_key(title):
    """URL-safe key for a channel tab title: 'Home', 'Videos'..."""
    return re.sub(r'[^a-z0-9]+', '-', title.lower()).strip('-') or 'tab'


def _tab_params(client, channel_id, key):
    header = channel_header(client, channel_id) or {}
    params = next((tab['params'] for tab in header.get('tabs') or ()
                   if tab['key'] == key), CHANNEL_TABS.get(key))
    return params, header


def channel_sorts(client, channel_id, key):
    """The chips YouTube offers above a channel tab: sort orders such as
    Latest / Popular / Oldest, or filters such as Members only. Each opens
    a re-sorted listing through its continuation token."""
    params, _ = _tab_params(client, channel_id, key)
    result = request(client, 'browse', browseId=channel_id, params=params)
    chips = []
    for bar in _find_all(result.get('contents'), 'chipBarViewModel'):
        for chip in bar.get('chips') or ():
            model = chip.get('chipViewModel') or {}
            title = model.get('text')
            token = find_first(model.get('tapCommand'), 'token',
                               lambda value: isinstance(value, str))
            if title and token:
                chips.append({'key': tab_key(title), 'title': title,
                              'token': token,
                              'selected': model.get('selected') is not False})
        break
    # Whichever YouTube marks selected is the tab's own listing.
    if chips and not any(chip['selected'] for chip in chips):
        chips[0]['selected'] = True
    elif chips:
        first = next(chip for chip in chips if chip['selected'])
        for chip in chips:
            chip['selected'] = chip is first
    return chips


def _find_all(node, key):
    found = []
    stack = [node]
    while stack:
        current = stack.pop()
        if isinstance(current, dict):
            if key in current:
                found.append(current[key])
            stack.extend(reversed(list(current.values())))
        elif isinstance(current, list):
            stack.extend(reversed(current))
    return found


def channel_tab(client, channel_id, key, page_token=None, sort=None):
    """One tab of a channel page, found by its key in the channel header
    (YouTube names and orders the tabs per channel), optionally in the
    order of one of its sort chips."""
    if page_token:
        # A continuation carries the tab (and its order) with it.
        return channel_videos(client, channel_id, page_token)
    if sort:
        chip = next((chip for chip in channel_sorts(client, channel_id, key)
                     if chip['key'] == sort), None)
        if chip and not chip['selected']:
            result = request(client, 'browse', continuation=chip['token'])
            page = collect(result.get('onResponseReceivedActions'),
                           shorts=True)
            for item in page['items']:
                if item['kind'] == 'video':
                    item['channel_id'] = item.get('channel_id') or channel_id
            return page
    params, header = _tab_params(client, channel_id, key)
    page = channel_videos(client, channel_id, params=params)
    page['header_title'] = header.get('title')
    return page


def channel_videos(client, channel_id, page_token=None, tab='videos',
                   params=None):
    if page_token:
        result = request(client, 'browse', continuation=page_token)
        page = collect(result.get('onResponseReceivedActions'), shorts=True)
    else:
        result = request(client, 'browse', browseId=channel_id,
                         params=params or CHANNEL_TABS.get(
                             tab, CHANNEL_VIDEOS_PARAMS))
        page = collect(result.get('contents'), shorts=True)
        page['title'] = (dig(result, 'metadata', 'channelMetadataRenderer',
                             'title')
                         or text(dig(result, 'header', 'pageHeaderRenderer',
                                     'pageTitle')))
    for item in page['items']:
        if item['kind'] == 'video':
            item['channel_id'] = item.get('channel_id') or channel_id
            item['channel'] = item.get('channel') or page.get('title', '')
    return page


def playlist(client, playlist_id, page_token=None):
    if page_token:
        result = request(client, 'browse', continuation=page_token)
        return collect(result.get('onResponseReceivedActions'))
    result = request(client, 'browse', browseId='VL' + playlist_id)
    return collect(result.get('contents'))


def shelves(client, browse_id, client_name='tv', do_auth=False):
    """The item lists of every shelf on a browse page, in page order."""
    result = request(client, 'browse', client_name=client_name,
                     do_auth=do_auth, browseId=browse_id)
    found = []
    stack = [result.get('contents')]
    while stack:
        node = stack.pop()
        if isinstance(node, dict):
            for key in ('shelfRenderer', 'richShelfRenderer'):
                if key in node:
                    found.append(collect(node[key])['items'])
                    break
            else:
                stack.extend(reversed(list(node.values())))
        elif isinstance(node, list):
            stack.extend(reversed(node))
    return [entries for entries in found if entries]


def videos_only(entries):
    """Playable videos; upcoming premieres can't be played yet."""
    return [item for item in entries
            if item['kind'] == 'video' and not item.get('upcoming')]


def destination(client, name):
    page = shelves(client, DESTINATIONS[name])
    return {'items': interleave(*[videos_only(e) for e in page])
            if name == 'live' else
            [item for entries in page for item in videos_only(entries)],
            'next': None}


def trending(client):
    with ThreadPoolExecutor(max_workers=len(TRENDING_SOURCES)) as pool:
        pages = list(pool.map(
            lambda name: shelves(client, DESTINATIONS[name]),
            TRENDING_SOURCES))
    top = []
    for page in pages:
        page = [videos_only(entries) for entries in page]
        top.extend(entries for entries in page[:TRENDING_SHELVES] if entries)
    return {'items': interleave(*top), 'next': None}


# -- the signed-in account ---------------------------------------------------
#
# These read the account's own lists with the engine's TV sign-in (the TV
# client accepts that token; the web client does not). Callers must check
# client.logged_in first: without a token the engine skips the request.
# The ``_account`` argument only keys the result cache per account.

def _tv_browse(client, **post_data):
    return request(client, 'browse', client_name='tv', do_auth=True,
                   **post_data)


def _next_token(renderer):
    return dig(renderer, 'continuations', 0, 'nextContinuationData',
               'continuation')


def _unique(entries):
    seen = set()
    unique = []
    for item in entries:
        key = (item['kind'], item['id'])
        if key not in seen:
            seen.add(key)
            unique.append(item)
    return unique


def _sections(client, browse_id, page_token, pages):
    """The shelves of up to ``pages`` pages of a TV section list, and the
    token of the page after them."""
    found = []
    for _ in range(pages):
        if page_token:
            result = _tv_browse(client, continuation=page_token)
            section = dig(result, 'continuationContents',
                          'sectionListContinuation')
        else:
            result = _tv_browse(client, browseId=browse_id)
            contents = result.get('contents')
            # Subscriptions keep the feed in the selected tab of a nav whose
            # other tabs are the single channels, still unloaded.
            tabs = find_first(contents, 'tabs')
            if tabs:
                contents = next((tab for tab in tabs
                                 if dig(tab, 'tabRenderer', 'selected')),
                                tabs[0])
            section = find_first(contents, 'sectionListRenderer')
        if not section:
            return found, None
        found.extend(content['shelfRenderer']
                     for content in section.get('contents') or ()
                     if 'shelfRenderer' in content)
        page_token = _next_token(section)
        if not page_token:
            break
    return found, page_token


def _shelf_videos(found):
    return _unique(videos_only(
        [item for shelf in found for item in collect(shelf)['items']]))


def home_feed(client, _account=None):
    """The account's own TV home feed, shelf after shelf."""
    found, _ = _sections(client, 'FEwhat_to_watch', None, HOME_PAGES)
    return {'items': _shelf_videos(found), 'next': None}


def subscriptions(client, _account, page_token=None):
    """Newest uploads of the subscribed channels, newest first.

    The TV feed opens with labelled picks ("Most relevant", Shorts); the
    unlabelled shelves after them are the plain upload feed, three videos
    each, so a listing page joins a few feed pages."""
    found, page_token = _sections(client, 'FEsubscriptions', page_token,
                                  SUBSCRIPTION_PAGES)
    feed = [shelf for shelf in found
            if not text(find_first(shelf.get('headerRenderer'), 'title'))]
    return {'items': _shelf_videos(feed or found), 'next': page_token}


def history(client, _account, page_token=None):
    """The account's YouTube watch history, newest first: what was watched
    on any device (phone, browser, TV), with how far each video got."""
    # A grid of tiles (15 a page) rather than shelves; each tile carries
    # the watched percentage.
    items = []
    for _ in range(HISTORY_PAGES):
        if page_token:
            result = _tv_browse(client, continuation=page_token)
            grid = dig(result, 'continuationContents', 'gridContinuation')
        else:
            result = _tv_browse(client, browseId='FEhistory')
            grid = find_first(result.get('contents'), 'gridRenderer')
        if not grid:
            break
        items.extend(collect(grid)['items'])
        page_token = _next_token(grid)
        if not page_token:
            break
    return {'items': _unique(videos_only(items)), 'next': page_token}


def account_playlist(client, _account, playlist_id, page_token=None):
    """A playlist read as the account, so private ones (liked videos,
    watch later, the account's own private lists) open as well."""
    if page_token:
        result = _tv_browse(client, continuation=page_token)
        return collect(result.get('continuationContents'))
    result = _tv_browse(client, browseId='VL' + playlist_id)
    return collect(result.get('contents'))


def liked(client, account, page_token=None):
    return account_playlist(client, account, 'LL', page_token)


def _library_playlists(client):
    """Every playlist in the account's library, and the account's own
    channel ID (the owner of its liked videos and watch later lists)."""
    entries = []
    seen = set()
    page_token = None
    for _ in range(LIBRARY_PAGES):
        if page_token:
            result = _tv_browse(client, continuation=page_token)
            root = result.get('continuationContents')
        else:
            result = _tv_browse(client, browseId='FEplaylist_aggregation')
            root = result.get('contents')
        grid = find_first(root, 'gridRenderer')
        if not grid:
            break
        new = [item for item in collect(grid.get('items'))['items']
               if item['kind'] == 'playlist' and item['id'] not in seen]
        if not new:
            # The grid's "show more" pages repeat what it already holds.
            break
        seen.update(item['id'] for item in new)
        entries.extend(new)
        page_token = _next_token(grid)
        if not page_token:
            break
    own_id = next((item['channel_id'] for item in entries
                   if item['id'] in ACCOUNT_LISTS and item.get('channel_id')),
                  None)
    return entries, own_id


def my_playlists(client, _account, _page_token=None):
    """Playlists the account owns. Liked videos has a row of its own."""
    entries, own_id = _library_playlists(client)
    return {'items': [item for item in entries
                      if own_id and item.get('channel_id') == own_id
                      and item['id'] != 'LL'],
            'next': None}


def saved_playlists(client, _account, _page_token=None):
    """Other channels' playlists the account saved to its library."""
    entries, own_id = _library_playlists(client)
    return {'items': [item for item in entries
                      if item['id'] not in ACCOUNT_LISTS
                      and not (own_id and item.get('channel_id') == own_id)],
            'next': None}


def recommended(client, seed_ids):
    """Related videos of recently watched ones, the way the engine builds
    its own recommendations, but without the v3 detail lookups."""
    seed_ids = list(seed_ids)[:RECOMMEND_SEEDS]
    if not seed_ids:
        return {'items': [], 'next': None}
    with ThreadPoolExecutor(max_workers=len(seed_ids)) as pool:
        pages = list(pool.map(lambda video_id: related(client, video_id),
                              seed_ids))
    watched = set(seed_ids)
    merged = interleave(*[videos_only(page['items']) for page in pages])
    return {'items': [item for item in merged if item['id'] not in watched],
            'next': None}
