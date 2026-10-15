#!/usr/bin/env python3
"""Generate the leanback window XML.

Kodi script skins can't use <include> from the user's skin, so the repeated
row/tile markup is templated here instead. Edit this file, then run:

    python tools/gen_skin.py
"""

from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = (ROOT / 'resources' / 'skins' / 'Default' / '1080i'
       / 'script-youtube-leanback-main.xml')

ROW_COUNT = 8
NAV_ID = 9000
ROWS_GROUP_ID = 100
GRID_ID = 200

BG = 'FF0F0F0F'
TEXT = 'FFF1F1F1'
TEXT_DIM = 'FFAAAAAA'
ACCENT = 'FFFF0033'
ADDON = 'script.youtube.leanback'

VIEW_ROWS = 'String.IsEqual(Window.Property(view),rows)'
VIEW_GRID = 'String.IsEqual(Window.Property(view),grid)'


def tile(width, focused):
    """One video tile: 16:9 thumbnail, duration badge, title, channel line."""
    thumb_w = width - 20
    thumb_h = thumb_w * 9 // 16
    title_color = TEXT if focused else TEXT_DIM
    border = '''
                    <control type="image">
                        <left>4</left><top>-6</top>
                        <width>{bw}</width><height>{bh}</height>
                        <texture border="5">border.png</texture>
                    </control>'''.format(bw=thumb_w + 12, bh=thumb_h + 12) if focused else ''
    return '''
                    <control type="image">
                        <left>10</left><top>0</top>
                        <width>{tw}</width><height>{th}</height>
                        <texture colordiffuse="FF272727">white.png</texture>
                    </control>
                    <control type="image">
                        <left>10</left><top>0</top>
                        <width>{tw}</width><height>{th}</height>
                        <aspectratio>scale</aspectratio>
                        <fadetime>150</fadetime>
                        <texture background="true">$INFO[ListItem.Art(thumb)]</texture>
                    </control>
                    <control type="group">
                        <visible>!String.IsEmpty(ListItem.Duration)</visible>
                        <control type="image">
                            <left>{bx}</left><top>{by}</top>
                            <width>96</width><height>34</height>
                            <texture colordiffuse="CC000000">pill.png</texture>
                        </control>
                        <control type="label">
                            <left>{bx}</left><top>{by}</top>
                            <width>96</width><height>34</height>
                            <font>font12</font>
                            <align>center</align><aligny>center</aligny>
                            <textcolor>FFFFFFFF</textcolor>
                            <label>$INFO[ListItem.Duration]</label>
                        </control>
                    </control>
                    <control type="image">
                        <left>10</left><top>{wy}</top>
                        <width>{tw}</width><height>6</height>
                        <visible>ListItem.IsResumable</visible>
                        <texture colordiffuse="{accent}">white.png</texture>
                    </control>{border}
                    <control type="label">
                        <left>14</left><top>{ly}</top>
                        <width>{lw}</width><height>34</height>
                        <font>font13</font>
                        <textcolor>{title_color}</textcolor>
                        <scroll>{scroll}</scroll>
                        <label>$INFO[ListItem.Label]</label>
                    </control>
                    <control type="label">
                        <left>14</left><top>{cy}</top>
                        <width>{lw}</width><height>30</height>
                        <font>font12</font>
                        <textcolor>{dim}</textcolor>
                        <label>$INFO[ListItem.Artist]$INFO[ListItem.Property(PublishedSince), • ]</label>
                    </control>'''.format(
        tw=thumb_w, th=thumb_h, bx=10 + thumb_w - 106, by=thumb_h - 44,
        wy=thumb_h - 6, accent=ACCENT, border=border, ly=thumb_h + 10,
        cy=thumb_h + 44, lw=thumb_w - 8, title_color=title_color,
        scroll='true' if focused else 'false', dim=TEXT_DIM)


def row(index):
    list_id = ROWS_GROUP_ID + index
    prop = 'row{}'.format(index)
    return '''
            <control type="group">
                <height>380</height>
                <visible>!String.IsEmpty(Window.Property({prop}.path)) + [Container({lid}).IsUpdating | Integer.IsGreater(Container({lid}).NumItems,0)]</visible>
                <control type="label">
                    <left>14</left><top>0</top>
                    <width>1200</width><height>44</height>
                    <font>font27</font>
                    <textcolor>{text}</textcolor>
                    <label>$INFO[Window.Property({prop}.label)]</label>
                </control>
                <control type="label">
                    <left>1300</left><top>0</top>
                    <width>400</width><height>44</height>
                    <font>font12</font><align>right</align>
                    <textcolor>{dim}</textcolor>
                    <visible>Container({lid}).IsUpdating</visible>
                    <label>$LOCALIZE[31042]...</label>
                </control>
                <control type="list" id="{lid}">
                    <left>0</left><top>56</top>
                    <width>1770</width><height>324</height>
                    <orientation>horizontal</orientation>
                    <onleft>{nav}</onleft>
                    <scrolltime tween="cubic" easing="out">250</scrolltime>
                    <focusposition>0</focusposition>
                    <movement>1</movement>
                    <content target="videos">$INFO[Window.Property({prop}.path)]</content>
                    <itemlayout width="430" height="324">{item}
                    </itemlayout>
                    <focusedlayout width="430" height="324">{focused}
                    </focusedlayout>
                </control>
            </control>'''.format(prop=prop, lid=list_id, text=TEXT, dim=TEXT_DIM,
                                 nav=NAV_ID, item=tile(430, False),
                                 focused=tile(430, True))


def nav_item(focused):
    pill = '''
                <control type="image">
                    <left>14</left><top>10</top>
                    <width>332</width><height>68</height>
                    <visible>Control.HasFocus({nav})</visible>
                    <texture border="16" colordiffuse="FF3D3D3D">pill.png</texture>
                </control>
                <control type="image">
                    <left>14</left><top>10</top>
                    <width>68</width><height>68</height>
                    <visible>!Control.HasFocus({nav})</visible>
                    <texture border="16" colordiffuse="33FFFFFF">pill.png</texture>
                </control>'''.format(nav=NAV_ID) if focused else ''
    return '''{pill}
                <control type="image">
                    <left>28</left><top>24</top>
                    <width>40</width><height>40</height>
                    <aspectratio>keep</aspectratio>
                    <texture>$INFO[ListItem.Icon]</texture>
                </control>
                <control type="label">
                    <left>100</left><top>10</top>
                    <width>236</width><height>68</height>
                    <font>font13</font><aligny>center</aligny>
                    <textcolor>{color}</textcolor>
                    <visible>Control.HasFocus({nav})</visible>
                    <label>$INFO[ListItem.Label]</label>
                </control>'''.format(
        pill=pill, nav=NAV_ID, color=TEXT if focused else TEXT_DIM)


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

        <!-- Hero: details of the focused video, YouTube TV style -->
        <control type="group">
            <visible>{rows} + !Control.HasFocus({nav}) + !String.IsEmpty(ListItem.Label)</visible>
            <animation effect="fade" time="200">VisibleChange</animation>
            <control type="image">
                <left>720</left><top>0</top><width>1200</width><height>675</height>
                <aspectratio>scale</aspectratio>
                <fadetime>250</fadetime>
                <texture background="true">$INFO[ListItem.Art(thumb)]</texture>
            </control>
            <control type="image">
                <left>720</left><top>0</top><width>760</width><height>675</height>
                <texture colordiffuse="{bg}">grad_left.png</texture>
            </control>
            <control type="image">
                <left>720</left><top>335</top><width>1200</width><height>340</height>
                <texture colordiffuse="{bg}">grad_bottom.png</texture>
            </control>
            <control type="textbox">
                <left>150</left><top>120</top><width>900</width><height>130</height>
                <font>font37</font>
                <textcolor>{text}</textcolor>
                <label>$INFO[ListItem.Label]</label>
            </control>
            <control type="label">
                <left>150</left><top>262</top><width>900</width><height>40</height>
                <font>font13</font>
                <textcolor>{dim}</textcolor>
                <label>$INFO[ListItem.Artist]$INFO[ListItem.Property(PublishedSince), • ]$INFO[ListItem.Duration, • ]</label>
            </control>
            <control type="textbox">
                <left>150</left><top>314</top><width>800</width><height>132</height>
                <font>font12</font>
                <textcolor>{dim}</textcolor>
                <label>$INFO[ListItem.Plot]</label>
            </control>
        </control>

        <!-- Brand mark -->
        <control type="label">
            <left>150</left><top>36</top><width>400</width><height>50</height>
            <font>font27</font>
            <textcolor>{text}</textcolor>
            <label>[COLOR {accent}]▶[/COLOR] [B]YouTube[/B]</label>
        </control>

        <!-- Rows view (Home, Library) -->
        <control type="grouplist" id="{rows_id}">
            <left>150</left><top>470</top><width>1770</width><height>610</height>
            <orientation>vertical</orientation>
            <itemgap>0</itemgap>
            <scrolltime tween="cubic" easing="out">300</scrolltime>
            <onleft>{nav}</onleft>
            <visible>{rows}</visible>{rows_xml}
        </control>

        <!-- Grid view (search, channel, playlist, subscriptions) -->
        <control type="group">
            <visible>{grid}</visible>
            <control type="label">
                <left>164</left><top>100</top><width>1500</width><height>60</height>
                <font>font37</font>
                <textcolor>{text}</textcolor>
                <label>$INFO[Window.Property(grid.title)]</label>
            </control>
            <control type="label">
                <left>164</left><top>400</top><width>1600</width><height>60</height>
                <font>font27</font><align>center</align>
                <textcolor>{dim}</textcolor>
                <visible>Container({grid_id}).IsUpdating</visible>
                <label>$LOCALIZE[31042]...</label>
            </control>
            <control type="label">
                <left>164</left><top>400</top><width>1600</width><height>60</height>
                <font>font27</font><align>center</align>
                <textcolor>{dim}</textcolor>
                <visible>!Container({grid_id}).IsUpdating + Integer.IsEqual(Container({grid_id}).NumItems,0)</visible>
                <label>$ADDON[{addon} 39118]</label>
            </control>
            <control type="panel" id="{grid_id}">
                <left>150</left><top>190</top><width>1770</width><height>890</height>
                <orientation>vertical</orientation>
                <onleft>{nav}</onleft>
                <scrolltime tween="cubic" easing="out">250</scrolltime>
                <content target="videos">$INFO[Window.Property(grid.path)]</content>
                <itemlayout width="430" height="350">{grid_item}
                </itemlayout>
                <focusedlayout width="430" height="350">{grid_focused}
                </focusedlayout>
            </control>
        </control>

        <!-- Left navigation rail, expands while focused -->
        <control type="image">
            <left>0</left><top>0</top><width>120</width><height>1080</height>
            <texture colordiffuse="{bg}">white.png</texture>
        </control>
        <control type="group">
            <visible>Control.HasFocus({nav})</visible>
            <animation effect="slide" start="-260,0" end="0,0" time="200" tween="cubic" easing="out">Visible</animation>
            <animation effect="slide" start="0,0" end="-260,0" time="150">Hidden</animation>
            <control type="image">
                <left>0</left><top>0</top><width>380</width><height>1080</height>
                <texture colordiffuse="F2161616">white.png</texture>
            </control>
            <control type="image">
                <left>380</left><top>0</top><width>200</width><height>1080</height>
                <texture colordiffuse="99000000">grad_left.png</texture>
            </control>
        </control>
        <control type="list" id="{nav}">
            <left>10</left><top>300</top><width>360</width><height>560</height>
            <orientation>vertical</orientation>
            <onright condition="{grid}">SetFocus({grid_id})</onright>
            <onright condition="!{grid}">SetFocus({rows_id})</onright>
            <scrolltime>0</scrolltime>
            <itemlayout width="360" height="88">{nav_item}
            </itemlayout>
            <focusedlayout width="360" height="88">{nav_focused}
            </focusedlayout>
        </control>
    </controls>
</window>
'''.format(nav=NAV_ID, rows_id=ROWS_GROUP_ID, grid_id=GRID_ID, bg=BG,
           text=TEXT, dim=TEXT_DIM, accent=ACCENT, addon=ADDON,
           rows=VIEW_ROWS, grid=VIEW_GRID, rows_xml=rows,
           grid_item=tile(430, False), grid_focused=tile(430, True),
           nav_item=nav_item(False), nav_focused=nav_item(True))


def main():
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(build(), encoding='utf-8', newline='\n')
    print('Wrote', OUT.relative_to(ROOT))


if __name__ == '__main__':
    main()
