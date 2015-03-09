#####################################################################
# -*- coding: iso-8859-1 -*-                                        #
#                                                                   #
# Frets on Fire                                                     #
# Copyright (C) 2009 Team FoFiX                                     #
#               2009 Blazingamer(n_hydock@comcast.net)              #
#                                                                   #
# This program is free software; you can redistribute it and/or     #
# modify it under the terms of the GNU General Public License       #
# as published by the Free Software Foundation; either version 2    #++-
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
import random

from OpenGL.GL import *
import numpy as np

from fofix.game.Song import Bars
from fofix.game import Song
from fofix.core import cmgl
from fofix.core import Log

class Neck:
    def __init__(self, engine, instrument, playerObj):

        self.engine         = engine
        self.player         = instrument.player
        self.instrument     = instrument

        self.isDrum       = self.instrument.isDrum
        self.isBassGuitar = self.instrument.isBassGuitar
        self.isVocal      = self.instrument.isVocal

        self.oNeckovr = None    #MFH - needs to be here to prevent crashes!

        self.staticStrings  = self.engine.config.get("performance", "static_strings")


        self.boardWidth     = self.engine.theme.neckWidth
        self.boardLength    = self.engine.theme.neckLength

        self.beatsPerBoard  = 5.0
        self.beatsPerUnit   = self.beatsPerBoard / self.boardLength

        color = (1.0,1.0,1.0)


        size = 0

        # evilynux - Neck color
        self.board_col  = np.array([[color[0], color[1], color[2], 0.0],
                                 [color[0], color[1], color[2], 0.0],
                                 [color[0], color[1], color[2], 1.0],
                                 [color[0], color[1], color[2], 1.0],
                                 [color[0], color[1], color[2], 1.0],
                                 [color[0], color[1], color[2], 1.0],
                                 [color[0], color[1], color[2], 0.0],
                                 [color[0], color[1], color[2], 0.0]], dtype=np.float32)

        w            = self.boardWidth
        l            = self.boardLength

        self.board_vtx = np.array([[-w / 2.0, 0.0, -2.0],
                                [w / 2.0, 0.0, -2.0],
                                [-w/ 2.0, 0.0, -1.0],
                                [w / 2.0, 0.0, -1.0],
                                [-w / 2.0, 0.0, l * .7],
                                [w / 2.0, 0.0, l * .7],
                                [-w / 2.0, 0.0, l],
                                [w / 2.0, 0.0, l]], dtype=np.float32)

        self.board_tex  = np.array([[0.0, 0],
                                    [1.0, 0],
                                    [0.0, 0],
                                    [1.0, 0],
                                    [0.0, 0],
                                    [1.0, 0],
                                    [0.0, 0],
                                    [1.0, 0]], dtype=np.float32)


        self.track_vtx = np.array([[-w / 2.0, 0.0, -2.0+size],
                                [w / 2.0, 0.0, -2.0+size],
                                [-w / 2.0, 0.0, -1.0+size],
                                [w / 2.0, 0.0, -1.0+size],
                                [-w / 2.0, 0.0, l * .7],
                                [w / 2.0, 0.0, l * .7],
                                [-w / 2.0, 0.0, l],
                                [w / 2.0, 0.0, l]], dtype=np.float32)

        # evilynux - Sidebars vertices
        w += 0.15
        self.sidebars_vtx = np.array([[-w / 2.0, 0.0, -2.0],
                                   [w / 2.0, 0.0, -2.0],
                                   [-w/ 2.0, 0.0, -1.0],
                                   [w / 2.0, 0.0, -1.0],
                                   [-w / 2.0, 0.0, l * .7],
                                   [w / 2.0, 0.0, l * .7],
                                   [-w / 2.0, 0.0, l],
                                   [w / 2.0, 0.0, l]], dtype=np.float32)

        self.bpm_vtx  = np.array([[-w / 2.0, 0.0,  0.0],
                               [-w / 2.0, 0.0,  0.0],
                               [w / 2.0, 0.0,  0.0],
                               [w / 2.0, 0.0,  0.0]], dtype=np.float32)

        self.bpm_tex  = np.array([[0.0, 1.0],
                               [0.0, 0.0],
                               [1.0, 1.0],
                               [1.0, 0.0]], dtype=np.float32)

        self.bpm_col  = np.array([[color[0], color[1], color[2], 1.0],
                               [color[0], color[1], color[2], 1.0],
                               [color[0], color[1], color[2], 1.0],
                               [color[0], color[1], color[2], 1.0]], dtype=np.float32)

        self.incomingNeckMode = self.engine.config.get("game", "incoming_neck_mode")

        self.currentPeriod  = 60000.0 / self.instrument.currentBpm
        self.lastBpmChange  = -1.0
        self.baseBeat       = 0.0

        themename = self.engine.data.themeLabel
        themepath = os.path.join("themes", themename, "board")

        engine.loadImgDrawing(self, "neckDrawing", os.path.join("necks","defaultneck.png"),  textureSize = (256, 256))
        engine.loadImgDrawing(self, "sideBars", os.path.join(themepath, "side_bars.png"))
        engine.loadImgDrawing(self, "centerLines", os.path.join(themepath, "center_lines.png"))
        engine.loadImgDrawing(self, "bpm_halfbeat", os.path.join(themepath, "bpm_halfbeat.png"))
        engine.loadImgDrawing(self, "bpm_beat", os.path.join(themepath, "bpm_beat.png"))
        engine.loadImgDrawing(self, "bpm_measure", os.path.join(themepath, "bpm_measure.png"))

    def project(self, beat):
        return 0.125 * beat / self.beatsPerUnit    # glorandwarf: was 0.12

    def renderNeck(self, song, pos):
        if not song:
            return

        if not song.readyToGo:
            return

        glEnable(GL_TEXTURE_2D)

        if self.neckDrawing:
            self.neckDrawing.texture.bind()

        cmgl.drawArrays(GL_TRIANGLE_STRIP, vertices=self.board_vtx, colors=self.board_col, texcoords=self.board_tex)

        glDisable(GL_TEXTURE_2D)


    def drawTrack(self, song, pos):
        if not song:
            return
        if not song.readyToGo:
            return

        glEnable(GL_TEXTURE_2D)

        if self.centerLines:
            self.centerLines.texture.bind()

        cmgl.drawArrays(GL_TRIANGLE_STRIP, vertices=self.track_vtx, colors=self.board_col, texcoords=self.board_tex)

        glDisable(GL_TEXTURE_2D)

    def drawSideBars(self, song, pos):
        if not song:
            return
        if not song.readyToGo:
            return

        glEnable(GL_TEXTURE_2D)

        if self.sideBars:
            self.sideBars.texture.bind()

        cmgl.drawArrays(GL_TRIANGLE_STRIP, vertices=self.sidebars_vtx, colors=self.board_col, texcoords=self.board_tex)
        glDisable(GL_TEXTURE_2D)

    def drawBPM(self, song, pos):
        if not song:
            return
        if not song.readyToGo:
            return

        track = song.track[self.player]

        glEnable(GL_TEXTURE_2D)

        for time, event in track.getEvents(pos - self.currentPeriod * 2, pos + self.currentPeriod * self.beatsPerBoard):
            if not isinstance(event, Bars):
                continue

            glPushMatrix()
            z  = ((time - pos) / self.currentPeriod) / self.beatsPerUnit
            sw = 0.1 #width

            self.bpm_vtx[0][2] = self.bpm_vtx[2][2] = z + sw
            self.bpm_vtx[1][2] = self.bpm_vtx[3][2] = z - sw

            if event.barType == 0: #half-beat
                self.bpm_halfbeat.texture.bind()
            elif event.barType == 1: #beat
                self.bpm_beat.texture.bind()
            elif event.barType == 2: #measure
                self.bpm_measure.texture.bind()

            cmgl.drawArrays(GL_TRIANGLE_STRIP, vertices=self.bpm_vtx, colors=self.bpm_col, texcoords=self.bpm_tex)

            glPopMatrix()

        glDisable(GL_TEXTURE_2D)

    def render(self, visibility, song, pos):

        l = self.boardLength

        self.currentPeriod = self.instrument.neckSpeed
        offset = (pos - self.lastBpmChange) / self.currentPeriod + self.baseBeat

        #basically sets the scrolling of the necks
        self.board_tex[0][1] = self.board_tex[1][1] = self.project(offset - 2 * self.beatsPerUnit)
        self.board_tex[2][1] = self.board_tex[3][1] = self.project(offset - 1 * self.beatsPerUnit)
        self.board_tex[4][1] = self.board_tex[5][1] = self.project(offset + l * self.beatsPerUnit * .7)
        self.board_tex[6][1] = self.board_tex[7][1] = self.project(offset + l * self.beatsPerUnit)

        self.renderNeck(song, pos)
        self.drawTrack(song, pos)
        self.drawBPM(song, pos)
        self.drawSideBars(song, pos)