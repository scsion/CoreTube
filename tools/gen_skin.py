#!/usr/bin/env python3
"""Generate the leanback window XML.

Kodi script skins can't use <include> from the user's skin, so the repeated
row/tile markup is templated here instead. Edit this file, then run:

    python tools/gen_skin.py

The layout follows YouTube's own TV app (what TizenTube shows), measured from
its 1080p screenshots: a collapsed icon rail on the left, a search bar and
logo on top, and shelves whose 16:9 tiles carry the title, channel and stats
underneath. The focused shelf scrolls up under the top edge. Fonts come from
the running skin (Bald ships DM Sans); textures from tools/gen_textures.py.
"""

from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = (ROOT / 'resources' / 'skins' / 'Default' / '1080i'
       / 'script-youtube-leanback-main.xml')

ROW_COUNT = 8
NAV_ID = 9000
ROWS_GROUP_ID = 100
GRID_ID = 200
SEARCH_ID = 300
# Search view: on-screen keyboard, its Space/Clear/Search row, suggestions,
# results shelf.
KEYS_ID = 400
KEY_ACTIONS_ID = 401
SUGGEST_ID = 402
RESULTS_ID = 403
# Channel page: tabs (Videos, Live, Playlists) above the grid.
TABS_ID = 210
SORTS_ID = 211          # the tab's sort chips (Latest / Popular / Oldest)
SORTS_SHIFT = 76        # extra grid offset while a tab has sort chips
HAS_SORTS = '!String.IsEmpty(Window.Property(channel.sorts))'
CHANNEL_SHIFT = 160     # the grid sits this much lower under a channel header
TAB_W = 200             # tab chip slot (chip plus gap)
TAB_PAD = 8             # room around a chip for its focus ring
KEY = 67            # keyboard cell, as on YouTube TV at 1080p

BG = 'FF0F0F0F'
SURFACE = 'FF272727'       # search bar, placeholders
TEXT = 'FFF1F1F1'
TEXT_DIM = 'FFAAAAAA'
DARK_TEXT = 'FF0F0F0F'
ACCENT = 'FFFF0033'        # YouTube red: progress bars, live badge
ADDON = 'script.youtube.leanback'

# Bald's fonts (DM Sans). Sizes match YouTube TV's at 1080p.
FONT_SHELF = 'font25_title'      # SemiBold 25 - shelf titles
FONT_TITLE = 'Bald_InfoTagline'  # Medium 30 - tile titles
FONT_META = 'font12'             # Regular 25 - channel, stats
FONT_BADGE = 'Bald_DetailValue'  # Medium 21 - duration badge
FONT_NAV = 'font13'              # Regular 30 - rail labels, search text
FONT_PAGE = 'font40_title'       # SemiBold 40 - grid page title, logo

CONTENT_X = 156     # left edge of shelf titles and tiles
RAIL_W = 140        # collapsed rail
PAD = 10            # room around a thumbnail for the focus ring

# Tile sizes: regular shelves, the first home shelf, and grid pages.
REGULAR = {'w': 528, 'h': 297, 'gap': 36, 'mask': 'mask_tile.png'}
LARGE = {'w': 720, 'h': 405, 'gap': 34, 'mask': 'mask_tile_large.png'}
GRID = {'w': 405, 'h': 228, 'gap': 36, 'mask': 'mask_tile_grid.png'}

# Shelf positions: the first shelf's title sits under the search bar, each
# following shelf starts one block lower. The focused shelf scrolls up to
# FOCUS_TOP, taking the header with it.
FIRST_TOP = 180
FIRST_BLOCK = 740
BLOCK = 672
FOCUS_TOP = 96

VIEW_ROWS = 'String.IsEqual(Window.Property(view),rows)'
VIEW_GRID = 'String.IsEqual(Window.Property(view),grid)'
VIEW_SEARCH = 'String.IsEqual(Window.Property(view),search)'
VIEW_CHANNEL = 'String.IsEqual(Window.Property(view),channel)'


def row_top(index):
    if index == 1:
        return FIRST_TOP
    return FIRST_TOP + FIRST_BLOCK + (index - 2) * BLOCK


def text_height(size):
    """Title (two lines), channel and stats lines below a thumbnail."""
    return size['h'] + 2 * PAD + 22 + 84 + 6 + 34 + 34


def tile(size, focused, list_id):
    """One video tile as YouTube TV draws it. Kodi draws the focused layout
    for each list's selected item even while another list has focus, so the
    ring checks its own list."""
    w, h = size['w'], size['h']
    ring = '''
                    <control type="image">
                        <left>{x}</left><top>{x}</top>
                        <width>{rw}</width><height>{rh}</height>
                        <visible>Control.HasFocus({lid})</visible>
                        <texture border="20" colordiffuse="FFFFFFFF">focus_ring.png</texture>
                    </control>'''.format(x=PAD - 6, rw=w + 12, rh=h + 12,
                                         lid=list_id) if focused else ''
    wide = 'Integer.IsGreaterOrEqual(ListItem.Duration(secs),3600)'
    return '''
                    <control type="image">
                        <left>{p}</left><top>{p}</top>
                        <width>{w}</width><height>{h}</height>
                        <texture border="12" colordiffuse="{surface}">round12.png</texture>
                    </control>
                    <control type="image">
                        <left>{p}</left><top>{p}</top>
                        <width>{w}</width><height>{h}</height>
                        <aspectratio>scale</aspectratio>
                        <fadetime>120</fadetime>
                        <texture background="true" diffuse="{mask}">$INFO[ListItem.Art(thumb)]</texture>
                    </control>
                    <control type="progress">
                        <left>{p}</left><top>{bar_y}</top>
                        <width>{w}</width><height>6</height>
                        <visible>Integer.IsGreater(ListItem.PercentPlayed,0)</visible>
                        <texturebg colordiffuse="80FFFFFF">white.png</texturebg>
                        <midtexture colordiffuse="{accent}">white.png</midtexture>
                        <info>ListItem.PercentPlayed</info>
                    </control>
                    <control type="group">
                        <visible>!String.IsEmpty(ListItem.Duration)</visible>
                        <control type="image">
                            <left>{badge_x}</left><top>{badge_y}</top>
                            <width>78</width><height>34</height>
                            <visible>!{wide}</visible>
                            <texture border="8" colordiffuse="CC000000">round8.png</texture>
                        </control>
                        <control type="image">
                            <left>{badge_wx}</left><top>{badge_y}</top>
                            <width>104</width><height>34</height>
                            <visible>{wide}</visible>
                            <texture border="8" colordiffuse="CC000000">round8.png</texture>
                        </control>
                        <control type="label">
                            <left>{badge_wx}</left><top>{badge_y}</top>
                            <width>{badge_text_w}</width><height>34</height>
                            <font>{font_badge}</font>
                            <align>right</align><aligny>center</aligny>
                            <textcolor>{text}</textcolor>
                            <label>$INFO[ListItem.Duration]</label>
                        </control>
                    </control>
                    <control type="group">
                        <visible>String.IsEqual(ListItem.Property(live),true)</visible>
                        <control type="image">
                            <left>{live_x}</left><top>{badge_y}</top>
                            <width>72</width><height>34</height>
                            <texture border="8" colordiffuse="{accent}">round8.png</texture>
                        </control>
                        <control type="label">
                            <left>{live_x}</left><top>{badge_y}</top>
                            <width>72</width><height>34</height>
                            <font>{font_badge}</font>
                            <align>center</align><aligny>center</aligny>
                            <textcolor>{text}</textcolor>
                            <label>LIVE</label>
                        </control>
                    </control>{ring}
                    <control type="textbox">
                        <left>{p}</left><top>{title_y}</top>
                        <width>{w}</width><height>78</height>
                        <font>{font_title}</font>
                        <textcolor>{text}</textcolor>
                        <label>$INFO[ListItem.Label]</label>
                    </control>
                    <control type="label">
                        <left>{p}</left><top>{channel_y}</top>
                        <width>{w}</width><height>34</height>
                        <font>{font_meta}</font>
                        <textcolor>{dim}</textcolor>
                        <label>$INFO[ListItem.Artist]</label>
                    </control>
                    <control type="label">
                        <left>{p}</left><top>{meta_y}</top>
                        <width>{w}</width><height>34</height>
                        <font>{font_meta}</font>
                        <textcolor>{dim}</textcolor>
                        <label>$INFO[ListItem.Label2]</label>
                    </control>'''.format(
        p=PAD, w=w, h=h, mask=size['mask'], surface=SURFACE, accent=ACCENT,
        text=TEXT, dim=TEXT_DIM, ring=ring, wide=wide,
        bar_y=PAD + h - 6,
        badge_x=PAD + w - 10 - 78, badge_wx=PAD + w - 10 - 104,
        badge_y=PAD + h - 10 - 34, badge_text_w=104 - 10,
        live_x=PAD + w - 10 - 72,
        title_y=PAD + h + 22, channel_y=PAD + h + 22 + 84 + 6,
        meta_y=PAD + h + 22 + 84 + 6 + 34,
        font_title=FONT_TITLE, font_meta=FONT_META, font_badge=FONT_BADGE)


def placeholders(size, top):
    """Grey tiles shown while a shelf loads."""
    return ''.join('''
                <control type="image">
                    <left>{x}</left><top>{y}</top>
                    <width>{w}</width><height>{h}</height>
                    <texture border="12" colordiffuse="{surface}">round12.png</texture>
                </control>'''.format(x=CONTENT_X + i * (size['w'] + size['gap']),
                                     y=top + PAD, w=size['w'], h=size['h'],
                                     surface=SURFACE)
                   for i in range(4))


def layouts(size, list_id, condition=None):
    item_w = size['w'] + size['gap']
    item_h = text_height(size)
    cond = ' condition="{}"'.format(condition) if condition else ''
    return '''
                    <itemlayout width="{iw}" height="{ih}"{cond}>{item}
                    </itemlayout>
                    <focusedlayout width="{iw}" height="{ih}"{cond}>{focused}
                    </focusedlayout>'''.format(iw=item_w, ih=item_h, cond=cond,
                                               item=tile(size, False, list_id),
                                               focused=tile(size, True, list_id))


def row(index):
    """One shelf. The window fills its list itself (see leanback/loader.py),
    so there is no <content>. A shelf shows as soon as it has a path."""
    list_id = ROWS_GROUP_ID + index
    prop = 'row{}'.format(index)
    top = row_top(index)
    # The first home shelf uses the big tiles; any other view the regular.
    if index == 1:
        large = 'String.IsEqual(Window.Property(row1.large),true)'
        tiles = (layouts(LARGE, list_id, large)
                 + layouts(REGULAR, list_id, '!' + large))
        loading = ('''
                <control type="group">
                    <visible>{large}</visible>{big}
                </control>
                <control type="group">
                    <visible>!{large}</visible>{small}
                </control>'''.format(large=large,
                                     big=placeholders(LARGE, 48),
                                     small=placeholders(REGULAR, 48)))
        height = text_height(LARGE)
    else:
        tiles = layouts(REGULAR, list_id)
        loading = placeholders(REGULAR, 48)
        height = text_height(REGULAR)
    up = SEARCH_ID if index == 1 else list_id - 1
    down = min(list_id + 1, ROWS_GROUP_ID + ROW_COUNT)
    return '''
            <control type="group">
                <left>0</left><top>{top}</top>
                <visible>!String.IsEmpty(Window.Property({prop}.path))</visible>
                <control type="label">
                    <left>{x}</left><top>0</top>
                    <width>1600</width><height>40</height>
                    <font>{font_shelf}</font>
                    <textcolor>{text}</textcolor>
                    <label>$INFO[Window.Property({prop}.label)]</label>
                </control>
                <control type="group">
                    <left>0</left><top>0</top>
                    <visible>String.IsEqual(Window.Property({prop}.loading),true)</visible>{loading}
                </control>
                <control type="list" id="{lid}">
                    <left>{lx}</left><top>48</top>
                    <width>{lw}</width><height>{h}</height>
                    <orientation>horizontal</orientation>
                    <onleft>{nav}</onleft>
                    <onup>{up}</onup>
                    <ondown>{down}</ondown>
                    <onright>noop</onright>
                    <scrolltime tween="cubic" easing="out">250</scrolltime>
                    <focusposition>0</focusposition>
                    <movement>1</movement>{tiles}
                </control>
            </control>'''.format(top=top, prop=prop, x=CONTENT_X,
                                 font_shelf=FONT_SHELF, text=TEXT,
                                 loading=loading, lid=list_id,
                                 lx=CONTENT_X - PAD, lw=1920 - CONTENT_X + PAD,
                                 h=height, nav=NAV_ID, up=up, down=down,
                                 tiles=tiles)


def scroll_animations():
    """Slide the page so the focused shelf sits near the top edge.

    One slide per shelf boundary, each active while the focus is on or below
    that shelf, so moving one shelf starts or reverses exactly one slide of
    one shelf's height. (One absolute slide per shelf made two slides run
    against each other on every move, which lurched lower down the page.)"""
    steps = []
    for i in range(2, ROW_COUNT + 1):
        start = FOCUS_TOP - row_top(i - 1) if i > 2 else 0
        steps.append('''
            <animation effect="slide" end="0,{dy}" time="300" tween="cubic" easing="out" condition="Integer.IsGreaterOrEqual(Window.Property(focusrow),{i})">Conditional</animation>'''
                     .format(i=i, dy=(FOCUS_TOP - row_top(i)) - start))
    return ''.join(steps)


def header():
    """Search bar and logo; they scroll away with the first shelf."""
    return '''
            <control type="image">
                <left>{x}</left><top>67</top>
                <width>70</width><height>70</height>
                <texture colordiffuse="{surface}">circle.png</texture>
            </control>
            <control type="image">
                <left>{mic_x}</left><top>86</top>
                <width>32</width><height>32</height>
                <aspectratio>keep</aspectratio>
                <texture>icon_mic.png</texture>
            </control>
            <control type="button" id="{search}">
                <left>{pill_x}</left><top>67</top>
                <width>630</width><height>70</height>
                <font>{font_nav}</font>
                <textoffsetx>36</textoffsetx>
                <aligny>center</aligny>
                <textcolor>{dim}</textcolor>
                <focusedcolor>{dark}</focusedcolor>
                <texturefocus border="35" colordiffuse="{text}">pill.png</texturefocus>
                <texturenofocus border="35" colordiffuse="{surface}">pill.png</texturenofocus>
                <label>$ADDON[{addon} 39100]</label>
                <onleft>{nav}</onleft>
                <ondown>{first}</ondown>
            </control>
            <control type="image">
                <left>1430</left><top>67</top>
                <width>400</width><height>70</height>
                <aspectratio align="right">keep</aspectratio>
                <!-- Logo option a or b (leanback/brand.py), set by the window. -->
                <texture>$INFO[Window.Property(logo),brand_lockup_,.png]</texture>
            </control>'''.format(x=CONTENT_X, mic_x=CONTENT_X + 19,
                                 pill_x=CONTENT_X + 94, surface=SURFACE,
                                 addon=ADDON, search=SEARCH_ID,
                                 font_nav=FONT_NAV, dim=TEXT_DIM,
                                 dark=DARK_TEXT, text=TEXT, nav=NAV_ID,
                                 first=ROWS_GROUP_ID + 1,
                                 font_page=FONT_PAGE)


def _key(focused):
    """Keyboard cell: a letter, or an icon for backspace; white rounded
    square with dark text while focused."""
    has_focus = 'Control.HasFocus({})'.format(KEYS_ID)
    on = has_focus if focused else 'false'
    return '''
                    <control type="image">
                        <left>4</left><top>4</top>
                        <width>{c}</width><height>{c}</height>
                        <visible>{on}</visible>
                        <texture border="12" colordiffuse="{text}">round12.png</texture>
                    </control>
                    <control type="label">
                        <left>0</left><top>0</top>
                        <width>{k}</width><height>{k}</height>
                        <font>{font}</font>
                        <align>center</align><aligny>center</aligny>
                        <textcolor>{dim}</textcolor>
                        <visible>String.IsEmpty(ListItem.Icon) + !{on}</visible>
                        <label>$INFO[ListItem.Label]</label>
                    </control>
                    <control type="label">
                        <left>0</left><top>0</top>
                        <width>{k}</width><height>{k}</height>
                        <font>{font}</font>
                        <align>center</align><aligny>center</aligny>
                        <textcolor>{dark}</textcolor>
                        <visible>String.IsEmpty(ListItem.Icon) + {on}</visible>
                        <label>$INFO[ListItem.Label]</label>
                    </control>
                    <control type="image">
                        <left>{i}</left><top>{i}</top>
                        <width>30</width><height>30</height>
                        <aspectratio>keep</aspectratio>
                        <visible>!String.IsEmpty(ListItem.Icon) + !{on}</visible>
                        <texture colordiffuse="{dim}">$INFO[ListItem.Icon]</texture>
                    </control>
                    <control type="image">
                        <left>{i}</left><top>{i}</top>
                        <width>30</width><height>30</height>
                        <aspectratio>keep</aspectratio>
                        <visible>!String.IsEmpty(ListItem.Icon) + {on}</visible>
                        <texture colordiffuse="{dark}">$INFO[ListItem.Icon]</texture>
                    </control>'''.format(c=KEY - 8, k=KEY, i=(KEY - 30) // 2,
                                     on=on, text=TEXT, dim=TEXT_DIM,
                                     dark=DARK_TEXT, font=FONT_NAV)


def _pill_item(width, height, list_id, focused, icon=False):
    """Rounded chip with a label (and an optional icon), white while
    focused, as YouTube TV draws buttons and suggestions."""
    on = 'Control.HasFocus({})'.format(list_id) if focused else 'false'
    text_x = 64 if icon else 0
    icon_xml = '''
                    <control type="image">
                        <left>22</left><top>{iy}</top>
                        <width>28</width><height>28</height>
                        <aspectratio>keep</aspectratio>
                        <visible>!{on}</visible>
                        <texture colordiffuse="{dim}">$INFO[ListItem.Icon]</texture>
                    </control>
                    <control type="image">
                        <left>22</left><top>{iy}</top>
                        <width>28</width><height>28</height>
                        <aspectratio>keep</aspectratio>
                        <visible>{on}</visible>
                        <texture colordiffuse="{dark}">$INFO[ListItem.Icon]</texture>
                    </control>'''.format(iy=(height - 10 - 28) // 2, on=on,
                                     dim=TEXT_DIM, dark=DARK_TEXT) if icon else ''
    return '''
                    <control type="image">
                        <left>0</left><top>0</top>
                        <width>{w}</width><height>{h}</height>
                        <visible>!{on}</visible>
                        <texture border="25" colordiffuse="{surface}">pill.png</texture>
                    </control>
                    <control type="image">
                        <left>0</left><top>0</top>
                        <width>{w}</width><height>{h}</height>
                        <visible>{on}</visible>
                        <texture border="25" colordiffuse="{text}">pill.png</texture>
                    </control>{icon}
                    <control type="label">
                        <left>{tx}</left><top>0</top>
                        <width>{tw}</width><height>{h}</height>
                        <font>{font}</font>
                        <align>{align}</align><aligny>center</aligny>
                        <textcolor>{dim}</textcolor>
                        <focusedcolor>{dim}</focusedcolor>
                        <visible>!{on}</visible>
                        <label>$INFO[ListItem.Label]</label>
                    </control>
                    <control type="label">
                        <left>{tx}</left><top>0</top>
                        <width>{tw}</width><height>{h}</height>
                        <font>{font}</font>
                        <align>{align}</align><aligny>center</aligny>
                        <textcolor>{dark}</textcolor>
                        <visible>{on}</visible>
                        <label>$INFO[ListItem.Label]</label>
                    </control>'''.format(
        w=width, h=height - 10, on=on, surface=SURFACE, text=TEXT,
        dim=TEXT_DIM, dark=DARK_TEXT, icon=icon_xml, tx=text_x,
        tw=width - text_x - (24 if icon else 0),
        align='left' if icon else 'center', font=FONT_META)


def channel_header():
    """YouTube TV's channel header: the banner fading into the page, the
    round avatar, name, handle and counts, and the tab pills."""
    return '''
            <control type="group">
                <visible>{view}</visible>
                <control type="image">
                    <left>0</left><top>0</top>
                    <width>1920</width><height>320</height>
                    <aspectratio>scale</aspectratio>
                    <fadetime>200</fadetime>
                    <texture background="true">$INFO[Window.Property(channel.banner)]</texture>
                </control>
                <control type="image">
                    <left>0</left><top>0</top>
                    <width>1920</width><height>320</height>
                    <texture colordiffuse="B30F0F0F">white.png</texture>
                </control>
                <control type="image">
                    <left>0</left><top>120</top>
                    <width>1920</width><height>200</height>
                    <texture colordiffuse="{bg}">grad_bottom.png</texture>
                </control>
                <control type="image">
                    <left>{x}</left><top>56</top>
                    <width>140</width><height>140</height>
                    <texture colordiffuse="{surface}">circle.png</texture>
                </control>
                <control type="image">
                    <left>{x}</left><top>56</top>
                    <width>140</width><height>140</height>
                    <aspectratio>scale</aspectratio>
                    <fadetime>200</fadetime>
                    <texture background="true" diffuse="circle.png">$INFO[Window.Property(channel.avatar)]</texture>
                </control>
                <control type="label">
                    <left>{tx}</left><top>62</top>
                    <width>1350</width><height>60</height>
                    <font>{font_page}</font>
                    <textcolor>{text}</textcolor>
                    <label>$INFO[Window.Property(channel.name)]</label>
                </control>
                <control type="label">
                    <left>{tx}</left><top>124</top>
                    <width>1350</width><height>40</height>
                    <font>{font_meta}</font>
                    <textcolor>{dim}</textcolor>
                    <label>$INFO[Window.Property(channel.handle)]$INFO[Window.Property(channel.stats), • ]</label>
                </control>
                <control type="image">
                    <left>{divider_x}</left><top>{divider_y}</top>
                    <width>1540</width><height>2</height>
                    <texture colordiffuse="33FFFFFF">white.png</texture>
                </control>
                <control type="list" id="{tabs}">
                    <left>{tabs_x}</left><top>{tabs_y}</top>
                    <width>1560</width><height>{tabs_h}</height>
                    <orientation>horizontal</orientation>
                    <onleft>{nav}</onleft>
                    <ondown condition="{has_sorts}">SetFocus({sorts})</ondown>
                    <ondown condition="!{has_sorts}">SetFocus({grid})</ondown>
                    <onright>noop</onright>
                    <scrolltime tween="cubic" easing="out">200</scrolltime>
                    <itemlayout width="{tab_w}" height="{tabs_h}">{tab}
                    </itemlayout>
                    <focusedlayout width="{tab_w}" height="{tabs_h}">{tab_focused}
                    </focusedlayout>
                </control>
                <control type="list" id="{sorts}">
                    <left>{tabs_x}</left><top>{sorts_y}</top>
                    <width>1560</width><height>{tabs_h}</height>
                    <visible>{has_sorts}</visible>
                    <orientation>horizontal</orientation>
                    <onleft>{nav}</onleft>
                    <onup>{tabs}</onup>
                    <ondown>{grid}</ondown>
                    <onright>noop</onright>
                    <scrolltime tween="cubic" easing="out">200</scrolltime>
                    <itemlayout width="{tab_w}" height="{tabs_h}">{sort}
                    </itemlayout>
                    <focusedlayout width="{tab_w}" height="{tabs_h}">{sort_focused}
                    </focusedlayout>
                </control>
            </control>'''.format(
        view=VIEW_CHANNEL, x=CONTENT_X, tx=CONTENT_X + 174, bg=BG,
        surface=SURFACE, text=TEXT, dim=TEXT_DIM, font_page=FONT_PAGE,
        font_meta=FONT_META, tabs=TABS_ID, nav=NAV_ID, grid=GRID_ID,
        tab=_text_tab(False), tab_focused=_text_tab(True), tab_w=TAB_W,
        sort=_tab(False, SORTS_ID), sort_focused=_tab(True, SORTS_ID),
        sorts=SORTS_ID, has_sorts=HAS_SORTS, sorts_y=184 - TAB_PAD + 72,
        divider_x=CONTENT_X + 174, divider_y=184 + 52 + 6,
        tabs_x=CONTENT_X + 174 - TAB_PAD, tabs_y=184 - TAB_PAD,
        tabs_h=52 + 2 * TAB_PAD)


# Underline widths the window picks from per tab title (leanback/gui.py
# estimates the text width; Kodi can't size an image to a label).
UNDERLINES = tuple(range(40, 201, 20))


def _text_tab(focused):
    """Channel tab as YouTube draws them, to tell them from the sort chips
    below: plain text, grey, the open tab white with a white underline.
    The tab under the remote's focus gets a white highlight, as on
    YouTube TV."""
    on = 'Control.HasFocus({})'.format(TABS_ID) if focused else 'false'
    selected = 'String.IsEqual(ListItem.Property(selected),true)'
    w, h, pad = TAB_W - 16, 52, TAB_PAD
    underlines = ''.join('''
                    <control type="image">
                        <left>{x}</left><top>{y}</top>
                        <width>{uw}</width><height>4</height>
                        <visible>{selected} + !{on} + String.IsEqual(ListItem.Property(ulw),{uw})</visible>
                        <texture border="2" colordiffuse="{text}">round8.png</texture>
                    </control>'''.format(x=pad + (w - uw) // 2, y=pad + h - 2, uw=uw,
                                     selected=selected, on=on, text=TEXT)
                         for uw in UNDERLINES)
    return '''
                    <control type="image">
                        <left>{pad}</left><top>{pad}</top>
                        <width>{w}</width><height>{h}</height>
                        <visible>{on}</visible>
                        <texture border="12" colordiffuse="{text}">round12.png</texture>
                    </control>{underlines}
                    <control type="label">
                        <left>{pad}</left><top>{pad}</top>
                        <width>{w}</width><height>{lh}</height>
                        <font>{font}</font>
                        <align>center</align><aligny>center</aligny>
                        <textcolor>{dark}</textcolor>
                        <visible>{on}</visible>
                        <label>$INFO[ListItem.Label]</label>
                    </control>
                    <control type="label">
                        <left>{pad}</left><top>{pad}</top>
                        <width>{w}</width><height>{lh}</height>
                        <font>{font}</font>
                        <align>center</align><aligny>center</aligny>
                        <textcolor>{text}</textcolor>
                        <visible>!{on} + {selected}</visible>
                        <label>$INFO[ListItem.Label]</label>
                    </control>
                    <control type="label">
                        <left>{pad}</left><top>{pad}</top>
                        <width>{w}</width><height>{lh}</height>
                        <font>{font}</font>
                        <align>center</align><aligny>center</aligny>
                        <textcolor>{dim}</textcolor>
                        <visible>!{on} + !{selected}</visible>
                        <label>$INFO[ListItem.Label]</label>
                    </control>'''.format(on=on, selected=selected, w=w, h=h, lh=h - 6,
                                     pad=pad, text=TEXT, dim=TEXT_DIM,
                                     dark=DARK_TEXT, font=FONT_TITLE,
                                     underlines=underlines)


def _tab(focused, list_id=TABS_ID):
    """Tab chip, as YouTube draws its chips: a rounded rectangle, the open
    tab light with dark text, the others dark grey with white text. The
    focused chip gets the same white ring as a focused video tile."""
    on = 'Control.HasFocus({})'.format(list_id) if focused else 'false'
    selected = 'String.IsEqual(ListItem.Property(selected),true)'
    w, h = TAB_W - 16, 52
    pad = TAB_PAD
    return '''
                    <control type="image">
                        <left>{pad}</left><top>{pad}</top>
                        <width>{w}</width><height>{h}</height>
                        <visible>{selected}</visible>
                        <texture border="12" colordiffuse="{light}">round12.png</texture>
                    </control>
                    <control type="image">
                        <left>{pad}</left><top>{pad}</top>
                        <width>{w}</width><height>{h}</height>
                        <visible>!{selected}</visible>
                        <texture border="12" colordiffuse="{surface}">round12.png</texture>
                    </control>
                    <control type="image">
                        <left>{ring}</left><top>{ring}</top>
                        <width>{rw}</width><height>{rh}</height>
                        <visible>{on}</visible>
                        <texture border="20" colordiffuse="FFFFFFFF">focus_ring.png</texture>
                    </control>
                    <control type="label">
                        <left>{pad}</left><top>{pad}</top>
                        <width>{w}</width><height>{h}</height>
                        <font>{font}</font>
                        <align>center</align><aligny>center</aligny>
                        <textcolor>{dark}</textcolor>
                        <visible>{selected}</visible>
                        <label>$INFO[ListItem.Label]</label>
                    </control>
                    <control type="label">
                        <left>{pad}</left><top>{pad}</top>
                        <width>{w}</width><height>{h}</height>
                        <font>{font}</font>
                        <align>center</align><aligny>center</aligny>
                        <textcolor>{text}</textcolor>
                        <visible>!{selected}</visible>
                        <label>$INFO[ListItem.Label]</label>
                    </control>'''.format(on=on, selected=selected, w=w, h=h,
                                     rw=w + 12, rh=h + 12, pad=pad, ring=pad - 6, light=TEXT,
                                     text=TEXT, surface=SURFACE,
                                     dark=DARK_TEXT, font=FONT_TITLE)


def search_view():
    """YouTube TV's search screen: the query in the bar, suggestions down
    the left, the keyboard grid with Space/Clear/Search, results below."""
    keys_x, keys_y = 704, 164
    actions_y = keys_y + 4 * KEY + 14
    results_top = 560
    return '''
        <control type="group">
            <visible>{view}</visible>
            <!-- Like YouTube TV: going down into the results scrolls the
                 keyboard away and brings the shelf up to the top. -->
            <animation effect="slide" end="0,{results_shift}" time="300" tween="cubic" easing="out" condition="Control.HasFocus({results})">Conditional</animation>
            <control type="image">
                <left>{x}</left><top>67</top>
                <width>70</width><height>70</height>
                <texture colordiffuse="{surface}">circle.png</texture>
            </control>
            <control type="image">
                <left>{mic_x}</left><top>86</top>
                <width>32</width><height>32</height>
                <aspectratio>keep</aspectratio>
                <texture>icon_mic.png</texture>
            </control>
            <control type="image">
                <left>{bar_x}</left><top>67</top>
                <width>1030</width><height>70</height>
                <texture border="35" colordiffuse="{surface}">pill.png</texture>
            </control>
            <control type="label">
                <left>{bar_tx}</left><top>67</top>
                <width>980</width><height>70</height>
                <font>{font_nav}</font><aligny>center</aligny>
                <textcolor>{text}</textcolor>
                <visible>!String.IsEmpty(Window.Property(search.query))</visible>
                <label>$INFO[Window.Property(search.query)][COLOR {accent}]|[/COLOR]</label>
            </control>
            <control type="label">
                <left>{bar_tx}</left><top>67</top>
                <width>980</width><height>70</height>
                <font>{font_nav}</font><aligny>center</aligny>
                <textcolor>{dim}</textcolor>
                <visible>String.IsEmpty(Window.Property(search.query))</visible>
                <label>$ADDON[{addon} 39107]</label>
            </control>
            <control type="image">
                <left>1430</left><top>67</top>
                <width>400</width><height>70</height>
                <aspectratio align="right">keep</aspectratio>
                <texture>$INFO[Window.Property(logo),brand_lockup_,.png]</texture>
            </control>

            <control type="list" id="{suggest}">
                <left>{x}</left><top>166</top>
                <width>500</width><height>340</height>
                <orientation>vertical</orientation>
                <onleft>{nav}</onleft>
                <onright>{keys}</onright>
                <ondown>{results}</ondown>
                <onup>noop</onup>
                <scrolltime>150</scrolltime>
                <itemlayout width="500" height="68">{chip}
                </itemlayout>
                <focusedlayout width="500" height="68">{chip_focused}
                </focusedlayout>
            </control>

            <control type="panel" id="{keys}">
                <left>{keys_x}</left><top>{keys_y}</top>
                <width>{keys_w}</width><height>{keys_h}</height>
                <orientation>vertical</orientation>
                <onleft>{suggest}</onleft>
                <ondown>{actions}</ondown>
                <onup>noop</onup>
                <onright>noop</onright>
                <scrolltime>0</scrolltime>
                <itemlayout width="{k}" height="{k}">{key}
                </itemlayout>
                <focusedlayout width="{k}" height="{k}">{key_focused}
                </focusedlayout>
            </control>
            <control type="list" id="{actions}">
                <left>{keys_x}</left><top>{actions_y}</top>
                <width>{keys_w}</width><height>60</height>
                <orientation>horizontal</orientation>
                <onup>{keys}</onup>
                <ondown>{results}</ondown>
                <onleft>{suggest}</onleft>
                <onright>noop</onright>
                <scrolltime>0</scrolltime>
                <itemlayout width="148" height="60">{action}
                </itemlayout>
                <focusedlayout width="148" height="60">{action_focused}
                </focusedlayout>
            </control>

            <control type="label">
                <left>{x}</left><top>{results_top}</top>
                <width>1600</width><height>40</height>
                <font>{font_shelf}</font>
                <textcolor>{text}</textcolor>
                <label>$INFO[Window.Property(search.title)]</label>
            </control>
            <control type="group">
                <left>0</left><top>{results_top}</top>
                <visible>String.IsEqual(Window.Property(search.loading),true)</visible>{loading}
            </control>
            <control type="list" id="{results}">
                <left>{lx}</left><top>{results_list_y}</top>
                <width>{lw}</width><height>{rh}</height>
                <orientation>horizontal</orientation>
                <onleft>{nav}</onleft>
                <onup>{actions}</onup>
                <onright>noop</onright>
                <ondown>noop</ondown>
                <scrolltime tween="cubic" easing="out">250</scrolltime>
                <focusposition>0</focusposition>
                <movement>1</movement>{tiles}
            </control>
        </control>'''.format(
        view=VIEW_SEARCH, x=CONTENT_X, mic_x=CONTENT_X + 19,
        bar_x=CONTENT_X + 94, bar_tx=CONTENT_X + 94 + 36,
        surface=SURFACE, text=TEXT, dim=TEXT_DIM, accent=ACCENT, addon=ADDON,
        font_nav=FONT_NAV, font_shelf=FONT_SHELF, nav=NAV_ID,
        suggest=SUGGEST_ID, keys=KEYS_ID, actions=KEY_ACTIONS_ID,
        results=RESULTS_ID, keys_x=keys_x, keys_y=keys_y, keys_w=8 * KEY,
        keys_h=4 * KEY, actions_y=actions_y, k=KEY,
        key=_key(False), key_focused=_key(True),
        chip=_pill_item(480, 68, SUGGEST_ID, False, icon=True),
        chip_focused=_pill_item(480, 68, SUGGEST_ID, True, icon=True),
        action=_pill_item(136, 60, KEY_ACTIONS_ID, False),
        action_focused=_pill_item(136, 60, KEY_ACTIONS_ID, True),
        results_top=results_top, results_list_y=results_top + 48,
        results_shift=FOCUS_TOP - results_top,
        loading=placeholders(REGULAR, 48), lx=CONTENT_X - PAD,
        lw=1920 - CONTENT_X + PAD, rh=text_height(REGULAR),
        tiles=layouts(REGULAR, RESULTS_ID))


def nav_item(focused):
    """Rail entry: an icon when collapsed, a white pill with label when the
    rail is focused. The current section's icon stays bright."""
    current = 'String.IsEqual(ListItem.Property(nav),Window.Property(section))'
    pill = '''
                <control type="image">
                    <left>30</left><top>7</top>
                    <width>360</width><height>64</height>
                    <visible>Control.HasFocus({nav})</visible>
                    <texture border="32" colordiffuse="{text}">pill.png</texture>
                </control>'''.format(nav=NAV_ID, text=TEXT) if focused else ''
    # Kodi also uses the focused layout for the rail's selected item while the
    # rail is collapsed, so the dark-on-white icon only applies with focus.
    on_pill = 'Control.HasFocus({})'.format(NAV_ID) if focused else 'false'
    icon = '''
                <control type="image">
                    <left>54</left><top>23</top>
                    <width>32</width><height>32</height>
                    <aspectratio>keep</aspectratio>
                    <visible>{visible}</visible>
                    <texture colordiffuse="{color}">$INFO[ListItem.Icon]</texture>
                </control>'''
    icons = ''.join(icon.format(visible=visible, color=color) for visible, color in (
        (on_pill, DARK_TEXT),
        ('!{p} + [{c} | Control.HasFocus({n})]'.format(p=on_pill, c=current,
                                                      n=NAV_ID), TEXT),
        ('!{p} + !{c} + !Control.HasFocus({n})'.format(p=on_pill, c=current,
                                                      n=NAV_ID), TEXT_DIM),
    ))
    return '''{pill}{icons}
                <control type="label">
                    <left>112</left><top>7</top>
                    <width>270</width><height>64</height>
                    <font>{font_nav}</font><aligny>center</aligny>
                    <textcolor>{label}</textcolor>
                    <visible>Control.HasFocus({nav})</visible>
                    <label>$INFO[ListItem.Label]</label>
                </control>'''.format(
        pill=pill, icons=icons, nav=NAV_ID, font_nav=FONT_NAV,
        label=DARK_TEXT if focused else TEXT)


def build():
    rows = ''.join(row(i) for i in range(1, ROW_COUNT + 1))
    return '''<?xml version="1.0" encoding="UTF-8"?>
<!-- Generated by tools/gen_skin.py - edit that file instead. -->
<window>
    <defaultcontrol always="true">{nav}</defaultcontrol>
    <animation effect="fade" time="250">WindowOpen</animation>
    <animation effect="fade" time="200">WindowClose</animation>
    <controls>
        <control type="image">
            <left>0</left><top>0</top><width>1920</width><height>1080</height>
            <texture colordiffuse="{bg}">white.png</texture>
        </control>

        <!-- Rows view (Home, Library): header plus shelves, scrolled so the
             focused shelf sits at the top -->
        <control type="group" id="{rows_id}">
            <defaultcontrol>{first}</defaultcontrol>
            <visible>{view_rows}</visible>{scroll}{header}{rows_xml}
        </control>

        <!-- Search view -->{search_view}

        <!-- Grid view (search, channel, playlist, related). Filled by the
             window like the shelves, more pages appended as you scroll. -->
        <control type="group">
            <visible>{view_grid} | {view_channel}</visible>{channel_header}
            <control type="label">
                <left>{x}</left><top>60</top><width>1500</width><height>60</height>
                <font>{font_page}</font>
                <textcolor>{text}</textcolor>
                <visible>{view_grid}</visible>
                <label>$INFO[Window.Property(grid.title)]</label>
            </control>
            <control type="label">
                <left>{x}</left><top>400</top><width>1600</width><height>60</height>
                <font>{font_nav}</font><align>center</align>
                <textcolor>{dim}</textcolor>
                <visible>String.IsEqual(Window.Property(grid.loading),true) + Integer.IsEqual(Container({grid_id}).NumItems,0)</visible>
                <label>$ADDON[{addon} 39127]</label>
            </control>
            <control type="label">
                <left>{x}</left><top>400</top><width>1600</width><height>60</height>
                <font>{font_nav}</font><align>center</align>
                <textcolor>{dim}</textcolor>
                <visible>!String.IsEqual(Window.Property(grid.loading),true) + Integer.IsEqual(Container({grid_id}).NumItems,0)</visible>
                <label>$ADDON[{addon} 39118]</label>
            </control>
            <control type="panel" id="{grid_id}">
                <left>{gx}</left><top>150</top><width>{gw}</width><height>930</height>
                <!-- Under a channel header the grid starts lower. -->
                <animation effect="slide" end="0,{channel_shift}" time="0" condition="{view_channel}">Conditional</animation>
                <animation effect="slide" end="0,{sorts_shift}" time="0" condition="{view_channel} + {has_sorts}">Conditional</animation>
                <orientation>vertical</orientation>
                <onleft>{nav}</onleft>
                <onup condition="{view_channel} + {has_sorts}">SetFocus({sorts_id})</onup>
                <onup condition="{view_channel} + !{has_sorts}">SetFocus({tabs_id})</onup>
                <onup condition="!{view_channel}">noop</onup>
                <ondown>noop</ondown>
                <onright>noop</onright>
                <scrolltime tween="cubic" easing="out">250</scrolltime>{grid_tiles}
            </control>
        </control>

        <!-- Left rail: icons, expanding to labels while focused -->
        <control type="image">
            <left>0</left><top>0</top><width>{rail_w}</width><height>1080</height>
            <texture colordiffuse="{bg}">white.png</texture>
        </control>
        <control type="group">
            <visible>Control.HasFocus({nav})</visible>
            <animation effect="fade" time="150">VisibleChange</animation>
            <control type="image">
                <left>0</left><top>0</top><width>440</width><height>1080</height>
                <texture colordiffuse="F20F0F0F">white.png</texture>
            </control>
            <control type="image">
                <left>440</left><top>0</top><width>300</width><height>1080</height>
                <texture colordiffuse="F20F0F0F">grad_left.png</texture>
            </control>
        </control>
        <control type="image">
            <left>46</left><top>77</top>
            <width>48</width><height>48</height>
            <texture colordiffuse="FF3D3D3D">circle.png</texture>
        </control>
        <control type="image">
            <left>58</left><top>89</top>
            <width>24</width><height>24</height>
            <aspectratio>keep</aspectratio>
            <texture>icon_account.png</texture>
        </control>
        <control type="list" id="{nav}">
            <left>0</left><top>191</top><width>420</width><height>860</height>
            <orientation>vertical</orientation>
            <onup>noop</onup>
            <ondown>noop</ondown>
            <onright condition="{view_grid} | {view_channel}">SetFocus({grid_id})</onright>
            <onright condition="{view_search}">SetFocus({keys_id})</onright>
            <onright condition="!{view_grid} + !{view_channel} + !{view_search}">SetFocus({rows_id})</onright>
            <scrolltime>0</scrolltime>
            <itemlayout width="420" height="78">{nav_item}
            </itemlayout>
            <focusedlayout width="420" height="78">{nav_focused}
            </focusedlayout>
        </control>
    </controls>
</window>
'''.format(nav=NAV_ID, rows_id=ROWS_GROUP_ID, first=ROWS_GROUP_ID + 1,
           grid_id=GRID_ID, bg=BG, text=TEXT, dim=TEXT_DIM, addon=ADDON,
           view_rows=VIEW_ROWS, view_grid=VIEW_GRID, scroll=scroll_animations(),
           header=header(), rows_xml=rows, x=CONTENT_X,
           gx=CONTENT_X - PAD, gw=1920 - CONTENT_X + PAD,
           font_page=FONT_PAGE, font_nav=FONT_NAV, rail_w=RAIL_W,
           grid_tiles=layouts(GRID, GRID_ID),
           view_search=VIEW_SEARCH, keys_id=KEYS_ID,
           view_channel=VIEW_CHANNEL, channel_header=channel_header(),
           channel_shift=CHANNEL_SHIFT, tabs_id=TABS_ID,
           sorts_shift=SORTS_SHIFT, sorts_id=SORTS_ID, has_sorts=HAS_SORTS,
           search_view=search_view(),
           nav_item=nav_item(False), nav_focused=nav_item(True))


def main():
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(build(), encoding='utf-8', newline='\n')
    print('Wrote', OUT.relative_to(ROOT))


if __name__ == '__main__':
    main()
