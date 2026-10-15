"""Sign-in dialog with a QR code, used by the engine's device sign-in.

The engine signs in one OAuth client per token type (TV, then VR), each
with its own code from google.com/device. Kodi's progress dialog it uses
upstream can't show an image, so tools/sync_upstream.py points the sign-in
loop at sign_in_dialog() here instead: the same calls (update, set_total,
is_aborted, used as a context manager), plus a QR code that opens the
approval page with the code already filled in, and "Step 1 of 2".

The QR matrix comes from script.module.pyqrcode (Kodi's official repo);
the PNG is written here with zlib, so no image library is needed.
"""

import os
import struct
import zlib

import xbmc
import xbmcgui
import xbmcvfs

from . import ADDON_ID, addon, localize

XML_FILE = 'script-coretube-signin.xml'
QR_PATH = 'special://temp/{}-signin-{}.png'
QR_SCALE = 9          # pixels per QR module; the dialog shows it 1:1
QR_BORDER = 4         # quiet zone, in modules
DEFAULT_URL = 'https://www.google.com/device'
ACTION_PREVIOUS_MENU = 10
ACTION_NAV_BACK = 92
# The engine polls for 10 minutes before the code lapses.
CODE_MINUTES = 10


def log(msg, level=xbmc.LOGINFO):
    xbmc.log('[{}] Sign-in: {}'.format(ADDON_ID, msg), level)


def _png(rows, size):
    """Greyscale 8-bit PNG from rows of bytes."""
    def chunk(kind, data):
        return (struct.pack('>I', len(data)) + kind + data
                + struct.pack('>I', zlib.crc32(kind + data) & 0xffffffff))
    raw = b''.join(b'\x00' + row for row in rows)
    return b''.join((
        b'\x89PNG\r\n\x1a\n',
        chunk(b'IHDR', struct.pack('>IIBBBBB', size, size, 8, 0, 0, 0, 0)),
        chunk(b'IDAT', zlib.compress(raw, 9)),
        chunk(b'IEND', b''),
    ))


def write_qr(text, path):
    """Draw text as a QR code PNG at path. False if it can't be made."""
    try:
        import pyqrcode
        code = pyqrcode.create(text, error='M').code
    except Exception as exc:  # module missing or text too long
        log('no QR code: {}'.format(exc), xbmc.LOGWARNING)
        return False
    modules = len(code) + 2 * QR_BORDER
    rows = []
    for y in range(modules):
        cy = y - QR_BORDER
        row = bytearray()
        for x in range(modules):
            cx = x - QR_BORDER
            dark = (0 <= cy < len(code) and 0 <= cx < len(code)
                    and code[cy][cx])
            row += (b'\x00' if dark else b'\xff') * QR_SCALE
        rows.extend([bytes(row)] * QR_SCALE)
    with open(xbmcvfs.translatePath(path), 'wb') as out:
        out.write(_png(rows, modules * QR_SCALE))
    return True


class _Window(xbmcgui.WindowXMLDialog):
    def __init__(self, *args, **kwargs):
        super(_Window, self).__init__(*args, **kwargs)
        self.aborted = False

    def onAction(self, action):
        if action.getId() in (ACTION_PREVIOUS_MENU, ACTION_NAV_BACK):
            self.aborted = True
            self.close()


class SignInDialog(object):
    """Stands in for the engine's progress dialog during sign-in."""

    def __init__(self, url, code, step, steps):
        url = url or DEFAULT_URL
        if not url.startswith('http'):
            url = 'https://' + url
        shown_url = url.split('://', 1)[-1]
        if shown_url.startswith('www.'):
            shown_url = shown_url[4:]
        # One file per code: Kodi caches textures by path. A real path, not
        # special://, for Kodi's texture loader.
        self._qr = xbmcvfs.translatePath(QR_PATH.format(ADDON_ID, code))
        self._qr_retry = self._qr[:-4] + '-2.png'
        self._has_qr = write_qr('{}?user_code={}'.format(url, code), self._qr)
        self._total = 1
        self._done = 0
        self._window = _Window(XML_FILE, addon().getAddonInfo('path'),
                               'Default', '1080i')
        self._window.setProperty('heading', localize(39130))
        self._window.setProperty('step', localize(39131).format(step, steps)
                                 if steps > 1 else '')
        self._window.setProperty('instructions',
                                 localize(39132).format(shown_url))
        self._window.setProperty('code', code)
        self._window.setProperty('status', localize(39133))
        self._set_expiry()

    def __enter__(self):
        self._window.show()
        # Point at the image only once the dialog is up: set while Kodi was
        # still opening it, the texture load could fail and never retry.
        xbmc.Monitor().waitForAbort(0.3)
        if self._has_qr:
            self._window.setProperty('qr', self._qr)
        return self

    def __exit__(self, *exc):
        self._window.close()
        del self._window
        for path in (self._qr, self._qr_retry):
            try:
                os.remove(path)
            except OSError:
                pass
        return False

    # The engine's progress dialog interface.
    def set_total(self, total):
        self._total = max(int(total), 1)

    def grow_total(self, delta=1, **_kwargs):
        self._total += delta

    def update(self, *_args, **_kwargs):
        self._done += 1
        self._set_expiry()
        # Second poll, a few seconds in: show a fresh copy of the image, so
        # a texture load that failed gets another go under a new path.
        if self._done == 2 and self._has_qr:
            try:
                with open(self._qr, 'rb') as src:
                    data = src.read()
                with open(self._qr_retry, 'wb') as dst:
                    dst.write(data)
            except OSError:
                return
            self._window.setProperty('qr', self._qr_retry)

    def _set_expiry(self):
        left = CODE_MINUTES * (self._total - self._done)
        minutes = max(1, -(-left // self._total))
        self._window.setProperty('expires', localize(39134).format(minutes))

    def is_aborted(self):
        return self._window.aborted


def sign_in_dialog(ui, heading, message, url, code, token_idx, client):
    """The dialog for one code of the engine's sign-in loop; Kodi's plain
    progress dialog if ours can't be shown."""
    try:
        configured = [
            idx for idx in range(4)
            if (client._configs.get(client.TOKEN_TYPES.get(idx)) or {})
            .get('id')
        ]
        steps = len(configured) or 1
        step = configured.index(token_idx) + 1 if token_idx in configured else 1
        return SignInDialog(url, code, step, steps)
    except Exception as exc:
        log('falling back to the engine dialog: {}'.format(exc),
            xbmc.LOGWARNING)
        return ui.create_progress_dialog(heading=heading, message=message,
                                         background=False)
