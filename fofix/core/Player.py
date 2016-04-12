#####################################################################
# -*- coding: iso-8859-1 -*-                                        #
#                                                                   #
# Frets on Fire                                                     #
# Copyright (C) 2006 Sami Kyöstilä                                  #
#               2008 Alarian                                        #
#               2008 myfingershurt                                  #
#               2008 Glorandwarf                                    #
#               2008 QQStarS                                        #
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

from fofix.core.Language import _
from fofix.core import Config
from fofix.core import constants
from fofix.core import Log


LEFT    = 0x1
RIGHT   = 0x2
UP      = 0x4
DOWN    = 0x8
ACTION1 = 0x10
ACTION2 = 0x20
KEY1    = 0x40
KEY2    = 0x80
KEY3    = 0x100
KEY4    = 0x200
KEY5    = 0x400
START   = 0x800
CANCEL  = 0x1000

#akedrou: note that the drum controls map to guitar controls. Controller type is important!
DRUM1             = 8
DRUM2             = 10
DRUM3             = 12
DRUM4             = 14
DRUM5             = 6
DRUMBASS          = 16

GUITARTYPES = [-1, 0]
DRUMTYPES   = [-1, 2]

lefts    = [LEFT]
rights   = [RIGHT]
ups      = [UP]
downs    = [DOWN]
starts   = [START]
cancels  = [CANCEL]

key1s    = []
key2s    = []
key3s    = []
key4s    = []
key5s    = []
action1s = []
action2s = []

drum1s    = []
drum2s    = []
drum3s    = []
drum4s    = []
drum5s    = []
bassdrums = []

menuUp    = []
menuDown  = []
menuPrev  = []
menuNext  = []
menuYes   = []
menuNo    = []

# define configuration keys
Config.define("controller", "name",          str, tipText = _("Name your controller."))
Config.define("controller", "key_left",      str, "K_LEFT",     text = _("Move left"))
Config.define("controller", "key_right",     str, "K_RIGHT",    text = _("Move right"))
Config.define("controller", "key_up",        str, "K_UP",       text = _("Move up"))
Config.define("controller", "key_down",      str, "K_DOWN",     text = _("Move down"))
Config.define("controller", "key_action1",   str, "K_RETURN",   text = (_("Pick"), _("Bass Drum")))
Config.define("controller", "key_action2",   str, "K_RSHIFT",   text = (_("Secondary Pick"), _("Bass Drum 2")))
Config.define("controller", "key_1",         str, "K_F1",       text = (_("Fret #1"), _("Drum #4"), _("Drum #5")))
Config.define("controller", "key_2",         str, "K_F2",       text = (_("Fret #2"), _("Drum #1")))
Config.define("controller", "key_3",         str, "K_F3",       text = (_("Fret #3"), _("Drum #2"), _("Cymbal #2")))
Config.define("controller", "key_4",         str, "K_F4",       text = (_("Fret #4"), _("Drum #3")))
Config.define("controller", "key_5",         str, "K_F5",       text = (_("Fret #5"), None, _("Cymbal #4")))
Config.define("controller", "key_cancel",    str, "K_ESCAPE",   text = _("Cancel"))
Config.define("controller", "key_start",     str, "K_LCTRL",    text = _("Start"))

Config.define("player", "name",          str,  "")
Config.define("player", "difficulty",    int,  constants.MED_DIF)
Config.define("player", "part",          int,  constants.GUITAR_PART)
Config.define("player", "neck",          str,  "")
Config.define("player", "controller",    int,  0)

controllerDict = {}
playername = []
playerpref = []

def loadPlayers():
    global playername, playerpref
    playername = []
    playerpref = []

    playername.append("player")
    #u'2', u'', 0, 2, u''
    #neckt, neck, part, diff, upname
    part   = constants.GUITAR_PART
    diff   = constants.EXP_DIF
    upname = u'player'
    playerpref.append([part, diff, upname])

    return 1

guitarKeyMap = {
    'key_1': pygame.K_F1,
    'key_2': pygame.K_F2,
    'key_3': pygame.K_F3,
    'key_4': pygame.K_F4,
    'key_5': pygame.K_F5,
    'key_action1': pygame.K_RETURN,
    'key_action2': pygame.K_RSHIFT,
    'key_cancel': pygame.K_ESCAPE,
    'key_down': pygame.K_DOWN,
    'key_up': pygame.K_UP,
    'key_left': pygame.K_LEFT,
    'key_right': pygame.K_RIGHT,
    'key_start': pygame.K_LCTRL,
}

drumKeyMap = {
    'key_1': pygame.K_u,
    'key_2': pygame.K_a,
    'key_3': pygame.K_e,
    'key_4': pygame.K_t,
    'key_5': None,
    'key_action1': pygame.K_SPACE,
    'key_action2': None,
    'key_cancel': pygame.K_ESCAPE,
    'key_down': pygame.K_DOWN,
    'key_left': pygame.K_LEFT,
    'key_right': pygame.K_RIGHT,
    'key_start': pygame.K_LCTRL,
    'key_up': pygame.K_UP,
}


class Controls:
    def __init__(self):

        self.logClassInits = Config.get("game", "log_class_inits")
        if self.logClassInits == 1:
            Log.debug("Controls class init (Player.py)...")

        self.controls = ["defaultg", "defaultd"]

        self.maxplayers = 0
        self.guitars    = 0
        self.drums      = 0
        self.mics       = 0
        self.overlap    = []

        self.drumNav = Config.get("game", "drum_navigation")

        self.type       = [0, 2]

        self.flags = 0


        self.controlMapping = {}
        global menuUp, menuDown, menuNext, menuPrev, menuYes, menuNo
        global drum1s, drum2s, drum3s, drum4s, drum5s, bassdrums
        global key1s, key2s, key3s, key4s, key5s, action1s, action2s
        menuUp = []
        menuDown = []
        menuNext = []
        menuPrev = []
        menuYes = []
        menuNo = []
        drum1s = []
        drum2s = []
        drum3s = []
        drum4s = []
        drum5s = []
        bassdrums = []
        key1s = []
        key2s = []
        key3s = []
        key4s = []
        key5s = []
        action1s = []
        action2s = []

        for itype in self.type:
            if itype in DRUMTYPES: #drum set
                drum1s.extend([DRUM1])
                drum2s.extend([DRUM2])
                drum3s.extend([DRUM3])
                drum4s.extend([DRUM4])
                drum5s.extend([DRUM5])
                bassdrums.extend([DRUMBASS])
                if self.drumNav:
                    menuUp.extend([DRUM2])
                    if itype == 3:
                        menuDown.extend([DRUM4])
                    else:
                        menuDown.extend([DRUM3])
                    menuYes.extend([DRUM5])
                    menuNo.extend([DRUM1])
                    menuYes.append(START)
                    menuNo.append(CANCEL)
                    menuUp.append(UP)
                    menuDown.append(DOWN)
                    menuNext.append(RIGHT)
                    menuPrev.append(LEFT)
            elif itype in GUITARTYPES:
                if itype == 0:
                    key1s.extend([KEY1])
                else:
                    key1s.extend([KEY1])
                key2s.extend([KEY2])
                key3s.extend([KEY3])
                key4s.extend([KEY4])
                key5s.extend([KEY5])
                action1s.extend([ACTION1])
                action2s.extend([ACTION2])

                menuUp.extend([ACTION1, UP])
                menuDown.extend([ACTION2, DOWN])
                menuNext.extend([RIGHT, KEY4])
                menuPrev.extend([LEFT, KEY3])
                menuYes.extend([KEY1])
                menuNo.extend([KEY2])

            # if itype == 2:
            #     controlMapping = { #akedrou - drums do not need special declarations!
            #       drumKeyMap["key_left"]:          LEFT,
            #       drumKeyMap["key_right"]:         RIGHT,
            #       drumKeyMap["key_up"]:            UP,
            #       drumKeyMap["key_down"]:          DOWN,
            #       drumKeyMap["key_cancel"]:        CANCEL,
            #       drumKeyMap["key_action2"]:       DRUMBASSA,
            #       drumKeyMap["key_1"]:             DRUM5,
            #       drumKeyMap["key_2"]:             DRUM1,
            #       drumKeyMap["key_3"]:             DRUM2,
            #       drumKeyMap["key_4"]:             DRUM3,
            #       drumKeyMap["key_action1"]:       DRUMBASS,
            #       drumKeyMap["key_start"]:         START,
            #     }
            #if itype > -1:
            self.controlMapping = { #akedrou - drums do not need special declarations!
              guitarKeyMap["key_left"]:          LEFT,
              guitarKeyMap["key_right"]:         RIGHT,
              guitarKeyMap["key_up"]:            UP,
              guitarKeyMap["key_down"]:          DOWN,
              guitarKeyMap["key_cancel"]:        CANCEL,
              guitarKeyMap["key_1"]:             KEY1,
              guitarKeyMap["key_2"]:             KEY2,
              guitarKeyMap["key_3"]:             KEY3,
              guitarKeyMap["key_4"]:             KEY4,
              guitarKeyMap["key_5"]:             KEY5,
              guitarKeyMap["key_action2"]:       ACTION2,
              guitarKeyMap["key_action1"]:       ACTION1,
              guitarKeyMap["key_start"]:         START,
            }

        self.reverseControlMapping = {value: key for key, value in self.controlMapping.iteritems()}

        # Multiple key support
        self.heldKeys = {}

    def getMapping(self, key):
        try:
            return self.controlMapping[key]
        except KeyError:
            return None

    def getReverseMapping(self, control):
        return self.reverseControlMapping.get(control)

    def keyPressed(self, key):
        c = self.getMapping(key)
        if c:
            self.toggle(c, True)
            if c in self.heldKeys and not key in self.heldKeys[c]:
                self.heldKeys[c].append(key)
            return c
        return None

    def keyReleased(self, key):
        c = self.getMapping(key)
        if c:
            if c in self.heldKeys:
                if key in self.heldKeys[c]:
                    self.heldKeys[c].remove(key)
                    if not self.heldKeys[c]:
                        self.toggle(c, False)
                        return c
                return None
            self.toggle(c, False)
            return c
        return None

    def toggle(self, control, state):
        prevState = self.flags
        if state:
            self.flags |= control
            return not prevState & control
        else:
            self.flags &= ~control
            return prevState & control

    def getState(self, control):
        return self.flags & control

class Player(object):
    def __init__(self, name, number):

        self.logClassInits = Config.get("game", "log_class_inits")
        if self.logClassInits == 1:
            Log.debug("Player class init (Player.py)...")

        self.name     = name

        self.reset()
        self.keyList = [LEFT, RIGHT, UP, DOWN, ACTION1, ACTION2, KEY1, KEY2, KEY3, KEY4, KEY5, START, CANCEL]

        self.progressKeys = []
        self.drums        = []
        self.keys         = []
        self.actions      = []
        self.yes          = []
        self.no           = []
        self.conf         = []
        self.up           = []
        self.down         = []
        self.left         = []
        self.right        = []

        self.guitarNum    = None
        self.number       = number

        self.pref = playerpref[self.number]

        self.whichPart   = self.pref[0]
        self._upname      = self.pref[2]
        self._difficulty  = self.pref[1]

        self.startPos = 0.0

        self.hopoFreq = None

        self.controlType = 0 #self.type[self.controller]

    def reset(self):
        self.twoChord      = 0

    def configController(self):
        if self.keyList:
            if self.controlType == 1:
                self.keys      = [KEY1, KEY2, KEY3, KEY4, KEY5]
            else:
                self.keys   = [KEY1, KEY2, KEY3, KEY4, KEY5]

            self.actions  = [ACTION1, ACTION2]
            self.drums    = [DRUMBASS, DRUM1, DRUM2, DRUM3, DRUM5]
            if self.controlType == 1:
                self.progressKeys = [KEY1, CANCEL, START, KEY2]
            else:
                self.progressKeys = [KEY1, CANCEL, START, KEY2]

            if self.controlType in GUITARTYPES:
                self.yes  = [KEY1]
                self.no   = [KEY2]
                self.up   = [ACTION1]
                self.down = [ACTION2]
            elif self.controlType == 2:
                self.yes  = [DRUM5]
                self.no   = [DRUM1]
                self.up   = [DRUM2]
                self.down = [DRUM3]
            self.yes.append(START)
            self.no.append(CANCEL)
            self.up.append(UP)
            self.down.append(DOWN)
            self.left.append(LEFT)
            self.right.append(RIGHT)
            #akedrou - add drum4 to the drums when ready
            return True
        else:
            return False

    def getName(self):
        if self._upname == "" or self._upname is None:
            return self.name
        else:
            return self._upname

    def setName(self, name):
        self._upname = name
        self.pref[2] = name

    def getDifficulty(self):
        from fofix.game import Song
        return Song.difficulties.get(self._difficulty)

    def setDifficulty(self, difficulty):
        self.pref[1] = difficulty.id
        self._difficulty = difficulty.id

    def getDifficultyInt(self):
        return self._difficulty

    def getPart(self):
        from fofix.game import Song
        return Song.parts.get(self.whichPart)

    def setPart(self, part):
        self.whichPart = part.id

        self.pref[0] = self.whichPart

    difficulty = property(getDifficulty, setDifficulty)
    part = property(getPart, setPart)
    upname = property(getName, setName)
