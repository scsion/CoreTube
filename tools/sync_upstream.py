#!/usr/bin/env python3
"""Vendor the plugin.video.youtube engine into this add-on.

The YouTube client, sign-in, stream extraction and playback all come from
anxdpanic/plugin.video.youtube (GPL-2.0-only). This script copies a checkout
of it into our tree and applies the small patches that turn it into a
standalone fork running under our own add-on id. Re-run it whenever upstream
fixes something YouTube broke:

    git clone --depth 1 https://github.com/anxdpanic/plugin.video.youtube.git /tmp/yt
    python tools/sync_upstream.py /tmp/yt
"""

import argparse
import re
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
UPSTREAM_ID = 'plugin.video.youtube'
ADDON_ID = 'script.youtube.leanback'
# Upstream's local MPD/proxy server port. Shifted so both add-ons can coexist.
WINDOW_XML = 'script-youtube-leanback-main.xml'
UPSTREAM_PORT = '50152'
ADDON_PORT = '50162'

# (relative path inside upstream checkout, relative path inside our tree)
COPIES = [
    ('resources/lib/youtube_plugin', 'resources/lib/youtube_plugin'),
    ('resources/lib/plugin.py', 'resources/lib/plugin.py'),
    ('resources/language', 'resources/language'),
    ('resources/media', 'resources/media'),
    ('resources/settings.xml', 'resources/settings.xml'),
    ('LICENSES', 'LICENSES'),
]

LEANBACK_STRINGS_START = '# --- leanback strings ---'
LEANBACK_SETTINGS_FILE = ROOT / 'resources' / 'leanback_settings.xml'
LEANBACK_STRINGS_FILE = ROOT / 'resources' / 'leanback_strings.po'


def copy(src, dst):
    if dst.is_dir():
        # Empty it rather than removing it: on Windows a directory that is
        # some process's cwd can't be deleted, but its contents can.
        for child in dst.iterdir():
            if child.is_dir():
                shutil.rmtree(child)
            else:
                child.unlink()
    elif dst.exists():
        dst.unlink()
    dst.parent.mkdir(parents=True, exist_ok=True)
    if src.is_dir():
        shutil.copytree(src, dst, dirs_exist_ok=True,
                        ignore=shutil.ignore_patterns('__pycache__', '*.pyc'))
    else:
        shutil.copy2(src, dst)


def patch(path, replacements):
    text = path.read_text(encoding='utf-8')
    for old, new, expected in replacements:
        count = text.count(old)
        if count != expected:
            sys.exit('patch failed: {!r} found {} times in {} (expected {})'
                     .format(old, count, path, expected))
        text = text.replace(old, new)
    path.write_text(text, encoding='utf-8', newline='\n')


def main():
    parser = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    parser.add_argument('upstream', type=Path,
                        help='path to a plugin.video.youtube checkout')
    args = parser.parse_args()

    upstream = args.upstream.resolve()
    upstream_xml = (upstream / 'addon.xml').read_text(encoding='utf-8')
    if 'id="{}"'.format(UPSTREAM_ID) not in upstream_xml:
        sys.exit('{} does not look like a {} checkout'.format(
            upstream, UPSTREAM_ID))
    version = re.search(r'<addon[^>]+version="([^"]+)"', upstream_xml).group(1)

    for src, dst in COPIES:
        copy(upstream / src, ROOT / dst)

    lib = ROOT / 'resources' / 'lib' / 'youtube_plugin'
    patch(lib / 'kodion' / 'constants' / '__init__.py', [
        ("ADDON_ID = '{}'".format(UPSTREAM_ID),
         "ADDON_ID = '{}'".format(ADDON_ID), 1),
    ])
    patch(lib / 'kodion' / 'network' / 'http_server.py', [
        ("server_version = '{}/1.0'".format(UPSTREAM_ID),
         "server_version = '{}/1.0'".format(ADDON_ID), 1),
    ])
    # Listings requested by the leanback window's containers have no plugin
    # folder: container info comes back as False rather than a path.
    patch(lib / 'kodion' / 'context' / 'xbmc' / 'xbmc_context.py', [
        ('            uri=XbmcContextUI.get_container_info(\n'
         '                FOLDER_URI,\n'
         '            ),\n',
         '            uri=XbmcContextUI.get_container_info(\n'
         '                FOLDER_URI,\n'
         "            ) or '',\n", 1),
    ])
    # A failed listing makes the engine send Action(Back); inside the
    # leanback window that would close pages or exit, so skip it there.
    patch(lib / 'kodion' / 'plugin' / 'xbmc' / 'xbmc_plugin.py', [
        ('                    else:\n'
         '                        _, _post_run_action = self.uri_action(\n'
         '                            context,\n'
         "                            'command://Action(Back)',\n",
         '                    elif not xbmc.getCondVisibility(\n'
         "                            'Window.IsActive({})'):\n"
         '                        _, _post_run_action = self.uri_action(\n'
         '                            context,\n'
         "                            'command://Action(Back)',\n"
         .format(WINDOW_XML), 1),
    ])

    settings = ROOT / 'resources' / 'settings.xml'
    leanback_settings = LEANBACK_SETTINGS_FILE.read_text(encoding='utf-8')
    patch(settings, [
        ('<default>{}</default>'.format(UPSTREAM_PORT),
         '<default>{}</default>'.format(ADDON_PORT), 1),
        # Our categories go first so they open by default in the settings.
        ('<section id="{}">'.format(UPSTREAM_ID),
         '<section id="{}">\n{}'.format(ADDON_ID, leanback_settings.rstrip()),
         1),
    ])

    strings = (ROOT / 'resources' / 'language' / 'resource.language.en_gb'
               / 'strings.po')
    with strings.open('a', encoding='utf-8', newline='\n') as f:
        f.write('\n{}\n\n'.format(LEANBACK_STRINGS_START))
        f.write(LEANBACK_STRINGS_FILE.read_text(encoding='utf-8'))

    (ROOT / 'UPSTREAM_VERSION').write_text(version + '\n', encoding='utf-8')
    print('Synced {} {} into {}'.format(UPSTREAM_ID, version, ROOT))


if __name__ == '__main__':
    main()
