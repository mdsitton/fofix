#####################################################################
# -*- coding: iso-8859-1 -*-                                        #
#                                                                   #
# Frets on Fire                                                     #
# Copyright (C) 2006 Sami Kyöstilä                                  #
#               2008 myfingershurt                                  #
#               2008 Glorandwarf                                    #
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

import pygame

try:
    import pygame.midi
    haveMidi = True
except ImportError:
    haveMidi = False

haveMidi = False
from fofix.core.Player import Controls
from fofix.core.Task import Task
from fofix.core import Player
from fofix.core import Config
from fofix.core import Audio
from fofix.core import Log

class KeyListener:
    def keyPressed(self, key, unicode):
        pass

    def keyReleased(self, key):
        pass

    def lostFocus(self):
        pass

    def exitRequested(self):
        pass

class MouseListener:
    def mouseButtonPressed(self, button, pos):
        pass

    def mouseButtonReleased(self, button, pos):
        pass

    def mouseMoved(self, pos, rel):
        pass

class SystemEventListener:
    def screenResized(self, size):
        pass

    def restartRequested(self):
        pass

    def musicFinished(self):
        pass

    def quit(self):
        pass

class Input(Task):
    def __init__(self):

        self.logClassInits = Config.get("game", "log_class_inits")
        if self.logClassInits == 1:
            Log.debug("Input class init (Input.py)...")

        Task.__init__(self)
        self.mouse                = pygame.mouse
        self.mouseListeners       = []
        self.keyListeners         = []
        self.systemListeners      = []
        self.controls             = Controls()
        self.activeGameControls   = [0]
        self.type1                = self.controls.type[0]
        self.disableKeyRepeat()

        self.gameGuitars = 0
        self.gameDrums   = 0

    def showMouse(self):
        pygame.mouse.set_visible(True)

    def hideMouse(self):
        pygame.mouse.set_visible(False)

    def reloadControls(self):
        self.controls = Controls()

    def pluginControls(self):
        self.gameDrums = 0
        self.gameGuitars = 0
        for i in self.activeGameControls:
            if self.controls.type[i] in Player.DRUMTYPES:
                self.gameDrums += 1
            elif self.controls.type[i] in Player.GUITARTYPES:
                self.gameGuitars += 1

    def disableKeyRepeat(self):
        pygame.key.set_repeat(0, 0)

    def enableKeyRepeat(self):
        pygame.key.set_repeat(300, 30)

    def addKeyListener(self, listener):
        if not listener in self.keyListeners:
            self.keyListeners.append(listener)

    def removeKeyListener(self, listener):
        if listener in self.keyListeners:
            self.keyListeners.remove(listener)

    def addSystemEventListener(self, listener):
        if not listener in self.systemListeners:
            self.systemListeners.append(listener)

    def removeSystemEventListener(self, listener):
        if listener in self.systemListeners:
            self.systemListeners.remove(listener)

    def broadcastEvent(self, listeners, function, *args):
        for l in reversed(listeners):
            if getattr(l, function)(*args):
                return True
        else:
            return False

    def broadcastSystemEvent(self, name, *args):
        return self.broadcastEvent(self.systemListeners, name, *args)

    def run(self, ticks):
        pygame.event.pump()
        for event in pygame.event.get():
            if event.type == pygame.KEYDOWN:
                self.broadcastEvent(self.keyListeners, "keyPressed", event.key, event.unicode)
            elif event.type == pygame.KEYUP:
                self.broadcastEvent(self.keyListeners, "keyReleased", event.key)
            elif event.type == pygame.MOUSEMOTION:
                self.broadcastEvent(self.mouseListeners, "mouseMoved", event.pos, event.rel)
            elif event.type == pygame.MOUSEBUTTONDOWN:
                self.broadcastEvent(self.mouseListeners, "mouseButtonPressed", event.button, event.pos)
            elif event.type == pygame.MOUSEBUTTONUP:
                self.broadcastEvent(self.mouseListeners, "mouseButtonReleased", event.button, event.pos)
            elif event.type == pygame.VIDEORESIZE:
                self.broadcastEvent(self.systemListeners, "screenResized", event.size)
            elif event.type == pygame.QUIT:
                self.broadcastEvent(self.systemListeners, "quit")
            elif event.type == pygame.ACTIVEEVENT: # akedrou - catch for pause onLoseFocus
                if (event.state == 2 or event.state == 6) and event.gain == 0:
                    self.broadcastEvent(self.keyListeners, "lostFocus") # as a key event, since Scene clients don't handle system events
