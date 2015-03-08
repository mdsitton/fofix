#####################################################################
# -*- coding: iso-8859-1 -*-                                        #
#                                                                   #
# Frets on Fire                                                     #
# Copyright (C) 2006 Sami Kyöstilä                                  #
#               2008 myfingershurt                                  #
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

import os
import time
import string

import pygame
from OpenGL.GL import *

from fofix.core.Scene import Scene

from fofix.core.Settings import ConfigChoice, ActiveConfigChoice
from fofix.core.Texture import Texture
from fofix.core.Image import drawImage
from fofix.core.Camera import Camera
from fofix.core.Mesh import Mesh
from fofix.core.Language import _
from fofix.core import Player
from fofix.game import Dialogs
from fofix.game import Song
from fofix.core import Config
from fofix.core import Version
from fofix.game.Menu import Menu
from fofix.core import Log
from fofix.core.constants import *

PRACTICE = 1
CAREER = 2

instrumentDiff = {
  0 : (lambda a: a.diffGuitar),
  1 : (lambda a: a.diffGuitar),
  2 : (lambda a: a.diffBass),
  3 : (lambda a: a.diffGuitar),
  4 : (lambda a: a.diffDrums),
  5 : (lambda a: a.diffVocals)
}

class SongChoosingScene(Scene):
    def __init__(self, engine, libraryName = None, songName = None):
        Scene.__init__(self, engine)

        self.engine.world.sceneName = "SongChoosingScene"

        Song.updateSongDatabase(self.engine)

        self.wizardStarted = False
        self.libraryName   = libraryName
        self.songName      = songName

        if not self.libraryName:
            self.libraryName = self.engine.config.get("setlist", "selected_library")
            if not self.libraryName:
                self.libraryName = Song.DEFAULT_LIBRARY
        if not self.songName:
            self.songName = self.engine.config.get("setlist", "selected_song")

        self.sortOrder   = self.engine.config.get("game", "sort_order")
        self.playerList  = self.players

        self.gameStarted = False

        self.gamePlayers = len(self.playerList)
        self.parts = [None for i in self.playerList]
        self.diffs = [None for i in self.playerList]

        self.time       = 0
        self.lastTime   = 0
        self.miniLobbyTime = 0
        self.selected   = 0
        self.song       = None
        self.loaded     = False

        self.splash     = Dialogs.showLoadingSplashScreen(self.engine, _("Initializing Setlist..."))
        self.items      = []
        self.queued     = True

        self.loadStartTime = time.time()

        self.library    = os.path.join(self.engine.config.get("setlist", "base_library"), self.libraryName)
        if not os.path.isdir(self.engine.resource.fileName(self.library)):
            self.library = self.engine.resource.fileName(os.path.join(self.engine.config.get("setlist", "base_library"), Song.DEFAULT_LIBRARY))

        #user configurables and input management
        self.listingMode       = 0     #with libraries or List All
        self.preloadSongLabels = False
        self.scrolling        = 0
        self.scrollDelay      = self.engine.config.get("game", "scroll_delay")
        self.scrollRate       = self.engine.config.get("game", "scroll_rate")
        self.scrollTime       = 0
        self.scroller         = [lambda: None, self.scrollUp, self.scrollDown]
        self.scoreDifficulty  = Song.difficulties[self.engine.config.get("game", "songlist_difficulty")]
        self.scorePart        = Song.parts[self.engine.config.get("game", "songlist_instrument")]
        self.sortOrder        = self.engine.config.get("game", "sort_order")
        self.queueFormat      = self.engine.config.get("game", "queue_format")
        self.queueOrder       = self.engine.config.get("game", "queue_order")
        self.queueParts       = self.engine.config.get("game", "queue_parts")
        self.queueDiffs       = self.engine.config.get("game", "queue_diff")
        self.nilShowNextScore = self.engine.config.get("songlist",  "nil_show_next_score")

        #theme information
        self.themename = self.engine.data.themeLabel
        self.theme = self.engine.theme

        self.setlistStyle = 1
        self.headerSkip = 2
        self.footerSkip = 1
        self.itemSize = (0,.126)
        self.labelType = 0
        self.labelDistance = 0
        self.showMoreLabels = False
        self.texturedLabels = False
        self.itemsPerPage = 7
        self.followItemPos     = (self.itemsPerPage+1)/2
        self.showLockedSongs = False
        self.showSortTiers = True
        self.selectTiers = False

        if len(self.engine.world.songQueue) > 0:
            Dialogs.hideLoadingSplashScreen(self.engine, self.splash)
            return

        #variables for setlist management (Not that this is necessary here - just to see what exists.)
        self.tiersPresent     = False
        self.startingSelected = self.songName
        self.selectedIndex    = 0
        self.selectedItem     = None
        self.selectedOffset   = 0.0
        self.previewDelay     = 1000
        self.previewLoaded    = False
        self.itemRenderAngles = [0.0]
        self.itemLabels       = [None]
        self.xPos             = 0
        self.yPos             = 0
        self.pos              = 0

        self.infoPage         = 0

        self.song_name_text_color = self.theme.song_name_text_colorVar
        self.song_name_selected_color = self.theme.song_name_selected_colorVar
        self.artist_text_color = self.theme.artist_text_colorVar
        self.artist_selected_color = self.theme.artist_selected_colorVar
        self.song_listcd_list_xpos = self.theme.song_listcd_list_Xpos

        #now, load the first library
        self.loadLibrary()

    def loadLibrary(self):
        Log.debug("Loading libraries in %s" % self.library)
        self.loaded = False
        self.tiersPresent = False
        if self.splash:
            Dialogs.changeLoadingSplashScreenText(self.engine, self.splash, _("Browsing Collection..."))
        else:
            self.splash = Dialogs.showLoadingSplashScreen(self.engine, _("Browsing Collection..."))
            self.loadStartTime = time.time()
        self.engine.resource.load(self, "libraries", lambda: Song.getAvailableLibraries(self.engine, self.library), onLoad = self.loadSongs, synch = True)

    def loadSongs(self, libraries):
        Log.debug("Loading songs in %s" % self.library)
        self.engine.resource.load(self, "songs", lambda: Song.getAvailableSongsAndTitles(self.engine, self.library, progressCallback=self.progressCallback), onLoad = self.prepareSetlist, synch = True)

    def progressCallback(self, percent):
        if time.time() - self.loadStartTime > 7:
            Dialogs.changeLoadingSplashScreenText(self.engine, self.splash, _("Browsing Collection...") + ' (%d%%)' % (percent*100))

    def prepareSetlist(self, songs):
        msg = self.engine.setlistMsg
        self.engine.setlistMsg = None
        self.selectedIndex = 0
        self.items = self.songs
        self.itemRenderAngles = [0.0]  * len(self.items)
        self.itemLabels       = [None] * len(self.items)

        shownItems = []
        for item in self.items: #remove things we don't want to see. Some redundancy, but that's okay.
            if isinstance(item, Song.TitleInfo) or isinstance(item, Song.SortTitleInfo):
                if isinstance(item, Song.TitleInfo):
                    continue
                elif isinstance(item, Song.SortTitleInfo):
                    if not self.showSortTiers:
                        continue
                    if len(shownItems) > 0:
                        if isinstance(shownItems[-1], Song.SortTitleInfo):
                            shownItems.pop()
                    shownItems.append(item)
            elif isinstance(item, Song.SongInfo):
                shownItems.append(item)
            else:
                shownItems.append(item)
        if len(shownItems) > 0:
            if isinstance(shownItems[-1], Song.TitleInfo) or isinstance(shownItems[-1], Song.SortTitleInfo):
                shownItems.pop()

        if len(self.items) > 0 and len(shownItems) == 0:
            msg = _("No songs in this setlist are available to play!")
            Dialogs.showMessage(self.engine, msg)
        elif len(shownItems) > 0:
            for item in shownItems:
                if isinstance(item, Song.SongInfo) or isinstance(item, Song.LibraryInfo):
                    self.items = shownItems #make sure at least one item is selectable
                    break
            else:
                msg = _("No songs in this setlist are available to play!")
                Dialogs.showMessage(self.engine, msg)
                self.items = []

        if self.items == []:    #MFH: Catch when there ain't a damn thing in the current folder - back out!
            if self.library != Song.DEFAULT_LIBRARY:
                Dialogs.hideLoadingSplashScreen(self.engine, self.splash)
                self.splash = None
                self.startingSelected = self.library
                self.library     = os.path.dirname(self.library)
                self.selectedItem = None
                self.loadLibrary()
                return

        Log.debug("Setlist loaded.")

        self.loaded           = True

        if self.setlistStyle == 1:
            for i in range(self.headerSkip):
                self.items.insert(0, Song.BlankSpaceInfo())
            for i in range(self.footerSkip):
                self.items.append(Song.BlankSpaceInfo())

        if self.startingSelected is not None:
            for i, item in enumerate(self.items):
                if isinstance(item, Song.SongInfo) and self.startingSelected == item.songName: #TODO: SongDB
                    self.selectedIndex =  i
                    break
                elif isinstance(item, Song.LibraryInfo) and self.startingSelected == item.libraryName:
                    self.selectedIndex =  i
                    break

        for item in self.items:
            if isinstance(item, Song.SongInfo):
                item.name = Song.removeSongOrderPrefixFromName(item.name) #TODO: I don't like this.
            elif not self.tiersPresent and (isinstance(item, Song.TitleInfo) or isinstance(item, Song.SortTitleInfo)):
                self.tiersPresent = True

        while isinstance(self.items[self.selectedIndex], Song.BlankSpaceInfo) or ((isinstance(self.items[self.selectedIndex], Song.TitleInfo) or isinstance(self.items[self.selectedIndex], Song.SortTitleInfo)) and not self.selectTiers):
            self.selectedIndex += 1
            if self.selectedIndex >= len(self.items):
                self.selectedIndex = 0

        self.itemRenderAngles = [0.0]  * len(self.items)
        self.itemLabels       = [None] * len(self.items)

        if self.preloadSongLabels:
            for i in range(len(self.items)):
                self.loadStartTime = time.time()
                Dialogs.changeLoadingSplashScreenText(self.engine, self.splash, _("Loading Album Artwork..."))
                self.loadItemLabel(i, preload = True)

        self.updateSelection()
        Dialogs.hideLoadingSplashScreen(self.engine, self.splash)
        self.splash = None

    def loadItemLabel(self, i, preload = False):
        # Load the item label if it isn't yet loaded
        item = self.items[i]
        if self.itemLabels[i] is None:
            if isinstance(item, Song.SongInfo):
                if self.labelType == 1: #CD covers
                    f = "label.png"
                else:
                    f = "album.png"
                if self.texturedLabels:
                    label = self.engine.resource.fileName(item.libraryNam, item.songName, f)
                    if os.path.exists(label):
                        self.itemLabels[i] = Texture(label)
                    else:
                        self.itemLabels[i] = False
                else:
                    self.itemLabels[i] = self.engine.loadImgDrawing(None, "label", os.path.join(item.libraryNam, item.songName, f))

            elif isinstance(item, Song.LibraryInfo):
                if self.texturedLabels:
                    label = self.engine.resource.fileName(item.libraryName, "label.png")
                    if os.path.exists(label):
                        self.itemLabels[i] = Texture(label)
                    else:
                        self.itemLabels[i] = False
                else:
                    self.itemLabels[i] = self.engine.loadImgDrawing(None, "label", os.path.join(item.libraryName, "label.png"))
            elif isinstance(item, Song.RandomSongInfo):
                self.itemLabels[i] = "Random"
            else:
                return
            if preload:
                if time.time() - self.loadStartTime > 3:
                    self.loadStartTime = time.time()
                    percent = (i*100)/len(self.items)
                    Dialogs.changeLoadingSplashScreenText(self.engine, self.splash, _("Loading Album Artwork...") + " %d%%" % percent)

    def startGame(self, fromQueue = False): #note this is not refined.
        if len(self.engine.world.songQueue) == 0:
            return
        showDialog = True
        if not fromQueue and self.queueFormat == 1 and len(self.engine.world.songQueue) > 1:
            self.engine.world.songQueue.setFullQueue()
            self.engine.world.playingQueue = True
        if self.queueOrder == 1:
            self.songName, self.libraryName = self.engine.world.songQueue.getRandomSong()
        else:
            self.songName, self.libraryName = self.engine.world.songQueue.getSong()
        info = Song.loadSongInfo(self.engine, self.songName, library = self.libraryName)
        guitars = []
        drums = []
        vocals = []
        for part in info.parts:
            if part.id == 4 or part.id == 7:
                drums.append(part)
            elif part.id == 5:
                vocals.append(part)
            else:
                guitars.append(part)
        choose = [[] for i in self.players]
        for i, player in enumerate(self.players):
            j = self.engine.world.songQueue.getParts()[i]
            if player.controlType == 2 or player.controlType == 3:
                choose[i] = drums
            elif player.controlType == 5:
                choose[i] = vocals
            else:
                choose[i] = guitars
        if self.queued:
            showDialog = False
            for i, player in enumerate(self.players):
                if Song.parts[j] in choose[i]:
                    p = Song.parts[j]
                elif self.queueParts == 0:
                    if j == 0:
                        for k in [3, 1, 2]:
                            if Song.parts[k] in choose[i]:
                                p = Song.parts[k]
                                break
                    elif j == 1:
                        for k in [2, 0, 3]:
                            if Song.parts[k] in choose[i]:
                                p = Song.parts[k]
                                break
                    elif j == 2:
                        for k in [1, 0, 3]:
                            if Song.parts[k] in choose[i]:
                                p = Song.parts[k]
                                break
                    elif j == 3:
                        for k in [0, 1, 2]:
                            if Song.parts[k] in choose[i]:
                                p = Song.parts[k]
                                break
                j = self.engine.world.songQueue.getDiffs()[i]
                if Song.difficulties[j] in info.partDifficulties[p.id]:
                    d = Song.difficulties[j]
                elif self.queueDiffs == 0:
                    if j == 0:
                        for k in range(1,4):
                            if Song.difficulties[k] in info.partDifficulties[p.id]:
                                d = Song.difficulties[k]
                    elif j == 1:
                        for k in range(2,5):
                            if Song.difficulties[k%4] in info.partDifficulties[p.id]:
                                d = Song.difficulties[k%4]
                    elif j == 2:
                        if Song.difficulties[3] in info.partDifficulties[p.id]:
                            d = Song.difficulties[3]
                        else:
                            for k in range(1, -1, -1):
                                if Song.difficulties[k] in info.partDifficulties[p.id]:
                                    d = Song.difficulties[k]
                    else:
                        for k in range(2, -1, -1):
                            if Song.difficulties[k] in info.partDifficulties[p.id]:
                                d = Song.difficulties[k]
                elif self.queueDiffs == 1:
                    if j == 3:
                        for k in range(2,-1, -1):
                            if Song.difficulties[k] in info.partDifficulties[p.id]:
                                d = Song.difficulties[k]
                    elif j == 2:
                        for k in range(1,-2,-1):
                            if Song.difficulties[k%4] in info.partDifficulties[p.id]:
                                d = Song.difficulties[k%4]
                    elif j == 1:
                        if Song.difficulties[0] in info.partDifficulties[p.id]:
                            d = Song.difficulties[0]
                        else:
                            for k in range(2,4):
                                if Song.difficulties[k] in info.partDifficulties[p.id]:
                                    d = Song.difficulties[k]
                    else:
                        for k in range(1,4):
                            if Song.difficulties[k] in info.partDifficulties[p.id]:
                                d = Song.difficulties[k]
                if p and d:
                    player.part = p
                    player.difficulty = d
                else:
                    showDialog = True
        if showDialog:
            ready = False
            while not ready:
                ready = Dialogs.choosePartDiffs(self.engine, choose, info, self.players)
                if not ready and not self.queued:
                    return False
        self.freeResources()
        self.engine.world.createScene("GuitarScene", libraryName = self.libraryName, songName = self.songName)
        self.gameStarted = True

    def freeResources(self):
        self.songs = None
        self.folder = None
        self.label = None
        for img in dir(self):
            if img.startswith("img"):
                self.__dict__[img] = None
        self.itemLabels = None
        self.selectedItem = None

    def updateSelection(self):
        self.selectedItem  = self.items[self.selectedIndex]
        self.previewDelay  = 1000
        self.previewLoaded = False

        if len(self.items) < self.itemsPerPage:
            self.pos = 0
        else:
            self.pos = self.selectedIndex - self.itemsPerPage + self.followItemPos
            if self.pos + self.itemsPerPage > len(self.items):
                self.pos = len(self.items) - self.itemsPerPage
            elif self.pos < 0:
                self.pos = 0
        w, h = self.engine.view.geometry[2:4]
        self.xPos = self.pos*(self.itemSize[0]*w)
        self.yPos = self.pos*(self.itemSize[1]*h)

        self.loadItemLabel(self.selectedIndex)
        for i in range(1,1+self.labelDistance):
            if self.selectedIndex+i < len(self.items):
                self.loadItemLabel(self.selectedIndex+i)
            if self.selectedIndex-i >= 0:
                self.loadItemLabel(self.selectedIndex-i)

    def quit(self):
        self.freeResources()
        self.engine.world.resetWorld()

    def keyPressed(self, key, unicode):
        self.lastTime = self.time
        c = self.engine.input.controls.getMapping(key)

        if c in Player.menuNo or key == pygame.K_ESCAPE:
            self.engine.data.cancelSound.play()
            self.quit()
        elif (c in Player.menuYes and not c in Player.starts) or key == pygame.K_RETURN:

            self.engine.data.acceptSound.play()
            if isinstance(self.selectedItem, Song.LibraryInfo):
                self.library = self.selectedItem.libraryName
                self.startingSelected = None
                Log.debug("New library selected: " + str(self.library) )
                self.loadLibrary()
            elif isinstance(self.selectedItem, Song.SongInfo):
                self.libraryName = self.selectedItem.libraryNam
                self.songName = self.selectedItem.songName
                self.engine.config.set("setlist", "selected_library", self.libraryName)
                self.engine.config.set("setlist", "selected_song",    self.songName)
                if self.queueFormat == 0:
                    self.engine.world.songQueue.addSong(self.songName, self.libraryName)
                    self.startGame()
                elif self.queueFormat == 1:
                    if self.engine.world.songQueue.addSongCheckReady(self.songName, self.libraryName):
                        self.startGame()
        elif c in Player.menuDown or key == pygame.K_DOWN:
            self.scrolling = 2
            self.scrollTime = self.scrollDelay
            self.scrollDown()
        elif c in Player.menuUp or key == pygame.K_UP:
            self.scrolling = 1
            self.scrollTime = self.scrollDelay
            self.scrollUp()

    def scrollUp(self):
        self.selectedIndex -= 1
        if self.selectedIndex < 0:
            self.selectedIndex = len(self.items) - 1
        while isinstance(self.items[self.selectedIndex], Song.BlankSpaceInfo) or ((isinstance(self.items[self.selectedIndex], Song.TitleInfo) or isinstance(self.items[self.selectedIndex], Song.SortTitleInfo)) and not self.selectTiers):
            self.selectedIndex -= 1
            if self.selectedIndex < 0:
                self.selectedIndex = len(self.items) - 1
        self.updateSelection()

    def scrollDown(self):
        self.selectedIndex += 1
        if self.selectedIndex >= len(self.items):
            self.selectedIndex = 0
        while isinstance(self.items[self.selectedIndex], Song.BlankSpaceInfo) or ((isinstance(self.items[self.selectedIndex], Song.TitleInfo) or isinstance(self.items[self.selectedIndex], Song.SortTitleInfo)) and not self.selectTiers):
            self.selectedIndex += 1
            if self.selectedIndex >= len(self.items):
                self.selectedIndex = 0
        self.updateSelection()

    def keyReleased(self, key):
        self.scrolling = 0

    def run(self, ticks):
        if len(self.engine.world.songQueue) > 0 and self.queued:
            self.startGame(fromQueue = True)
            return
        if self.gameStarted or self.items == []:
            return

        Scene.run(self, ticks)
        if self.queued:
            self.queued = False
        if self.scrolling:
            self.scrollTime -= ticks
            if self.scrollTime < 0:
                self.scrollTime = self.scrollRate
                self.scroller[self.scrolling]()

        for i in range(len(self.itemRenderAngles)):
            if i == self.selectedIndex:
                self.itemRenderAngles[i] = min(90, self.itemRenderAngles[i] + ticks / 2.0)
            else:
                self.itemRenderAngles[i] = max(0,  self.itemRenderAngles[i] - ticks / 2.0)

    def renderSetlist(self, visibility, topMost):
        w, h = self.engine.view.geometry[2:4]

        #render the item list itself
        for n, i in enumerate(range(self.pos, self.pos+self.itemsPerPage)):
            if i >= len(self.items):
                break
            if i == self.selectedIndex:
                ns = n
                continue
            if isinstance(self.items[i], Song.BlankSpaceInfo):
                continue
            self.renderUnselectedItem(self, i, n)
        self.renderSelectedItem(self, ns) #we render this last to allow overlapping effects.

        #render the foreground stuff last
        self.renderForeground(self)


    def renderForeground(self, scene):
        font = scene.fontDict['songListFont']
        w, h = scene.geometry

        text = scene.scorePart.text
        scale = 0.00250
        glColor3f(1, 1, 1)
        font.render(text, (0.95, 0.000), scale=scale, align = 2)

    def renderUnselectedItem(self, scene, i, n):

        font = self.fontDict['songListFont']

        if not self.items:
            return

        item = self.items[i]
        c1,c2,c3 = self.song_name_text_color
        glColor4f(c1,c2,c3,1)
        text = item.name
        scale = font.scaleText(text, maxwidth = 0.45)
        font.render(text, (self.song_listcd_list_xpos, .09*(n+1)), scale = scale)

        if isinstance(item, Song.SongInfo) and not item.getLocked():
            if not item.frets == "":
                suffix = ", ("+item.frets+")"
            else:
                suffix = ""

            if not item.year == "":
                yeartag = ", "+item.year
            else:
                yeartag = ""

            scale = .0014
            c1,c2,c3 = self.artist_text_color
            glColor4f(c1,c2,c3,1)

            text = string.upper(item.artist)+suffix+yeartag

            scale = font.scaleText(text, maxwidth = 0.4, scale = scale)
            font.render(text, (self.song_listcd_list_xpos + .05, .09*(n+1)+.05), scale=scale)

    def renderSelectedItem(self, scene, n):

        font = self.fontDict['songListFont']
        item = self.selectedItem

        if not item:
            return
        if isinstance(item, Song.BlankSpaceInfo):
            return

        c1,c2,c3 = self.song_name_selected_color
        glColor4f(c1,c2,c3,1)
        text = item.name
        scale = font.scaleText(text, maxwidth = 0.45)
        font.render(text, (self.song_listcd_list_xpos, .09*(n+1)), scale = scale)

        if isinstance(item, Song.SongInfo):
            if not item.frets == "":
                suffix = ", ("+item.frets+")"
            else:
                suffix = ""

            if not item.year == "":
                yeartag = ", "+item.year
            else:
                yeartag = ""

            scale = .0014
            c1,c2,c3 = self.artist_selected_color
            glColor4f(c1,c2,c3,1)
            text = string.upper(item.artist)+suffix+yeartag

            scale = font.scaleText(text, maxwidth = 0.4, scale = scale)
            font.render(text, (self.song_listcd_list_xpos + .05, .09*(n+1)+.05), scale=scale)


    def render(self, visibility, topMost):
        if self.gameStarted:
            return
        if self.items == []:
            return
        Scene.render(self, visibility, topMost)
        with self.engine.view.orthogonalProjection(normalize = True):
            self.engine.view.setViewport(1,0)
            w, h = self.engine.view.geometry[2:4]

            self.renderSetlist(visibility, topMost)
