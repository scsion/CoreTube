#!/usr/bin/env python3
"""Write the Kodi repository that keeps CoreTube up to date.

    python tools/build_repo.py <checkout of the "repo" branch>

The repository add-on (repository/repository.coretube) points Kodi at the
"repo" branch of github.com/scsion/CoreTube. This writes into a checkout of
that branch:

    addons.xml, addons.xml.md5            what Kodi reads to find updates
    <addon id>/<addon id>-<version>.zip   one zip per version (old ones kept)
    <addon id>/<icon, fanart>             shown in Kodi's add-on browser
    repository.coretube.zip               fixed link for first-time installs

Commit and push the branch afterwards; Kodi checks it for updates on its
own schedule.
"""

import hashlib
import re
import shutil
import sys
import zipfile
from pathlib import Path

import build_zip

ROOT = Path(__file__).resolve().parent.parent
REPO_ADDON = ROOT / 'repository' / 'repository.coretube'
REPO_ID = 'repository.coretube'


def addon_version(addon_xml):
    return re.search(r'<addon[^>]+version="([^"]+)"', addon_xml).group(1)


def addon_assets(addon_xml):
    return re.findall(r'<(?:icon|fanart)>([^<]+)</(?:icon|fanart)>', addon_xml)


def write_zip(path, addon_id, files, base):
    path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(path, 'w', zipfile.ZIP_DEFLATED) as zf:
        for f in files:
            zf.write(f, '{}/{}'.format(addon_id, f.relative_to(base).as_posix()))


def publish(addon_id, base, files, out):
    addon_xml = (base / 'addon.xml').read_text(encoding='utf-8')
    version = addon_version(addon_xml)
    target = out / addon_id / '{}-{}.zip'.format(addon_id, version)
    write_zip(target, addon_id, files, base)
    for asset in addon_assets(addon_xml):
        dest = out / addon_id / asset
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(base / asset, dest)
    print('Wrote', target.relative_to(out))
    return addon_xml, target


def main():
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    out = Path(sys.argv[1]).resolve()
    if not (out / '.git').exists():
        sys.exit('{} is not a checkout of the repo branch'.format(out))

    coretube_xml, _ = publish(build_zip.ADDON_ID, ROOT,
                              list(build_zip.files()), out)
    repo_files = sorted(f for f in REPO_ADDON.rglob('*') if f.is_file())
    repo_xml, repo_zip = publish(REPO_ID, REPO_ADDON, repo_files, out)
    shutil.copyfile(repo_zip, out / '{}.zip'.format(REPO_ID))

    bodies = [re.sub(r'^\s*<\?xml[^>]*\?>\s*', '', xml).strip()
              for xml in (coretube_xml, repo_xml)]
    addons = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
              '<addons>\n{}\n</addons>\n'.format('\n'.join(bodies)))
    (out / 'addons.xml').write_text(addons, encoding='utf-8', newline='\n')
    md5 = hashlib.md5(addons.encode('utf-8')).hexdigest()
    (out / 'addons.xml.md5').write_text(md5, encoding='utf-8', newline='\n')
    print('Wrote addons.xml ({}), addons.xml.md5'.format(md5))


if __name__ == '__main__':
    main()
