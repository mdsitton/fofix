#####################################################################
# -*- coding: iso-8859-1 -*-                                        #
#                                                                   #
# Frets on Fire X (FoFiX)                                           #
# Copyright (C) 2006 Sami Kyöstilä                                  #
#               2008 myfingershurt                                  #
#               2008 Blazingamer                                    #
#               2008 evilynux <evilynux@gmail.com>                  #
#                                                                   #
# This program is free software; you can redistribute it and/or     #
# modify it under the terms of the GNU General Public License       #
# as published by the Free Software Foundation; either version 2    #
# of the License, or (at your option) any later version.            #
#                                                                   #
# This program is distributed in the hope that it will be useful,   #
# but WITHOUT ANY WARRANTY; without even the implied warranty of    #
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the     #
# GNU General Public License for more details.                      #
#                                                                   #
# You should have received a copy of the GNU General Public License #
# along with this program; if not, write to the Free Software       #
# Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston,        #
# MA  02110-1301, USA.                                              #
#####################################################################

import os
import sys
import imp
import math

from OpenGL.GL import *
from OpenGL.GLU import *

from fofix.core import Log
from fofix.core import Version
from fofix.core import Config
from fofix.game import Song
from fofix.core.Language import _
from fofix.core.Image import drawImage
from fofix.core.Task import Task
from fofix.core.constants import *
from fofix.core.utils import hexToColor, isTrue

#Theme Constants.
GUITARTYPES = [0, 1, 4]
DRUMTYPES   = [2, 3]
MICTYPES    = [5]

defaultDict = {}
classNames = {'partDiff': lambda x: ThemeParts(x)}

def halign(value, default='center'):
    try:
        return {'left':   LEFT,
                'center': CENTER,
                'right':  RIGHT}[value.lower()]
    except KeyError:
        Log.warn('Invalid horizontal alignment value - defaulting to %s' % default)
        return halign(default)

def valign(value, default='middle'):
    try:
        if value.lower() == 'center':
            Log.notice('Use of "center" for vertical alignment is deprecated. Use "middle" instead.')
        return {'top':    TOP,
                'middle': MIDDLE,  # for consistency with HTML/CSS terminology
                'center': MIDDLE,  # for temporary backward compatibility
                'bottom': BOTTOM}[value.lower()]
    except KeyError:
        Log.warn('Invalid vertical alignment value - defaulting to %s' % default)
        return valign(default)

class Theme(Task):

    def __getattr__(self, attr):
        try: #getting to this function is kinda slow. Set it on the first get to keep renders from lagging.
            object.__getattribute__(self, '__dict__')[attr] = defaultDict[attr]
            Log.debug("No theme variable for %s - Loading default..." % attr)
            return object.__getattribute__(self, attr)
        except KeyError:
            if attr in classNames.keys():
                Log.warn("No theme class for %s - Loading default..." % attr)
                object.__getattribute__(self, '__dict__')[attr] = classNames[attr](self)
                return object.__getattribute__(self, attr)
            elif attr.startswith('__') and attr.endswith('__'): #for object's attributes (eg: __hash__, __eq__)
                return object.__getattribute__(self, attr)
            Log.error("Attempted to load theme variable %s - no default found." % attr)

    def __init__(self, path, name):
        self.name = name
        self.path = path

        self.themePath = os.path.join(Version.dataPath(),"themes", name)
        if not os.path.exists(self.themePath):
            Log.warn("Theme: %s does not exist!\n" % self.themePath)
            name = Config.get("coffee", "themename")
            Log.notice("Theme: Attempting fallback to default theme \"%s\"." % name)
            self.themePath = os.path.join(Version.dataPath(),"themes", name)
            if not os.path.exists(self.themePath):
                Log.error("Theme: %s does not exist!\nExiting.\n" % self.themePath)
                sys.exit(1)

        if os.path.exists(os.path.join(self.themePath, "theme.ini")):
            self.config = Config.MyConfigParser()
            self.config.read(os.path.join(self.themePath, "theme.ini"))
            Log.debug("theme.ini loaded")
        else:
            self.config = None
            Log.debug("no theme.ini")

        def get(value, type = str, default = None):
            if self.config:
                if self.config.has_option("theme", value):
                    if type == bool:
                        return isTrue(self.config.get("theme", value).lower())
                    elif type == "color":
                        try:
                            value = hexToColor(self.config.get("theme", value))
                        except ValueError:
                            value = self.config.get("theme", value)

                        return value
                    else:
                        return type(self.config.get("theme", value))
            if type == "color":
                try:
                    value = hexToColor(default)
                except ValueError:
                    value = default
                return value
            return default

        #These colors are very important
        #background_color defines what color openGL will clear too
        # (the color that shows then no image is present)
        #base_color is the default color of text in menus
        #selected_color is the color of text when it is selected
        # (like in the settings menu or when selecting a song)
        self.backgroundColor = get("background_color", "color", "#000000")
        self.baseColor       = get("base_color",       "color", "#FFFFFF")
        self.selectedColor   = get("selected_color",   "color", "#FFBF00")

        #notes that are not textured are drawn in 3 parts (Mesh, Mesh_001, Mesh_002, and occasionally Mesh_003)
        #The color of mesh is set by mesh_color (on a GH note this is the black ring)
        #The color of the Mesh_001 is the color of the note (green, red, yellow, etc)
        #Mesh_002 is set by the hopo_color but if Mesh_003 is present it will be colored spot_color
        #When Mesh_003 is present it will be colored hopo_color
        self.meshColor   = get("mesh_color",   "color", "#000000")
        self.hopoColor   = get("hopo_color",   "color", "#00AAAA")
        self.spotColor   = get("spot_color",   "color", "#FFFFFF")

        #keys when they are not textured are made of three parts (Mesh, Key_001, Key_002),
        #two of which can be colored by the CustomTheme.py or the Theme.ini (Mesh, Mesh_002).
        #These will only work if the object has a Glow_001 mesh in it, else it will render
        #the whole object the color of the fret
        #Key_001 is colored by key_color, Key_002 is colored by key2_color, pretty obvious, eh?
        self.keyColor    = get("key_color",    "color", "#333333")
        self.key2Color   = get("key2_color",   "color", "#000000")

        #when a note is hit a glow will show aside from the hitflames, this has been around
        #since the original Frets on Fire.  What glow_color allows you to do is set it so
        #the glow is either the color of the fret it's over or it can be the color the image
        #actually is (if the image is white then no matter what key is hit the glow will be white)

        self.hitGlowColor   = get("hit_glow_color", str, "frets")
        if not self.hitGlowColor == "frets":
            self.hitGlowColor = hexToColor(self.hitGlowColor)

        #Sets the color of the glow.png
        self.glowColor   = get("glow_color",       str,    "frets")
        if not self.glowColor == "frets":
            self.glowColor = hexToColor(self.glowColor)

        #Acts similar to the glowColor but its does so for flames instead
        self.flamesColor   = get("flames_color",       str,    "frets")
        if not self.flamesColor == "frets":
            self.flamesColor = hexToColor(self.flamesColor)

        #Note Colors (this applies to frets and notes)
        #default is green, red, yellow, blue, orange, purple (I don't know why there's a 6th color)
        default_color = ["#22FF22", "#FF2222", "#FFFF22", "#3333FF", "#FF9933", "#CC22CC"]
        self.noteColors  = [get("fret%d_color" % i, "color", default_color[i]) for i in range(6)]
        self.spNoteColor =  get("fretS_color",      "color", "#4CB2E5")

        #Color of the tails when whammied, default is set to the colors of the frets
        self.killNoteColor  = get("fretK_color",       str,    "frets")
        if not self.killNoteColor == "frets":
            self.killNoteColor = hexToColor(self.killNoteColor)

        #just like glow_color, this allows you to have tails use either the color of the note
        #or the actual color of the tail
        self.use_fret_colors =  get("use_fret_colors", bool, False)

        #themes can define how many frames their hitflames will be.
        # Separate variables for hit and hold animation frame counts.
        self.HitFlameFrameLimit    = get("hit_flame_frame_limit",  int, 13)
        self.HoldFlameFrameLimit   = get("hold_flame_frame_limit", int, 16)

        #Lets themers turn alpha = True to alpha = False making black not removed from the flames or glows.
        self.hitFlameBlackRemove   = get("hit_flame_black_remove", bool, True)
        self.hitGlowsBlackRemove   = get("hit_Glows_black_remove", bool, True)

        #Rotation in degrees for the hitFlames and hitGlows x y and z axix
        self.hitFlameRotation     = (get("flame_rotation_base", float, 90), get("flame_rotation_x", float, 1), get("flame_rotation_y", float, 0), get("flame_rotation_z", float, 0))
        self.hitGlowsRotation     = (get("hit_glow_rotation_base", float, 90), get("hit_glow_rotation_x", float, .5), get("hit_glow_rotation_y", float, 0), get("hit_glow_rotation_z", float, 0))

        #The rotation offset will offset each flame/glow so that if the themer chooses so
        #they can align them with the frets individually
        self.hitGlowOffset     = (get("hit_glow_offset_0", float, 0), get("hit_glow_offset_1", float, 0), get("hit_glow_offset_2", float, 0), get("hit_glow_offset_3", float, 0), get("hit_glow_offset_4", float, 0))
        self.hitFlameOffset     = (get("flame_offset_0", float, 0), get("flame_offset_1", float, 0), get("flame_offset_2", float, 0), get("flame_offset_3", float, 0), get("flame_offset_4", float, 0))
        self.drumHitFlameOffset = (get("drum_flame_offset_0", float, 0), get("drum_flame_offset_1", float, 0), get("drum_flame_offset_2", float, 0), get("drum_flame_offset_3", float, 0), get("drum_flame_offset_4", float, 0))

        #controls the size of the hitflames
        self.hitFlameSize   = get("hit_flame_size", float, .075)

        #controls the y and y position of the hitflames
        self.hitFlamePos  = (get("hit_flame_y_position", float, .3), get("hit_flame_z_position", float, 0))

        #controls the size of the hitflame glows
        self.holdFlameSize   = get("hold_flame_size", float, .075)

        #controls the y position of the hitflames glows
        self.holdFlamePos   = (get("hold_flame_y_position", int, 0), get("hold_flame_z_position", int, 0))

        self.fretPress = get("fretPress", bool, False)

        #Point of View (x, y, z)
        self.povTarget  = (get("pov_target_x", float), get("pov_target_y", float), get("pov_target_z", float))
        self.povOrigin  = (get("pov_origin_x", float), get("pov_origin_y", float), get("pov_origin_z", float))

        #pov presets
        self.povPreset = (get("pov_preset", str, "rb"))

        #Render necks toggle
        self.doNecksRender = (get("render_necks", bool, True))

        #Pause menu type
        self.pauseMenuType = (get("pause_menu_type", str, "RB"))

                #fretboard intro animation
        self.povIntroAnimation = (get("fretboard_intro_animation", str, "fofix"))

        #Note Tail Speed multiplier
        self.noteTailSpeedMulti = (get("note_tail_speed", float, 0))

        #Loading phrases
        self.loadingPhrase = get("loading_phrase", str, "Let's get this show on the Road_Impress the Crowd_" +
                                                        "Don't forget to strum!_Rock the house!_Jurgen is watching").split("_")
        self.resultsPhrase = get("results_phrase", str, "").split("_")

        #crowd_loop_delay controls how long (in milliseconds) FoFiX needs to wait before
        #playing the crowd noise again in the results screen after it finishes
        self.crowdLoopDelay = get("crowd_loop_delay", int)

        #When a song starts up it displays the info of the song (artist, name, etc)
        #positioning and the size of the font are handled by these values respectively
        self.songInfoDisplayScale = get("song_info_display_scale", float, 0.0020)
        self.songInfoDisplayX     = get("song_info_display_X",     float,   0.05)
        self.songInfoDisplayY     = get("song_info_display_Y",     float,   0.05)

        #when AI is enabled, this value controls where in the player's window
        #it should say that "Jurgen is here" and how large the words need to be
        self.jurgTextPos   = get("jurgen_text_pos", str, "1,1,.00035").split(",")

        #just a little misc option that allows you to change the name of what you
        #what starpower/overdrive to be called.  Some enjoy the classic Jurgen Power
        #name from Hering's mod.
        self.power_up_name = get("power_up_name", str, "Jurgen Power")

        self.countdownPosX = get("countdown_pos_x", float, 0.5)
        self.countdownPosY = get("countdown_pos_y", float, 0.45)

        #These values determine the width of the neck as well as the length of it
        #width seems pretty obvious but length has an advantage in that by making
        #it shorter the fade away comes sooner.  This is handy for unique POV because
        #sometimes static hud object (the lyric display) can get in the way.
        self.neckWidth  = get("neck_width",  float, 3.0)
        self.neckLength = get("neck_length", float, 9.0)

        #When in the neck choosing screen, these values determine the position of the
        #prompt that is usually at the top of the screen and says how to choose a neck
        self.neck_prompt_x = get("menu_neck_choose_x", float,  0.1)
        self.neck_prompt_y = get("menu_neck_choose_y", float, 0.05)

        #Big Rock Ending and Solo Frame Graphics
        self.breScoreBackgroundScale = get("breScoreBackgroundScale", float,  1.0)
        self.breScoreFrameScale      = get("breScoreFrameScale", float,  1.0)
        self.soloFrameScale          = get("soloFrameScale", float,  1.0)

        #Setlist
        #This is really a bit of a mess but luckily most of the names are quite self
        #explanatory.  These values are only necessary if your theme is using the old
        #default code that takes advantage of having the 4 different modes
        #list, cd, list/cd hybrid, rb2
        #if you're not using the default setlist display then don't bother with these values
        self.songListDisplay               = get("song_list_display", int, 0)

        self.setlistguidebuttonsposX       = get("setlistguidebuttonsposX",    float,  0.408)
        self.setlistguidebuttonsposY       = get("setlistguidebuttonsposY",    float, 0.0322)
        self.setlistguidebuttonsscaleX     = get("setlistguidebuttonsscaleX",  float,   0.29)
        self.setlistguidebuttonsscaleY     = get("setlistguidebuttonsscaleY",  float,  0.308)
        self.setlistpreviewbuttonposX      = get("setlistpreviewbuttonposX",   float,    0.5)
        self.setlistpreviewbuttonposY      = get("setlistpreviewbuttonposY",   float,    0.5)
        self.setlistpreviewbuttonscaleX    = get("setlistpreviewbuttonscaleX", float,    0.5)
        self.setlistpreviewbuttonscaleY    = get("setlistpreviewbuttonscaleY", float,    0.5)

        self.songSelectSubmenuOffsetLines  = get("song_select_submenu_offset_lines")
        self.songSelectSubmenuOffsetSpaces = get("song_select_submenu_offset_spaces")
        self.songSelectSubmenuX            = get("song_select_submenu_x")
        self.songSelectSubmenuY            = get("song_select_submenu_y")

        self.song_cd_Xpos                  = get("song_cd_x",      float, 0.0)
        self.song_cdscore_Xpos             = get("song_cdscore_x", float, 0.6)

        self.song_listcd_cd_Xpos           = get("song_listcd_cd_x",    float, .75)
        self.song_listcd_cd_Ypos           = get("song_listcd_cd_y",    float,  .6)
        self.song_listcd_score_Xpos        = get("song_listcd_score_x", float,  .6)
        self.song_listcd_score_Ypos        = get("song_listcd_score_y", float,  .5)
        self.song_listcd_list_Xpos         = get("song_listcd_list_x",  float,  .1)

        self.song_list_Xpos                = get("song_list_x",      float, 0.15)
        self.song_listscore_Xpos           = get("song_listscore_x", float,  0.8)

        self.songlist_score_colorVar       = get("songlist_score_color",       "color", "#93C351")
        self.songlistcd_score_colorVar     = get("songlistcd_score_color",     "color", "#FFFFFF")
        self.career_title_colorVar         = get("career_title_color",         "color", "#000000")
        self.song_name_text_colorVar       = get("song_name_text_color",       "color", "#FFFFFF")
        self.song_name_selected_colorVar   = get("song_name_selected_color",   "color", "#FFBF00")
        self.artist_text_colorVar          = get("artist_text_color",          "color", "#4080FF")
        self.artist_selected_colorVar      = get("artist_selected_color",      "color", "#4080FF")
        self.library_text_colorVar         = get("library_text_color",         "color", "#FFFFFF")
        self.library_selected_colorVar     = get("library_selected_color",     "color", "#FFBF00")
        self.song_rb2_diff_colorVar        = get("song_rb2_diff_color",        "color", "#FFBF00")

        #main menu system
        self.menuPos = [get("menu_x", float, 0.2), get("menu_y", float, 0.8)]
        self.main_menu_scaleVar    = get("main_menu_scale",    float, 0.5)
        self.main_menu_vspacingVar = get("main_menu_vspacing", float, .09)

        #Settings option scale
        self.settingsmenuScale = get("settings_menu_scale",    float, 0.002)

        #loading Parameters
        self.loadingX = get("loading_x", float, 0.5)
        self.loadingY = get("loading_y", float, 0.6)
        self.loadingFScale   = get("loading_font_scale",   float,    0.0015)
        self.loadingRMargin  = get("loading_right_margin", float,       1.0)
        self.loadingLSpacing = get("loading_line_spacing", float,       1.0)
        self.loadingColor    = get("loading_text_color", "color", "#FFFFFF")

        #this is the amount you can offset the shadow in the loading screen text
        self.shadowoffsetx = get("shadowoffsetx", float, .0022)
        self.shadowoffsety = get("shadowoffsety", float, .0005)

        self.sub_menu_xVar    = get("sub_menu_x", float, None)
        self.sub_menu_yVar    = get("sub_menu_y", float, None)
        #self.songback         = get("songback")


        #these are the little help messages at the bottom of the
        #options screen when you hover over an item
        self.menuTipTextY = get("menu_tip_text_y", float, .7)
        self.menuTipTextFont = get("menu_tip_text_font", str, "font")
        self.menuTipTextScale = get("menu_tip_text_scale", float, .002)
        self.menuTipTextColor = get("menu_tip_text_color", "color", "#FFFFFF")
        self.menuTipTextScrollSpace = get("menu_tip_text_scroll_space", float, .25)
        self.menuTipTextScrollMode = get("menu_tip_text_scroll_mode", int, 0)
        self.menuTipTextDisplay = get("menu_tip_text_display", bool, False)

        self.lobbyOptionFont = get("lobbyOptionFont", str, "font")

        self.partDiffTitleText = get("partDiffTitleText", str, "Select a Part and Difficulty")
        self.partDiffTitleTextPos = (get("partDiffTitleTextX", float, .5),
                                     get("partDiffTitleTextY", float, .1))
        self.partDiffTitleTextAlign = halign(get("partDiffTitleTextAlign", str, "CENTER"))
        self.partDiffTitleTextScale = get("partDiffTitleTextScale", float, .0025)
        self.partDiffTitleTextFont = get("partDiffTitleTextFont", str, "font")

        self.partDiffSubtitleText = get("partDiffSubtitleText", str, "Ready to Play!")
        self.partDiffSubtitleTextPos = (get("partDiffSubtitleX", float, .5),
                                        get("partDiffSubtitleY", float, .15))
        self.partDiffSubtitleTextAlign = halign(get("partDiffSubtitleTextAlign", str, "CENTER"))
        self.partDiffSubtitleTextScale = get("partDiffSubtitleTextScale", float, .0015)
        self.partDiffSubtitleTextFont = get("partDiffSubtitleTextFont", str, "font")

        self.partDiffOptionScale = get("partDiffOptionScale", float, .001)
        self.partDiffOptionAlign = halign(get("partDiffOptionAlign", str, "CENTER"))
        self.partDiffOptionFont = get("partDiffOptionFont", str, "font")
        self.partDiffOptionPos = (get("partDiffOptionX", float, .5),
                                  get("partDiffOptionY", float, .46))
        self.partDiffOptionSpace = get("partDiffOptionScale", float, .04)
        self.partDiffOptionColor = get("partDiffOptionColor", "color", "#FFFFFF")
        self.partDiffSelectedColor = get("partDiffSelectedColor", "color", "#FFFF66")

        self.partDiffGameModeScale = get("partDiffGameModeScale", float, .001)
        self.partDiffGameModeAlign = halign(get("partDiffGameModeAlign", str, "CENTER"))
        self.partDiffGameModeFont  = get("partDiffGameModeFont", str, "font")
        self.partDiffGameModePos   = (get("partDiffGameModeX", float, .07),
                                      get("partDiffGameModeY", float,  .015))
        self.partDiffGameModeColor = get("partDiffGameModeColor", "color", "#FFFFFF")

        self.partDiffPanelNameScale = get("partDiffPanelNameScale", float, .001)
        self.partDiffPanelNameAlign = halign(get("partDiffPanelNameAlign", str, "LEFT"), 'left')
        self.partDiffPanelNameFont  = get("partDiffPanelNameFont", str, "font")
        self.partDiffPanelNamePos   = (get("partDiffPanelNameX", float, 0.0),
                                       get("partDiffPanelNameY", float, 0.0))

        self.partDiffControlScale = get("partDiffControlScale", float, .0025)
        self.partDiffControlAlign = halign(get("partDiffControlAlign", str, "CENTER"))
        self.partDiffControlFont  = get("partDiffControlFont", str, "font")
        self.partDiffControlPos   = (get("partDiffControlX", float, .5),
                                     get("partDiffControlY", float,  .375))
        self.partDiffHeaderColor = get("partDiffHeaderColor", "color", "#FFFFFF")

        self.partDiffPartScale = get("partDiffPartScale", float, .25)
        self.partDiffPartPos = (get("partDiffPartX", float, .5),
                                get("partDiffpartY", float, .52))

        self.partDiffKeyboardImgScale = get("partDiffKeyboardImgScale", float, .1)
        self.partDiffKeyboardImgPos = (get("partDiffKeyboardImgX", float, .8),
                                       get("partDiffKeyboardImgY", float, .95))

        self.partDiffPanelSpacing = get("partDiffPanelSpacing", float, .24)
        self.partDiffPanelPos = (get("partDiffPanelX", float, .04),
                                 get("partDiffPanelY", float, .1))
        self.partDiffPanelSize = (get("partDiffPanelWidth", float,  .2),
                                  get("partDiffPanelHeight", float, .8))

        #Submenus
        self.submenuScale = {}
        self.submenuX = {}
        self.submenuY = {}
        self.submenuVSpace = {}
        if os.path.exists(os.path.join(self.themePath,"menu")):
            allfiles = os.listdir(os.path.join(self.themePath,"menu"))
            listmenu = []
            for name in allfiles:
                if name.find("text") > -1:
                    found = os.path.splitext(name)[0]
                    if found == "maintext":
                        continue
                    Config.define("theme", found, str, None)
                    self.submenuScale[found] = None
                    self.submenuX[found] = None
                    self.submenuY[found] = None
                    self.submenuVSpace[found] = None
                    listmenu.append(found)
            for i in listmenu:
                if i == "maintext":
                    continue
                if self.submenuX[i]:
                    self.submenuX[i] = get(i).split(",")[0].strip()
                if self.submenuY[i]:
                    self.submenuY[i] = get(i).split(",")[1].strip()
                if self.submenuScale[i]:
                    self.submenuScale[i] = get(i).split(",")[2].strip()
                if self.submenuVSpace[i]:
                    self.submenuVSpace[i] = get(i).split(",")[3].strip()

    def setSelectedColor(self, alpha = 1.0):
        glColor4f(*(self.selectedColor + (alpha,)))

    def setBaseColor(self, alpha = 1.0):
        glColor4f(*(self.baseColor + (alpha,)))

    def hexToColorResults(self, color):
        # TODO - Go through GameResultsScene and remove the usage of this.
        try:
            return hexToColor(color)
        except ValueError, TypeError:
            return self.baseColor

    def packTupleKey(self, key, type = str):
        vals = key.split(',')
        if isinstance(type, list):
            retval = tuple(type[i](n.strip()) for i, n in enumerate(vals))
        else:
            retval = tuple(type(n.strip()) for n in vals)
        return retval

    def run(self, ticks):
        pass

class ThemeParts:
    def __init__(self, theme):
        self.theme = theme
    def run(self, ticks):
        pass
    def drawPartImage(self, dialog, part, scale, coord):
        if part in [0, 2, 4, 5]:
            if dialog.partImages[part]:
                drawImage(dialog.partImages[part], scale = scale, coord = coord)
        else:
            if dialog.partImages[part]:
                drawImage(dialog.partImages[part], scale = scale, coord = coord)
            else:
                if dialog.partImages[0]:
                    drawImage(dialog.partImages[0], scale = scale, coord = coord)
    def renderPanels(self, dialog):
        x = self.theme.partDiffPanelPos[0]
        y = self.theme.partDiffPanelPos[1]
        w, h = dialog.geometry
        font = dialog.fontDict['font']
        controlFont   = dialog.fontDict[self.theme.partDiffControlFont]
        panelNameFont = dialog.fontDict[self.theme.partDiffPanelNameFont]
        wP = w*self.theme.partDiffPanelSize[0]
        hP = h*self.theme.partDiffPanelSize[1]
        glColor3f(*self.theme.partDiffHeaderColor)
        dialog.engine.fadeScreen(-2.00)
        if self.theme.partDiffTitleText:
            dialog.fontDict[self.theme.partDiffTitleTextFont].render(self.theme.partDiffTitleText, self.theme.partDiffTitleTextPos, scale = self.theme.partDiffTitleTextScale, align = self.theme.partDiffTitleTextAlign)
        if self.theme.partDiffSubtitleText:
            dialog.fontDict[self.theme.partDiffSubtitleTextFont].render(self.theme.partDiffSubtitleText, self.theme.partDiffSubtitleTextPos, scale = self.theme.partDiffSubtitleTextScale, align = self.theme.partDiffSubtitleTextAlign)
        for i in range(len(dialog.players)):
            glColor3f(*self.theme.partDiffHeaderColor)
            dialog.fontDict[self.theme.partDiffGameModeFont].render(dialog.gameModeText, self.theme.partDiffGameModePos, scale = self.theme.partDiffGameModeScale, align = self.theme.partDiffGameModeAlign)
            if i == dialog.keyControl and dialog.img_keyboard_panel:
                drawImage(dialog.img_keyboard_panel, scale = (self.theme.partDiffPanelSize[0], -self.theme.partDiffPanelSize[1]), coord = (wP*.5+w*x,hP*.5+h*y), stretched = FULL_SCREEN)
            elif dialog.img_panel:
                drawImage(dialog.img_panel, scale = (self.theme.partDiffPanelSize[0], -self.theme.partDiffPanelSize[1]), coord = (wP*.5+w*x,hP*.5+h*y), stretched = FULL_SCREEN)
            if i == dialog.keyControl and dialog.img_keyboard:
                drawImage(dialog.img_keyboard, scale = (self.theme.partDiffKeyboardImgScale, -self.theme.partDiffKeyboardImgScale), coord = (wP*self.theme.partDiffKeyboardImgPos[0]+w*x, hP*self.theme.partDiffKeyboardImgPos[1]+h*y))
            controlFont.render(dialog.players[i].name, (self.theme.partDiffPanelSize[0]*self.theme.partDiffControlPos[0]+x, self.theme.partDiffPanelSize[1]*self.theme.partDiffControlPos[1]+y), scale = self.theme.partDiffControlScale, align = self.theme.partDiffControlAlign, new = True)
            panelNameFont.render(dialog.players[i].name.lower(), (x+w*self.theme.partDiffPanelNamePos[0], y+h*self.theme.partDiffPanelNamePos[1]), scale = self.theme.partDiffPanelNameScale, align = self.theme.partDiffPanelNameAlign, new = True)
            if dialog.mode[i] == 0:
                self.drawPartImage(dialog, dialog.parts[i][dialog.selected[i]].id, scale = (self.theme.partDiffPartScale, -self.theme.partDiffPartScale), coord = (wP*self.theme.partDiffPartPos[0]+w*x, hP*self.theme.partDiffPartPos[1]+h*y))
                for p in range(len(dialog.parts[i])):
                    if dialog.selected[i] == p:
                        if dialog.img_selected:
                            drawImage(dialog.img_selected, scale = (.5, -.5), coord = (wP*.5+w*x, hP*(.46*.75)+h*y-(h*.04*p)/.75))
                        glColor3f(*self.theme.partDiffSelectedColor)
                    else:
                        glColor3f(*self.theme.partDiffOptionColor)
                    font.render(str(dialog.parts[i][p]), (.2*.5+x,.8*.46+y+.04*p), scale = .001, align = 1, new = True)
            elif dialog.mode[i] == 1:
                self.drawPartImage(dialog, dialog.players[i].part.id, scale = (self.theme.partDiffPartScale, -self.theme.partDiffPartScale), coord = (wP*self.theme.partDiffPartPos[0]+w*x, hP*self.theme.partDiffPartPos[1]+h*y))
                for d in range(len(dialog.info.partDifficulties[dialog.players[i].part.id])):
                    if dialog.selected[i] == d:
                        if dialog.img_selected:
                            drawImage(dialog.img_selected, scale = (.5, -.5), coord = (wP*.5+w*x, hP*(.46*.75)+h*y-(h*.04*d)/.75))
                        glColor3f(*self.theme.partDiffSelectedColor)
                    else:
                        glColor3f(*self.theme.partDiffOptionColor)
                    font.render(str(dialog.info.partDifficulties[dialog.players[i].part.id][d]), (.2*.5+x,.8*.46+y+.04*d), scale = .001, align = 1, new = True)
                if i in dialog.readyPlayers:
                    if dialog.img_ready:
                        drawImage(dialog.img_ready, scale = (.5, -.5), coord = (wP*.5+w*x,hP*(.75*.46)+h*y))
            x += .24


__all__ = ["LEFT", "CENTER", "RIGHT", "_", "Theme"]
