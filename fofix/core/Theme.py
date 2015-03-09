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
classNames = {'themeLobby': lambda x: ThemeLobby(x), 'partDiff': lambda x: ThemeParts(x)}

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

        #Specifies how the power color is used in-game for both Active power and gaining power
        self.powerGainColorToggle    = get("power_color_gain_toggle",      bool, True)
        self.powerActiveColorToggle  = get("power_color_active_toggle",    bool, False)

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

        #These determine the position of the version tag on the main menu.
        self.versiontagScale = get("versiontagScale", float, 0.5)
        self.versiontagposX = get("versiontagposX", float, 0.5)
        self.versiontagposY = get("versiontagposY", float, 0.05)

        #pause menu and fail menu positions and text colors
        self.pause_bkg_pos           = get("pause_bkg",                str, "0.5,0.5,1.0,1.0").split(",")
        self.pause_text_xPos         = get("pause_text_x",           float)
        self.pause_text_yPos         = get("pause_text_y",           float)
        self.pause_text_colorVar     = get("pause_text_color",     "color", "#FFFFFF")
        self.pause_selected_colorVar = get("pause_selected_color", "color", "#FFBF00")

        self.fail_completed_colorVar = get("fail_completed_color", "color", "#FFFFFF")
        self.fail_text_colorVar      = get("fail_text_color",      "color", "#FFFFFF")
        self.fail_selected_colorVar  = get("fail_selected_color",  "color", "#FFBF00")

        self.fail_bkg_pos       = get("fail_bkg",          str, "0.5,0.5,1.0,1.0").split(",")
        self.fail_text_xPos     = get("fail_text_x",     float)
        self.fail_text_yPos     = get("fail_text_y",     float)
        self.fail_songname_xPos = get("fail_songname_x", float,  0.5)
        self.fail_songname_yPos = get("fail_songname_y", float, 0.35)

        self.opt_bkg_size          = get("opt_bkg",                str, "0.5,0.5,1.0,1.0").split(",")
        self.opt_text_xPos         = get("opt_text_x",           float)
        self.opt_text_yPos         = get("opt_text_y",           float)
        self.opt_text_colorVar     = get("opt_text_color",     "color",         "#FFFFFF")
        self.opt_selected_colorVar = get("opt_selected_color", "color",         "#FFBF00")

        #main menu system
        self.menuPos = [get("menu_x", float, 0.2), get("menu_y", float, 0.8)]
        self.menuRB  = get("rbmenu", bool, False)
        self.main_menu_scaleVar    = get("main_menu_scale",    float, 0.5)
        self.main_menu_vspacingVar = get("main_menu_vspacing", float, .09)
        self.use_solo_submenu      = get("use_solo_submenu",   bool, True)

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

        self.versiontag = get("versiontag", bool, False)

        #these are the little help messages at the bottom of the
        #options screen when you hover over an item
        self.menuTipTextY = get("menu_tip_text_y", float, .7)
        self.menuTipTextFont = get("menu_tip_text_font", str, "font")
        self.menuTipTextScale = get("menu_tip_text_scale", float, .002)
        self.menuTipTextColor = get("menu_tip_text_color", "color", "#FFFFFF")
        self.menuTipTextScrollSpace = get("menu_tip_text_scroll_space", float, .25)
        self.menuTipTextScrollMode = get("menu_tip_text_scroll_mode", int, 0)
        self.menuTipTextDisplay = get("menu_tip_text_display", bool, False)

        #Lobby
        self.controlActivateX        = get("control_activate_x",         float, 0.645)
        self.controlActivateSelectX  = get("control_activate_select_x",  float, 0.5)
        self.controlActivatePartX    = get("control_activate_part_x",    float, 0.41)
        self.controlActivateY        = get("control_activate_y",         float, 0.18)
        self.controlActivateScale    = get("control_activate_scale",     float, 0.0018)
        self.controlActivateSpace    = get("control_activate_part_size", float, 22.000)
        self.controlActivatePartSize = get("control_activate_space",     float, 0.045)
        self.controlActivateFont     = get("control_activate_font",        str, "font")
        self.controlDescriptionX     = get("control_description_x",      float, 0.5)
        self.controlDescriptionY     = get("control_description_y",      float, 0.13)
        self.controlDescriptionScale = get("control_description_scale",  float, 0.002)
        self.controlDescriptionFont  = get("control_description_font",     str, "font")
        self.controlCheckX           = get("control_description_scale", float, 0.002)
        self.controlCheckY           = get("control_check_x",           float, 0.16)
        self.controlCheckTextY       = get("control_check_text_y",      float, 0.61)
        self.controlCheckPartMult    = get("control_check_part_mult",   float, 2.8)
        self.controlCheckScale       = get("control_check_space",       float, 0.23)
        self.controlCheckSpace       = get("control_check_scale",       float, 0.0018)
        self.controlCheckFont        = get("control_check_font",          str, "font")

        self.lobbyMode           = get("lobby_mode", int, 0)
        self.lobbyPreviewX       = get("lobby_preview_x", float, 0.7)
        self.lobbyPreviewY       = get("lobby_preview_y", float, 0.0)
        self.lobbyPreviewSpacing = get("lobby_preview_spacing", float, 0.04)

        self.lobbyTitleX          = get("lobby_title_x", float, 0.5)
        self.lobbyTitleY          = get("lobby_title_y", float, 0.07)
        self.lobbyTitleCharacterX = get("lobby_title_character_x", float, 0.26)
        self.lobbyTitleCharacterY = get("lobby_title_character_y", float, 0.24)
        self.lobbyTitleScale      = get("lobby_title_scale", float, 0.0024)
        self.lobbyTitleFont       = get("lobby_title_font", str, "loadingFont")

        self.lobbyAvatarX      = get("lobby_avatar_x",        float, 0.7)
        self.lobbyAvatarY      = get("lobby_avatar_y",        float, 0.75)
        self.lobbyAvatarScale  = get("lobby_avatar_scale",    float, 1.0)

        self.lobbySelectX      = get("lobby_select_x",        float, 0.4)
        self.lobbySelectY      = get("lobby_select_y",        float, 0.32)
        self.lobbySelectImageX = get("lobby_select_image_x",  float, 0.255)
        self.lobbySelectImageY = get("lobby_select_image_y",  float, 0.335)
        self.lobbySelectScale  = get("lobby_select_scale",    float, 0.0018)
        self.lobbySelectSpace  = get("lobby_select_space",    float, 0.04)
        self.lobbySelectFont   = get("lobby_select_font",       str, "font")
        self.lobbySelectLength = get("lobby_select_length",     int, 5)

        self.lobbyTitleColor   = get("lobby_title_color",   "color", "#FFFFFF")
        self.lobbyInfoColor    = get("lobby_info_color",    "color", "#FFFFFF")
        self.lobbyFontColor    = get("lobby_font_color",    "color", "#FFFFFF")
        self.lobbyPlayerColor  = get("lobby_player_color",  "color", "#FFFFFF")
        self.lobbySelectColor  = get("lobby_select_color",  "color", "#FFBF00")
        self.lobbyDisableColor = get("lobby_disable_color", "color", "#666666")

        self.characterCreateX           = get("character_create_x",          float,   0.25)
        self.characterCreateY           = get("character_create_y",          float,   0.15)
        self.characterCreateHelpX       = get("character_create_help_x",     float,    0.5)
        self.characterCreateHelpY       = get("character_create_help_y",     float,   0.73)
        self.characterCreateScale       = get("character_create_scale",      float, 0.0018)
        self.characterCreateSpace       = get("character_create_space",      float,  0.045)
        self.characterCreateHelpScale   = get("character_create_help_scale", float, 0.0018)
        self.characterCreateOptionX     = get("character_create_option_x",   float,   0.75)

        self.characterCreateOptionFont  = get("character_create_option_font", str, "font")
        self.characterCreateHelpFont    = get("character_create_help_font", str, "loadingFont")

        self.characterCreateFontColor   = get("character_create_font_color", "color", "#FFFFFF")
        self.characterCreateSelectColor = get("character_create_select_color", "color", "#FFBF00")
        self.characterCreateHelpColor   = get("character_create_help_color", "color", "#FFFFFF")

        self.avatarSelectTextX     = get("avatar_select_text_x", float, 0.44)
        self.avatarSelectTextY     = get("avatar_select_text_y", float, 0.16)
        self.avatarSelectTextScale = get("avatar_select_text_scale", float, 0.0027)

        self.avatarSelectAvX    = get("avatar_select_avatar_x", float, 0.667)
        self.avatarSelectAvY    = get("avatar_select_avatar_y", float, 0.5)

        self.avatarSelectWheelY = get("avatar_select_wheel_y", float, 0.0)

        self.avatarSelectFont   = get("avatar_select_font", str, "font")

        self.lobbyPanelAvatarDimension = (get("lobbyPanelAvatarWidth", float, 200.00),
                                          get("lobbyPanelAvatarHeight", float, 110.00))
        self.lobbyTitleText = get("lobbyTitleText", str, "Lobby")
        self.lobbyTitleTextPos = (get("lobbyTitleTextX", str, 0.3),
                                  get("lobbyTitleTextY", float, 0.015))
        self.lobbyTitleTextAlign = halign(get("lobbyTitleTextAlign", str, "CENTER"))
        self.lobbyTitleTextScale = get("lobbyTitleTextScale", float, .001)
        self.lobbyTitleTextFont = get("lobbyTitleTextFont", str, "font")

        self.lobbySubtitleText = get("lobbySubtitleText", str, "Choose Your Character!")
        self.lobbySubtitleTextPos = (get("lobbySubtitleTextX", float, 0.5),
                                     get("lobbySubtitleTextY", float, 0.015))
        self.lobbySubtitleTextScale = get("lobbySubtitleTextScale", float, .0015)
        self.lobbySubtitleTextFont = get("lobbySubtitleTextFont", str, "font")
        self.lobbySubtitleTextAlign = halign(get("lobbySubtitleTextAlign", str, "CENTER"))

        self.lobbyOptionScale = get("lobbyOptionScale", float, .001)
        self.lobbyOptionAlign = halign(get("lobbyOptionAlign", str, "CENTER"))
        self.lobbyOptionFont = get("lobbyOptionFont", str, "font")
        self.lobbyOptionPos = (get("lobbyOptionX", float, .5),
                               get("lobbyOptionY", float, .46))
        self.lobbyOptionSpace = get("lobbyOptionSpace", float, .04)
        self.lobbyOptionColor = get("lobbyOptionColor", "color", "#FFFFFF")

        self.lobbySaveCharScale = get("lobbySaveCharScale", float, .001)
        self.lobbySaveCharAlign = halign(get("lobbySaveCharAlign", str, "CENTER"))
        self.lobbySaveCharFont = get("lobbySaveCharFont", str, "font")
        self.lobbySaveCharColor = get("lobbySaveCharColor", "color", "#FFFFFF")

        self.lobbyGameModePos = (get("lobbyGameModeX", float, 0.7),
                                 get("lobbyGameModeY", float, 0.015))
        self.lobbyGameModeScale = get("lobbyGameModeScale", float, .001)
        self.lobbyGameModeAlign = halign(get("lobbyGameModeAlign", str, "CENTER"))
        self.lobbyGameModeFont = get("lobbyGameModeFont", str, "font")
        self.lobbyGameModeColor = get("lobbyGameModeColor", "color", "#FFFFFF")

        self.lobbyPanelNamePos = (get("lobbyPanelNameX", float, 0.0),
                                  get("lobbyPanelNameY", float, 0.0))
        self.lobbyPanelNameFont = get("lobbyPanelNameFont", str, "font")
        self.lobbyPanelNameScale = get("lobbyPanelNameScale", float, .001)
        self.lobbyPanelNameAlign = halign(get("lobbyPanelNameAlign", str, "LEFT"), 'left')
        self.lobbyControlPos = (get("lobbyControlX", float, .5),
                                get("lobbyControlY", float, .375))
        self.lobbyControlFont = get("lobbyControlFont", str, "font")
        self.lobbyControlScale = get("lobbyControlScale", float, .0025)
        self.lobbyControlAlign = halign(get("lobbyControlAlign", str, "CENTER"))
        self.lobbyHeaderColor = get("lobbyHeaderColor", "color", "#FFFFFF")
        self.lobbySelectLength = get("lobbySelectLength", int, 4)

        self.lobbyPartScale = get("lobbyPartScale", float, .25)
        self.lobbyPartPos = (get("lobbyPartX", float, .5),
                             get("lobbyPartY", float, .52))
        self.lobbyControlImgScale = get("lobbyControlImgScale", float, .25)
        self.lobbyControlImgPos = (get("lobbyControlImgX", float, .5),
                                   get("lobbyControlImgY", float, .55))

        self.lobbyKeyboardImgScale = get("lobbyKeyboardImgScale", float, .1)
        self.lobbyKeyboardImgPos = (get("lobbyKeyboardImgX", float, .8),
                                    get("lobbyKeyboardImgY", float, .95))
        self.lobbySelectedColor = get("lobbySelectedColor", "color", "#FFFF66")
        self.lobbyDisabledColor = get("lobbyDisabledColor", "color", "#BBBBBB")
        self.lobbyPanelSize = (get("lobbyPanelWidth", float, .2),
                               get("lobbyPanelHeight", float, .8))
        self.lobbyPanelPos = (get("lobbyPanelX", float, .04),
                              get("lobbyPanelY", float, .1))
        self.lobbyPanelSpacing = get("lobbyPanelSpacing", float, .24)

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

        #Vocal mode
        self.vocalMeterSize = get("vocal_meter_size", float, 45.000)
        self.vocalMeterX = get("vocal_meter_x", float, .25)
        self.vocalMeterY = get("vocal_meter_y", float, .8)
        self.vocalMultX  = get("vocal_mult_x", float, .28)
        self.vocalMultY  = get("vocal_mult_y", float, .8)

        self.vocalPowerX = get("vocal_power_x", float, .5)
        self.vocalPowerY = get("vocal_power_y", float, .8)

        self.vocalFillupCenterX   = get("vocal_fillup_center_x",   int, 139)
        self.vocalFillupCenterY   = get("vocal_fillup_center_y",   int, 151)
        self.vocalFillupInRadius  = get("vocal_fillup_in_radius",  int, 25)
        self.vocalFillupOutRadius = get("vocal_fillup_out_radius", int, 139)
        self.vocalFillupFactor    = get("vocal_fillup_factor",   float, 300.000)
        self.vocalFillupColor     = get("vocal_fillup_color",  "color", "#DFDFDE")
        self.vocalCircularFillup  = get("vocal_circular_fillup",  bool, True)

        self.vocalLaneSize = get("vocal_lane_size", float, .002)
        self.vocalGlowSize = get("vocal_glow_size", float, .012)
        self.vocalGlowFade = get("vocal_glow_fade", float,   .6)

        self.vocalLaneColor       = get("vocal_lane_color",        "color", "#99FF80")
        self.vocalShadowColor     = get("vocal_shadow_color",      "color", "#CCFFBF")
        self.vocalGlowColor       = get("vocal_glow_color",        "color", "#33FF00")
        self.vocalLaneColorStar   = get("vocal_lane_color_star",   "color", "#FFFF80")
        self.vocalShadowColorStar = get("vocal_shadow_color_star", "color", "#FFFFBF")
        self.vocalGlowColorStar   = get("vocal_glow_color_star",   "color", "#FFFF00")

        #3D Note/Fret rendering system
        self.twoDnote = get("twoDnote", bool, True)
        self.twoDkeys = get("twoDkeys", bool, True)

        #3D notes spin when they are star power notes
        self.threeDspin  = get("threeDspin", bool, False)

        #configure rotation and positioning along the neck for the 3d objects scrolling down
        self.noterot     = [get("noterot"+str(i+1),     float, 0) for i in range(5)]
        self.keyrot      = [get("keyrot"+str(i+1),      float, 0) for i in range(5)]
        self.drumnoterot = [get("drumnoterot"+str(i+1), float, 0) for i in range(5)]
        self.drumkeyrot  = [get("drumkeyrot"+str(i+1),  float, 0) for i in range(5)]
        self.notepos     = [get("notepos"+str(i+1),     float, 0) for i in range(5)]
        self.keypos      = [get("keypos"+str(i+1),      float, 0) for i in range(5)]
        self.drumnotepos = [get("drumnotepos"+str(i+1), float, 0) for i in range(5)]
        self.drumkeypos  = [get("drumkeypos"+str(i+1),  float, 0) for i in range(5)]

        #3D setting for making the notes always face the camera
        self.billboardNote = get("billboardNote", bool, True)

        #In-game rendering
        self.hopoIndicatorX = get("hopo_indicator_x")
        self.hopoIndicatorY = get("hopo_indicator_y")
        self.hopoIndicatorActiveColor = get("hopo_indicator_active_color", "color", "#FFFFFF")
        self.hopoIndicatorInactiveColor = get("hopo_indicator_inactive_color", "color", "#666666")
        self.markSolos = get("mark_solo_sections", int, 2)
        self.ingame_stats_colorVar = get("ingame_stats_color", "color", "#FFFFFF")
        self.fpsRenderPos = (get("fps_display_pos_x", float, .85), get("fps_display_pos_y", float, .055))

        #Game results scene
        self.result_score = get("result_score", str, ".5,.11,0.0025,None,None").split(",")
        self.result_star = get("result_star", str, ".5,.4,0.15,1.1").split(",")
        self.result_song = get("result_song", str, ".05,.045,.002,None,None").split(",")
        self.result_song_form = get("result_song_form", int, 0)
        self.result_song_text = get("result_song_text", str, "%s Finished!").strip()
        self.result_stats_part = get("result_stats_part", str, ".5,.64,0.002,None,None").split(",")
        self.result_stats_part_text = get("result_stats_part_text", str, "Part: %s").strip()
        self.result_stats_name = get("result_stats_name", str, ".5,.73,0.002,None,None").split(",")
        self.result_stats_diff = get("result_stats_diff", str, ".5,.55,0.002,None,None").split(",")
        self.result_stats_diff_text = get("result_stats_diff_text", str, "Difficulty: %s").strip()
        self.result_stats_accuracy = get("result_stats_accuracy", str, ".5,.61,0.002,None,None").split(",")
        self.result_stats_accuracy_text = get("result_stats_accuracy_text", str, "Accuracy: %.1f%%").strip()
        self.result_stats_streak = get("result_stats_streak", str, ".5,.58,0.002,None,None").split(",")
        self.result_stats_streak_text = get("result_stats_streak_text", str, "Long Streak: %s").strip()
        self.result_stats_notes = get("result_stats_notes", str, ".5,.52,0.002,None,None").split(",")
        self.result_stats_notes_text = get("result_stats_notes_text", str, "%s Notes Hit").strip()
        self.result_cheats_info = get("result_cheats_info", str, ".5,.3,.002").split(",")
        self.result_cheats_numbers = get("result_cheats_numbers", str, ".5,.35,.0015").split(",")
        self.result_cheats_percent = get("result_cheats_percent", str, ".45,.4,.0015").split(",")
        self.result_cheats_score   = get("result_cheats_score", str, ".75,.4,.0015").split(",")
        self.result_cheats_color   = get("result_cheats_color", "color", "#FFFFFF")
        self.result_cheats_font    = get("result_cheats_font", str, "font")
        self.result_high_score_font = get("result_high_score_font", str, "font")
        self.result_menu_x         = get("result_menu_x", float, .5)
        self.result_menu_y         = get("result_menu_y", float, .2)
        self.result_star_type      = get("result_star_type", int, 0)

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

    def loadThemeModule(self, moduleName):
        try:
            fp, pathname, description = imp.find_module(moduleName,[self.path])
            module = imp.load_module(moduleName, fp, pathname, description)
            if moduleName in ["CustomLobby", "ThemeLobby"]:
                return module.CustomLobby(self)
            elif moduleName in ["CustomSetlist", "Setlist"]:
                return module.CustomSetlist(self)
            elif moduleName in ["CustomParts", "ThemeParts"]:
                return module.CustomParts(self)
            else:
                return None
        except ImportError:
            if moduleName in ["CustomLobby", "ThemeLobby"]:
                return ThemeLobby(self)
            elif moduleName in ["CustomSetlist", "Setlist"]:
                return Setlist(self)
            elif moduleName in ["CustomParts", "ThemeParts"]:
                return ThemeParts(self)
            else:
                return None

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
