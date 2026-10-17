"""One-time settings changes for existing installs.

A changed <default> in settings.xml only reaches new installs: Kodi keeps
the stored value for everyone else. Each change here runs once per install
(recorded in a marker file), so a user who later sets it back keeps their
choice. Called by the service when Kodi starts.
"""

import os

import xbmc
import xbmcvfs

from . import ADDON_ID, addon

MARKER = 'special://profile/addon_data/{}/migrations.txt'.format(ADDON_ID)


def _log(msg):
    xbmc.log('[{}] Migration: {}'.format(ADDON_ID, msg), xbmc.LOGINFO)


def _remote_history(settings):
    """0.9.1: report playback to the account's YouTube history, so what's
    watched in CoreTube shows on the phone as well."""
    # setSetting rather than getSettings().setBool: only this one is saved
    # to disk straight away.
    if settings.getSetting('kodion.history.remote') != 'true':
        settings.setSetting('kodion.history.remote', 'true')
        _log('YouTube watch history sync enabled')


MIGRATIONS = (
    ('remote-history', _remote_history),
)


def run():
    path = xbmcvfs.translatePath(MARKER)
    try:
        with open(path, encoding='utf-8') as f:
            done = set(f.read().split())
    except OSError:
        done = set()
    pending = [(name, step) for name, step in MIGRATIONS if name not in done]
    if not pending:
        return
    settings = addon()
    for name, step in pending:
        try:
            step(settings)
        except Exception as exc:  # never keep the service from starting
            _log('{} failed: {}'.format(name, exc))
            continue
        done.add(name)
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, 'w', encoding='utf-8') as f:
            f.write('\n'.join(sorted(done)) + '\n')
    except OSError as exc:
        _log('could not record: {}'.format(exc))
