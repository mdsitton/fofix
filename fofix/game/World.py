#####################################################################
# -*- coding: iso-8859-1 -*-                                        #
#                                                                   #
# Frets on Fire X (FoFiX)                                           #
# Copyright (C) 2009 FoFiX Team                                     #
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

from fofix.game.Song import SongQueue
from fofix.core.Language import _
from fofix.core import Player
from fofix.game import Dialogs
from fofix.core import SceneFactory

STARTUP_SCENE = "SongChoosingScene"

class World:
    def __init__(self, engine, allowGuitar = True, allowDrum = True, ):
        self.engine       = engine
        self.players      = []
        self.minPlayers   = 1
        self.maxPlayers   = 1
        self.allowGuitar  = allowGuitar
        self.allowDrum    = allowDrum
        self.scene        = None
        self.sceneName    = ""
        self.songQueue    = SongQueue()
        self.playingQueue = False
        self.done         = False
        self.gameName = _("Quickplay")

    def finishGame(self):
        if self.done:
            return
        self.players = []
        if self.scene:
            self.engine.view.popLayer(self.scene)
            self.engine.removeTask(self.scene)
        for layer in self.engine.view.layers:
            if isinstance(layer, Dialogs.LoadingSplashScreen):
                Dialogs.hideLoadingSplashScreen(self.engine, layer)
        self.scene   = None
        self.done    = True
        self.engine.finishGame()

    def startGame(self, **args):
        self.createScene(STARTUP_SCENE, **args)

    def resetWorld(self):
        if self.scene:
            self.engine.view.popLayer(self.scene)
            self.engine.removeTask(self.scene)
        for layer in self.engine.view.layers:
            if isinstance(layer, Dialogs.LoadingSplashScreen):
                Dialogs.hideLoadingSplashScreen(self.engine, layer)
        self.scene = None
        self.sceneName = ""
        self.players = []
        self.songQueue.reset()
        self.engine.mainMenu.restartGame()

    def createPlayer(self, name):
        playerNum = len(self.players)
        player = Player.Player(name, playerNum)
        player.controller = self.engine.input.activeGameControls[playerNum]
        player.controlType = self.engine.input.controls.type[player.controller]
        player.keyList = Player.playerkeys[playerNum]
        player.configController()
        self.players.append(player)
        self.songQueue.parts.append(player.part.id)
        self.songQueue.diffs.append(player.getDifficultyInt())
        if self.scene:
            self.scene.addPlayer(player)

    def deletePlayer(self, number):
        player = self.players.pop(number)
        if self.scene:
            self.scene.removePlayer(player)

    def createScene(self, name, **args):
        if self.scene:
            self.engine.view.popLayer(self.scene)
            self.engine.removeTask(self.scene)
        self.scene = SceneFactory.create(engine = self.engine, name = name, **args)
        self.engine.addTask(self.scene)
        self.engine.view.pushLayer(self.scene)

    def getPlayers(self):
        return self.players
