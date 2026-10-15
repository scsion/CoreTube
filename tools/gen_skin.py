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
    """Slide the page so the focused shelf sits near the top edge."""
    return ''.join('''
            <animation effect="slide" end="0,{dy}" time="300" tween="cubic" easing="out" condition="String.IsEqual(Window.Property(focusrow),{i})">Conditional</animation>'''
                   .format(i=i, dy=FOCUS_TOP - row_top(i))
                   for i in range(2, ROW_COUNT + 1))


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
                <left>1567</left><top>74</top>
                <width>197</width><height>56</height>
                <aspectratio>keep</aspectratio>
                <texture>brand_lockup.png</texture>
            </control>'''.format(x=CONTENT_X, mic_x=CONTENT_X + 19,
                                 pill_x=CONTENT_X + 94, surface=SURFACE,
                                 addon=ADDON, search=SEARCH_ID,
                                 font_nav=FONT_NAV, dim=TEXT_DIM,
                                 dark=DARK_TEXT, text=TEXT, nav=NAV_ID,
                                 first=ROWS_GROUP_ID + 1,
                                 font_page=FONT_PAGE)


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

        <!-- Grid view (search, channel, playlist, related) -->
        <control type="group">
            <visible>{view_grid}</visible>
            <control type="label">
                <left>{x}</left><top>60</top><width>1500</width><height>60</height>
                <font>{font_page}</font>
                <textcolor>{text}</textcolor>
                <label>$INFO[Window.Property(grid.title)]</label>
            </control>
            <control type="label">
                <left>{x}</left><top>400</top><width>1600</width><height>60</height>
                <font>{font_nav}</font><align>center</align>
                <textcolor>{dim}</textcolor>
                <visible>Container({grid_id}).IsUpdating</visible>
                <label>$LOCALIZE[31042]...</label>
            </control>
            <control type="label">
                <left>{x}</left><top>400</top><width>1600</width><height>60</height>
                <font>{font_nav}</font><align>center</align>
                <textcolor>{dim}</textcolor>
                <visible>!Container({grid_id}).IsUpdating + Integer.IsEqual(Container({grid_id}).NumItems,0)</visible>
                <label>$ADDON[{addon} 39118]</label>
            </control>
            <control type="panel" id="{grid_id}">
                <left>{gx}</left><top>150</top><width>{gw}</width><height>930</height>
                <orientation>vertical</orientation>
                <onleft>{nav}</onleft>
                <scrolltime tween="cubic" easing="out">250</scrolltime>
                <content target="videos">$INFO[Window.Property(grid.path)]</content>{grid_tiles}
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
            <onright condition="{view_grid}">SetFocus({grid_id})</onright>
            <onright condition="!{view_grid}">SetFocus({rows_id})</onright>
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
           nav_item=nav_item(False), nav_focused=nav_item(True))


def main():
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(build(), encoding='utf-8', newline='\n')
    print('Wrote', OUT.relative_to(ROOT))


if __name__ == '__main__':
    main()
