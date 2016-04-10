#####################################################################
# -*- coding: iso-8859-1 -*-                                        #
#                                                                   #
# Frets on Fire                                                     #
# Copyright (C) 2006 Sami Kyostila                                  #
#               2008 Alarian                                        #
#               2008 myfingershurt                                  #
#               2008 Capo                                           #
#               2008 Glorandwarf                                    #
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

from copy import deepcopy
import math
import os

from OpenGL.GL import *
import numpy as np

from fofix.game.guitarscene.instruments.Instrument import Instrument
from fofix.game.Song import Note, Tempo
from fofix.core.Mesh import Mesh
from fofix.game import Song
from fofix.core import cmgl
from fofix.core import Log

class Guitar(Instrument):
    def __init__(self, engine, playerObj, player = 0, bass = False):

        self.isDrum = False
        self.isBassGuitar = bass
        self.isVocal = False

        super(Guitar, self).__init__(engine, playerObj, player)


        self.strings        = 5
        self.strings2       = 5

        self.debugMode = False
        self.matchingNotes = []

        self.logClassInits = self.engine.config.get("game", "log_class_inits")
        if self.logClassInits == 1:
            Log.debug("Guitar class init...")

        self.lastPlayedNotes = []   #MFH - for reverting when game discovers it implied incorrectly

        self.missedNotes    = []
        self.missedNoteNums = []

        self.fretActivity   = [0.0] * self.strings

        #myfingershurt:
        self.hopoStyle        = self.engine.config.get("game", "hopo_system")
        self.sfxVolume    = self.engine.config.get("audio", "SFX_volume")

        #blazingamer
        self.killfx = self.engine.config.get("performance", "killfx")
        self.killCount         = 0

        #Get theme
        #now theme determination logic is only in data.py:
        self.theme = self.engine.data.theme

        self.oFlash = None

        self.lanenumber     = float(5)
        self.fretImgColNumber = float(3)

        #myfingershurt:
        self.bassGrooveNeckMode = self.engine.config.get("game", "bass_groove_neck")

        self.tailsEnabled = True

        self.loadImages()

        self.rockLevel = 0.0

    def render(self, visibility, song, pos, controls):
        self.neck.render(visibility, song, pos)
        notes = self.getRequiredNotesForRender(song, pos)
        self.renderTails(notes, visibility, song, pos)
        self.renderFrets(visibility, song, controls)
        self.renderNotes(notes, visibility, song, pos)
        self.renderHitGlow()
        self.renderHitTrails(controls)
        self.renderFlames(notes, song, pos)    #MFH - only when freestyle inactive!

    def controlsMatchNotes(self, controls, notes, hopo = False):
        # no notes?
        if not notes:
            return False

        # check each valid chord
        chords = {}
        for time, note in notes:
            if note.hopod == True and (controls.getState(self.keys[note.number]) or controls.getState(self.keys[note.number + 5])):
                self.playedNotes = []
                return True
            if not time in chords:
                chords[time] = []
            chords[time].append((time, note))

        #Make sure the notes are in the right time order
        chordlist = chords.values()
        chordlist.sort(key=lambda a: a[0][0])

        self.missedNotes = []
        self.missedNoteNums = []
        for chord in chordlist:
            # matching keys?
            requiredKeys = [note.number for time, note in chord]
            requiredKeys = self.uniqify(requiredKeys)

            if (self.controlsMatchNote(controls, chord, requiredKeys, hopo)):
                for time, note in chord:
                    note.played = True
            if hopo == True:
                break
            self.missedNotes.append(chord)
        else:
            self.missedNotes = []
            self.missedNoteNums = []

        for chord in self.missedNotes:
            for time, note in chord:
                if self.debugMode:
                    self.missedNoteNums.append(note.number)
                note.skipped = True
                note.played = False

        return True

    def uniqify(self, seq):
        # order preserving
        result = []
        for item in seq:
            if item in result:
                continue
            result.append(item)
        return result

    def controlsMatchNote(self, controls, chordTuple, requiredKeys, hopo):
        if len(chordTuple) > 1:
        #Chords must match exactly
            for n in range(self.strings):
                if (n in requiredKeys and not (controls.getState(self.keys[n]) or controls.getState(self.keys[n+5]))) or (n not in requiredKeys and (controls.getState(self.keys[n]) or controls.getState(self.keys[n+5]))):
                    return False
        else:
        #Single Note must match that note
            requiredKey = requiredKeys[0]
            if not controls.getState(self.keys[requiredKey]) and not controls.getState(self.keys[requiredKey+5]):
                return False


            # myfingershurt: this is where to filter out higher frets held when HOPOing:
            # Check for higher numbered frets
            for n, k in enumerate(self.keys):
                if (n > requiredKey and n < 5) or (n > 4 and n > requiredKey + 5):
                #higher numbered frets cannot be held
                    if controls.getState(k):
                        return False

        return True

    def startPick3(self, song, pos, controls, hopo = False):
        if not song:
            return False
        if not song.readyToGo:
            return False

        self.lastPlayedNotes = self.playedNotes
        self.playedNotes = []

        self.matchingNotes = self.getRequiredNotes(song, pos)

        self.controlsMatchNotes(controls, self.matchingNotes, hopo)

        #myfingershurt

        for time, note in self.matchingNotes:
            if note.played != True:
                continue

            if hopo:
                note.hopod        = True
            else:
                note.played       = True
            if note.tappable == 1 or note.tappable == 2:
                self.hopoActive = time
                self.wasLastNoteHopod = True
            elif note.tappable == 3:
                self.hopoActive = -time
                self.wasLastNoteHopod = True
                if hopo:  #MFH - you just tapped a 3 - make a note of it. (har har)
                    self.hopoProblemNoteNum = note.number
                    self.sameNoteHopoString = True
            else:
                self.hopoActive = 0
                self.wasLastNoteHopod = False
            self.hopoLast     = note.number
            self.playedNotes.append([time, note])

        #myfingershurt: be sure to catch when a chord is played
        if len(self.playedNotes) > 1:
            lastPlayedNote = None
            for time, note in self.playedNotes:
                if isinstance(lastPlayedNote, Note):
                    if note.tappable == 1 and lastPlayedNote.tappable == 1:
                        self.LastStrumWasChord = True
                    else:
                        self.LastStrumWasChord = False
                lastPlayedNote = note

        elif len(self.playedNotes) > 0: #ensure at least that a note was played here
            self.LastStrumWasChord = False

        if len(self.playedNotes) != 0:
            self.processedFirstNoteYet = True
            return True
        return False

    def run(self, ticks, pos, song, controls):

        if not self.paused:
            self.time += ticks

        activeFrets = [note.number for time, note in self.playedNotes]

        for n in range(self.strings):
            if n in activeFrets:
                self.fretActivity[n] = min(self.fretActivity[n] + ticks / 32.0, 1.0)
            else:
                self.fretActivity[n] = max(self.fretActivity[n] - ticks / 64.0, 0.0)

            #MFH - THIS is where note sustains should be determined... NOT in renderNotes / renderFrets / renderFlames  -.-
            if self.fretActivity[n]:
                self.hit[n] = True
            else:
                self.hit[n] = False

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

        missedNotes = self.getMissedNotes(song, pos, catchup = True)
        if self.paused:
            missedNotes = []

        if not self.processedFirstNoteYet and not self.playedNotes and len(missedNotes) > 0:

            self.processedFirstNoteYet = True
            self.hopoLast = -1

            self.hopoActive = 0
            self.wasLastNoteHopod = False
            self.sameNoteHopoString = False
            self.hopoProblemNoteNum = -1
