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
ADDON_ID = 'script.coretube'
# Upstream's local MPD/proxy server port. Shifted so both add-ons can coexist.
WINDOW_XML = 'script-coretube-main.xml'
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


# The engine titles its dialogs (setup wizard, sign-in) with string #30003,
# its add-on name. Show ours there, in every language.
REBRAND = (
    ('#30003', 'CoreTube'),
    ('#30634', 'CoreTube API Configuration'),
    ('#30731', 'This needs your own YouTube Data API key (Settings > API).'
               '[CR][CR]Home rows, search and channels work without one.'),
)


def rebrand_strings():
    import re
    for po in (ROOT / 'resources' / 'language').glob('*/strings.po'):
        text = po.read_text(encoding='utf-8')
        for ctxt, name in REBRAND:
            english = po.parent.name == 'resource.language.en_gb'
            text, n = re.subn(
                r'(msgctxt "{}"\nmsgid ")[^"\n]*("\nmsgstr ")[^"\n]*(")'
                .format(ctxt),
                (r'\g<1>{0}\g<2>\g<3>' if english else r'\g<1>{0}\g<2>{0}\g<3>')
                .format(name), text)
            if english and n != 1:
                sys.exit('rebrand failed: {} found {} times'.format(ctxt, n))
        po.write_text(text, encoding='utf-8', newline='\n')


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

    # CoreTube works without a Data API key: callers of a skipped v3
    # request fall back (built-in language list, the /leanback/ InnerTube
    # routes), so don't stop the user with a key prompt. Upstream also
    # passes the prompt unlocalized, which shows the bare string id.
    patch(lib / 'youtube' / 'client' / 'data_client.py', [
        ("            if abort_prompt and kwargs.get('notify', True):\n"
         '                context.get_ui().on_ok(context.get_name(), abort_prompt)\n',
         "            if (abort_prompt and abort_prompt != 'key.requirement'\n"
         "                    and kwargs.get('notify', True)):\n"
         '                context.get_ui().on_ok(context.get_name(),\n'
         '                                       context.localize(abort_prompt))\n',
         1),
    ])

    # The stream proxy's server_close() never closes the listening socket,
    # and the server binds with allow_reuse_port. Every idle sleep or ping
    # restart therefore leaves a dead listener on the port, and the kernel
    # hands it a share of new connections that nobody accepts: segment
    # requests hang until Kodi times out (60 s each), and playback can take
    # minutes to start or fail outright. Close the socket first, give
    # connections a timeout, and never let a stuck close keep a dead server
    # registered as running.
    patch(lib / 'kodion' / 'network' / 'http_server.py', [
        ('    def server_close(self):\n'
         '        request_handler = self.RequestHandlerClass\n',
         '    def server_close(self):\n'
         '        TCPServer.server_close(self)\n'
         '        request_handler = self.RequestHandlerClass\n', 1),
        ('    RequestHandler.timeout = None\n',
         '    RequestHandler.timeout = 60\n', 1),
    ])
    patch(lib / 'kodion' / 'monitors' / 'service_monitor.py', [
        ('        self.httpd.server_close()\n'
         '\n'
         '        self.httpd_thread = None\n'
         '        self.httpd = None\n',
         '        close_thread = Thread(target=self.httpd.server_close)\n'
         '        close_thread.daemon = True\n'
         '        close_thread.start()\n'
         '        close_thread.join(5)\n'
         '\n'
         '        self.httpd_thread = None\n'
         '        self.httpd = None\n', 1),
        ('    def start_httpd(self):\n'
         '        if self.httpd:\n',
         '    def start_httpd(self):\n'
         '        if self.httpd and not (self.httpd_thread\n'
         '                               and self.httpd_thread.is_alive()):\n'
         '            self.shutdown_httpd(terminate=True)\n'
         '        if self.httpd:\n', 1),
    ])

    # Pick the quality once and keep it. With 'adaptive' InputStream
    # Adaptive switches resolution mid-video when its bandwidth estimate
    # dips (4K -> 1440p); on Amlogic boxes each switch restarts the hardware
    # decoder, which can leave a black picture with sound, a stall or a stop.
    # 'fixed-res' chooses the best stream for the screen and connection at
    # the start, the way a Blu-ray or remux plays.
    patch(lib / 'kodion' / 'items' / 'xbmc' / 'xbmc_items.py', [
        ("            props['inputstream.adaptive.stream_selection_type']"
         " = 'adaptive'\n",
         "            props['inputstream.adaptive.stream_selection_type']"
         " = 'fixed-res'\n", 1),
    ])

    # Sign-in codes go in CoreTube's own dialog (leanback/signin.py): a QR
    # code that opens google.com/device with the code filled in, and
    # "Step 1 of 2" so the second code (VR client) isn't taken for a repeat.
    patch(lib / 'youtube' / 'helper' / 'yt_login.py', [
        # The upstream "you may be prompted ... multiple applications" box
        # before the first code: our dialog says Step 1 of 2 instead.
        ("    ui.on_ok(localize('sign.multi.title'),"
         " localize('sign.multi.text'))\n",
         '', 1),
        ('from ...kodion import logging\n',
         'from ...kodion import logging\n'
         'from leanback.signin import sign_in_dialog\n', 1),
        ('            with ui.create_progress_dialog(\n'
         "                    heading=localize('sign.in'),\n"
         '                    message=message,\n'
         '                    background=False\n'
         '            ) as progress_dialog:\n',
         '            with sign_in_dialog(\n'
         "                    ui, localize('sign.in'), message,\n"
         "                    json_data.get('verification_url'), user_code,\n"
         '                    token_idx, client,\n'
         '            ) as progress_dialog:\n', 1),
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

    rebrand_strings()
    (ROOT / 'UPSTREAM_VERSION').write_text(version + '\n', encoding='utf-8')
    print('Synced {} {} into {}'.format(UPSTREAM_ID, version, ROOT))


if __name__ == '__main__':
    main()
