#####################################################################
# -*- coding: iso-8859-1 -*-                                        #
#                                                                   #
# Frets on Fire                                                     #
# Copyright (C) 2006 Sami Kyöstilä                                  #
#               2008 Alarian                                        #
#               2008 myfingershurt                                  #
#               2008 Spikehead777                                   #
#               2008 Glorandwarf                                    #
#               2008 ShiekOdaSandz                                  #
#               2008 QQStarS                                        #
#               2008 Blazingamer                                    #
#               2008 evilynux <evilynux@gmail.com>                  #
#               2008 fablaculp                                      #
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

import pygame

from fofix.core.Language import _
from fofix.core.View import BackgroundLayer
from fofix.core.Input import KeyListener
from fofix.game.Song import VOCAL_PART
from fofix.game import Menu
from fofix.game import Dialogs
from fofix.core import Version
from fofix.core import Config
from fofix.core import Player
from fofix.core import Mod
from fofix.core import VFS
from fofix.core import Log

class ConfigChoice(Menu.Choice):
    def __init__(self, engine, config, section, option, autoApply = False):
        self.engine    = engine
        self.config    = config

        self.section    = section
        self.option     = option
        self.changed    = False
        self.value      = None
        self.autoApply  = autoApply
        tipText = config.getTipText(section, option)
        o = config.prototype[section][option]
        v = config.get(section, option)
        if isinstance(o.options, dict):
            values     = o.options.values()
            values.sort()
            try:
                valueIndex = values.index(o.options[v])
            except KeyError:
                valueIndex = 0
        elif isinstance(o.options, list):
            values     = o.options
            try:
                valueIndex = values.index(v)
            except ValueError:
                valueIndex = 0
        else:
            raise RuntimeError("No usable options for %s.%s." % (section, option))
        Menu.Choice.__init__(self, text = o.text, callback = self.change, values = values, valueIndex = valueIndex, tipText = tipText)

    def change(self, value):
        o = self.config.prototype[self.section][self.option]

        if isinstance(o.options, dict):
            for k, v in o.options.items():
                if v == value:
                    value = k
                    break

        self.changed = True
        self.value   = value

        self.apply()  #stump: it wasn't correctly saving some "restart required" settings
        if not self.autoApply:
            self.engine.restartRequired = True

    def apply(self):
        if self.changed:
            self.config.set(self.section, self.option, self.value)

class ActiveConfigChoice(ConfigChoice):
    """
    ConfigChoice with an additional callback function.
    """
    def __init__(self, engine, config, section, option, onChange, autoApply = True, volume = False):
        ConfigChoice.__init__(self, engine, config, section, option, autoApply = autoApply)
        self.engine   = engine
        self.onChange = onChange
        self.volume   = volume

    def change(self, value):
        ConfigChoice.change(self, value)
        if self.volume:
            sound = self.engine.data.screwUpSound
            sound.setVolume(self.value)
            sound.play()

    def apply(self):
        ConfigChoice.apply(self)
        self.onChange()

class VolumeConfigChoice(ConfigChoice):
    def __init__(self, engine, config, section, option, autoApply = False):
        ConfigChoice.__init__(self, engine, config, section, option, autoApply)
        self.engine = engine



    def change(self, value):
        ConfigChoice.change(self, value)
        sound = self.engine.data.screwUpSound
        sound.setVolume(self.value)
        sound.play()


class SettingsMenu(Menu.Menu):
    def __init__(self, engine):

        self.engine = engine

        self.opt_text_x = .25
        self.opt_text_y = .14
        self.opt_text_color = (1,1,1)
        self.opt_selected_color = (1,0.75,0)

        self.basicSettings = [
            ConfigChoice(self.engine, self.engine.config, "game",  "language"),
            ConfigChoice(self.engine, self.engine.config, "game", "resume_countdown", autoApply = True), #akedrou
            ConfigChoice(self.engine, self.engine.config, "audio",  "delay", autoApply = True),     #myfingershurt: so a/v delay can be set without restarting FoF
            ConfigChoice(self.engine, self.engine.config, "game", "song_hopo_freq", autoApply = True),
        ]

        self.basicSettingsMenu = Menu.Menu(self.engine, self.basicSettings, pos = (self.opt_text_x, self.opt_text_y), textColor = self.opt_text_color, selectedColor = self.opt_selected_color)

        self.fretSettings = [
            ConfigChoice(self.engine, self.engine.config, "fretboard", "point_of_view", autoApply = True),
            ConfigChoice(self.engine, self.engine.config, "game", "frets_under_notes", autoApply = True), #MFH
            ConfigChoice(self.engine, self.engine.config, "game", "nstype", autoApply = True),      #blazingamer
            ConfigChoice(self.engine, self.engine.config, "coffee", "neckSpeed", autoApply = True),
        ]
        self.fretSettingsMenu = Menu.Menu(self.engine, self.fretSettings, pos = (self.opt_text_x, self.opt_text_y), textColor = self.opt_text_color, selectedColor = self.opt_selected_color)

        modes = self.engine.video.getVideoModes()
        modes.reverse()
        Config.define("video",  "resolution", str,   "1024x768", text = _("Video Resolution"), options = ["%dx%d" % (m[0], m[1]) for m in modes], tipText = _("Set the resolution of the game. In windowed mode, higher values mean a larger screen."))
        self.videoSettings = [
            ConfigChoice(engine, engine.config, "coffee", "themename"), #was autoapply... why?
            ConfigChoice(engine, engine.config, "video",  "resolution"),
            ConfigChoice(engine, engine.config, "video",  "fullscreen"),
            ConfigChoice(self.engine, self.engine.config, "video",  "fps"),
            ConfigChoice(self.engine, self.engine.config, "video",  "multisamples"),
            (_("Fretboard Settings"), self.fretSettingsMenu, _("Change settings related to the fretboard.")),
        ]
        self.videoSettingsMenu = Menu.Menu(self.engine, self.videoSettings, pos = (self.opt_text_x, self.opt_text_y), textColor = self.opt_text_color, selectedColor = self.opt_selected_color)

        self.audioSettings = [
            ConfigChoice(engine, engine.config, "game", "sustain_muting", autoApply = True),   #myfingershurt
            ConfigChoice(engine, engine.config, "game", "mute_drum_fill", autoApply = True),
            ConfigChoice(engine, engine.config, "audio", "mute_last_second", autoApply = True), #MFH
            ConfigChoice(engine, engine.config, "game", "bass_kick_sound", autoApply = True),   #myfingershurt
            ConfigChoice(engine, engine.config, "game", "star_claps", autoApply = True),      #myfingershurt
            ConfigChoice(engine, engine.config, "game", "beat_claps", autoApply = True), #racer
            ConfigChoice(engine, engine.config, "audio", "enable_crowd_tracks", autoApply = True),
            ConfigChoice(engine, engine.config, "audio",  "frequency"),
            ConfigChoice(engine, engine.config, "audio",  "bits"),
            ConfigChoice(engine, engine.config, "audio",  "buffersize"),
            ConfigChoice(engine, engine.config, "game", "result_cheer_loop", autoApply = True), #MFH
            ConfigChoice(engine, engine.config, "game", "cheer_loop_delay", autoApply = True), #MFH
        ]
        self.audioSettingsMenu = Menu.Menu(engine, self.audioSettings, pos = (self.opt_text_x, self.opt_text_y), textColor = self.opt_text_color, selectedColor = self.opt_selected_color)

        advancedSettings = [
            ConfigChoice(engine, engine.config, "performance", "game_priority", autoApply = True),
            ConfigChoice(engine, engine.config, "performance", "restrict_to_first_processor"),  #stump
            ConfigChoice(engine, engine.config, "video", "show_fps"),#evilynux
            ConfigChoice(engine, engine.config, "game", "hopo_debug_disp", autoApply = True),#myfingershurt
            ConfigChoice(engine, engine.config, "debug",   "use_new_vbpm_beta", autoApply = True),#myfingershurt
        ]
        self.advancedSettingsMenu = Menu.Menu(engine, advancedSettings, pos = (self.opt_text_x, self.opt_text_y), textColor = self.opt_text_color, selectedColor = self.opt_selected_color)

        settings = [
            (_("Gameplay Settings"),   self.basicSettingsMenu, _("Settings that affect the rules of the game.")),
            (_("Display Settings"),     self.videoSettingsMenu, _("Theme, neck, resolution, etc.")),
            (_("Audio Settings"),      self.audioSettingsMenu, _("Volume controls, etc.")),
            (_("Advanced Settings"), self.advancedSettingsMenu, _("Settings that probably don't need to be changed.")),
            (_("%s Credits") % (Version.PROGRAM_NAME), lambda: Dialogs.showCredits(engine), _("See who made this game.")),
        ]

        self.settingsToApply = self.videoSettings + \
                               self.basicSettings

        Menu.Menu.__init__(self, engine, settings, name = "advsettings", onCancel = self.applySettings, pos = (self.opt_text_x, self.opt_text_y), textColor = self.opt_text_color, selectedColor = self.opt_selected_color)   #MFH - add position to this so we can move it

    def applySettings(self):
        if self.engine.restartRequired:
            Dialogs.showMessage(self.engine, _("FoFiX needs to restart to apply setting changes."))
            for option in self.settingsToApply:
                if isinstance(option, ConfigChoice):
                    option.apply()
            self.engine.restart()

class GameSettingsMenu(Menu.Menu):
    def __init__(self, engine, gTextColor, gSelectedColor, players):

        settings = [
          VolumeConfigChoice(engine, engine.config, "audio",  "guitarvol", autoApply = True),
          VolumeConfigChoice(engine, engine.config, "audio",  "songvol", autoApply = True),
          VolumeConfigChoice(engine, engine.config, "audio",  "screwupvol", autoApply = True),
          VolumeConfigChoice(engine, engine.config, "audio",  "miss_volume", autoApply = True),
          VolumeConfigChoice(engine, engine.config, "audio",  "single_track_miss_volume", autoApply = True),
          VolumeConfigChoice(engine, engine.config, "audio",  "crowd_volume", autoApply = True),
          VolumeConfigChoice(engine, engine.config, "audio",  "kill_volume", autoApply = True), #MFH
          ActiveConfigChoice(engine, engine.config, "audio",  "SFX_volume", autoApply = True, onChange = engine.data.SetAllSoundFxObjectVolumes, volume = True), #MFH
          ConfigChoice(engine, engine.config, "audio",  "delay", autoApply = True),   #myfingershurt: so the a/v delay can be adjusted in-game
        ]
        Menu.Menu.__init__(self, engine, settings, pos = (.360, .250), viewSize = 5, textColor = gTextColor, selectedColor = gSelectedColor, showTips = False) #Worldrave- Changed Pause-Submenu Position more centered until i add a theme.ini setting.
