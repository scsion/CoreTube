# CoreTube

A full-screen, remote-first YouTube interface for Kodi, laid out like
YouTube's own TV app. Built for CoreELEC.

> **Tested on:** Ugoos AM9 Pro · CoreELEC 22 (Kodi 22 "Piers") · Bald skin.
> It should work on any Kodi 21/22 box and skin, but that's the only setup
> it has been tested on so far.

## Features

- **Home rows**: Subscriptions, Recommended, Trending, Continue watching,
  Live, News, Sports, Gaming, Watch later (each can be switched off in the
  settings)
- **Search** with an on-screen keyboard, live YouTube suggestions and recent
  searches
- **Channel pages** with a banner, avatar and subscriber count, plus the
  creator's tabs (Home, Videos, Shorts, Live, Shows, Podcasts, Playlists) and
  Latest / Popular / Oldest sorting
- **Endless scrolling**: grids load the next page as you reach the end, with no
  "Next page" tiles
- **Plays straight away** and resumes where you left off, without a
  Play / Resume prompt
- **Works without an API key**: everything above comes from YouTube's own
  keyless InnerTube API
- **Signed-in feeds**: subscriptions, liked videos, your playlists, saved
  playlists and Watch later
- **SponsorBlock**: skips sponsor and other segments automatically, with a
  choice of categories
- **YouTube TV look**: an icon rail that expands on focus, a search bar, a
  large first shelf, focus ring, duration / LIVE badges and progress bars
- **Two logo styles** to choose from in the settings (Appearance → CoreTube logo)

## Install

1. Download `CoreTube-<version>.zip` from the
   [Releases](https://github.com/scsion/CoreTube/releases) page and copy it
   to the box (for example over SMB to `\\coreelec\Downloads`).
2. In Kodi, go to **Settings → System → Add-ons** and turn on
   **Unknown sources**.
3. Go to **Settings → Add-ons → Install from zip file** and pick the zip.
   Kodi pulls in `inputstream.adaptive` and `script.module.requests` from the
   official repository.
4. Open **Add-ons → Program add-ons → CoreTube**.

Updates are installed the same way, from the newer zip. Your settings and
sign-in are kept.

### Signing in (optional)

Choose **Sign in** in the rail. Then, on your phone, enter the codes it shows
at google.com/device. There are two codes, because the engine signs in both
its TV and VR clients. No API key is needed: subscriptions, liked videos,
playlists and the personal home feed come straight from YouTube.

If you have your own YouTube Data API key, you can enter it under
Settings → **API**. CoreTube then uses the official API listings instead.

### Adding CoreTube to the Bald home menu

Instead of widgets, CoreTube works well as its own entry in Bald's home menu:

1. Open Bald's home menu editor and add a new item labelled **CoreTube**.
2. Set its action to `RunScript(script.coretube)`.
3. Optionally, set its background to
   `special://home/addons/script.coretube/resources/brand/fanart.jpg`.

Selecting the entry opens the TV interface straight away. Opening CoreTube
from **Videos → Video add-ons** does the same.

## Remote controls

| Key | Action |
| --- | --- |
| Arrows / OK | Move, open, play |
| Left at the start of a row | Open the navigation rail |
| Context menu (`C` / long-press OK) | Play, related videos, go to channel |
| Back | Previous page, then the rail, then exit |

## How it's built

The YouTube side is a **standalone fork** of
[plugin.video.youtube](https://github.com/anxdpanic/plugin.video.youtube)
(GPL-2.0-only). It handles:

- the YouTube Data API and InnerTube clients
- OAuth sign-in
- stream deciphering and DASH manifests
- playback through InputStream Adaptive

It's vendored into `resources/lib/youtube_plugin` and runs under CoreTube's
own add-on id. So it doesn't depend on the YouTube add-on and can run
alongside it: its local server uses port 50162 instead of 50152.

The interface (`resources/lib/leanback`, `resources/skins`) is a Kodi window
that fills its shelves and grids itself. It runs the engine's routes in
worker threads, so all home rows arrive together in about three seconds.

The add-on's own `/leanback/...` routes (`resources/lib/leanback/routes.py`)
query InnerTube, the API that YouTube's web and TV apps use. InnerTube answers
anonymous requests:

- **Recommended**: videos related to what you watched last, or to trending
  videos before you have watched anything. When signed in, this is your
  account's TV home feed.
- **Trending / News / Sports / Gaming / Live**: the shelves of YouTube's
  Explore pages.
- **Search, channels, playlists, related videos**: the web client's search,
  browse and next endpoints.
- **Signed-in feeds**: the TV client's browse pages, read with the engine's
  TV sign-in.

The layout follows YouTube's TV app.
[tizen-youtube](https://github.com/SushyDev/tizen-youtube) (GPL-3.0) was used
only as a visual reference, and none of its code is included.

```
addon.xml                        add-on manifest (plugin + script + service)
resources/lib/default.py         script entry: opens the TV UI / runs engine actions
resources/lib/service_main.py    service entry: SponsorBlock, logo switching, engine service
resources/lib/leanback_plugin.py plugin entry: engine + keyless /leanback/ routes
resources/lib/leanback/          TV UI controller, InnerTube routes, search, SponsorBlock
resources/lib/youtube_plugin/    vendored engine (do not edit - re-sync instead)
resources/skins/Default/         window XML and textures (both generated)
resources/brand/                 CoreTube logo and background, options A and B
tools/sync_upstream.py           re-vendors the engine from an upstream checkout
tools/gen_skin.py                generates the window XML
tools/gen_textures.py            draws the rounded shapes and rail icons (needs Pillow)
tools/gen_brand.py               draws the logo and background (needs Pillow + Gotham)
tools/build_zip.py               builds dist/CoreTube-<version>.zip
```

## Building from source

```
python tools/build_zip.py
```

### Updating the engine when YouTube breaks something

```
git clone --depth 1 https://github.com/anxdpanic/plugin.video.youtube.git ../yt-upstream
python tools/sync_upstream.py ../yt-upstream
python tools/build_zip.py
```

`UPSTREAM_VERSION` records which engine release is vendored. The sync is
scripted, and it stops with an error if any of its patches no longer match
upstream.

## License

GPL-2.0-only. See `LICENSES/`.

CoreTube is a fan project. It is not affiliated with or endorsed by Google,
YouTube or the CoreELEC team. YouTube and the YouTube logo are trademarks of
Google LLC. The CoreTube emblem borrows CoreELEC's ring, and each logo belongs
to its owner.
