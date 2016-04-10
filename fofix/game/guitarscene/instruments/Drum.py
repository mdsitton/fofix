#####################################################################
# -*- coding: iso-8859-1 -*-                                        #
#                                                                   #
# Frets on Fire                                                     #
# Copyright (C) 2006 Sami Kyostila                                  #
#               2008 Alarian                                        #
#               2008 myfingershurt                                  #
#               2008 Glorandwarf                                    #
#               2008 Capo                                           #
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
import math

import numpy as np
from OpenGL.GL import *

from fofix.game.guitarscene.instruments.Instrument import Instrument
from fofix.game.Song import Note, Tempo
from fofix.core.Image import draw3Dtex
from fofix.core.Mesh import Mesh
from fofix.game import Song
from fofix.core import cmgl
from fofix.core import Log

#Normal guitar key color order: Green, Red, Yellow, Blue, Orange
#Drum fret color order: Red, Yellow, Blue, Green
#actual drum note numbers:
#0 = bass drum (stretched Orange fret), normally Green fret
#1 = drum Red fret, normally Red fret
#2 = drum Yellow fret, normally Yellow fret
#3 = drum Blue fret, normally Blue fret
#4 = drum Green fret, normally Orange fret
#
#So, with regard to note number coloring, swap note.number 0's color with note.number 4.

#akedrou - 5-drum support is now available.
# to enable it, only here and Player.drums should need changing.

class Drum(Instrument):
    def __init__(self, engine, playerObj, player = 0):

        self.isDrum = True
        self.isBassGuitar = False
        self.isVocal = False

        super(Drum, self).__init__(engine, playerObj, player)


        self.drumsHeldDown = [0, 0, 0, 0, 0]

        self.lastFretWasBassDrum = False
        self.lastFretWasT1 = False   #Faaa Drum sound
        self.lastFretWasT2 = False
        self.lastFretWasT3 = False
        self.lastFretWasC = False


        self.matchingNotes = None

        self.strings        = 4
        self.strings2       = 5

        self.openFretActivity = 0.0
        self.openFretColor  = self.fretColors[5]

        self.lanenumber     = float(4)
        self.fretImgColNumber = float(6)

        self.logClassInits = self.engine.config.get("game", "log_class_inits")
        if self.logClassInits == 1:
            Log.debug("Drum class initialization!")

        self.fretActivity   = [0.0] * self.strings

        #blazingamer
        self.opencolor = self.fretColors[5]
        self.rockLevel = 0.0

        if self.engine.config.get("game", "large_drum_neck"):
            self.boardWidth     *= (4.0/3.0)
            self.boardLength    *= (4.0/3.0)

        #Get theme
        #now theme determination logic is only in data.py:
        self.theme = self.engine.data.theme

        self.tailsEnabled = False

        self.loadImages()

        self.barsColor = self.engine.theme.barsColor

    def loadNotes(self):
        super(Drum, self).loadNotes()
        engine = self.engine

        get = lambda file: self.checkPath("tails", file)

        size = (self.boardWidth/1.9, (self.boardWidth/self.strings)/3.0)
        self.openVtx = np.array([[-size[0],  0.0, size[1]],
                                 [size[0],  0.0, size[1]],
                                 [-size[0], 0.0, -size[1]],
                                 [size[0], 0.0, -size[1]]],
                                 dtype=np.float32)

        self.noteTexCoord = [[np.array([[i/float(self.strings), s/6.0],
                                       [(i+1)/float(self.strings), s/6.0],
                                       [i/float(self.strings), (s+1)/6.0],
                                       [(i+1)/float(self.strings), (s+1)/6.0]],
                                       dtype=np.float32)
                              for i in range(self.strings)] for s in range(0,5,2)]
        self.openTexCoord = [np.array([[0.0, s/6.0],
                                       [1.0, s/6.0],
                                       [0.0, (s+1)/6.0],
                                       [1.0, (s+1)/6.0]], dtype=np.float32) for s in range(1,6,2)]


    def loadFrets(self):
        super(Drum, self).loadFrets()
        engine = self.engine
        themename = self.engine.data.themeLabel

        get = lambda file: self.checkPath("frets", file)

        engine.loadImgDrawing(self, "fretButtons", os.path.join("themes",themename, "frets", "drum", "fretbuttons.png"))

    def render(self, visibility, song, pos, controls, killswitch):
        notes = self.getRequiredNotesForRender(song, pos)
        self.renderFrets(visibility, song, controls)
        self.renderOpenNotes(notes, visibility, song, pos)
        self.renderNotes(notes, visibility, song, pos)
        self.renderFlames(notes, song, pos)

    def hitNote(self, time, note):
        self.playedNotes.append([time, note])
        note.played = True
        return True

    def startPick(self, song, pos, controls, hopo = False):
        if not song:
            return False
        if not song.readyToGo:
            return

        self.matchingNotes = self.getRequiredNotes(song, pos)    #MFH - ignore skipped notes please!

        # no self.matchingNotes?
        if not self.matchingNotes:
            return False
        self.playedNotes = []

        #adding bass drum hit every bass fret:
        for time, note in self.matchingNotes:
            for i in range(5):
                if note.number == i and (controls.getState(self.keys[i]) or controls.getState(self.keys[i+5])) and self.drumsHeldDown[i] > 0:
                    return self.hitNote(time, note)

        return False


    def run(self, ticks, pos, song, controls):
        if not self.paused:
            self.time += ticks

        for i in range(len(self.drumsHeldDown)):
            if self.drumsHeldDown[i] > 0:
                self.drumsHeldDown[i] -= ticks
                if self.drumsHeldDown[i] < 0:
                    self.drumsHeldDown[i] = 0

        activeFrets = [(note.number - 1) for time, note in self.playedNotes]


        if -1 in activeFrets:
            self.openFretActivity = min(self.openFretActivity + ticks / 24.0, 0.6)

        for n in range(self.strings):
            if n in activeFrets:
                self.fretActivity[n] = min(self.fretActivity[n] + ticks / 32.0, 1.0)
            else:
                self.fretActivity[n] = max(self.fretActivity[n] - ticks / 64.0, 0.0)

        if song:
            index = 0
            event = None
            for i in xrange(song.tempoEventTrack.currentIndex, song.tempoEventTrack.maxIndex):
                index += 1
                event = song.tempoEventTrack.getNextEvent(index)
                if isinstance(event[1], Tempo):
                    break
                else:
                    event = None
            tempoTemp = event

            if tempoTemp:
                eventTime, event = tempoTemp
                if pos >= eventTime:
                    song.tempoEventTrack.currentIndex += 1
                    song.tempoEventTrack.currentBpm = event.bpm
                    self.setBPM(event.bpm, eventTime, pos)


        for time, note in self.playedNotes:
            if pos > time + note.length:
                self.endPick(pos)
