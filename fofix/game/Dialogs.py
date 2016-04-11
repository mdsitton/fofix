#####################################################################
# -*- coding: iso-8859-1 -*-                                        #
#                                                                   #
# Frets on Fire                                                     #
# Copyright (C) 2006 Sami Kyöstilä                                  #
#               2008 myfingershurt                                  #
#               2008 Glorandwarf                                    #
#               2008 ShiekOdaSandz                                  #
#               2008 QQStarS                                        #
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

"""A bunch of dialog functions for interacting with the user."""

from __future__ import with_statement

import fnmatch
import math
import os

import pygame
from OpenGL.GL import *

from fofix.core.View import Layer, BackgroundLayer
from fofix.core.Input import KeyListener
from fofix.core.Unicode import unicodify
from fofix.core.Image import drawImage
from fofix.game.Credits import Credits
from fofix.core.constants import *
from fofix.core.Language import _
from fofix.game.Menu import Menu
from fofix.core import Log
from fofix.core import Player
from fofix.core import Config

#MFH - for loading phrases
def wrapCenteredText(font, pos, text, rightMargin = 1.0, scale = 0.002, visibility = 0.0, linespace = 1.0, allowshadowoffset = False, shadowoffset = (.0022, .0005)):
    """
    Wrap a piece of text inside given margins.

    @param pos:         (x, y) tuple, x defines the centerline
    @param text:        Text to wrap
    @param rightMargin: Right margin
    @param scale:       Text scale
    @param visibility:  Visibility factor [0..1], 0 is fully visible
    """


    x, y = pos

    #MFH: rewriting WrapCenteredText function to properly wrap lines in a centered fashion around a defined centerline (x)
    sentence = ""
    for n, word in enumerate(text.split(" ")):
        w, h = font.getStringSize(sentence + " " + word, scale = scale)
        if x + (w/2) > rightMargin or word == "\n":
            w, h = font.getStringSize(sentence, scale = scale)
            glPushMatrix()
            glRotate(visibility * (n + 1) * -45, 0, 0, 1)
            if allowshadowoffset == True:
                font.render(sentence, (x - (w/2), y + visibility * n), scale = scale, shadowoffset = shadowoffset)
            else:
                font.render(sentence, (x - (w/2), y + visibility * n), scale = scale)
            glPopMatrix()
            sentence = word
            y += h * linespace
        else:
            if sentence == "" or sentence == "\n":
                sentence = word
            else:
                sentence = sentence + " " + word
    else:
        w, h = font.getStringSize(sentence, scale = scale)
        glPushMatrix()
        glRotate(visibility * (n + 1) * -45, 0, 0, 1)
        if allowshadowoffset == True:
            font.render(sentence, (x - (w/2), y + visibility * n), scale = scale, shadowoffset = shadowoffset)
        else:
            font.render(sentence, (x - (w/2), y + visibility * n), scale = scale)
        glPopMatrix()
        y += h * linespace

    return (x, y)

def wrapText(font, pos, text, rightMargin = 0.9, scale = 0.002, visibility = 0.0):
    """
    Wrap a piece of text inside given margins.

    @param pos:         (x, y) tuple, x defines the left margin
    @param text:        Text to wrap
    @param rightMargin: Right margin
    @param scale:       Text scale
    @param visibility:  Visibility factor [0..1], 0 is fully visible
    """
    x, y = pos
    w = h = 0
    space = font.getStringSize(" ", scale = scale)[0]

    # evilynux - No longer requires "\n" to be in between spaces
    for n, sentence in enumerate(text.split("\n")):
        y += h
        x = pos[0]
        if n == 0:
            y = pos[1]
        for n, word in enumerate(sentence.strip().split(" ")):
            w, h = font.getStringSize(word, scale = scale)
            if x + w > rightMargin:
                x = pos[0]
                y += h
            glPushMatrix()
            glRotate(visibility * (n + 1) * -45, 0, 0, 1)
            font.render(word, (x, y + visibility * n), scale = scale)
            glPopMatrix()
            x += w + space
    return (x - space, y)

class MainDialog(Layer, KeyListener):
    def __init__(self, engine):
        self.engine           = engine
        self.fontDict         = self.engine.data.fontDict
        self.geometry         = self.engine.view.geometry[2:4]
        self.fontScreenBottom = self.engine.data.fontScreenBottom
        self.aspectRatio      = self.engine.view.aspectRatio
        self.drawStarScore    = self.engine.drawStarScore

    def shown(self):
        self.engine.input.addKeyListener(self)

    def hidden(self):
        self.engine.input.removeKeyListener(self)

class GetText(Layer, KeyListener):
    """Text input layer."""
    def __init__(self, engine, prompt = "", text = ""):
        self.text = text
        self.prompt = prompt
        self.engine = engine
        self.time = 0
        self.accepted = False

        self.logClassInits = self.engine.config.get("game", "log_class_inits")
        if self.logClassInits == 1:
            Log.debug("GetText class init (Dialogs.py)...")

        self.sfxVolume    = self.engine.config.get("audio", "SFX_volume")

        self.drumHighScoreNav = self.engine.config.get("game", "drum_navigation")  #MFH



    def shown(self):
        self.engine.input.addKeyListener(self)
        self.engine.input.enableKeyRepeat()

    def hidden(self):
        self.engine.input.removeKeyListener(self)
        self.engine.input.disableKeyRepeat()

    def keyPressed(self, key, unicode):
        self.time = 0
        c = self.engine.input.controls.getMapping(key)
        if key == pygame.K_BACKSPACE and not self.accepted:
            self.text = self.text[:-1]
        elif unicode and ord(unicode) > 31 and not self.accepted:
            self.text += unicode
        elif key == pygame.K_LSHIFT or key == pygame.K_RSHIFT:
            return True
        elif (c in Player.menuYes or key == pygame.K_RETURN) and not self.accepted:   #MFH - adding support for green drum "OK"
            self.engine.view.popLayer(self)
            self.accepted = True
            if c in Player.key1s:
                self.engine.data.acceptSound.setVolume(self.sfxVolume)  #MFH
                self.engine.data.acceptSound.play()
        elif (c in Player.menuNo or key == pygame.K_ESCAPE) and not self.accepted:
            self.text = ""
            self.engine.view.popLayer(self)
            self.accepted = True
            if c in Player.key2s:
                self.engine.data.cancelSound.setVolume(self.sfxVolume)  #MFH
                self.engine.data.cancelSound.play()
        elif c in Player.key4s and not self.accepted:
            self.text = self.text[:-1]
            if c in Player.key4s:
                self.engine.data.cancelSound.setVolume(self.sfxVolume)  #MFH
                self.engine.data.cancelSound.play()
        elif c in Player.key3s and not self.accepted:
            self.text += self.text[len(self.text) - 1]
            self.engine.data.acceptSound.setVolume(self.sfxVolume)  #MFH
            self.engine.data.acceptSound.play()
        elif c in Player.action1s and not self.accepted:
            if len(self.text) == 0:
                self.text = "A"
                return True
            letter = self.text[len(self.text)-1]
            letterNum = ord(letter)
            if letterNum == ord('A'):
                letterNum = ord(' ')
            elif letterNum == ord(' '):
                letterNum = ord('_')
            elif letterNum == ord('_'):
                letterNum = ord('-')
            elif letterNum == ord('-'):
                letterNum = ord('9')
            elif letterNum == ord('0'):
                letterNum = ord('z')
            elif letterNum == ord('a'):
                letterNum = ord('Z')
            else:
                letterNum -= 1
            self.text = self.text[:-1] + chr(letterNum)
            self.engine.data.selectSound.setVolume(self.sfxVolume)  #MFH
            self.engine.data.selectSound.play()
        elif c in Player.action2s and not self.accepted:
            if len(self.text) == 0:
                self.text = "A"
                return True
            letter = self.text[len(self.text)-1]
            letterNum = ord(letter)
            if letterNum == ord('Z'):
                letterNum = ord('a')
            elif letterNum == ord('z'):
                letterNum = ord('0')
            elif letterNum == ord('9'):
                letterNum = ord('-')
            elif letterNum == ord('-'):
                letterNum = ord('_')
            elif letterNum == ord('_'):
                letterNum = ord(' ')
            elif letterNum == ord(' '):
                letterNum = ord('A')
            else:
                letterNum += 1
            self.text = self.text[:-1] + chr(letterNum)
            self.engine.data.selectSound.setVolume(self.sfxVolume)  #MFH
            self.engine.data.selectSound.play()
        return True

    def run(self, ticks):
        self.time += ticks / 50.0

    def render(self, visibility, topMost):
        self.engine.view.setViewport(1,0)
        font = self.engine.data.font
        with self.engine.view.orthogonalProjection(normalize = True):
            v = (1 - visibility) ** 2

            self.engine.fadeScreen(v)
            self.engine.theme.setBaseColor(1 - v)

            if (self.time % 10) < 5 and visibility > .9:
                cursor = "|"
            else:
                cursor = ""

            pos = wrapText(font, (.1, .33 - v), self.prompt)

            self.engine.theme.setSelectedColor(1 - v)

            if self.text is not None:
                pos = wrapText(font, (.1, (pos[1] + v) + .08 + v / 4), self.text)
                font.render(cursor, pos)

class LoadingScreen(Layer, KeyListener):
    """Loading screen layer."""
    def __init__(self, engine, condition, text, allowCancel = False):
        self.engine       = engine
        self.text         = text
        self.condition    = condition
        self.ready        = False
        self.allowCancel  = allowCancel
        self.time         = 0.0

        self.logClassInits = self.engine.config.get("game", "log_class_inits")
        if self.logClassInits == 1:
            Log.debug("LoadingScreen class init (Dialogs.py)...")

        self.loadingx = self.engine.theme.loadingX
        self.loadingy = self.engine.theme.loadingY
        self.allowtext = self.engine.config.get("game", "lphrases")

        #Get theme
        self.theme = self.engine.data.theme

    def shown(self):
        self.engine.input.addKeyListener(self)

    def keyPressed(self, key, unicode):
        c = self.engine.input.controls.getMapping(key)
        if self.allowCancel and c in Player.menuNo:
            self.engine.view.popLayer(self)
        return True

    def hidden(self):
        self.engine.input.removeKeyListener(self)

    def run(self, ticks):
        self.time += ticks / 50.0
        if not self.ready and self.condition():
            self.engine.view.popLayer(self)
            self.ready = True

    def render(self, visibility, topMost):
        self.engine.view.setViewport(1,0)
        font = self.engine.data.loadingFont

        if not font:
            return

        with self.engine.view.orthogonalProjection(normalize = True):
            v = (1 - visibility) ** 2
            self.engine.fadeScreen(v)

            w, h = self.engine.view.geometry[2:4]
            self.loadingImg = self.engine.data.loadingImage

            #MFH - auto-scaling of loading screen
            #Volshebnyi - fit to screen applied
            if self.loadingImg:
                drawImage(self.loadingImg, scale = (1.0,-1.0), coord = (w/2,h/2), stretched = FULL_SCREEN)

            self.engine.theme.setBaseColor(1 - v)
            w, h = font.getStringSize(self.text)

            if self.loadingx != None:
                if self.loadingy != None:
                    x = self.loadingx - w / 2
                    y = self.loadingy - h / 2 + v * .5
                else:
                    x = self.loadingx - w / 2
                    y = .6 - h / 2 + v * .5
            elif self.loadingy != None:
                x = .5 - w / 2
                y = .6 - h / 2 + v * .5
            else:
                x = .5 - w / 2
                y = .6 - h / 2 + v * .5

            if self.allowtext:
                if self.theme == 1:
                    font.render(self.text, (x, y), shadowoffset = (self.engine.theme.shadowoffsetx, self.engine.theme.shadowoffsety))
                else:
                    font.render(self.text, (x, y))

class MessageScreen(Layer, KeyListener):
    """Message screen layer."""
    def __init__(self, engine, text, prompt = _("<OK>")):
        self.engine = engine
        self.text = text
        self.time = 0.0
        self.prompt = prompt

        self.logClassInits = self.engine.config.get("game", "log_class_inits")
        if self.logClassInits == 1:
            Log.debug("MessageScreen class init (Dialogs.py)...")


    def shown(self):
        self.engine.input.addKeyListener(self)

    def keyPressed(self, key, unicode):
        c = self.engine.input.controls.getMapping(key)
        if c in (Player.menuYes + Player.menuNo) or key in [pygame.K_RETURN, pygame.K_ESCAPE, pygame.K_LCTRL, pygame.K_RCTRL]:
            self.engine.view.popLayer(self)
        return True

    def hidden(self):
        self.engine.input.removeKeyListener(self)

    def run(self, ticks):
        self.time += ticks / 50.0

    def render(self, visibility, topMost):
        self.engine.view.setViewport(1,0)
        font = self.engine.data.font

        if not font:
            return

        with self.engine.view.orthogonalProjection(normalize = True):
            v = (1 - visibility) ** 2
            self.engine.fadeScreen(v)

            x = .1
            y = .3 + v * 2
            self.engine.theme.setBaseColor(1 - v)
            pos = wrapText(font, (x, y), self.text, visibility = v)

            w, h = font.getStringSize(self.prompt, scale = 0.001)
            x = .5 - w / 2
            y = pos[1] + 3 * h + v * 2
            self.engine.theme.setSelectedColor(1 - v)
            font.render(self.prompt, (x, y), scale = 0.001)

class PartDiffChooser(MainDialog):
    """Part and difficulty select layer"""
    def __init__(self, engine, parts, info, players, back = False):
        MainDialog.__init__(self, engine)
        self.parts   = parts
        self.info    = info
        self.players = players
        self.theme   = engine.theme

        self.retVal  = None

        self.gameModeText = self.engine.world.gameName

        self.logClassInits = self.engine.config.get("game", "log_class_inits")
        if self.logClassInits == 1:
            Log.debug("PartDiffChooser class init (Dialogs.py)...")
        self.time    = 0.0

        self.yes        = []
        self.no         = []
        self.conf       = []
        self.up         = []
        self.down       = []

        for player in self.players:
            self.yes.extend(player.yes)
            self.no.extend(player.no)
            self.conf.extend(player.conf)
            self.up.extend(player.up)
            self.down.extend(player.down)

        self.partImages     = self.engine.data.partImages
        self.keyControl     = 0
        self.scrolling      = [0 for i in self.players]
        self.rate           = [0 for i in self.players]
        self.delay          = [0 for i in self.players]
        self.scroller       = [0, self.scrollUp, self.scrollDown]
        self.selected       = []
        self.mode           = [back and 1 or 0 for i in self.players]
        self.readyPlayers   = []
        for i in range(len(self.players)):
            if self.mode[i] == 1:
                if len(self.info.partDifficulties[self.players[i].part.id]) == 1:
                    self.mode[i] -= 1
                else:
                    for j, d in enumerate(self.info.partDifficulties[self.players[i].part]):
                        if d == self.players[i].difficulty:
                            self.selected.append(j)
                            break
                    else:
                        self.selected.append(0)
            if self.mode[i] == 0:
                if len(self.parts[i]) == 1:
                    self.players[i].part = self.parts[i][0]
                    self.mode[i] += 1
                    if len(self.info.partDifficulties[self.players[i].part.id]) == 1:
                        self.players[i].difficulty = self.info.partDifficulties[self.players[i].part.id][0]
                        self.readyPlayers.append(i)
                        self.selected.append(0)
                    else:
                        for j, d in enumerate(self.info.partDifficulties[self.players[i].part.id]):
                            if d == self.players[i].difficulty:
                                self.selected.append(j)
                                break
                        else:
                            self.selected.append(0)
                else:
                    for j, p in enumerate(self.parts[i]):
                        if p == self.players[i].part:
                            self.selected.append(j)
                            break
                    else:
                        self.selected.append(0)
        if len(self.readyPlayers) == len(self.players):
            self.retval = True
            self.engine.view.popLayer(self)
            return

        if os.path.isdir(os.path.join(self.engine.data.path,"themes",self.engine.data.themeLabel,"setlist","parts")):
            self.engine.data.loadAllImages(self, os.path.join("themes",self.engine.data.themeLabel,"setlist","parts"))

    def scrollUp(self, i):
        self.selected[i] -= 1
        if self.selected[i] < 0:
            if self.mode[i] == 0:
                self.selected[i] = len(self.parts[i]) - 1
            elif self.mode[i] == 1:
                self.selected[i] = len(self.info.partDifficulties[self.players[i].part.id]) - 1

    def scrollDown(self, i):
        self.selected[i] += 1
        if self.mode[i] == 0:
            if self.selected[i] == len(self.parts[i]):
                self.selected[i] = 0
        elif self.mode[i] == 1:
            if self.selected[i] == len(self.info.partDifficulties[self.players[i].part.id]):
                self.selected[i] = 0

    def keyPressed(self, key, unicode):
        c = self.engine.input.controls.getMapping(key)
        for i in range(len(self.players)):
            if key in [pygame.K_ESCAPE, pygame.K_RETURN, pygame.K_LCTRL, pygame.K_RCTRL, pygame.K_UP, pygame.K_DOWN, pygame.K_RIGHT, pygame.K_LEFT, pygame.K_SPACE]:
                continue
            if c and c in self.players[i].keyList:
                break
        else:
            i = self.keyControl
        if c in self.yes + [self.players[i].keyList[Player.UP]] or key == pygame.K_RETURN:
            if self.mode[i] == 0:
                self.players[i].part = self.parts[i][self.selected[i]]
                for j, d in enumerate(self.info.partDifficulties[self.players[i].part.id]):
                    if d == self.players[i].difficulty:
                        self.selected[i] = j
                else:
                    self.selected[i] = 0
                self.mode[i] += 1
            elif self.mode[i] == 1:
                self.players[i].difficulty = self.info.partDifficulties[self.players[i].part.id][self.selected[i]]
                if i not in self.readyPlayers:
                    self.engine.data.acceptSound.play()
                    self.readyPlayers.append(i)
                if len(self.readyPlayers) == len(self.players):
                    self.retVal = True
                    self.engine.view.popLayer(self)
            return True
        elif c in self.no + [self.players[i].keyList[Player.KEY2]] or key == pygame.K_ESCAPE:
            if self.mode[i] == 0:
                if c in Player.menuNo:
                    self.engine.data.cancelSound.play()
                    self.retVal = False
                    self.engine.view.popLayer(self)
            elif self.mode[i] == 1:
                self.engine.data.cancelSound.play()
                if i in self.readyPlayers:
                    self.readyPlayers.remove(i)
                else:
                    self.mode[i] = 0
                    for j, p in enumerate(self.parts[i]):
                        if p == self.players[i].part:
                            self.selected[i] = j
                            break
                    else:
                        self.selected[i] = 0
            return True
        elif i in self.readyPlayers:
            return True
        elif c in self.up + [self.players[i].keyList[Player.UP]] or key == pygame.K_LEFT or key == pygame.K_UP:
            self.scrolling[i] = 1
            self.scrollUp(i)
            self.delay[i] = self.engine.scrollDelay
        elif c in self.down + [self.players[i].keyList[Player.DOWN]] or key == pygame.K_RIGHT or key == pygame.K_DOWN:
            self.scrolling[i] = 2
            self.scrollDown(i)
            self.delay[i] = self.engine.scrollDelay
        elif key == pygame.K_SPACE:
            pass
        return True

    def keyReleased(self, key):
        c = self.engine.input.controls.getMapping(key)
        for i in range(len(self.players)):
            if key in [pygame.K_ESCAPE, pygame.K_RETURN, pygame.K_LCTRL, pygame.K_RCTRL, pygame.K_UP, pygame.K_DOWN, pygame.K_RIGHT, pygame.K_LEFT]:
                continue
            if c and c in self.players[i].keyList:
                break
        else:
            i = self.keyControl
        self.scrolling[i] = 0

    def run(self, ticks):
        self.time += ticks/50.0
        for i in range(len(self.players)):
            if self.scrolling[i] > 0:
                self.delay[i] -= ticks
                self.rate[i] += ticks
                if self.delay[i] <= 0 and self.rate[i] >= self.engine.scrollRate:
                    self.rate[i] = 0
                    self.scroller[self.scrolling[i]](i)
        self.engine.theme.partDiff.run(ticks)

    def render(self, visibility, topMost):
        self.engine.view.setViewport(1,0)
        w, h = self.geometry

        with self.engine.view.orthogonalProjection(normalize = True):
            if self.img_background:
                drawImage(self.img_background, scale = (1.0, -1.0), coord = (w/2,h/2), stretched = FULL_SCREEN)
            self.theme.partDiff.renderPanels(self)

class ItemChooser(BackgroundLayer, KeyListener):
    """Item menu layer."""
    def __init__(self, engine, items, selected = None, prompt = "", pos = None):    #MFH
        self.prompt         = prompt
        self.engine         = engine

        self.logClassInits = self.engine.config.get("game", "log_class_inits")
        if self.logClassInits == 1:
            Log.debug("ItemChooser class init (Dialogs.py)...")

        self.accepted       = False
        self.selectedItem   = None
        self.time           = 0.0

        self.font = self.engine.data.streakFont2
        self.promptScale = 0.002
        self.promptWidth, self.promptHeight = self.font.getStringSize(self.prompt, scale=self.promptScale)
        widthOfSpace, heightOfSpace = self.font.getStringSize(" ", scale=self.promptScale)

        if pos: #MFH
            self.songSelectSubmenuOffsetLines = self.engine.theme.songSelectSubmenuOffsetLines
            self.songSelectSubmenuOffsetSpaces = self.engine.theme.songSelectSubmenuOffsetSpaces
            self.posX, self.posY = pos
            wrapX, wrapY = wrapText(self.font, (self.posX, self.posY), self.prompt, scale = self.promptScale)
            self.menu = Menu(self.engine, choices = [(c, self._callbackForItem(c)) for c in items], onClose = self.close, onCancel = self.cancel, font = self.engine.data.streakFont2, pos = (self.posX + widthOfSpace*(self.songSelectSubmenuOffsetSpaces+1), wrapY + self.promptHeight*(self.songSelectSubmenuOffsetLines+1)) )
        else:
            self.posX = .1    #MFH - default
            self.posY = .05   #MFH - default
            self.menu = Menu(self.engine, choices = [(c, self._callbackForItem(c)) for c in items], onClose = self.close, onCancel = self.cancel, font = self.engine.data.streakFont2)

        if selected and selected in items:
            self.menu.selectItem(items.index(selected))

        #Get theme
        self.theme = self.engine.data.theme

    def _callbackForItem(self, item):
        def cb():
            self.chooseItem(item)
        return cb

    def chooseItem(self, item):
        self.selectedItem = item
        self.engine.view.popLayer(self.menu)
        self.engine.view.popLayer(self)

    def cancel(self):
        self.accepted = True
        self.engine.view.popLayer(self)

    def close(self):
        self.accepted = True
        self.engine.view.popLayer(self)

    def shown(self):
        self.engine.view.pushLayer(self.menu)

    def getSelectedItem(self):
        return self.selectedItem

    def run(self, ticks):
        self.time += ticks / 50.0

    def render(self, visibility, topMost):
        v = (1 - visibility) ** 2

        # render the background
        self.engine.view.setViewport(1,0)
        w, h, = self.engine.view.geometry[2:4]

        #MFH - auto background scaling
        if self.engine.data.optionsBG:
            drawImage(self.engine.data.optionsBG, scale = (1.0, -1.0), coord = (w/2,h/2), stretched = FULL_SCREEN)

        with self.engine.view.orthogonalProjection(normalize = True):
            glEnable(GL_BLEND)
            glBlendFunc(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA)
            glEnable(GL_COLOR_MATERIAL)
            self.engine.theme.setBaseColor(1 - v)
            wrapText(self.font, (self.posX, self.posY - v), self.prompt, scale = self.promptScale)

def _runDialog(engine, dialog):
    """Run a dialog in a sub event loop until it is finished."""
    if not engine.running:
        return

    engine.view.pushLayer(dialog)

    while engine.running and dialog in engine.view.layers:
        engine.run()

def getText(engine, prompt, text = ""):
    """
    Get a string of text from the user.

    @param engine:  Game engine
    @param prompt:  Prompt shown to the user
    @param text:    Default text
    """
    d = GetText(engine, prompt, text)
    _runDialog(engine, d)
    return d.text

def getKey(engine, prompt, key = None, specialKeyList = []):
    """
    Ask the user to choose a key.

    @param engine:          Game engine
    @param prompt:          Prompt shown to the user
    @param key:             Default key
    @param specialKeyList:  A list of keys that are ineligible.
    """
    d = GetKey(engine, prompt, key, specialKeyList = specialKeyList)
    _runDialog(engine, d)
    return d.key

def chooseItem(engine, items, prompt = "", selected = None, pos = None):   #MFH
    """
    Ask the user to choose one item from a list.

    @param engine:    Game engine
    @param items:     List of items
    @param prompt:    Prompt shown to the user
    @param selected:  Item selected by default
    @param pos:       Position tuple (x,y) for placing the menu
    """
    d = ItemChooser(engine, items, prompt = prompt, selected = selected, pos = pos)
    _runDialog(engine, d)
    return d.getSelectedItem()

def choosePartDiffs(engine, parts, info, players):
    """
    Have the user select their part and difficulty.

    """
    d = PartDiffChooser(engine, parts, info, players)
    _runDialog(engine, d)
    return d.retVal

# evilynux - Show credits
def showCredits(engine):
    d = Credits(engine)
    _runDialog(engine, d)

def showLoadingScreen(engine, condition, text = _("Loading..."), allowCancel = False):
    """
    Show a loading screen until a condition is met.

    @param engine:      Game engine
    @param condition:   A function that will be polled until it returns a true value
    @param text:        Text shown to the user
    @type  allowCancel: bool
    @param allowCancel: Can the loading be canceled
    @return:            True if the condition was met, False if the loading was canceled.
    """

    # poll the condition first for some time
    n = 0
    while n < 32:
        n += 1
        if condition():
            return True
        engine.run()

    d = LoadingScreen(engine, condition, text, allowCancel)
    _runDialog(engine, d)
    return d.ready

def showMessage(engine, text):
    """
    Show a message to the user.

    @param engine:  Game engine
    @param text:    Message text
    """
    Log.notice("%s" % text)
    d = MessageScreen(engine, text)
    _runDialog(engine, d)

# glorandwarf: added derived class LoadingSplashScreen
class LoadingSplashScreen(Layer, KeyListener):
    """Loading splash screen layer"""
    def __init__(self, engine, text):
        self.engine       = engine
        self.text         = text
        self.time         = 0.0
        self.loadingx = self.engine.theme.loadingX
        self.loadingy = self.engine.theme.loadingY
        self.textColor = self.engine.theme.loadingColor
        self.allowtext = self.engine.config.get("game", "lphrases")
        self.fScale = self.engine.theme.loadingFScale
        self.rMargin = self.engine.theme.loadingRMargin
        self.lspacing = self.engine.theme.loadingLSpacing
        self.loadingImg = self.engine.data.loadingImage

        self.logClassInits = self.engine.config.get("game", "log_class_inits")
        if self.logClassInits == 1:
            Log.debug("LoadingSplashScreen class init (Dialogs.py)...")

        #Get theme
        self.theme = self.engine.data.theme

    def shown(self):
        self.engine.input.addKeyListener(self)

    def keyPressed(self, key, unicode):
        return True

    def hidden(self):
        self.engine.input.removeKeyListener(self)

    def run(self, ticks):
        self.time += ticks / 50.0

    def render(self, visibility, topMost):
        self.engine.view.setViewport(1,0)
        font = self.engine.data.loadingFont   #MFH - new font support

        if not font:
            return

        with self.engine.view.orthogonalProjection(normalize = True):
            v = (1 - visibility) ** 2
            self.engine.fadeScreen(v)
            w, h = self.engine.view.geometry[2:4]
            if self.loadingImg:
                drawImage(self.loadingImg, scale = (1.0,-1.0), coord = (w/2,h/2), stretched = FULL_SCREEN)

            self.engine.theme.setBaseColor(1 - v)
            w, h = font.getStringSize(self.text, scale=self.fScale)

            x = self.loadingx
            y = self.loadingy - h / 2 + v * .5

            #akedrou - support for Loading Text Color
            glColor3f(*self.textColor)

            # evilynux - Made text about 2 times smaller (as requested by worldrave)
            if self.allowtext:
                if self.theme == 1:
                    wrapCenteredText(font, (x,y), self.text, scale = self.fScale, rightMargin = self.rMargin, linespace = self.lspacing, allowshadowoffset = True, shadowoffset = (self.engine.theme.shadowoffsetx, self.engine.theme.shadowoffsety))
                else:
                    wrapCenteredText(font, (x,y), self.text, scale = self.fScale, rightMargin = self.rMargin, linespace = self.lspacing)

def showLoadingSplashScreen(engine, text = _("Loading...")):
    splash = LoadingSplashScreen(engine, text)
    engine.view.pushLayer(splash)
    engine.run()
    return splash

def changeLoadingSplashScreenText(engine, splash, text=_("Loading...")):
    splash.text = text
    engine.run()

def hideLoadingSplashScreen(engine, splash):
    engine.view.popLayer(splash)
