#####################################################################
# -*- coding: iso-8859-1 -*-                                        #
#                                                                   #
# Frets on Fire                                                     #
# Copyright (C) 2009 Blazingamer                                    #
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

import math
import os

from OpenGL.GL import *
import numpy as np

from fofix.game.guitarscene.Neck import Neck
from fofix.game.Song import Note, Tempo
from fofix.core.Image import draw3Dtex
from fofix.core.Mesh import Mesh
from fofix.game import Song
from fofix.core import cmgl
from fofix.core import Log


class Instrument(object):
    def __init__(self, engine, playerObj, player = 0):
        self.engine         = engine

        self.selectedString = 0
        self.time           = 0.0
        self.pickStartPos   = 0
        self.leftyMode      = False
        self.drumFlip       = False

        self.freestyleActive = False
        self.drumFillsActive = False

        self.beatsPerBoard            = 5.0
        self.boardWidth               = self.engine.theme.neckWidth
        self.boardLength              = self.engine.theme.neckLength
        self.beatsPerUnit             = self.beatsPerBoard / self.boardLength

        self.fretColors = self.engine.theme.noteColors
        self.flameColors = self.fretColors
        self.hitGlowColors = self.fretColors
        self.glowColor = self.fretColors
        self.killColor = self.fretColors

        self.playedNotes    = []
        self.missedNotes    = []

        self.sameNoteHopoString = False
        self.hopoProblemNoteNum = -1

        self.currentBpm     = 120.0   #MFH - need a default 120BPM to be set in case a custom song has no tempo events.
        self.currentPeriod  = 60000.0 / self.currentBpm
        self.targetBpm      = self.currentBpm
        self.targetPeriod   = 60000.0 / self.targetBpm
        self.lastBpmChange  = -1.0
        self.baseBeat       = 0.0

        self.camAngle = 0.0 #set from guitarScene

        self.indexFps       = self.engine.config.get("video", "fps")

        #myfingershurt: to keep track of pause status here as well
        self.paused = False

        # get difficulty
        self.difficulty = playerObj.getDifficultyInt()
        self.controlType = playerObj.controlType

        self.earlyHitWindowSizeFactor = 0.10
        self.hitw = 1.2

        #myfingershurt: need a separate variable to track whether or not hopos are actually active
        self.wasLastNoteHopod = False

        self.hopoLast       = -1
        self.player         = player

        self.hit = [False, False, False, False, False]

        #myfingershurt: this should be retrieved once at init, not repeatedly in-game whenever tails are rendered.
        self.fretsUnderNotes  = self.engine.config.get("game", "frets_under_notes")

        self.hopoActive     = 0

        self.LastStrumWasChord = False

        #Get theme
        self.theme = self.engine.data.theme

        #blazingamer
        self.nstype = self.engine.config.get("game", "nstype")                  # neck style
        self.noterotate = self.engine.config.get("coffee", "noterotate")        # adjust notes for if they were designed for FoF 1.1 or 1.2
        self.billboardNote = self.engine.theme.billboardNote                    # 3D notes follow the angle of the camera

        self.speed = self.engine.config.get("coffee", "neckSpeed") * 0.01

        self.boardScaleX    = self.boardWidth/3.0
        self.boardScaleY    = self.boardLength/9.0

        self.fretPress      = self.engine.theme.fret_press

        self.neck = Neck(self.engine, self, playerObj)
        self.setBPM(self.currentBpm)

        self.keys = []
        self.actions = []
        self.soloKey = []

        self.disableFretSFX  = self.engine.config.get("video", "disable_fretsfx")
        self.disableFlameSFX  = self.engine.config.get("video", "disable_flamesfx")

        self.meshColor  = self.engine.theme.meshColor
        self.hopoColor  = self.engine.theme.hopoColor
        self.spotColor = self.engine.theme.spotColor
        self.keyColor = self.engine.theme.keyColor
        self.key2Color = self.engine.theme.key2Color

        self.hitFlameYPos         = 0.5
        self.hitFlameZPos         = 0.0
        self.holdFlameYPos        = 0.0
        self.holdFlameZPos        = 0.0
        self.hitFlameSize         = 0.075
        self.holdFlameSize        = 0.075
        self.hitFlameBlackRemove  = True
        self.hitGlowsBlackRemove  = True
        self.hitFlameRotation = self.hitGlowsRotation = (90, 1, 0, 0)

        self.fretboardHop = 0.00  #stump

        #Tail's base arrays will get modified overtime

        self.tail_tex = np.array([[0.0, 0.0],
                                  [1.0, 0.0],
                                  [0.0, 1.0],
                                  [1.0, 1.0]], dtype=np.float32)

        self.tail_col = np.array([[0,0,0,1],
                                  [0,0,0,1],
                                  [0,0,0,1],
                                  [0,0,0,1]], dtype=np.float32)

        self.tail_vtx = np.array([[0, 0, 0],
                                  [0, 0, 0],
                                  [0, 0, 0],
                                  [0, 0, 0]], dtype=np.float32)

    #this checks to see if there is a "drum" or "bass" folder
    #inside the subdirectory for image replacement
    def checkPath(self, subdirectory, file, lastResort = False):
    #  parameters
    #     @subdirectory       the folder in the theme to search
    #                           if the instrument is drum or bass it will extend this
    #     @file               the file to search for
    #     @lastResort         if the file isn't even found in the default path then
    #                           resort to using the file in the data folder

        #Get theme
        themename = self.engine.data.themeLabel

        defaultpath = os.path.join("themes", themename, subdirectory)
        themepath = os.path.join("themes", themename, subdirectory)
        if self.isDrum:
            themepath = os.path.join(themepath, "drum")
        elif self.isBassGuitar:
            themepath = os.path.join(themepath, "bass")

        if self.engine.fileExists(os.path.join(themepath, file)):
            return os.path.join(themepath, file)
        else:
            if lastResort and not self.engine.fileExists(os.path.join(defaultpath, file)):
                return file
            Log.debug("Image not found: " + themepath + "/" + file)
            return os.path.join(defaultpath, file)

    def loadFlames(self):
        engine = self.engine
        themename = self.engine.data.themeLabel

        get = lambda file: self.checkPath("flames", file)

        self.HCount         = 0
        self.HFrameLimit    = self.engine.theme.HoldFlameFrameLimit
        self.HFrameLimit2   = self.engine.theme.HitFlameFrameLimit
        self.HCountAni      = False

        if self.disableFretSFX != False:
            self.glowDrawing = None
        else:
            engine.loadImgDrawing(self, "glowDrawing", get("glow.png"))
            if not self.glowDrawing:
                engine.loadImgDrawing(self, "glowDrawing", "glow.png")

        if self.disableFlameSFX == True:
            self.hitglow2Drawing = None
            self.hitglowDrawing = None
            self.hitglowAnim = None
            self.hitflamesAnim = None
            self.hitflames2Drawing = None
            self.hitflames1Drawing = None
        else:
            engine.loadImgDrawing(self, "hitflames1Drawing", get("hitflames1.png"))
            engine.loadImgDrawing(self, "hitflames2Drawing", get("hitflames2.png"))
            engine.loadImgDrawing(self, "hitflamesAnim", get("hitflamesanimation.png"))
            engine.loadImgDrawing(self, "powerHitflamesAnim", get("powerhitflamesanimation.png"))
            engine.loadImgDrawing(self, "hitglowAnim", get("hitglowanimation.png"))
            engine.loadImgDrawing(self, "hitglowDrawing", get("hitglow.png"))
            engine.loadImgDrawing(self, "hitglow2Drawing", get("hitglow2.png"))

        engine.loadImgDrawing(self, "hitlightning", os.path.join("themes",themename,"lightning.png"),  textureSize = (128, 128))

    def loadNotes(self):
        engine = self.engine

        get = lambda file: self.checkPath("notes", file)

        self.noteSpin = self.engine.config.get("performance", "animated_notes")

        self.spActTex = None
        self.noteTex = None
        self.noteButtons = None

        engine.loadImgDrawing(self, "noteButtons", get("notes.png"))

        size = (self.boardWidth/self.strings/2, self.boardWidth/self.strings/2)
        self.noteVtx = np.array([[-size[0],  0.0, size[1]],
                                 [size[0],  0.0, size[1]],
                                 [-size[0], 0.0, -size[1]],
                                 [size[0], 0.0, -size[1]]],
                                 dtype=np.float32)

        self.noteTexCoord = [[np.array([[i/float(self.strings), s/6.0],
                                       [(i+1)/float(self.strings), s/6.0],
                                       [i/float(self.strings), (s+1)/6.0],
                                       [(i+1)/float(self.strings), (s+1)/6.0]],
                                       dtype=np.float32)
                              for i in range(self.strings)] for s in range(6)]

    def loadFrets(self):
        engine = self.engine

        get = lambda file: self.checkPath("frets", file)

        engine.loadImgDrawing(self, "fretButtons", get("fretbuttons.png"))

    def loadTails(self):
        engine = self.engine

        get = lambda file: self.checkPath("tails", file)
        getD = lambda file: self.checkPath("tails", file, True) #resorts to checking data

        #MFH - freestyle tails (for drum fills & BREs)
        engine.loadImgDrawing(self, "freestyle1", getD("freestyletail1.png"),  textureSize = (128, 128))
        engine.loadImgDrawing(self, "freestyle2", getD("freestyletail2.png"),  textureSize = (128, 128))

        if self.tailsEnabled == True:
            self.simpleTails = False
            for i in range(0,7):
                if not engine.loadImgDrawing(self, "tail"+str(i), get("tail"+str(i)+".png"),  textureSize = (128, 128)):
                    self.simpleTails = True
                    break
                if not engine.loadImgDrawing(self, "taile"+str(i), get("taile"+str(i)+".png"),  textureSize = (128, 128)):
                    self.simpleTails = True
                    break
                if not engine.loadImgDrawing(self, "btail"+str(i), get("btail"+str(i)+".png"),  textureSize = (128, 128)):
                    self.simpleTails = True
                    break
                if not engine.loadImgDrawing(self, "btaile"+str(i), get("btaile"+str(i)+".png"),  textureSize = (128, 128)):
                    self.simpleTails = True
                    break

            if self.simpleTails:
                Log.debug("Simple tails used; complex tail loading error...")
                engine.loadImgDrawing(self, "tail1", getD("tail1.png"),  textureSize = (128, 128))
                engine.loadImgDrawing(self, "tail2", getD("tail2.png"),  textureSize = (128, 128))
                engine.loadImgDrawing(self, "bigTail1", getD("bigtail1.png"),  textureSize = (128, 128))
                engine.loadImgDrawing(self, "bigTail2", getD("bigtail2.png"),  textureSize = (128, 128))

            engine.loadImgDrawing(self, "kill1", getD("kill1.png"),  textureSize = (128, 128))
            engine.loadImgDrawing(self, "kill2", getD("kill2.png"),  textureSize = (128, 128))

        else:
            self.tail1 = None
            self.tail2 = None
            self.bigTail1 = None
            self.bigTail2 = None
            self.kill1 = None
            self.kill2 = None

    def loadImages(self):
        self.loadFrets()
        self.loadNotes()
        self.loadTails()
        self.loadFlames()

    def hitNote(self, time, note):
        self.pickStartPos = max(self.pickStartPos, time)
        self.playedNotes.append([time, note])
        note.played = True
        return True

    def endPick(self, pos):
        if not self.isDrum:
            for time, note in self.playedNotes:
                if time + note.length > pos + self.noteReleaseMargin:
                    self.playedNotes = []
                    return False

        self.playedNotes = []
        return True


    def setBPM(self, bpm, time=0, pos=0):
        if bpm > 200:
            bpm = 200

        #MFH - Filter out unnecessary BPM settings (when currentBPM is already set!)
        self.currentBpm = bpm   #update current BPM as well

        #MFH - Neck speed determination:
        if self.difficulty == 0:    #expert
            self.neckSpeed = 220/self.speed
        elif self.difficulty == 1:
            self.neckSpeed = 250/self.speed
        elif self.difficulty == 2:
            self.neckSpeed = 280/self.speed
        else:   #easy
            self.neckSpeed = 300/self.speed

        self.earlyMargin       = 250 - bpm/5 - 70*self.hitw
        self.lateMargin        = 250 - bpm/5 - 70*self.hitw

        self.noteReleaseMargin = (200 - bpm/5 - 70*1.0)

        self.currentPeriod  = 60000.0 / self.neckSpeed
        self.targetPeriod   = 60000.0 / self.neckSpeed

        self.baseBeat          += (time - self.lastBpmChange) / self.currentPeriod
        self.targetBpm          = bpm
        self.lastBpmChange      = time

        self.neck.lastBpmChange = time
        self.neck.baseBeat      = self.baseBeat

    #MFH - corrected and optimized:
    def getRequiredNotesMFH(self, song, pos, hopoTroubleCheck = False):

        track   = song.track[self.player]

        notes = [(time, event)
            for time, event in track.getEvents(pos - self.lateMargin, pos + self.earlyMargin) \
                if isinstance(event, Note) and                                                \
                    not (event.hopod or event.played or event.skipped) and                    \
                    (time >= (pos - self.lateMargin)) and (time <= (pos + self.earlyMargin)) ]

        return sorted(notes, key=lambda x: x[0])

    def areNotesTappable(self, notes):
        if not notes:
            return
        for time, note in notes:
            if note.tappable > 1:
                return True
        return False

    def getMissedNotesMFH(self, song, pos, catchup = False):
        if not song and not song.readyToGo:
            return

        m1      = self.lateMargin
        m2      = self.lateMargin * 2

        track   = song.track[self.player]

        notes   = [(time, event)                                               \
            for time, event in track.getEvents(pos - m2, pos - m1)             \
                if isinstance(event, Note) and                                 \
                    time >= (pos - m2) and time <= (pos - m1) and              \
                    not event.played and not event.hopod and not event.skipped ]

        if catchup:
            for time, event in notes:
                event.skipped = True

        return sorted(notes, key=lambda x: x[0])

    def getRequiredNotesForRender(self, song, pos):
        track   = song.track[self.player]
        return [(time, event) for time, event in track.getEvents(pos - self.currentPeriod * 2, pos + self.currentPeriod * self.beatsPerBoard)]

    #Renders the tail glow hitflame
    def renderHitTrails(self, controls):
        if self.hitGlowColors[0][0] == -1  or self.disableFlameSFX == True:
            return

        if self.HCountAni:
            for n in range(self.strings):

                w = self.boardWidth / self.strings
                x = (self.strings / 2 - n) * w

                y = 0.5 / 6 - self.holdFlameYPos

                flameSize = self.holdFlameSize

                alphaEnabled = self.hitGlowsBlackRemove

                if self.fretActivity[n]:
                    ms = math.sin(self.time) * .25 + 1
                    ff = self.fretActivity[n] + 1.2
                    vtx = flameSize * ff
                    s = ff/6

                    if not self.hitFlameYPos == 0:
                        y = s - self.holdFlameYPos
                    else:
                        y = 0

                    if not self.hitFlameZPos == 0:
                        z = s - self.holdFlameZPos
                    else:
                        z = 0

                    color = self.hitGlowColors[n]
                    color = tuple([color[ifc] + .38 for ifc in range(3)]) #to make sure the final color looks correct on any color set


                    if self.hitglowDrawing:
                        flameColorMod = (1.19, 1.97, 10.59)
                        flamecol = tuple([color[ifc]*flameColorMod[ifc] for ifc in range(3)])

                        draw3Dtex(self.hitglowDrawing, coord = (x, y + .15, z), rot = self.hitGlowsRotation,
                                              scale = (0.5 + .6 * ms * ff, 1.5 + .6 * ms * ff, 1 + .6 * ms * ff),
                                              vertex = (-vtx,-vtx,vtx,vtx), texcoord = (0.0,0.0,1.0,1.0),
                                              multiples = True, alpha = alphaEnabled, color = flamecol)


                    if self.hitglow2Drawing:
                        ff += .3
                        vtx = flameSize * ff

                        flameColorMod = (1.19, 1.78, 12.22)
                        flamecol = tuple([color[ifc]*flameColorMod[ifc] for ifc in range(3)])

                        draw3Dtex(self.hitglow2Drawing, coord = (x, y, z), rot = self.hitGlowsRotation,
                                              scale = (.40 + .6 * ms * ff, 1.5 + .6 * ms * ff, 1 + .6 * ms * ff),
                                              vertex = (-vtx,-vtx,vtx,vtx), texcoord = (0.0,0.0,1.0,1.0),
                                              multiples = True, alpha = alphaEnabled, color = flamecol)


    #renders the flames that appear when a note is struck
    def renderFlames(self, notes, song, pos):
        if not song or self.flameColors[0][0] == -1:
            return

        w = self.boardWidth / self.strings
        flameSize = self.hitFlameSize

        flameLimit = 10.0
        flameLimitHalf = round(flameLimit/2.0)
        renderedNotes = notes

        alphaEnabled = self.hitFlameBlackRemove

        for time, event in renderedNotes:
            if not isinstance(event, Note):
                continue

            if (event.played or event.hopod) and event.flameCount < flameLimit:
                if not self.disableFlameSFX:

                    if self.isDrum:
                        if event.number == 0:
                            continue

                        flameColor = self.flameColors[event.number]

                        x = (self.strings / 2 + .5 - event.number) * w

                    else:
                        x = (self.strings / 2 - event.number) * w
                        flameColor = self.flameColors[event.number]

                    ms = math.sin(self.time) * .25 + 1

                    xlightning = (self.strings / 2 - event.number)*2.2*w
                    ff = 1 + 0.25
                    s = ff/6

                    if not self.hitFlameYPos == 0:
                        y = s - self.hitFlameYPos
                    else:
                        y = 0

                    if not self.hitFlameZPos == 0:
                        z = s - self.hitFlameZPos
                    else:
                        z = 0

                    y + .665

                    ff += 1.5 #ff first time is 2.75 after this

                    vtx = flameSize * ff

                    if not self.hitflamesAnim:
                        self.HCountAni = True

                    if event.flameCount < flameLimitHalf and self.hitflames2Drawing:
                        draw3Dtex(self.hitflames2Drawing, coord = (x, y + .20, z), rot = self.hitFlameRotation,
                                              scale = (.25 + .6 * ms * ff, event.flameCount/6.0 + .6 * ms * ff, event.flameCount / 6.0 + .6 * ms * ff),
                                              vertex = (-vtx,-vtx,vtx,vtx), texcoord = (0.0,0.0,1.0,1.0),
                                              multiples = True, alpha = alphaEnabled, color = flameColor)

                        for i in range(3):
                            draw3Dtex(self.hitflames2Drawing, coord = (x-.005, y + .255, z), rot = self.hitFlameRotation,
                                                  scale = (.30 + i*0.05 + .6 * ms * ff, event.flameCount/(5.5 - i*0.4) + .6 * ms * ff, event.flameCount / (5.5 - i*0.4) + .6 * ms * ff),
                                                  vertex = (-vtx,-vtx,vtx,vtx), texcoord = (0.0,0.0,1.0,1.0),
                                                  multiples = True, alpha = alphaEnabled, color = flameColor)

                    flameColor = tuple([flameColor[ifc] + .38 for ifc in range(3)]) #to make sure the final color looks correct on any color set
                    flameColorMod = 0.1 * (flameLimit - event.flameCount)
                    flamecol = tuple([ifc*flameColorMod for ifc in flameColor])
                    scaleChange = (3.0,2.5,2.0,1.7)
                    yOffset = (.35, .405, .355, .355)
                    scaleMod = .6 * ms * ff

                    for step in range(4):
                        if step == 0:
                            yzscaleMod = event.flameCount/ scaleChange[step]
                        else:
                            yzscaleMod = (event.flameCount + 1)/ scaleChange[step]

                        if self.hitflames1Drawing:
                            draw3Dtex(self.hitflames1Drawing, coord = (x - .005, y + yOffset[step], z), rot = self.hitFlameRotation,
                                                  scale = (.25 + step*.05 + scaleMod, yzscaleMod + scaleMod, yzscaleMod + scaleMod),
                                                  vertex = (-vtx,-vtx,vtx,vtx), texcoord = (0.0,0.0,1.0,1.0),
                                                  multiples = True, alpha = alphaEnabled, color = flamecol)

                event.flameCount += 1

    def renderNote(self, length, sustain, color, tailOnly = False, isTappable = False, fret = 0, isOpen = False, spAct = False):

        if tailOnly:
            return

        noteImage = self.noteButtons

        tailOnly = True

        y = 0
        if isTappable:
            y += 1

        noteImage = self.noteButtons
        texCoord = self.noteTexCoord[y][fret]

        draw3Dtex(noteImage, vertex = self.noteVtx, texcoord = texCoord,
                              scale = (1,1,1), rot = (self.camAngle ,1,0,0), multiples = False, color = color)


    def renderNotes(self, notes, visibility, song, pos):
        if not song and not song.readyToGo:
            return

        w = self.boardWidth / self.strings

        renderedNotes = reversed(notes)
        for time, event in renderedNotes:

            if not isinstance(event, Note):
                continue

            if event.number == 0 and self.isDrum: #MFH - skip all open notes
                continue

            if self.isDrum:
                x  = (self.strings / 2 - .5 - (event.number - 1)) * w
            else:
                x  = (self.strings / 2 - (event.number)) * w

            z  = ((time - pos) / self.currentPeriod) / self.beatsPerUnit

            color      = (1, 1, 1, 1)

            length     = 0

            tailOnly   = False

            if event.tappable < 2 or self.isDrum:
                isTappable = False
            else:
                isTappable = True


            if (event.played or event.hopod): #if the note is hit
                continue

            if self.isDrum:
                sustain = False
            else:
                if event.length > 120:
                    length = (event.length - 50) / self.currentPeriod / self.beatsPerUnit
                if z + length < -1.0:
                    continue
                if event.length <= 120:
                    length = None

                sustain = False
                if event.length > (1.4 * (60000.0 / self.currentBpm) / 4):
                    sustain = True

            glPushMatrix()
            glTranslatef(x, 0, z)

            self.renderNote(length, sustain = sustain, color = color, tailOnly = tailOnly, isTappable = isTappable, fret = event.number, isOpen = False)
            glPopMatrix()

    def renderOpenNotes(self, notes, visibility, song, pos):
        if not song:
            return
        if not song.readyToGo:
            return

        renderedNotes = reversed(notes)
        for time, event in renderedNotes:

            if not isinstance(event, Note):
                continue

            if not event.number == 0: #if Normal note exit
                continue

            isOpen     = True
            x  = 0
            z  = ((time - pos) / self.currentPeriod) / self.beatsPerUnit

            color = (1,1,1,1)

            length = 0

            if (event.played or event.hopod): #if the note is hit
                continue

            glPushMatrix()
            glTranslatef(x, 0, z)
            self.renderNote(length, sustain = False, color = color, tailOnly = False, isTappable = False, fret = event.number, isOpen = isOpen)
            glPopMatrix()

    def renderFrets(self, visibility, song, controls):
        w = self.boardWidth / self.strings
        size = (.22, .22)
        v = 1.0 - visibility

        if self.isDrum:
            self.strings2 = self.strings + 1  # +1 is for the bass drum fret
        else:
            self.strings2 = self.strings

        # death_au:
        # if we leave the depth test enabled, it thinks that the bass drum images
        # are under the other frets and openGL culls them. So I just leave it disabled
        glEnable(GL_DEPTH_TEST)

        for n in range(self.strings2):

            if self.isDrum:  # Drum related fret press things
                if n == 4:
                    keyNumb = 0
                    x = 0 # bass fret x position
                    glDisable(GL_DEPTH_TEST)
                else:
                    keyNumb = n + 1
                    x = (self.strings / 2 - .5 - n) * w # drum fret x position

                pressed = self.drumsHeldDown[keyNumb]

            else:
                pressed = None  # to make sure guitar doesnt crash
                x = (self.strings / 2 - n) * w # guitar fret x position

            fretColor = (1, 1, 1, 1)

            if self.isDrum and n == 4:
                size = (self.boardWidth / 2, self.boardWidth / self.strings / 2.4)
                texSize = (0.0, 1.0)
                texY = (1.0 / self.fretImgColNumber, 2.0 / self.fretImgColNumber)
            else:
                size = (self.boardWidth / self.strings / 2, self.boardWidth / self.strings / 2.4)
                texSize = (n / self.lanenumber, n / self.lanenumber + 1 / self.lanenumber)

            if controls.getState(self.keys[n]) or controls.getState(self.keys[n+5]) or pressed: # fret press
                if self.isDrum:
                    if n == 4: # bass drum
                        texY = (3.0 / self.fretImgColNumber, 4.0 / self.fretImgColNumber)
                    else:
                        texY = (2.0 / self.fretImgColNumber, 3.0 / self.fretImgColNumber)
                else: # guitar / bass
                    texY = (1.0 / self.fretImgColNumber, 2.0 / self.fretImgColNumber)

            elif self.hit[n]: # frets on note hit
                if self.isDrum:
                    if n == 4: # bass drum
                        texY = (5.0 / self.fretImgColNumber, 1.0)
                    else:
                        texY = (4.0 / self.fretImgColNumber, 5.0 / self.fretImgColNumber)
                else: # guitar / bass
                    texY = (2.0 / self.fretImgColNumber, 1.0)
            else: # nothing being pressed or hit
                if self.isDrum and n == 4: # bass drum
                    texY = (1.0 / self.fretImgColNumber, 2.0 / self.fretImgColNumber)
                else:
                    texY = (0.0, 1.0 / self.fretImgColNumber)  # fret normal guitar/bass/drums

            draw3Dtex(self.fretButtons, vertex=(size[0], size[1], -size[0], -size[1]),
                texcoord=(texSize[0], texY[0], texSize[1], texY[1]),
                coord=(x, v, 0), multiples=True, color=fretColor, depth=True)

        glDisable(GL_DEPTH_TEST)

    def renderHitGlow(self):
        for n in range(self.strings2):
            c = self.glowColor[n]
            f = self.fretActivity[n]
            w = self.boardWidth / self.strings
            x = (self.strings / 2 - n) * w
            if self.fretPress:
                y = f / 6
            else:
                y = 0
            size = .22

            if f and self.disableFretSFX != True:

                if self.glowColor[0] == -1:
                    s = 1.0
                else:
                    s = 0.0

                while s < 1:
                    ms = s * (math.sin(self.time) * .25 + 1)
                    glColor3f(c[0] * (1 - ms), c[1] * (1 - ms), c[2] * (1 - ms))

                    glPushMatrix()
                    glTranslatef(x, y, 0)
                    glScalef(.1 + .02 * ms * f, .1 + .02 * ms * f, .1 + .02 * ms * f)
                    glRotatef( 90, 0, 1, 0)
                    glRotatef(-90, 1, 0, 0)
                    glRotatef(-90, 0, 0, 1)
                    glPopMatrix()
                    s += 0.2

                f += 2

                draw3Dtex(self.glowDrawing, coord = (x, 0, 0.01), rot = (f * 90 + self.time, 0, 1, 0),
                                    texcoord = (0.0, 0.0, 1.0, 1.0), vertex = (-size * f, -size * f, size * f, size * f),
                                    multiples = True, alpha = True, color = c[:3])

    def renderTail(self, song, length, sustain, color, tailOnly = False, big = False, fret = 0, pos = 0):

        def project(beat):
            return 0.125 * beat / self.beatsPerUnit    # glorandwarf: was 0.12

        offset = (pos - self.lastBpmChange) / self.currentPeriod + self.baseBeat

        self.tailSpeed = self.engine.theme.noteTailSpeedMulti


        if not self.simpleTails: #Seperate Tail images dont color the images
            tailcol = (1,1,1,1)

        elif big == False and tailOnly == True: #grey because the note was missed
            tailcol = (.6, .6, .6, color[3])

        else: #normal colors
            tailcol = (color)


        if length > self.boardLength:
            s = self.boardLength
        else:
            s = length

        size = (.4, s)

        if sustain:
            if not length == None:
                #myfingershurt: so any theme containing appropriate files can use new tails
                if not self.simpleTails:
                    for n in range(5):
                        if big == True and tailOnly == True:
                            if fret == n:
                                tex1 = getattr(self,"btail" + str(n+1))
                                tex2 = getattr(self,"btaile" + str(n+1))
                        else:
                            if tailOnly:#Note let go
                                tex1 = self.tail0
                                tex2 = self.taile0
                            else:
                                if fret == n:
                                    tex1 = getattr(self,"tail" + str(n+1))
                                    tex2 = getattr(self,"taile" + str(n+1))
                else:
                    if big == True and tailOnly == True:
                        tex1 = self.bigTail1
                        tex2 = self.bigTail2
                    else:
                        tex1 = self.tail1
                        tex2 = self.tail2

                #Render the long part of the tail

                glEnable(GL_TEXTURE_2D)

                if length >= self.boardLength:
                    movement1 = (project((offset * self.tailSpeed) * self.beatsPerUnit)*3) - (project(offset * self.beatsPerUnit)*3)
                    movement2 = (project(((offset * self.tailSpeed) + s) * self.beatsPerUnit)*3) - (project(offset * self.beatsPerUnit)*3)
                else:
                    movement1 = (project((offset * self.tailSpeed) * self.beatsPerUnit)*3)
                    movement2 = (project(((offset * self.tailSpeed) + s) * self.beatsPerUnit)*3)

                self.tail_tex[0][1] = self.tail_tex[1][1] = movement1
                self.tail_tex[2][1] = self.tail_tex[3][1] = movement2

                self.tail_col[0][0] = self.tail_col[1][0] = self.tail_col[2][0] = self.tail_col[3][0] = tailcol[0]
                self.tail_col[0][1] = self.tail_col[1][1] = self.tail_col[2][1] = self.tail_col[3][1] = tailcol[1]
                self.tail_col[0][2] = self.tail_col[1][2] = self.tail_col[2][2] = self.tail_col[3][2] = tailcol[2]

                self.tail_vtx[0][0] = self.tail_vtx[2][0] = -size[0]
                self.tail_vtx[1][0] = self.tail_vtx[3][0] = size[0]
                self.tail_vtx[0][2] = self.tail_vtx[1][2] = size[1]

                tex1.texture.bind()

                cmgl.drawArrays(GL_TRIANGLE_STRIP, vertices=self.tail_vtx, colors=self.tail_col, texcoords=self.tail_tex)

                glDisable(GL_TEXTURE_2D)

                draw3Dtex(tex2, vertex = (-size[0], size[1], size[0], size[1] + .6), texcoord = (0.0, 0.0, 1.0, 1.0), color = tailcol) # render the end of a tail

        if tailOnly:
            return

    def renderTails(self, notes, visibility, song, pos, killswitch):
        if not song:
            return
        if not song.readyToGo:
            return

        w = self.boardWidth / self.strings

        renderedNotes = notes

        for time, event in renderedNotes:

            if not isinstance(event, Note):
                continue

            if event.length <= 120:
                continue

            c = self.fretColors[event.number]

            x  = (self.strings / 2 - event.number) * w
            z  = ((time - pos) / self.currentPeriod) / self.beatsPerUnit

            color      = (.1 + .8 * c[0], .1 + .8 * c[1], .1 + .8 * c[2], 1.0)
            if event.length > 120:
                length     = (event.length - 50) / self.currentPeriod / self.beatsPerUnit
            else:
                length     = 0
            tailOnly   = False

            # Clip the played notes to the origin
            if event.played or event.hopod: # if the note is played
                tailOnly = True
                length += z
                z = 0
                if length <= 0:
                    continue
            elif z < 0: #if the note is missed
                color = (.6, .6, .6, 1.0)

            big = False
            for i in range(0, self.strings):
                if self.hit[i]:
                    big = True

            if z + length < -1.0:
                continue

            # crop to board edge
            if z+length > self.boardLength:
                length     = self.boardLength-z

            sustain = False
            if event.length > (1.4 * (60000.0 / self.currentBpm) / 4):
                sustain = True

            glPushMatrix()
            glTranslatef(x, (1.0 - visibility) ** (event.number + 1), z)

            if big == True:
                self.renderTail(song, length, sustain = sustain, color = color, tailOnly = tailOnly, big = True, fret = event.number, pos = pos)
            else:
                self.renderTail(song, length, sustain = sustain, color = color, tailOnly = tailOnly, fret = event.number, pos = pos)

            glPopMatrix()
