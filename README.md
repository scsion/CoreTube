# YouTube Leanback for Kodi

A full-screen, remote-first YouTube interface for Kodi (built for CoreELEC on
Kodi 22 "Piers"), styled after the YouTube TV app that
[tizen-youtube](https://github.com/SushyDev/tizen-youtube) runs on Samsung TVs.

- **Home rows**: Subscriptions, Recommended, Continue watching, Trending, Live, Watch later
- **Search** with the on-screen keyboard, plus channel, playlist and related-video pages
- **Signed-in feeds**: subscriptions, liked videos, your playlists and saved playlists
- **SponsorBlock**: skips sponsor and other segments automatically, with a choice of categories
- A left navigation rail that expands on focus and a large preview of the focused video

## How it's built

The YouTube side is a **standalone fork** of
[plugin.video.youtube](https://github.com/anxdpanic/plugin.video.youtube)
(GPL-2.0-only). It handles the YouTube Data API and InnerTube clients, OAuth
sign-in, stream deciphering, DASH manifests and playback through
InputStream Adaptive. It's vendored into `resources/lib/youtube_plugin` and
runs under this add-on's own id, so it doesn't depend on the YouTube add-on
and can run alongside it (its local server uses port 50162 instead of 50152).

The interface (`resources/lib/leanback`, `resources/skins`) never calls YouTube
directly. Each row and grid is a Kodi container whose content is a
`plugin://script.youtube.leanback/...` path served by the engine, so Kodi
handles loading, caching and thumbnails. tizen-youtube is GPL-3.0 and was used
only as a visual and feature reference. None of its code is included.

```
addon.xml                      add-on manifest (plugin + script + service)
resources/lib/default.py       script entry: opens the TV UI / runs engine actions
resources/lib/service_main.py  service entry: SponsorBlock + engine service
resources/lib/leanback/        TV UI controller and SponsorBlock skipper
resources/lib/youtube_plugin/  vendored engine (do not edit - re-sync instead)
resources/skins/Default/       window XML (generated) and textures
tools/sync_upstream.py         re-vendor the engine from an upstream checkout
tools/gen_skin.py              generates the window XML
tools/build_zip.py             builds dist/script.youtube.leanback-<ver>.zip
```

## Install on CoreELEC

1. Build the zip: `python tools/build_zip.py`
2. Copy `dist/script.youtube.leanback-<version>.zip` to the box (for example over
   SMB to `\\coreelec\Downloads`).
3. In Kodi, go to **Settings → System → Add-ons** and turn on **Unknown sources**.
4. **Settings → Add-ons → Install from zip file** and pick the zip. Kodi pulls in
   `inputstream.adaptive` and `script.module.requests` from the official repo.
5. Open **Add-ons → Program add-ons → YouTube Leanback**.

### Signing in

YouTube requires your own API keys for signed-in features. Open **Settings**
in the left rail, go to the **API** category and enter your API key, client ID
and client secret. The engine's setup wizard explains how to create them in the
Google Cloud console. Then choose **Sign in** in the rail and follow the
device-code prompt on your phone.

## Updating the engine when YouTube breaks something

```
git clone --depth 1 https://github.com/anxdpanic/plugin.video.youtube.git ../yt-upstream
python tools/sync_upstream.py ../yt-upstream
python tools/build_zip.py
```

`UPSTREAM_VERSION` records which engine release is vendored. The sync is
scripted and stops with an error if any of its patches no longer match
upstream.

## Remote controls

| Key | Action |
| --- | --- |
| Arrows / OK | Move, open, play |
| Left at the start of a row | Open the navigation rail |
| Context menu (`C` / long-press OK) | Play, related videos, go to channel |
| Back | Previous page, then the rail, then exit |

## License

GPL-2.0-only. See `LICENSES/`. Not affiliated with Google or YouTube.
