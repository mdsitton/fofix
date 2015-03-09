#####################################################################
# -*- coding: iso-8859-1 -*-                                        #
#                                                                   #
# Frets on Fire X                                                   #
# Copyright (C) 2006 Sami Kyöstilä                                  #
#               2008 rchiav                                         #
#               2009 Team FoFiX                                     #
#               2009 akedrou                                        #
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

from __future__ import with_statement

import shutil
import os

from OpenGL.GL import *
import pygame

from fofix.core.Player import GUITARTYPES, DRUMTYPES, MICTYPES
from fofix.core.Input import KeyListener
from fofix.core.Image import drawImage
from fofix.core.constants import *
from fofix.core.Language import _
from fofix.core.View import Layer
from fofix.game import Dialogs
from fofix.core import Player
from fofix.game import Song


class WorldNotStarted(Exception):
    def __str__(self):
        return _("World error. Please try again.")

class Lobby(Layer, KeyListener):
    def __init__(self, engine):
        if not engine.world:
            raise WorldNotStarted
        self.engine         = engine
        self.minPlayers     = self.engine.world.minPlayers
        self.maxPlayers     = self.engine.world.maxPlayers
        self.keyControl     = 0
        self.keyGrab        = False
        self.scrolling      = [0,0,0,0]
        self.rate           = [0,0,0,0]
        self.delay          = [0,0,0,0]
        self.gameStarted    = False
        self.done           = True
        self.active         = False
        self.blockedItems   = [1]
        self.selectedItems  = []
        self.blockedPlayers = []
        self.selectedPlayers = []
        self.playerList     = [None for i in range(4)]

        self.fontDict         = self.engine.data.fontDict

        self.engine.input.activeGameControls = [i for i in range(4)]
        self.engine.input.pluginControls()

        self.theme = self.engine.theme

        self.playerNames = Player.playername
        self.playerPrefs = Player.playerpref

    def shown(self):
        self.engine.input.addKeyListener(self)

    def hidden(self):
        self.engine.input.removeKeyListener(self)
        if not self.gameStarted:
            self.engine.view.pushLayer(self.engine.mainMenu)    #rchiav: use already-existing MainMenu instance

    def preparePlayers(self):
        c = []
        n = []
        for i, name in enumerate(self.playerList):
            if name is None:
                continue
            c.append(name[0])
            n.append(name[1])
            self.engine.config.set("game", "player%d" % i, name[1])
        self.engine.input.activeGameControls = c
        self.engine.input.pluginControls()
        for name in n: #this needs to be done after pluginControls so controller assignments are handled properly.
            self.engine.world.createPlayer(name)

    def handleGameStarted(self):
        self.gameStarted = True
        self.engine.gameStarted = True
        self.engine.view.popLayer(self)

    def keyPressed(self, key, unicode):

        if self.gameStarted:
            return True

        if key == pygame.K_ESCAPE:
            self.engine.data.cancelSound.play()
            self.engine.view.popLayer(self)

        elif key == pygame.K_RETURN:

            self.playerList[0] = (0, self.playerNames[0])
            self.gameStarted = True
            self.engine.menuMusic = False
            self.preparePlayers()
            self.engine.world.startGame()
            self.handleGameStarted()

        return True

    def render(self, visibility, topMost):

        with self.engine.view.orthogonalProjection(normalize = True):
            self.renderPanels()


    def renderPanels(self):
        optionFont    = self.fontDict[self.theme.lobbyOptionFont]
        glColor3f(1,1,1)
        optionFont.render("Test", (.5, .5))
