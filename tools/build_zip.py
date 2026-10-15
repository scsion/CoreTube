#!/usr/bin/env python3
"""Package the add-on as an installable zip for Kodi ("Install from zip file").

    python tools/build_zip.py   ->   dist/CoreTube-<version>.zip

The zip is named for people downloading it; inside, the add-on keeps its
id (script.youtube.leanback), which Kodi needs as the top folder.
"""

import re
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ADDON_ID = 'script.youtube.leanback'
INCLUDE = ['addon.xml', 'README.md', 'UPSTREAM_VERSION', 'LICENSES', 'resources']
# Build inputs only - already merged into settings.xml / strings.po.
EXCLUDE_NAMES = {'leanback_settings.xml', 'leanback_strings.po'}
EXCLUDE_PARTS = {'__pycache__'}


def files():
    for name in INCLUDE:
        path = ROOT / name
        if not path.exists():
            raise SystemExit('missing {} - run tools/sync_upstream.py first'
                             .format(name))
        candidates = [path] if path.is_file() else sorted(path.rglob('*'))
        for f in candidates:
            if (f.is_file() and f.name not in EXCLUDE_NAMES
                    and f.suffix != '.pyc'
                    and not EXCLUDE_PARTS.intersection(f.parts)):
                yield f


def main():
    xml = (ROOT / 'addon.xml').read_text(encoding='utf-8')
    version = re.search(r'<addon[^>]+version="([^"]+)"', xml).group(1)
    out = ROOT / 'dist' / 'CoreTube-{}.zip'.format(version)
    out.parent.mkdir(exist_ok=True)
    count = 0
    with zipfile.ZipFile(out, 'w', zipfile.ZIP_DEFLATED) as zf:
        for f in files():
            zf.write(f, '{}/{}'.format(ADDON_ID,
                                       f.relative_to(ROOT).as_posix()))
            count += 1
    print('Wrote {} ({} files)'.format(out.relative_to(ROOT), count))


if __name__ == '__main__':
    main()
