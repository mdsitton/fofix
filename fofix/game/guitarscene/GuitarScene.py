#####################################################################
# -*- coding: iso-8859-1 -*-                                        #
#                                                                   #
# Frets on Fire                                                     #
# Copyright (C) 2006 Sami Ky�stil?                                  #
#               2008 Alarian                                        #
#               2008 myfingershurt                                  #
#               2008 Capo                                           #
#               2008 Spikehead777                                   #
#               2008 Glorandwarf                                    #
#               2008 ShiekOdaSandz                                  #
#               2008 QQStarS                                        #
#               2008 .liquid.                                       #
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

from __future__ import with_statement

from math import degrees, atan
import locale
import os

from OpenGL.GL import *

from fofix.game.Song import Note, loadSong, VocalPhrase
from fofix.core.Player import STAR, KILL, CANCEL
from fofix.game.guitarscene.instruments import *
from fofix.core.Image import drawImage
from fofix.core.Scene import Scene
from fofix.core.constants import *
from fofix.core.Language import _
from fofix.game.Menu import Menu
from fofix.game import Dialogs
from fofix.core import Settings
from fofix.game import Song
from fofix.core import Player
from fofix.core import Log

import random

class GuitarScene(Scene):
    def __init__(self, engine, libraryName, songName):
        super(GuitarScene, self).__init__(engine)

        self.engine.world.sceneName = "GuitarScene"

        self.playerList   = self.players

        Log.debug("GuitarScene init...")

        splash = Dialogs.showLoadingSplashScreen(self.engine, _("Initializing..."))
        Dialogs.changeLoadingSplashScreenText(self.engine, splash, _("Initializing..."))

        self.countdownSeconds = 3   #MFH - don't change this initialization value unless you alter the other related variables to match
        self.countdown = 100   #MFH - arbitrary value to prevent song from starting right away
        self.countdownOK = False

        #MFH - retrieve game parameters:
        self.gamePlayers = len(self.engine.world.players)
        self.lostFocusPause = self.engine.config.get("game", "lost_focus_pause")

        self.careerMode = False

        self.splayers = self.gamePlayers #Spikehead777

        #myfingershurt: drums :)
        self.instruments = [] # akedrou - this combines Guitars, Drums, and Vocalists
        self.keysList = []
        self.numberOfGuitars = len(self.playerList)
        self.numOfPlayers    = len(self.playerList)
        self.neckrender = []

        gNum = 0
        for j,player in enumerate(self.playerList):
            guitar = True
            if player.part.id == Song.DRUM_PART:
                #myfingershurt: drums :)
                inst = Drum(self.engine,player,j)
                self.instruments.append(inst)
            else:
                bass = False
                if player.part.id == Song.BASS_PART:
                    bass = True
                inst = Guitar(self.engine,player,j, bass = bass)
                self.instruments.append(inst)

            if guitar:
                player.guitarNum = gNum
                gNum += 1
                self.neckrender.append(self.instruments[j].neck)
                if self.instruments[j].isDrum:
                    self.keysList.append(player.drums)
                    self.instruments[j].keys    = player.drums
                    self.instruments[j].actions = player.drums
                else:
                    self.keysList.append(player.keys)
                    self.instruments[j].keys    = player.keys
                    self.instruments[j].actions = player.actions
            else:
                self.neckrender.append(None)
                self.keysList.append([])

        #for number formatting with commas for Rock Band:
        locale.setlocale(locale.LC_ALL, '')   #more compatible

        self.visibility       = 1.0
        self.libraryName      = libraryName
        self.songName         = songName
        self.done             = False

        self.lastMultTime     = [None for i in self.playerList]
        self.song             = None

        self.numOfPlayers = len(self.playerList)

        self.timeLeft = None

        self.lastPickPos      = [None for i in self.playerList]
        self.keyBurstTimeout  = [None for i in self.playerList]
        self.keyBurstPeriod   = 30

        self.camera.target    = (0.0, 1.0, 8.0)
        self.camera.origin    = (0.0, 2.0, -3.4)
        self.audioDelay = -self.engine.config.get('audio', 'delay')
        self.songTime = self.audioDelay

        self.pause = False

        #Get theme
        self.themeName = self.engine.data.themeLabel

        self.lessHit = False
        self.minBase = 400
        self.pluBase = 15
        self.minGain = 2
        self.pluGain = 7

        #Dialogs.changeLoadingSplashScreenText(self.engine, splash, _("Loading Settings..."))
        self.loadSettings()
        #MFH pre-translate text strings:
        self.tsGetReady         = _("Get Ready to Rock")

        #MFH - precalculate full and player viewports
        self.engine.view.setViewport(1,0)
        self.wFull, self.hFull = self.engine.view.geometry[2:4]
        self.wPlayer = []
        self.hPlayer = []
        self.hOffset = []
        self.hFontOffset = []
        self.fontScreenBottom = self.engine.data.fontScreenBottom

        for i, player in enumerate(self.playerList):
            self.engine.view.setViewportHalf(self.numberOfGuitars,player.guitarNum)
            w = self.engine.view.geometryAllHalf[self.numberOfGuitars-1,player.guitarNum,2]
            h = self.engine.view.geometryAllHalf[self.numberOfGuitars-1,player.guitarNum,3]
            self.wPlayer.append( w )
            self.hPlayer.append( h )
            self.hOffset.append( h )
            self.hFontOffset.append( h )

            self.wPlayer[i] = self.wPlayer[i]*self.numberOfGuitars #QQstarS: set the width to right one
            if self.numberOfGuitars>1:
                self.hPlayer[i] = self.hPlayer[i]*self.numberOfGuitars/1.5 #QQstarS: Set the hight to right one
                self.hOffset[i] = self.hPlayer[i]*.4*(self.numberOfGuitars-1)
            else:
                self.hPlayer[i] = self.hPlayer[i]*self.numberOfGuitars #QQstarS: Set the hight to right one
                self.hOffset[i] = 0
            self.hFontOffset[i] = -self.hOffset[i]/self.hPlayer[i]*0.752 #QQstarS: font Height Offset when there are 2 players

        self.engine.view.setViewport(1,0)

        self.accuracy = [0 for i in self.playerList]
        self.resumeCountdownEnabled = self.engine.config.get("game", "resume_countdown")
        self.resumeCountdown = 0
        self.resumeCountdownSeconds = 0
        self.pausePos = 0

        self.countdownPosX = self.engine.theme.countdownPosX
        self.countdownPosY = self.engine.theme.countdownPosY

        self.fpsRenderPos = self.engine.theme.fpsRenderPos

        self.boardZ = 1

        Dialogs.changeLoadingSplashScreenText(self.engine, splash, _("Loading Song..."))

        #MFH - this is where song loading originally took place, and the loading screen was spawned.

        self.engine.resource.load(self, "song", lambda: loadSong(self.engine, songName, library = libraryName, part = [player.part for player in self.playerList]), synch = True, onLoad = self.songLoaded)

        Dialogs.changeLoadingSplashScreenText(self.engine, splash, _("Preparing Note Phrases..."))

        self.playerList[0].hopoFreq = self.song.info.hopofreq

        for instrument in self.instruments:    #MFH - force update of early hit window
            instrument.actualBpm = 0.0
            instrument.currentBpm = Song.DEFAULT_BPM
            instrument.setBPM(instrument.currentBpm)

        #akedrou - moved this to the part where it loads notes...
        for i in range(self.numOfPlayers):
            if not self.instruments[i].isDrum:
                self.song.track[i].markHopoGH2(self.song.info.eighthNoteHopo, self.song.info.hopofreq)

        lastTime = 0
        for i in range(self.numOfPlayers):
            for time, event in self.song.track[i].getAllEvents():
                if not isinstance(event, Note) and not isinstance(event, VocalPhrase):
                    continue
                if time + event.length > lastTime:
                    lastTime = time + event.length

        self.lastEvent = lastTime + 1000
        self.lastEvent = round(self.lastEvent / 1000) * 1000
        self.noteLastTime = 0

        #glorandwarf: need to store the song's beats per second (bps) for later
        self.songBPS = self.song.bpm / 60.0

        Dialogs.changeLoadingSplashScreenText(self.engine, splash, _("Loading Graphics..."))

        #Pause Screen
        self.engine.loadImgDrawing(self, "pauseScreen", os.path.join("themes",self.themeName,"pause.png"))

        self.counterY = -0.1

        #MFH - retrieve theme.ini pause background & text positions
        self.pause_bkg = [float(i) for i in self.engine.theme.pause_bkg_pos]
        self.pause_text_x = self.engine.theme.pause_text_xPos
        self.pause_text_y = self.engine.theme.pause_text_yPos

        if self.pause_text_x == None:
            self.pause_text_x = .3

        if self.pause_text_y == None:
            self.pause_text_y = .31

        #MFH - new theme.ini color options:
        self.ingame_stats_color = self.engine.theme.ingame_stats_colorVar
        self.pause_text_color = self.engine.theme.pause_text_colorVar
        self.pause_selected_color = self.engine.theme.pause_selected_colorVar

        settingsMenu = Settings.GameSettingsMenu(self.engine, self.pause_text_color, self.pause_selected_color, players = self.playerList)
        settingsMenu.fadeScreen = False

        Log.debug("Pause text / selected colors: " + str(self.pause_text_color) + " / " + str(self.pause_selected_color))

        self.menu = Menu(self.engine, [
          (_("   RESUME"),       self.resumeSong),
          (_("   RESTART"),      self.restartSong),
          (_("   CHANGE SONG"),       self.changeSong),
          (_("   SETTINGS"),          settingsMenu),
          (_("   QUIT"), self.quit),
        ],
        name = "pause",
        fadeScreen = False,
        onClose = self.resumeGame,
        font = self.engine.data.pauseFont,
        pos = (self.pause_text_x, self.pause_text_y),
        textColor = self.pause_text_color,
        selectedColor = self.pause_selected_color)

        self.restartSong(firstTime = True)

        # hide the splash screen
        Dialogs.hideLoadingSplashScreen(self.engine, splash)
        splash = None

        self.engine.collectGarbage()

        #MFH - end of GuitarScene client initialization routine

    def pauseGame(self):
        if self.song and self.song.readyToGo:
            self.pausePos = self.songTime
            self.song.pause()
            self.pause = True
            for instrument in self.instruments:
                instrument.paused = True
                instrument.neck.paused = True

    def resumeGame(self):
        self.loadSettings()
        self.setCamera()
        if self.resumeCountdownEnabled and not self.countdown:
            self.resumeCountdownSeconds = 3
            self.resumeCountdown = float(self.resumeCountdownSeconds) * self.songBPS
            self.pause = False
        else:
            if self.song and self.song.readyToGo:
                self.song.unpause()
                self.pause = False
                for instrument in self.instruments:
                    instrument.paused = False
                    instrument.neck.paused = False

    def resumeSong(self):
        self.engine.view.popLayer(self.menu)
        self.resumeGame()

    def setCamera(self):
        self.camera.target    = (0.0, 0.0, 4.0)
        self.camera.origin    = (0.0, 3.0, -3.0)

        self.camera.target = (self.camera.target[0], self.camera.target[1], self.camera.target[2]+self.boardZ-1)
        self.camera.origin = (self.camera.origin[0], self.camera.origin[1], self.camera.origin[2]+self.boardZ-1)

    def freeResources(self):
        self.engine.view.setViewport(1,0)
        self.counter = None
        self.menu = None
        self.mult = None
        self.pauseScreen = None
        self.rockTop = None

        #MFH - Ensure all event tracks are destroyed before removing Song object!
        if self.song:
            self.song.tracks = None
            self.song.eventTracks = None
            self.song.midiEventTracks = None

        self.song = None

    def loadSettings(self):

        self.pov              = self.engine.config.get("fretboard", "point_of_view")
        #CoffeeMod

        self.activeGameControls = self.engine.input.activeGameControls

        self.keysList = []
        for i, player in enumerate(self.playerList):
            if self.instruments[i].isDrum:
                self.keysList.append(player.drums)
            else:
                self.keysList.append(player.keys)

        if self.song and self.song.readyToGo:
            #myfingershurt: ensure that after a pause or restart, the a/v sync delay is refreshed:
            self.song.refreshAudioDelay()
            #myfingershurt: ensuring the miss volume gets refreshed:
            self.song.refreshVolumes()
            self.song.setAllTrackVolumes(1)
            self.song.setCrowdVolume(0.0)

    def songLoaded(self, song):
        for i, player in enumerate(self.playerList):
            song.difficulty[i] = player.difficulty
        self.song.readyToGo = False

    def quit(self):
        if self.song:
            self.song.stop()
        self.resetVariablesToDefaults()
        self.done = True

        self.engine.view.setViewport(1,0)
        self.engine.view.popLayer(self.menu)
        self.freeResources()
        self.engine.world.finishGame()

    def changeSong(self):
        if self.song:
            self.song.stop()
            self.song  = None
        self.resetVariablesToDefaults()
        self.engine.view.setViewport(1,0)
        self.engine.view.popLayer(self.menu)
        self.freeResources()
        self.engine.world.createScene("SongChoosingScene")

    def resetVariablesToDefaults(self):
        if self.song:
            self.song.readyToGo = False
        self.countdownSeconds = 3   #MFH - This needs to be reset for song restarts, too!
        self.countdown = float(self.countdownSeconds) * self.songBPS
        self.countdownOK = False
        self.resumeCountdown = 0
        self.resumeCountdownSeconds = 0
        self.pausePos = 0
        self.audioDelay = -self.engine.config.get('audio', 'delay')
        self.songTime = self.audioDelay

        #MFH - reset global tempo variables

        for player in self.playerList:
            player.reset()

        for instrument in self.instruments:
            instrument.hopoActive = 0
            instrument.wasLastNoteHopod = False
            instrument.sameNoteHopoString = False
            instrument.hopoLast = -1

        self.engine.collectGarbage()
        self.boardY = 2
        self.setCamera()


        if self.song:
            self.song.readyToGo = True


    def restartSong(self, firstTime = False):  #QQstarS: Fix this function
        self.resetVariablesToDefaults()
        self.engine.data.startSound.play()
        self.engine.view.popLayer(self.menu)

        if not self.song:
            return

        # glorandwarf: the countdown is now the number of beats to run
        # before the song begins

        for instrument in self.instruments:
            instrument.endPick(0) #akedrou: this is the position of the song, not a player number!
        self.song.stop()

    def doPick(self, num):
        if not self.song:
            return

        if self.instruments[num].playedNotes:
            # If all the played notes are tappable, there are no required notes and
            # the last note was played recently enough, ignore this pick
            if self.instruments[num].areNotesTappable(self.instruments[num].playedNotes) and \
               not self.instruments[num].getRequiredNotes(self.song, self.songTime) and \
               self.songTime - self.lastPickPos[num] <= self.song.period / 2:
                return
            self.endPick(num)

        self.lastPickPos[num] = self.songTime

        if self.instruments[num].startPick(self.song, self.songTime, self.controls):
            self.song.setInstrumentVolume(1.0, self.playerList[num].part)
        else:
            self.song.setInstrumentVolume(0.0, self.playerList[num].part)

    def handlePick(self, playerNum, hopo = False, pullOff = False):
        num = playerNum
        guitar = self.instruments[num]

        if self.resumeCountdown > 0:    #MFH - conditions to completely ignore picks
            return

        if not self.song:
            return

        pos = self.songTime

        #hopo fudge
        hopoFudge = abs(abs(self.instruments[num].hopoActive) - pos)

        activeKeyList = []
        #myfingershurt: the following checks should be performed every time so GH2 Strict pull-offs can be detected properly.
        LastHopoFretStillHeld = False
        HigherFretsHeld = False
        problemNoteStillHeld = False

        for n, k in enumerate(self.keysList[num]):
            if self.controls.getState(k):
                activeKeyList.append(k)
                if self.instruments[num].hopoLast == n or self.instruments[num].hopoLast == n - 5:
                    LastHopoFretStillHeld = True
                elif (n > self.instruments[num].hopoLast and n < 5) or (n - 5 > self.instruments[num].hopoLast and n > 4):
                    HigherFretsHeld = True
                if self.instruments[num].hopoProblemNoteNum == n or self.instruments[num].hopoProblemNoteNum == n - 5:
                    problemNoteStillHeld = True

        if not hopo and self.instruments[num].wasLastNoteHopod and not self.instruments[num].LastStrumWasChord and not self.instruments[num].sameNoteHopoString:
            if LastHopoFretStillHeld == True and HigherFretsHeld == False:
                if self.instruments[num].wasLastNoteHopod and hopoFudge >= 0 and hopoFudge < self.instruments[num].lateMargin:
                    if self.instruments[num].hopoActive < 0:
                        self.instruments[num].wasLastNoteHopod = False
                        return
                    elif self.instruments[num].hopoActive > 0:  #make sure it's hopoActive!
                        self.instruments[num].wasLastNoteHopod = False
                        return

        #MFH - here, just check to see if we can release the expectation for an acceptable overstrum:
        if self.instruments[num].sameNoteHopoString and not problemNoteStillHeld:
            self.instruments[num].sameNoteHopoString = False
            self.instruments[num].hopoProblemNoteNum = -1

        if self.instruments[num].startPick3(self.song, pos, self.controls, hopo):
            self.song.setInstrumentVolume(1.0, self.playerList[num].part)

        else:
            ApplyPenalty = True

            if pullOff:   #always ignore bad pull-offs
                ApplyPenalty = False

            if hopo == True:
                ApplyPenalty = False
                if not (self.instruments[num].LastStrumWasChord or (self.instruments[num].wasLastNoteHopod and LastHopoFretStillHeld)):
                    self.instruments[num].hopoActive = 0
                    self.instruments[num].wasLastNoteHopod = False
                    self.instruments[num].LastStrumWasChord = False
                    self.instruments[num].sameNoteHopoString = False
                    self.instruments[num].hopoProblemNoteNum = -1
                    self.instruments[num].hopoLast = -1

            if self.instruments[num].sameNoteHopoString:
                if LastHopoFretStillHeld:
                    ApplyPenalty = False
                    self.instruments[num].playedNotes = self.instruments[num].lastPlayedNotes   #restore played notes status
                    self.instruments[num].sameNoteHopoString = False
                    self.instruments[num].hopoProblemNoteNum = -1
                elif HigherFretsHeld:
                    self.instruments[num].sameNoteHopoString = False
                    self.instruments[num].hopoProblemNoteNum = -1


            if ApplyPenalty == True:

                self.instruments[num].hopoActive = 0
                self.instruments[num].wasLastNoteHopod = False
                self.instruments[num].sameNoteHopoString = False
                self.instruments[num].hopoProblemNoteNum = -1
                self.instruments[num].hopoLast = -1
                self.song.setInstrumentVolume(0.0, self.playerList[num].part)

    def keyPressed(self, key, unicode, control=None, pullOff = False):

        if not control:
            control = self.controls.keyPressed(key)

        if control in Player.starts:
            self.pauseGame()
            self.engine.view.pushLayer(self.menu)
            return True

        num = self.getPlayerNum(control)
        if num is None:
            return

        pressed = False

        if self.instruments[num].isDrum and control in (self.instruments[num].keys):
            pressed = True
            if control in Player.bassdrums:
                self.instruments[num].drumsHeldDown[0] = 100
                self.instruments[num].playedSound[0] = False
            elif control in Player.drum1s:
                self.instruments[num].drumsHeldDown[1] = 100
                self.instruments[num].playedSound[1] = False
            elif control in Player.drum2s:
                self.instruments[num].drumsHeldDown[2] = 100
                self.instruments[num].playedSound[2] = False
            elif control in Player.drum3s:
                self.instruments[num].drumsHeldDown[3] = 100
                self.instruments[num].playedSound[3] = False
            elif control in Player.drum5s:
                self.instruments[num].drumsHeldDown[4] = 100
                self.instruments[num].playedSound[4] = False
            else:
                pressed = False
        else:

            activeList = [k for k in self.keysList[num] if self.controls.getState(k)]

            hopo = False
            if control in self.instruments[num].actions:
                pressed = True
            elif control in self.instruments[num].keys:
                if self.instruments[num].hopoActive > 0 or (self.instruments[num].wasLastNoteHopod and self.instruments[num].hopoActive == 0):

                    hopo = True
                    pressed = True
                    if not pullOff:
                        # don't allow lower-fret tapping while holding a higher fret
                        activeKeyList = []
                        LastHopoFretStillHeld = False
                        HigherFretsHeld = False
                        for p, k in enumerate(self.keysList[num]):
                            if self.controls.getState(k):
                                activeKeyList.append(k)
                                if self.instruments[num].hopoLast == p or self.instruments[num].hopoLast-5 == p:
                                    LastHopoFretStillHeld = True
                                elif (p > self.instruments[num].hopoLast and p < 5) or (p > self.instruments[num].hopoLast and p > 4):
                                    HigherFretsHeld = True

                        if not(LastHopoFretStillHeld and not HigherFretsHeld):  #tapping a lower note should do nothing.
                            pressed = True

            if control in (self.instruments[num].actions):
                for k in self.keysList[num]:
                    if self.controls.getState(k):
                        self.keyBurstTimeout[num] = None
                        break
                else:
                    return True
        if pressed:
            if self.instruments[num].isDrum:
                self.doPick(num)
            else:
                self.handlePick(num, hopo = hopo, pullOff = pullOff)

    def keyReleased(self, key):

        control = self.controls.keyReleased(key)
        num = self.getPlayerNum(control)
        if num is None:
            return

        if self.instruments[num].isDrum:
            return True

        if control in self.keysList[num] and self.song:
            for time, note in self.instruments[num].playedNotes:
                #myfingershurt: only end the pick if no notes are being held.
                if (self.instruments[num].hit[note.number] == True and (control == self.keysList[num][note.number] or control == self.keysList[num][note.number+5])):
                    self.endPick(num)

        if self.keysList[num] is not None:
            activeList = [k for k in self.keysList[num] if self.controls.getState(k) and k != control]
            if len(activeList) != 0 and self.instruments[num].hopoActive > 0 and control in self.keysList[num]:
                self.keyPressed(None, 0, control=activeList[0], pullOff = True)

    def endPick(self, num):
        self.instruments[num].endPick(self.song.getPosition())

    def run(self, ticks):
        super(GuitarScene, self).run(ticks)
        if self.song and self.song.readyToGo and not self.pause:
            sngPos = self.song.getPosition()
            # calculate song position during the song countdown
            if self.songTime <= -self.audioDelay and sngPos == -self.song.delay:
                self.songTime = sngPos-(self.countdown * self.song.period)
            if not self.countdown and not self.resumeCountdown and not self.pause:
                # increment song position
                self.songTime += ticks
                sngDiff = abs(sngPos - self.songTime)
                if sngDiff > 100: # Correct for potential large lag spikes
                    self.songTime = sngPos
                elif sngDiff < 1.0: # normal operation
                    pass
                elif self.songTime > sngPos: # to fast
                    self.songTime -= 0.1
                elif self.songTime < sngPos: # to slow
                    self.songTime += 0.1

                self.song.update(ticks)

            for i,instrument in enumerate(self.instruments):
                playerNum = i

                instrument.camAngle = -degrees(atan(abs(self.camera.origin[2] - self.camera.target[2]) / abs(self.camera.origin[1] - self.camera.target[1])))
                instrument.run(ticks, self.songTime, self.song, self.controls)

            if self.countdown > 0 and self.countdownOK: #MFH won't start song playing if you failed or pause
                self.countdown = max(self.countdown - ticks / self.song.period, 0)
                self.countdownSeconds = self.countdown / self.songBPS + 1

                if not self.countdown:  #MFH - when countdown reaches zero, will only be executed once
                    self.song.setAllTrackVolumes(1)
                    self.song.play()

            if self.resumeCountdown > 0: #unpause delay
                self.resumeCountdown = max(self.resumeCountdown - ticks / self.song.period, 0)
                self.resumeCountdownSeconds = self.resumeCountdown / self.songBPS + 1

                if not self.resumeCountdown:
                    self.song.unpause()
                    self.pause = False
                    missedNotes = []
                    for instrument in self.instruments:
                        instrument.paused = False

    def render3D(self):
        self.renderGuitar()

    def renderGuitar(self):
        for i, guitar in enumerate(self.instruments):
            if not self.pause:
                glPushMatrix()
                self.neckrender[i].render(self.visibility, self.song, self.songTime)
                guitar.render(self.visibility, self.song, self.songTime, self.controls, False)#last is killswitch  #QQstarS: new
                glPopMatrix()

            self.engine.view.setViewport(1,0)

    def goToResults(self):
        if self.song:
            self.song.stop()
            self.done  = True
            noScore = False

            self.changeSong()

    def getPlayerNum(self, control):
        for i, player in enumerate(self.playerList):
            if control and control in player.keyList:
                return i

    def render(self, visibility, topMost):

        w = self.wFull
        h = self.hFull

        font    = self.engine.data.font
        bigFont = self.engine.data.bigFont

        if self.song and self.song.readyToGo:

            if self.boardZ <= 1:
                self.setCamera()
                if self.countdown > 0:
                    self.countdownOK = True
                    self.boardZ = 1

            super(GuitarScene, self).render(visibility, topMost)

            self.visibility = v = 1.0 - ((1 - visibility) ** 2)

            with self.engine.view.orthogonalProjection(normalize = True):

                for i, player in enumerate(self.playerList):

                    self.engine.view.setViewportHalf(1,0)

                    self.engine.theme.setBaseColor()

                    if self.song and self.pause:
                        self.engine.view.setViewport(1,0)
                        if self.engine.graphicMenuShown == False:
                            drawImage(self.pauseScreen, scale = (self.pause_bkg[2], -self.pause_bkg[3]), coord = (w*self.pause_bkg[0],h*self.pause_bkg[1]), stretched = FULL_SCREEN)

                self.engine.view.setViewport(1,0)

                # evilynux - Display framerate
                if self.engine.show_fps: #probably only need to once through.
                    c1,c2,c3 = self.ingame_stats_color
                    glColor3f(c1, c2, c3)
                    text = _("FPS: %.2f" % self.engine.fpsEstimate)
                    w, h = font.getStringSize(text, scale = 0.00140)
                    font.render(text, (self.fpsRenderPos[0], self.fpsRenderPos[1] - h/2), (1,0,0), 0.00140)

                #MFH - Get Ready to Rock & countdown
                if not self.pause:
                    # show countdown
                    # glorandwarf: fixed the countdown timer
                    if self.countdownSeconds > 1:
                        self.engine.theme.setBaseColor(min(1.0, 3.0 - abs(4.0 - self.countdownSeconds)))
                        text = self.tsGetReady
                        w, h = font.getStringSize(text)
                        font.render(text,  (.5 - w / 2, .3))
                        if self.countdownSeconds < 6:
                            scale = 0.002 + 0.0005 * (self.countdownSeconds % 1) ** 3
                            text = "%d" % (self.countdownSeconds)
                            w, h = bigFont.getStringSize(text, scale = scale)
                            self.engine.theme.setBaseColor()
                            bigFont.render(text,  (self.countdownPosX - w / 2, self.countdownPosY - h / 2), scale = scale)

                    if self.resumeCountdownSeconds > 1:
                        scale = 0.002 + 0.0005 * (self.resumeCountdownSeconds % 1) ** 3
                        text = "%d" % (self.resumeCountdownSeconds)
                        w, h = bigFont.getStringSize(text, scale = scale)
                        self.engine.theme.setBaseColor()
                        bigFont.render(text,  (self.countdownPosX - w / 2, self.countdownPosY - h / 2), scale = scale)
