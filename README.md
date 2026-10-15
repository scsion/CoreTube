# YouTube Leanback for Kodi

A full-screen, remote-first YouTube interface for Kodi (built for CoreELEC on
Kodi 22 "Piers"), styled after the YouTube TV app that
[tizen-youtube](https://github.com/SushyDev/tizen-youtube) runs on Samsung TVs.

- **Home rows**: Subscriptions, Recommended, Continue watching, Trending, Live, Watch later
- **Search** with the on-screen keyboard, plus channel, playlist and related-video pages
- **Works without an API key**: home rows, search, channels, playlists and
  related videos fall back to YouTube's own keyless InnerTube API
- **Signed-in feeds**: subscriptions, liked videos, your playlists and saved playlists
- **SponsorBlock**: skips sponsor and other segments automatically, with a choice of categories
- **YouTube TV look**: laid out like YouTube's own TV app (what TizenTube shows):
  icon rail that expands on focus, search bar, big first shelf, focus ring,
  duration / LIVE badges and progress bars, focused shelf scrolls to the top

## How it's built

The YouTube side is a **standalone fork** of
[plugin.video.youtube](https://github.com/anxdpanic/plugin.video.youtube)
(GPL-2.0-only). It handles the YouTube Data API and InnerTube clients, OAuth
sign-in, stream deciphering, DASH manifests and playback through
InputStream Adaptive. It's vendored into `resources/lib/youtube_plugin` and
runs under this add-on's own id, so it doesn't depend on the YouTube add-on
and can run alongside it (its local server uses port 50162 instead of 50152).

The interface (`resources/lib/leanback`, `resources/skins`) shows
`plugin://script.youtube.leanback/...` listings served by the engine. Grid
pages are Kodi containers that load those paths themselves. Home and Library
shelves are filled by the window (`leanback/loader.py`), which runs the same
engine routes in worker threads: all shelves arrive together in about three
seconds instead of one plugin run after another.

Without a Data API key the window uses the add-on's own `/leanback/...` plugin
routes instead (`resources/lib/leanback/routes.py`, registered on the engine's
router by `resources/lib/leanback_plugin.py`). They query InnerTube, the API
the YouTube web and TV apps use, which answers anonymous requests:

- **Recommended**: related videos of what you watched last, or of trending
  videos before you have watched anything (your account's TV
  home feed when signed in)
- **Trending / News / Sports / Gaming / Live**: the shelves of YouTube's
  Explore destination pages (YouTube retired its Trending page in 2025)
- **Search, channel videos, playlists, related videos**: the web client's
  search, browse and next endpoints
- **Signed in: subscriptions, liked videos, your playlists, saved
  playlists**: the TV client's browse pages (`FEsubscriptions`, `VLLL`,
  `FEplaylist_aggregation`), read with the engine's TV sign-in, which needs
  no key either. Playlists open as the account too, so private ones such as
  Watch later work

tizen-youtube is GPL-3.0 and was used
only as a visual and feature reference. None of its code is included.

```
addon.xml                      add-on manifest (plugin + script + service)
resources/lib/default.py       script entry: opens the TV UI / runs engine actions
resources/lib/service_main.py  service entry: SponsorBlock + engine service
resources/lib/leanback_plugin.py plugin entry: engine + keyless /leanback/ routes
resources/lib/leanback/        TV UI controller, keyless InnerTube routes, SponsorBlock
resources/lib/youtube_plugin/  vendored engine (do not edit - re-sync instead)
resources/skins/Default/       window XML and textures (both generated)
tools/sync_upstream.py         re-vendor the engine from an upstream checkout
tools/gen_skin.py              generates the window XML
tools/gen_textures.py          draws the rounded shapes and rail icons (needs Pillow)
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

Choose **Sign in** in the rail and enter the codes it shows at
google.com/device on your phone (there are two: the engine signs in its TV and
VR clients). No API key is needed: subscriptions, liked videos, your playlists,
saved playlists and the personal home feed then come straight from InnerTube.

With your own Data API key (Settings, **API** category; the engine's setup
wizard explains how to create one in the Google Cloud console) the window uses
the engine's Data API listings instead.

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
