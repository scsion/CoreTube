# -*- coding: utf-8 -*-
"""
    SponsorBlock segment skipping for videos played through this add-on.

    Uses the public SponsorBlock API (https://sponsor.ajay.app) with the
    k-anonymity endpoint: only the first 4 hex chars of the video id's SHA-256
    are sent, and the matching video is picked out locally.

    SPDX-License-Identifier: GPL-2.0-only
"""

import hashlib
import json
import re
import threading
from urllib.error import URLError
from urllib.parse import quote
from urllib.request import Request, urlopen

import xbmc
import xbmcgui

from . import HINT_PROPERTY, localize, setting_bool

API_URL = 'https://sponsor.ajay.app/api/skipSegments/{prefix}?categories={categories}'
CATEGORIES = (
    'sponsor',
    'selfpromo',
    'interaction',
    'intro',
    'outro',
    'preview',
    'music_offtopic',
    'filler',
)
CATEGORY_LABELS = {
    'sponsor': 39031,
    'selfpromo': 39032,
    'interaction': 39033,
    'intro': 39034,
    'outro': 39035,
    'preview': 39036,
    'music_offtopic': 39037,
    'filler': 39038,
}
VIDEO_ID_RE = re.compile(r'(?:video_id=|/vi/|v=)([A-Za-z0-9_-]{11})')
POLL_SECONDS = 0.25
# Don't seek for a segment we are already within this distance of the end of.
END_TOLERANCE = 0.75


def log(msg, level=xbmc.LOGINFO):
    xbmc.log('[script.youtube.leanback] SponsorBlock: ' + msg, level)


def enabled_categories():
    return [cat for cat in CATEGORIES
            if setting_bool('leanback.sb.' + cat)]


def fetch_segments(video_id, categories):
    """Return [(start, end, category), ...] sorted by start time."""
    prefix = hashlib.sha256(video_id.encode('utf-8')).hexdigest()[:4]
    url = API_URL.format(prefix=prefix,
                         categories=quote(json.dumps(categories)))
    request = Request(url, headers={'User-Agent': 'script.youtube.leanback'})
    try:
        with urlopen(request, timeout=10) as response:
            data = json.loads(response.read().decode('utf-8'))
    except URLError as exc:
        # 404 simply means no segments for any video with this prefix.
        if getattr(exc, 'code', None) != 404:
            log('lookup failed: {}'.format(exc), xbmc.LOGWARNING)
        return []
    except ValueError as exc:
        log('bad response: {}'.format(exc), xbmc.LOGWARNING)
        return []

    segments = []
    for video in data:
        if video.get('videoID') != video_id:
            continue
        for seg in video.get('segments', []):
            if seg.get('actionType', 'skip') != 'skip':
                continue
            start, end = seg['segment'][:2]
            if end > start:
                segments.append((float(start), float(end), seg['category']))
    segments.sort()
    return segments


class SponsorBlockPlayer(xbmc.Player):
    def __init__(self):
        super(SponsorBlockPlayer, self).__init__()
        self._monitor = xbmc.Monitor()
        self._session = 0
        self._lock = threading.Lock()

    def shutdown(self):
        self._new_session()

    def _new_session(self):
        with self._lock:
            self._session += 1
            return self._session

    def _is_current(self, session):
        return session == self._session and not self._monitor.abortRequested()

    def _current_video_id(self):
        """Work out the YouTube video id of what is playing, if any."""
        home = xbmcgui.Window(10000)
        hint = home.getProperty(HINT_PROPERTY)
        home.clearProperty(HINT_PROPERTY)
        try:
            item = self.getPlayingItem()
            video_id = item.getProperty('video_id')
            if video_id:
                return video_id
            path = item.getPath()
        except RuntimeError:
            path = ''
        try:
            path = path or self.getPlayingFile()
        except RuntimeError:
            pass
        match = VIDEO_ID_RE.search(path or '')
        if match:
            return match.group(1)
        return hint or None

    def onAVStarted(self):
        session = self._new_session()
        if not self.isPlayingVideo() or not setting_bool('leanback.sb.enabled'):
            return
        video_id = self._current_video_id()
        if not video_id:
            return
        thread = threading.Thread(target=self._run,
                                  args=(session, video_id),
                                  name='SponsorBlock')
        thread.daemon = True
        thread.start()

    def onPlayBackStopped(self):
        self._new_session()

    def onPlayBackEnded(self):
        self._new_session()

    def onPlayBackError(self):
        self._new_session()

    def _run(self, session, video_id):
        categories = enabled_categories()
        if not categories:
            return
        segments = fetch_segments(video_id, categories)
        if not segments or not self._is_current(session):
            return
        log('{}: {} segment(s)'.format(video_id, len(segments)))
        notify = setting_bool('leanback.sb.notify')
        skipped = set()

        while self._is_current(session):
            try:
                if not self.isPlaying():
                    break
                now = self.getTime()
            except RuntimeError:
                break
            for index, (start, end, category) in enumerate(segments):
                if index in skipped or not start <= now < end - END_TOLERANCE:
                    continue
                # Skip once only, so seeking back into a segment works.
                skipped.add(index)
                try:
                    self.seekTime(end)
                except RuntimeError:
                    break
                log('{}: skipped {} {:.1f}-{:.1f}'.format(
                    video_id, category, start, end))
                if notify:
                    xbmcgui.Dialog().notification(
                        'SponsorBlock',
                        localize(39112).format(
                            localize(CATEGORY_LABELS[category])),
                        xbmcgui.NOTIFICATION_INFO, 2000, False)
                break
            if self._monitor.waitForAbort(POLL_SECONDS):
                break
