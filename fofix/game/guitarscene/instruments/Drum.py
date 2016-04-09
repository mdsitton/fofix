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
        self.playedSound  = [True, True, True, True, True]

        self.openFretActivity = 0.0
        self.openFretColor  = self.fretColors[5]

        self.lanenumber     = float(4)
        self.fretImgColNumber = float(6)

        self.logClassInits = self.engine.config.get("game", "log_class_inits")
        if self.logClassInits == 1:
            Log.debug("Drum class initialization!")

        self.fretActivity   = [0.0] * self.strings

        #myfingershurt:
        self.hopoStyle = 0

        self.drumFretButtons = None

        #blazingamer
        self.opencolor = self.fretColors[5]
        self.rockLevel = 0.0

        self.bigMax = 1

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

        if engine.loadImgDrawing(self, "fretButtons", os.path.join("themes",themename, "frets", "drum", "fretbuttons.png")):
            self.drumFretButtons = True
        elif engine.loadImgDrawing(self, "fretButtons", os.path.join("themes",themename, "frets", "fretbuttons.png")):
            self.drumFretButtons = None


    def renderNote(self, length, sustain, color, tailOnly = False, isTappable = False, fret = 0, spNote = False, isOpen = False, spAct = False):

        if tailOnly:
            return

        tailOnly = True

        y = 0

        if isOpen:
            vtx = self.openVtx
            if not noteImage:
                noteImage = self.noteButtons
                texCoord = self.noteTexCoord[y]
        else:
            fret -= 1
            vtx = self.noteVtx
            noteImage = self.noteButtons
            texCoord = self.noteTexCoord[y][fret]

        draw3Dtex(noteImage, vertex = vtx, texcoord = texCoord,
                              scale = (1,1,1), rot = (self.camAngle,1,0,0), multiples = False, color = color)


    def renderFrets(self, visibility, song, controls):
        w = self.boardWidth / self.strings
        size = (.22, .22)
        v = 1.0 - visibility

        glEnable(GL_DEPTH_TEST)

        for n in range(self.strings2):
            if n == 4:
                keyNumb = 0
            else:
                keyNumb = n + 1
            f = self.drumsHeldDown[keyNumb]/200.0
            pressed = self.drumsHeldDown[keyNumb]

            if n == 3: #Set colors of frets
                c = list(self.fretColors[0])
            elif not n == 4:
                c = list(self.fretColors[n + 1])

            if n == 4:
                y = v + f / 6
                x = 0
            else:
                y = v / 6
                x = (self.strings / 2 - .5 - n) * w

            if n == 4: #Weirdpeople - so the drum bass fret can be seen with 2d frets
                glDisable(GL_DEPTH_TEST)
                size = (self.boardWidth/2, self.boardWidth/self.strings/2.4)
                texSize = (0.0,1.0)
            else:
                size = (self.boardWidth / self.strings / 2, self.boardWidth / self.strings / 2.4)
                texSize = (n / self.lanenumber, n / self.lanenumber + 1 / self.lanenumber)

            fretColor = (1,1,1,1)

            if self.drumFretButtons == None:
                if n == 4:
                    continue
                whichFret = n+1
                if whichFret == 4:
                    whichFret = 0
                    #reversing fret 0 since it's angled in Rock Band
                    texSize = (whichFret/5.0+0.2,whichFret/5.0)
                else:
                    texSize = (whichFret/5.0,whichFret/5.0+0.2)

                texY = (0.0,1.0/3.0)
                if pressed:
                    texY = (1.0/3.0,2.0/3.0)
                if self.hit[n]: #Currently broken
                    texY = (2.0/3.0,1.0)

            else:
                if controls.getState(self.keys[n]) or controls.getState(self.keys[n+5]) or pressed: #pressed
                    if n == 4: #bass drum
                        texY = (3.0 / self.fretImgColNumber, 4.0 / self.fretImgColNumber)
                    else:
                        texY = (2.0 / self.fretImgColNumber, 3.0 / self.fretImgColNumber)

                elif self.hit[n]: #being hit - Currently broken
                    if n == 4: #bass drum
                        texY = (5.0 / self.fretImgColNumber, 1.0)
                    else:
                        texY = (4.0 / self.fretImgColNumber, 5.0 / self.fretImgColNumber)

                else: #nothing being pressed or hit
                    if n == 4: #bass drum
                        texY = (1.0 / self.fretImgColNumber, 2.0 / self.fretImgColNumber)
                    else:
                        texY = (0.0, 1.0 / self.fretImgColNumber)

            draw3Dtex(self.fretButtons, vertex = (size[0],size[1],-size[0],-size[1]), texcoord = (texSize[0], texY[0], texSize[1], texY[1]),
                                    coord = (x,v,0), multiples = True,color = fretColor, depth = True)

        glDisable(GL_DEPTH_TEST)


    def render(self, visibility, song, pos, controls, killswitch):
        notes = self.getRequiredNotesForRender(song, pos)
        self.renderFrets(visibility, song, controls)
        self.renderOpenNotes(notes, visibility, song, pos)
        self.renderNotes(notes, visibility, song, pos)
        self.renderFlames(notes, song, pos)


    def playDrumSounds(self, controls, playBassDrumOnly = False):   #MFH - handles playing of drum sounds.
        #Returns list of drums that were just hit (including logic for detecting a held bass pedal)
        #pass playBassDrumOnly = True (optional paramater) to only play the bass drum sound, but still
        #  return a list of drums just hit (intelligently play the bass drum if it's held down during gameplay)
        drumsJustHit = [False, False, False, False, False]

        for i in range (5):
            if controls.getState(self.keys[i]) or controls.getState(self.keys[5+i]):
                if i == 0:
                    if self.playedSound[i] == False:  #MFH - gotta check if bass drum pedal is just held down!
                        self.engine.data.bassDrumSound.play()
                        self.playedSound[i] = True
                        drumsJustHit[0] = True
                        if self.fretboardHop < 0.04:
                            self.fretboardHop = 0.04  #stump
                if i == 1:
                    if not playBassDrumOnly and self.playedSound[i] == False:
                        self.engine.data.T1DrumSound.play()
                    self.playedSound[i] = True
                    drumsJustHit[i] = True
                if i == 2:
                    if not playBassDrumOnly and self.playedSound[i] == False:
                        self.engine.data.T2DrumSound.play()
                    self.playedSound[i] = True
                    drumsJustHit[i] = True
                if i == 3:
                    if not playBassDrumOnly and self.playedSound[i] == False:
                        self.engine.data.T3DrumSound.play()
                    self.playedSound[i] = True
                    drumsJustHit[i] = True
                if i == 4:   #MFH - must actually activate starpower!
                    if not playBassDrumOnly and self.playedSound[i] == False:
                        self.engine.data.CDrumSound.play()
                    self.playedSound[i] = True
                    drumsJustHit[i] = True

        return drumsJustHit


    def startPick(self, song, pos, controls, hopo = False):
        if not song:
            return False
        if not song.readyToGo:
            return

        self.matchingNotes = self.getRequiredNotesMFH(song, pos)    #MFH - ignore skipped notes please!


        # no self.matchingNotes?
        if not self.matchingNotes:
            return False
        self.playedNotes = []
        self.pickStartPos = pos

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
                return False

        return True
