#####################################################################
# -*- coding: iso-8859-1 -*-                                        #
#                                                                   #
# Frets on Fire                                                     #
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


import random
import string
import sys
import os

from fofix.core.View import BackgroundLayer
from fofix.core.Image import drawImage
from fofix.game.Lobby import Lobby
from fofix.core.constants import *
from fofix.core.Language import _
from fofix.game.Menu import Menu
from fofix.core import Config
from fofix.game import Dialogs
from fofix.core import Audio
from fofix.core import Settings
from fofix.core import Version
from fofix.core import VFS
from fofix.core import Log


class MainMenu(BackgroundLayer):
    def __init__(self, engine):
        self.engine              = engine

        self.logClassInits = Config.get("game", "log_class_inits")
        if self.logClassInits == 1:
            Log.debug("MainMenu class init (MainMenu.py)...")

        self.time                = 0.0
        self.nextLayer           = None
        self.visibility          = 0.0
        self.active              = False

        self.showStartupMessages = False

        exists = 0

        #Get theme
        self.theme       = self.engine.data.theme
        self.themeCoOp   = self.engine.data.themeCoOp
        self.themename   = self.engine.data.themeLabel
        self.useSoloMenu = self.engine.theme.use_solo_submenu

        self.menux = self.engine.theme.menuPos[0]
        self.menuy = self.engine.theme.menuPos[1]

        self.rbmenu = self.engine.theme.menuRB

        #MFH
        self.main_menu_scale = self.engine.theme.main_menu_scaleVar
        self.main_menu_vspacing = self.engine.theme.main_menu_vspacingVar

        self.opt_text_color     = self.engine.theme.opt_text_colorVar
        self.opt_selected_color = self.engine.theme.opt_selected_colorVar

        self.opt_bkg_size = [float(i) for i in self.engine.theme.opt_bkg_size]
        self.opt_text_color = self.engine.theme.opt_text_colorVar
        self.opt_selected_color = self.engine.theme.opt_selected_colorVar

        strQuickplay = "Quickplay"
        strSettings = "Settings"
        strQuit = "Quit"

        mainMenu = [
          (strQuickplay, lambda:        self.newLocalGame()),
          ((strSettings,"settings"),  self.settingsMenu),
          (strQuit,        self.quit),
        ]


        w, h, = self.engine.view.geometry[2:4]

        self.menu = Menu(self.engine, mainMenu, onClose = lambda: self.engine.view.popLayer(self), pos = (self.menux, .75-(.75*self.menuy)))

        engine.mainMenu = self    #Points engine.mainMenu to the one and only MainMenu object instance

        ## whether the main menu has come into view at least once
        self.shownOnce = False

    def settingsMenu(self):
        self.settingsMenuObject = Settings.SettingsMenu(self.engine)
        return self.settingsMenuObject

    def shown(self):
        self.engine.view.pushLayer(self.menu)

    def hidden(self):
        self.engine.view.popLayer(self.menu)
        if self.nextLayer:
            self.engine.view.pushLayer(self.nextLayer())
            self.nextLayer = None
        else:
            self.engine.quit()

    def quit(self):
        self.engine.view.popLayer(self.menu)

    def launchLayer(self, layerFunc):
        if not self.nextLayer:
            self.nextLayer = layerFunc
            self.engine.view.popAllLayers()

    def newLocalGame(self, players=1, maxplayers = None, allowGuitar = True, allowDrum = True): #mode1p=0(quickplay),1(practice),2(career) / mode2p=0(faceoff),1(profaceoff)
        self.engine.startWorld(players, maxplayers, allowGuitar, allowDrum)
        self.launchLayer(lambda: Lobby(self.engine))

    def restartGame(self):
        splash = Dialogs.showLoadingSplashScreen(self.engine, "")
        self.engine.view.pushLayer(Lobby(self.engine))
        Dialogs.hideLoadingSplashScreen(self.engine, splash)

    def showMessages(self):
        msg = self.engine.startupMessages.pop()
        self.showStartupMessages = False
        Dialogs.showMessage(self.engine, msg)

    def run(self, ticks):
        self.time += ticks / 50.0
        if self.showStartupMessages:
            self.showMessages()
        if len(self.engine.startupMessages) > 0:
            self.showStartupMessages = True


    def render(self, visibility, topMost):
        pass