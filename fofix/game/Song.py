#####################################################################
# -*- coding: iso-8859-1 -*-                                        #
#                                                                   #
# Frets on Fire                                                     #
# Copyright (C) 2006 Sami Kyöstilä                                  #
#               2008 myfingershurt                                  #
#               2009 Pascal Giard                                   #
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
import re
import time
import random
import hashlib

from fofix.core.utils import hexToColor, colorToHex
from fofix.core.Unicode import utf8
from fofix.core.Language import _
from fofix.core.Theme import *
from fofix.core import midi
from fofix.core import Log
from fofix.core import Audio
from fofix.core import Config
from fofix.core import Version
from fofix.core.constants import EXP_DIF, HAR_DIF, MED_DIF, EAS_DIF
from fofix.core.constants import GUITAR_TRACK, RHYTHM_TRACK, DRUM_TRACK
from fofix.core.constants import GUITAR_PART, RHYTHM_PART, BASS_PART, LEAD_PART, \
                                 DRUM_PART, VOCAL_PART, PRO_GUITAR_PART, PRO_DRUM_PART

DEFAULT_BPM = 120.0
DEFAULT_LIBRARY         = "songs"

#MFH - special / global text-event tracks for the separated text-event list variable
TK_SCRIPT = 0         #script.txt events
TK_SECTIONS = 1       #Section events
TK_GUITAR_SOLOS = 2   #Guitar Solo start/stop events
TK_LYRICS = 3         #RB MIDI Lyric events
TK_UNUSED_TEXT = 4    #Unused / other text events

#MFH
MIDI_TYPE_GH            = 0       #GH type MIDIs have starpower phrases marked with a long G8 note on that instrument's track
MIDI_TYPE_RB            = 1       #RB type MIDIs have overdrive phrases marked with a long G#9 note on that instrument's track
MIDI_TYPE_WT            = 2       #WT type MIDIs have six notes and HOPOs marked on F# of the track

#MFH
EARLY_HIT_WINDOW_NONE   = 1       #GH1/RB1/RB2 = NONE
EARLY_HIT_WINDOW_HALF   = 2       #GH2/GH3/GHA/GH80's = HALF
EARLY_HIT_WINDOW_FULL   = 3       #FoF = FULL

PART_SORT               = [0,2,3,1,6,4,7,5] # these put Lead before Rhythm in menus.
                                            # group by instrument type
SORT_PART               = [0,3,1,2,4,5]

instrumentDiff = {
  0 : (lambda a: a.diffGuitar),
  1 : (lambda a: a.diffGuitar),
  2 : (lambda a: a.diffBass),
  3 : (lambda a: a.diffGuitar),
  4 : (lambda a: a.diffDrums),
  5 : (lambda a: a.diffVocals)
}

class Part:
    def __init__(self, id, text, trackName):
        self.id   = id
        self.text = text
        self.trackName = trackName  #name of which the part is called in the midi

    def __cmp__(self, other):
        if isinstance(other, Part):
            return cmp(PART_SORT[self.id], PART_SORT[other.id])
        else:
            return cmp(self.id, other) #if it's not being compared with a part, we probably want its real ID.

    def __str__(self):
        return self.text

    def __repr__(self):
        return self.text

parts = {
  GUITAR_PART: Part(GUITAR_PART, _("Guitar"), ["PART GUITAR", "T1 GEMS" "Click", "Midi Out"]),
  BASS_PART:   Part(BASS_PART,   _("Bass"),   ["PART BASS"]),
  DRUM_PART:   Part(DRUM_PART,   _("Drums"),  ["PART DRUMS", "PART DRUM"]),
  VOCAL_PART:  Part(VOCAL_PART,  _("Vocals"), ["PART VOCALS"]),
}

class Difficulty:
    def __init__(self, id, text):
        self.id   = id
        self.text = text

    def __cmp__(self, other):
        if isinstance(other, Difficulty):
            return cmp(self.id, other.id)
        else:
            return cmp(self.id, other)

    def __str__(self):
        return self.text

    def __repr__(self):
        return self.text

difficulties = {
  EAS_DIF: Difficulty(EAS_DIF, _("Easy")),
  MED_DIF: Difficulty(MED_DIF, _("Medium")),
  HAR_DIF: Difficulty(HAR_DIF, _("Hard")),
  EXP_DIF: Difficulty(EXP_DIF, _("Expert")),
}


class SongInfo(object):
    def __init__(self, infoFileName, songLibrary = DEFAULT_LIBRARY):
        self.songName      = os.path.basename(os.path.dirname(infoFileName))
        self.fileName      = infoFileName
        self.libraryNam    = songLibrary[:]
        self.info          = Config.MyConfigParser()
        self._partDifficulties = {}
        self._parts        = None
        self._midiStyle    = None

        self.name = _("NoName")

        try:
            self.info.read(infoFileName)
        except:
            pass

        self.logClassInits = Config.get("game", "log_class_inits")
        if self.logClassInits == 1:
            Log.debug("SongInfo class init (song.py): " + self.name)

        notefile = "notes.mid"
        self.noteFileName = os.path.join(os.path.dirname(self.fileName), notefile)

    def _set(self, attr, value):
        if not self.info.has_section("song"):
            self.info.add_section("song")
        self.info.set("song", attr, utf8(value))

    def _get(self, attr, type = None, default = ""):
        try:
            v = self.info.get("song", attr)
        except:
            v = default
        if v == "": #key found, but empty - need to catch as int("") will burn.
            v = default
        if v is not None and type:
            v = type(v)
        return v

    def getPartDifficulties(self):
        if len(self._partDifficulties) != 0:
            return self._partDifficulties
        self.getParts()
        return self._partDifficulties

    partDifficulties = property(getPartDifficulties)

    def getMidiStyle(self):
        if self._midiStyle is not None:
            return self._midiStyle
        self.getParts()
        return self._midiStyle

    midiStyle = property(getMidiStyle)

    def getParts(self):
        if self._parts is not None:
            return self._parts

        # See which parts are available
        try:
            noteFileName = self.noteFileName
            Log.debug("Retrieving parts from: " + noteFileName)
            info = MidiPartsDiffReader()

            midiIn = midi.MidiInFile(info, noteFileName)
            midiIn.read()
            if info.parts == []:
                Log.debug("Improperly named tracks. Attempting to force first track guitar.")
                info = MidiPartsDiffReader(forceGuitar = True)
                midiIn = midi.MidiInFile(info, noteFileName)
                midiIn.read()
            if info.parts == []:
                Log.warn("No tracks found!")
                raise Exception
            self._midiStyle = info.midiStyle
            info.parts.sort(lambda b, a: cmp(b.id, a.id))
            self._parts = info.parts
            for part in info.parts:
                info.difficulties[part.id].sort(lambda a, b: cmp(a.id, b.id))
                self._partDifficulties[part.id] = info.difficulties[part.id]
        except:
            Log.warn("Note file not parsed correctly. Selected part and/or difficulty may not be available.")
            self._parts = parts.values()
            for part in self._parts:
                self._partDifficulties[part.id] = difficulties.values()
        return self._parts

    def getName(self):
        return self._get("name")

    def setName(self, value):
        self._set("name", value)

    @property
    def artist(self):
        return self._get("artist")

    @property
    def album(self):
        return self._get("album")

    @property
    def genre(self):
        return self._get("genre")

    @property
    def icon(self):
        return self._get("icon")

    @property
    def diffSong(self):
        return self._get("diff_band", int, -1)

    @property
    def diffGuitar(self):
        return self._get("diff_guitar", int, -1)

    @property
    def diffDrums(self):
        return self._get("diff_drums", int, -1)

    @property
    def diffBass(self):
        return self._get("diff_bass", int, -1)

    @property
    def diffVocals(self):
        return self._get("diff_vocals", int, -1)

    @property
    def year(self):
        return self._get("year")

    @property
    def loadingPhrase(self):
        return self._get("loading_phrase")

    @property
    def cassetteColor(self):
        c = self._get("cassettecolor")
        if c:
            return hexToColor(c)

    @property
    def delay(self):
        return self._get("delay", int, 0)

    @property
    def frets(self):
        return self._get("frets")

    @property
    def version(self):
        return self._get("version")

    @property
    def tags(self):
        return self._get("tags")

    def getCount(self):
        return self._get("count")

    def setCount(self, value):
        self._set("count", value)

    @property
    def lyrics(self):
        return self._get("lyrics")

    def findTag(self, find, value = None):
        for tag in self.tags.split(','):
            temp = tag.split('=')
            if find == temp[0]:
                if value == None:
                    return True
                elif len(temp) == 2 and value == temp[1]:
                    return True

        return False

    # TODO - Remove these
    @property
    def eighthNoteHopo(self):
        return self._get("eighthnote_hopo")
    @property
    def hopofreq(self):  #MFH
        return self._get("hopofreq")

    name          = property(getName, setName)
    #New RF-mod Items
    parts         = property(getParts)
    count         = property(getCount, setCount)

class LibraryInfo(object):
    def __init__(self, libraryName, infoFileName):
        self.libraryName   = libraryName
        self.fileName      = infoFileName
        self.info          = Config.MyConfigParser()
        self.songCount     = 0

        self.artist = None

        self.logClassInits = Config.get("game", "log_class_inits")
        if self.logClassInits == 1:
            Log.debug("LibraryInfo class init (song.py)...")


        try:
            self.info.read(infoFileName)
        except:
            pass

        # Set a default name
        if not self.name:
            self.name = os.path.basename(os.path.dirname(self.fileName))
        if Config.get("performance", "disable_libcount") == True:
            return
        # Count the available songs
        libraryRoot = os.path.dirname(self.fileName)
        for name in os.listdir(libraryRoot):
            if not os.path.isdir(os.path.join(libraryRoot, name)) or name.startswith("."):
                continue
            if os.path.isfile(os.path.join(libraryRoot, name, "notes.mid")):
                self.songCount += 1
            elif os.path.isfile(os.path.join(libraryRoot, name, "notes-unedited.mid")):
                self.songCount += 1


    def _set(self, attr, value):
        if not self.info.has_section("library"):
            self.info.add_section("library")
        self.info.set("library", attr, utf8(value))

    def _get(self, attr, type = None, default = ""):
        try:
            v = self.info.get("library", attr)
        except:
            v = default
        if v is not None and type:
            v = type(v)
        return v

    def getName(self):
        return self._get("name")

    def setName(self, value):
        self._set("name", value)

    def getColor(self):
        c = self._get("color")
        if c:
            return hexToColor(c)

    def setColor(self, color):
        self._set("color", colorToHex(color))

    name          = property(getName, setName)
    color         = property(getColor, setColor)




class BlankSpaceInfo(object): #MFH
    def __init__(self, nameToDisplay = ""):

        self.logClassInits = Config.get("game", "log_class_inits")
        if self.logClassInits == 1:
            Log.debug("BlankSpaceInfo class init (song.py)...")

        self.name = nameToDisplay
        self.color = None
        self.artist = None    #MFH - prevents search errors


class RandomSongInfo(object): #MFH
    def __init__(self):
        self.logClassInits = Config.get("game", "log_class_inits")
        if self.logClassInits == 1:
            Log.debug("RandomSongInfo class init (song.py)...")

        self.name = _("   (Random Song)")
        self.color = None
        self.artist = None    #MFH - prevents search errors


#coolguy567's unlock system
class TitleInfo(object):
    def __init__(self, config, section):
        self.info    = config
        self.section = section

        self.logClassInits = Config.get("game", "log_class_inits")
        if self.logClassInits == 1:
            Log.debug("TitleInfo class init (song.py)...")

        self.artist = None    #MFH - prevents search errors

    def _set(self, attr, value):
        self.info.set(self.section, attr, utf8(value))

    def _get(self, attr, type = None, default = ""):
        try:
            v = self.info.get(self.section, attr)
        except:
            v = default
        if v is not None and type:
            v = type(v)
        return v

    def getName(self):
        return self._get("name")

    def setName(self, value):
        self._set("name", value)

    def getColor(self):
        c = self._get("color")
        if c:
            return hexToColor(c)

    def setColor(self, color):
        self._set("color", colorToHex(color))


    name          = property(getName, setName)
    color         = property(getColor, setColor)


class SortTitleInfo(object):
    def __init__(self, nameToDisplay):

        self.logClassInits = Config.get("game", "log_class_inits")
        if self.logClassInits == 1:
            Log.debug("TitleInfo class init (song.py)...")

        self.name = nameToDisplay
        self.color = None
        self.artist = None    #MFH - prevents search errors


class Event(object):
    def __init__(self, length):
        self.length = length


class MarkerNote(Event): #MFH
    def __init__(self, number, length, endMarker = False):
        Event.__init__(self, length)
        self.number   = number
        self.endMarker = endMarker
        self.happened = False

    def copy(self):
        return MarkerNote(self.number, self.length, endMarker=self.endMarker)

    def __repr__(self):
        return "<#%d>" % self.number


class Note(Event):
    def __init__(self, number, length, special = False, tappable = 0, star = False, finalStar = False):
        Event.__init__(self, length)
        self.number   = number      #keeps track of fret number
        self.played   = False
        self.special  = special
        self.tappable = tappable
        #RF-mod
        self.hopod   = False
        self.skipped = False
        self.flameCount = 0
        self.HCount2 = 0
        self.star = star
        self.finalStar = finalStar
        #pro-mode
        self.lane = 0               #named lane to be vague so then it can be used in guitar and drums

    def copy(self):
        return Note(self.number, self.length,
                    special=self.special,
                    tappable=self.tappable,
                    star=self.star,
                    finalStar=self.finalStar,)

    def __repr__(self):
        return "<#%d>" % self.number

class VocalNote(Event):
    def __init__(self, note, length, tap = False):
        Event.__init__(self, length)
        self.note = note
        self.phrase = 0
        self.played = False
        self.stopped = False
        self.accuracy = 0.0
        self.tap = tap
        self.speak = False
        self.extra = False #not sure what this is yet - "^"
        self.lyric = None
        self.heldNote = False

class Bars(Event):
    def __init__(self, barType):
        Event.__init__(self, barType)
        self.barType   = barType #0 half-beat, 1 beat, 2 measure
        self.soundPlayed = False

    def __repr__(self):
        return "<BAR #%d>" % self.barType

class Tempo(Event):
    def __init__(self, bpm):
        Event.__init__(self, 0)
        self.bpm = bpm

    def __repr__(self):
        return "<%d bpm>" % self.bpm

class TextEvent(Event):
    def __init__(self, text, length):
        Event.__init__(self, length)
        self.text = text

    def __repr__(self):
        return "<%s>" % self.text

class PictureEvent(Event):
    def __init__(self, fileName, length):
        Event.__init__(self, length)
        self.fileName = fileName

class Track(object):    #MFH - Changing Track class to a base class.  NoteTrack and TempoTrack will extend it.
    granularity = 50

    def __init__(self, engine):
        self.events = []
        self.allEvents = []
        self.marked = False

        self.currentIndex = None   #MFH
        self.maxIndex = None   #MFH

        if engine is not None:
            self.logClassInits = Config.get("game", "log_class_inits")
            if self.logClassInits == 1:
                Log.debug("Track class init (song.py)...")

    def __getitem__(self, index):
        return self.allEvents[index]

    def __len__(self):
        return len(self.allEvents)

    @property
    def length(self):
        lastTime = 0
        for time, event in self.getAllEvents():
            if not isinstance(event, Note) and not isinstance(event, VocalPhrase):
                continue
            if time + event.length > lastTime:
                lastTime = time + event.length
        return round((lastTime+1000.0) / 1000.0) * 1000.0

    def addEvent(self, time, event):
        for t in range(int(time / self.granularity), int((time + event.length) / self.granularity) + 1):
            if len(self.events) < t + 1:
                n = t + 1 - len(self.events)
                n *= 8
                self.events = self.events + [[] for n in range(n)]
            self.events[t].append((time - (t * self.granularity), event))
        self.allEvents.append((time, event))

        if self.maxIndex == None:   #MFH - tracking track size
            self.maxIndex = 0
            self.currentIndex = 0
        else:
            self.maxIndex += 1

    def removeEvent(self, time, event):
        for t in range(int(time / self.granularity), int((time + event.length) / self.granularity) + 1):
            e = (time - (t * self.granularity), event)
            if t < len(self.events) and e in self.events[t]:
                self.events[t].remove(e)
        if (time, event) in self.allEvents:
            self.allEvents.remove((time, event))

            #MFH - tracking track size
            if self.maxIndex != None:
                self.maxIndex -= 1
                if self.maxIndex < 0:
                    self.maxIndex = None
                    self.currentIndex = None

    def getNextEvent(self, lookAhead = 0):  #MFH
        if self.maxIndex != None and self.currentIndex != None:
            #lookAhead > 0 means look that many indices ahead of the Next event
            if (self.currentIndex + lookAhead) <= self.maxIndex:
                return self.allEvents[self.currentIndex + lookAhead]
        return None

    def getPrevEvent(self, lookBehind = 0):  #MFH - lookBehind of 0 = return previous event.
        if self.maxIndex != None and self.currentIndex != None:
            #lookBehind > 0 means look that many indices behind of the Prev event
            if (self.currentIndex - 1 - lookBehind) >= 0:
                return self.allEvents[self.currentIndex - 1 - lookBehind]
        return None

    def getEvents(self, startTime, endTime):
        t1, t2 = [int(x) for x in [startTime / self.granularity, endTime / self.granularity]]
        if t1 > t2:
            t1, t2 = t2, t1

        events = []
        for t in range(max(t1, 0), min(len(self.events), t2)):
            for diff, event in self.events[t]:
                time = (self.granularity * t) + diff
                if not (time, event) in events:
                    events.append((time, event))
        return events

    def getAllEvents(self):
        return self.allEvents

    def reset(self):
        if self.maxIndex:
            self.currentIndex = 0
        for eventList in self.events:
            for time, event in eventList:
                if isinstance(event, Note):
                    event.played = False
                    event.hopod = False
                    event.skipped = False
                    event.flameCount = 0
                if isinstance(event, MarkerNote):
                    event.happened = False

class VocalTrack(Track):
    def __init__(self, engine):
        self.allNotes = {}
        self.allWords = {}
        self.starTimes = []
        self.minPitch = 127
        self.maxPitch = 0
        self.logTempoEvents = 0
        if engine:
            self.logTempoEvents = engine.config.get("log",   "log_tempo_events")
        Track.__init__(self, engine)

    def getAllNotes(self):
        return self.allNotes

    def addEvent(self, time, event):
        if isinstance(event, VocalNote) or isinstance(event, VocalPhrase):
            Track.addEvent(self, time, event)

    def markPhrases(self):
        phraseId = 0
        phraseTimes = []
        markStars = False
        if len(self.starTimes) < 2:
            markStars = True
            Log.warn("This song does not appear to have any vocal star power events - falling back on auto-generation.")
        for time, event in self.getAllEvents():
            if isinstance(event, VocalPhrase):
                if time in self.starTimes and not markStars:
                    event.star = True
                if time in phraseTimes:
                    Log.warn("Phrase repeated - some lyric phrase errors may occur.")
                    phraseId += 1
                    continue
                if markStars and phraseId+1 % 7 == 0:
                    event.star = True
                phraseTimes.append(time)
                phraseId += 1
        for time, tuple in self.allNotes.iteritems():
            phraseId = 0
            for i, phraseTime in enumerate(self.getAllEvents()):
                if time > phraseTime[0] and time < phraseTime[0] + phraseTime[1].length:
                    phraseId = i
                    if phraseId < 0:
                        phraseId = 0
                    break
            tuple[1].phrase = phraseId
            if not tuple[1].tap:
                try:
                    lyric = self.allWords[tuple[0]]
                except KeyError:
                    lyric = None
                if lyric:
                    if lyric.find("+") >= 0:
                        tuple[1].heldNote = True
                    else:
                        if lyric.find("#") >= 0:
                            tuple[1].speak = True
                            tuple[1].lyric = lyric.strip("#")
                        elif lyric.find("^") >= 0:
                            tuple[1].extra = True
                            tuple[1].lyric = lyric.strip("^")
                        else:
                            tuple[1].lyric = lyric
            else:
                self.allEvents[phraseId][1].tapPhrase = True
            self.allEvents[phraseId][1].addEvent(tuple[0], tuple[1])
            self.allEvents[phraseId][1].minPitch = min(self.allEvents[phraseId][1].minPitch, tuple[1].note)
            self.allEvents[phraseId][1].maxPitch = max(self.allEvents[phraseId][1].maxPitch, tuple[1].note)
        for time, event in self.getAllEvents():
            if isinstance(event, VocalPhrase):
                event.sort()

    def reset(self):
        if self.maxIndex:
            self.currentIndex = 0
        for eventList in self.events:
            for time, event in eventList:
                if isinstance(event, VocalPhrase):
                    for time, note in event.allEvents:
                        note.played = False
                        note.stopped = False
                        note.accuracy = 0.0

class VocalPhrase(VocalTrack, Event):
    def __init__(self, length, star = False):
        Event.__init__(self, length)
        VocalTrack.__init__(self, engine = None)
        self.star = star
        self.tapPhrase = False

    def sort(self):
        eventDict = {}
        newEvents = []
        for time, event in self.allEvents:
            if isinstance(event, VocalNote):
                eventDict[int(time)] = (time, event)
        times = eventDict.keys()
        times.sort()
        for time in times:
            newEvents.append(eventDict[time])
        self.allEvents = newEvents

class TempoTrack(Track):    #MFH - special Track type for tempo events
    def __init__(self, engine):
        Track.__init__(self, engine)
        self.currentBpm = DEFAULT_BPM

    def reset(self):
        self.currentBpm = DEFAULT_BPM

    #MFH - function to track current tempo in realtime based on time / position
    def getCurrentTempo(self, pos):   #MFH
        tempEventHolder = self.getNextEvent()   #MFH - check if next BPM change is here yet
        if tempEventHolder:
            time, event = tempEventHolder
            if pos >= time:
                self.currentIndex += 1
                self.currentBpm = event.bpm
        return self.currentBpm

    def getNextTempoChange(self, pos):  #MFH
        index = 0
        event = None
        while self.currentIndex <= self.maxIndex:
            index += 1
            event = self.getNextEvent(index)
            if isinstance(event[1], Tempo):
                break
            else:
                event = None

        return event

    def markBars(self):
        tempoTime = []
        tempoBpm = []

        #get all the bpm changes and their times
        #MFH - TODO - count tempo events.  If 0, realize and log that this is a song with no tempo events - and go mark all 120BPM bars.
        for time, event in self.allEvents:
            if isinstance(event, Tempo):
                tempoTime.append(time)
                tempoBpm.append(event.bpm)
                continue

        #calculate and add the measures/beats/half-beats
        passes = 0
        limit = len(tempoTime)
        time = tempoTime[0]
        THnote = 256.0 #256th note
        drawBar = True

        for i in xrange(limit-1):
            msTotal = tempoTime[i+1] - time
            if msTotal == 0:
                continue
            tempbpm = tempoBpm[i]
            nbars = (msTotal * (tempbpm / (240.0 / THnote) )) / 1000.0
            inc = msTotal / nbars

            while time < tempoTime[i+1]:
                if drawBar == True:
                    if (passes % (THnote / 1.0) == 0.0): #256/1
                        event = Bars(2) #measure
                        self.addEvent(time, event)
                    elif (passes % (THnote / 4.0) == 0.0): #256/4
                        event = Bars(1) #beat
                        self.addEvent(time, event)
                    elif (passes % (THnote / 8.0) == 0.0): #256/8
                        event = Bars(0) #half-beat
                        self.addEvent(time, event)

                    passes = passes + 1

                time = time + inc
                drawBar = True

            if time > tempoTime[i+1]:
                time = time - inc
                drawBar = False

        #add the last measure/beat/half-beat
        if time == tempoTime[i]:
            if (passes % (THnote / 1.0) == 0.0): #256/1
                event = Bars(2) #measure
                self.addEvent(time, event)
            elif (passes % (THnote / 4.0) == 0.0): #256/4
                event = Bars(1) #beat
                self.addEvent(time, event)
            elif (passes % (THnote / 8.0) == 0.0): #256/8
                event = Bars(0) #half-beat
                self.addEvent(time, event)


class NoteTrack(Track):   #MFH - special Track type for note events, with marking functions
    def __init__(self, engine):
        Track.__init__(self, engine)
        self.chordFudge = 1

        self.hopoTick = engine.config.get("coffee", "hopo_frequency")
        self.songHopoFreq = engine.config.get("game", "song_hopo_freq")
        self.logTempoEvents = engine.config.get("log",   "log_tempo_events")

    def flipDrums(self):
        for time, event in self.allEvents:
            if isinstance(event, Note):
                event.number = (5-event.number)%5

    def markHopoGH2(self, eighthNH, songHopoFreq):
        lastTick = 0
        lastTime  = 0
        lastEvent = Note

        tickDelta = 0
        noteDelta = 0

        try:
            songHopoFreq = int(songHopoFreq)
        except Exception:
            songHopoFreq = None
        if self.songHopoFreq == 1 and (songHopoFreq == 0 or songHopoFreq == 1 or songHopoFreq == 2 or songHopoFreq == 3 or songHopoFreq == 4 or songHopoFreq == 5):
            Log.debug("markHopoGH2: song-specific HOPO frequency %d forced" % songHopoFreq)
            self.hopoTick = songHopoFreq


        #dtb file says 170 ticks
        hopoDelta = 170
        if str(eighthNH) == "1":
            hopoDelta = 250
        else:
            hopoDelta = 170

        self.chordFudge = 1   #MFH - there should be no chord fudge.

        if self.hopoTick == 0:
            ticksPerBeat = 960
        elif self.hopoTick == 1:
            ticksPerBeat = 720
        elif self.hopoTick == 2:
            ticksPerBeat = 480
        elif self.hopoTick == 3:
            ticksPerBeat = 360
        elif self.hopoTick == 4:
            ticksPerBeat = 240
        else:
            ticksPerBeat = 240
            hopoDelta = 250



        hopoNotes = []

        #myfingershurt:
        tickDeltaBeforeLast = 0     #3 notes in the past
        lastTickDelta = 0   #2 notes in the past


        bpmNotes = []
        firstTime = 1

        #MFH - to prevent crashes on songs without a BPM set
        bpmEvent = None
        bpm = None

        #If already processed abort
        if self.marked == True:
            return

        for time, event in self.allEvents:
            if isinstance(event, Tempo):
                bpmNotes.append([time, event])
                continue
            if not isinstance(event, Note):
                continue



            while bpmNotes and time >= bpmNotes[0][0]:
                #Adjust to new BPM
                #bpm = bpmNotes[0][1].bpm
                bpmTime, bpmEvent = bpmNotes.pop(0)
                bpm = bpmEvent.bpm

            if not bpm:
                bpm = DEFAULT_BPM

            tick = (time * bpm * ticksPerBeat) / 60000.0
            lastTick = (lastTime * bpm * ticksPerBeat) / 60000.0




            #skip first note
            if firstTime == 1:
                event.tappable = -3
                lastEvent = event
                lastTime  = time
                eventBeforeLast = lastEvent
                eventBeforeEventBeforeLast = eventBeforeLast
                firstTime = 0
                continue

            #tickDeltaBeforeTickDeltaBeforeLast = tickDeltaBeforeLast    #4 notes in the past
            tickDeltaBeforeLast = lastTickDelta     #3 notes in the past
            lastTickDelta = tickDelta   #2 notes in the past

            tickDelta = tick - lastTick
            noteDelta = event.number - lastEvent.number
            #myfingershurt: This initial sweep drops any notes within the timing
            # threshold into the hopoNotes array (which would be more aptly named,
            #  the "potentialHopoNotes" array).  Another loop down below
            #   further refines the HOPO determinations...

            #previous note and current note HOPOable
            if tickDelta <= hopoDelta:
                #Add both notes to HOPO list even if duplicate.  Will come out in processing
                if (not hopoNotes) or not (hopoNotes[-1][0] == lastTime and hopoNotes[-1][1] == lastEvent):
                    #special case for first marker note.  Change it to a HOPO start
                    if not hopoNotes and lastEvent.tappable == -3:
                        lastEvent.tappable = 1
                    #this may be incorrect if a bpm event happened inbetween this note and last note


                    if bpmEvent:
                        hopoNotes.append([lastTime, bpmEvent])

                    hopoNotes.append([lastTime, lastEvent])


                if bpmEvent:
                    hopoNotes.append([bpmTime, bpmEvent])

                hopoNotes.append([time, event])

            #HOPO definitely over - time since last note too great.
            if tickDelta > hopoDelta:
                if hopoNotes != []:
                    #If the last event is the last HOPO note, mark it as a HOPO end
                    if lastEvent.tappable != -1 and hopoNotes[-1][1] == lastEvent:
                        if lastEvent.tappable >= 0:
                            lastEvent.tappable = 3
                        else:
                            lastEvent.tappable = -1

        #note pattern:
            # R R R R R
            # Y       Y
        #should be
            # 1 3-2-2-4
        #first pass:
            #actual: if first RY considered "same note" as next R:
            #-4 0-2-2
                     #if last RY considered "same note" as prev R:
            #-4 0-2-2-2
            #actual: if first RY not considered "same note" as next R:
            #-4 0-2-2

            #This is the same note as before
            elif noteDelta == 0:
                #Add both notes to bad list even if duplicate.  Will come out in processing
                #myfingershurt: to fix same-note HOPO bug.
                if lastEvent.tappable != -4:   #if the last note was not a chord,
                    if eventBeforeLast.tappable == -4 and lastTickDelta <= hopoDelta:  #and if the event before last was a chord, don't remark the last one.
                        event.tappable = -5
                    else:
                        event.tappable = -2
                    #myfingershurt: yeah, mark the last one.
                    lastEvent.tappable = -2

            #This is a chord
            #myfingershurt: both this note and the last note are listed at the same time
            #to allow after-chord HOPOs, we need a separate identification for "chord" notes
            #and also might need to track the "last" chord notes in a separate array
            elif tickDelta < self.chordFudge:
                #Add both notes to bad list even if duplicate.  Will come out in processing
                #myfingershurt:
                if eventBeforeLast.tappable == -2 and lastTickDelta <= hopoDelta:
                    if eventBeforeEventBeforeLast.tappable >= 0 and tickDeltaBeforeLast <= hopoDelta:
                        eventBeforeLast.tappable = -5   #special case that needs to be caught
                    if lastEvent.tappable == -2:    #catch case where event before last event was marked as the same note
                        if eventBeforeEventBeforeLast.tappable >= 0 and tickDeltaBeforeLast <= hopoDelta:
                            eventBeforeLast.tappable = 0
                lastEvent.tappable = -4
                event.tappable = -4

            #myfingershurt: to really check marking, need to track 3 notes into the past.
            eventBeforeEventBeforeLast = eventBeforeLast
            eventBeforeLast = lastEvent
            lastEvent = event
            lastTime = time

        else:
            #Add last note to HOPO list if applicable
            #myfingershurt:
            if noteDelta != 0 and tickDelta > self.chordFudge and tickDelta < hopoDelta and isinstance(event, Note):

                if bpmEvent:
                    hopoNotes.append([time, bpmEvent])

                hopoNotes.append([time, event])

            #myfingershurt marker: (next - FOR loop)----

        #myfingershurt: comments - updated marking system
        #--at this point, the initial note marking sweep has taken place.  Here is further marking of hopoNotes.
        #the .tappable property has special meanings:
        # -5 = This note is the same as the last note, which was a HOPO, and the next note is a chord.
        #       or, this note is the same as the last note, which was a HOPO, so no matter what it shouldn't be tappable.
        # -4 = This note is part of a chord
        # -3 = This is the very first note in a song
        # -2 = This note is part of a string of "same notes"
        # -1 = This note is too far away from the last note to be tappable.
        #  0 = This note is nowhere near another note and must be strummed (also default value)
        #  1 = This note is the first in a string of HOPOs - this note must be strummed to initiate the HOPOs following it!
        #  2 = This note is in the midst of HOPOs
        #  3 = This note is the final of a string of HOPOs


        firstTime = 1
        note = None

        tickDeltaBeforeTickDeltaBeforeLast = 0    #4 notes in the past
        tickDeltaBeforeLast = 0     #3 notes in the past
        lastTickDelta = 0   #2 notes in the past

        bpmNotes = []

        for time, note in list(hopoNotes):
            if isinstance(note, Tempo):
                bpmNotes.append([time, note])
                continue
            if not isinstance(note, Note):
                continue
            while bpmNotes and time >= bpmNotes[0][0]:
                #Adjust to new BPM
                #bpm = bpmNotes[0][1].bpm
                bpmTime, bpmEvent = bpmNotes.pop(0)
                bpm = bpmEvent.bpm

            if firstTime == 1:
                if note.tappable >= 0:
                    note.tappable = 1
                lastEvent = note
                lastTime = time
                firstTime = 0
                eventBeforeLast = lastEvent
                eventBeforeEventBeforeLast = eventBeforeLast
                eventBeforeEventBeforeEventBeforeLast = eventBeforeLast
                continue

            #need to recompute (or carry forward) BPM at this time

            tickDeltaBeforeTickDeltaBeforeLast = tickDeltaBeforeLast    #4 notes in the past
            tickDeltaBeforeLast = lastTickDelta     #3 notes in the past
            lastTickDelta = tickDelta   #2 notes in the past
            tick = (time * bpm * ticksPerBeat) / 60000.0
            lastTick = (lastTime * bpm * ticksPerBeat) / 60000.0
            tickDelta = tick - lastTick

            #current Note Invalid for HOPO----------
            if note.tappable < 0:

        #test note pattern:
            # R   R     R R R R
            # Y Y Y Y Y     Y
        #first pass:
            #-4-2-4-2-5-2-2-4
        #second pass:
            # 1 3 1 3 1 3-2-4

                #myfingershurt:
                #If current note is beginning of a same note sequence, it's valid for END of HOPO only
                #need to alter this to not screw up single-same-note-before chords:
                if (lastEvent.tappable == 1 or lastEvent.tappable == 2) and note.tappable == -2:
                    note.tappable = 3
                #If current note is invalid for HOPO, and previous note was start of a HOPO section, then previous note not HOPO
                elif lastEvent.tappable == 1:
                    lastEvent.tappable = 0


                #and let's not forget the special case when two same-note-sequences on different frets are in sequence:
                elif lastEvent.tappable == -2 and note.tappable == -2 and lastEvent.number != note.number:
                    lastEvent.tappable = 1
                    note.tappable = 3
                #special case where the new -5 note is followed by a string same notes on a different fret:
                elif lastEvent.tappable == -5 and note.tappable == -2:
                    lastEvent.tappable = 1
                    note.tappable = 3

                #special case where last note was a chord, and this note is counted as the same note as the last in the chord
                elif lastEvent.tappable == -4 and note.tappable == -2:
                    thisNoteShouldStillBeAHopo = True
                    #determine the highest note in the chord:
                    topChordNote = lastEvent.number
                    if eventBeforeLast.number > topChordNote:
                        topChordNote = eventBeforeLast.number
                    numChordNotes = 2
                    #now to determine how many notes were in that chord:
                    if tickDeltaBeforeLast < self.chordFudge:  #is there a 3rd note in the same chord?
                        if eventBeforeEventBeforeLast.number > topChordNote:
                            topChordNote = eventBeforeEventBeforeLast.number
                        numChordNotes = 3
                        if tickDeltaBeforeTickDeltaBeforeLast < self.chordFudge:  #is there a 4th note in the same chord?
                            if eventBeforeEventBeforeEventBeforeLast.number > topChordNote:
                                topChordNote = eventBeforeEventBeforeEventBeforeLast.number
                            numChordNotes = 4
                    if topChordNote == note.number:   #only if the note number matches the top chord note do we outlaw the HOPO.
                        thisNoteShouldStillBeAHopo = False
                    if thisNoteShouldStillBeAHopo:
                        #here, need to go back and mark all notes in this chord as tappable = 1 not just the last one.
                        #chord max of 4 frets (5 is just ridiculous) - so if "lastEvent" is the 4th, must go back and change 3rd, 2nd, and 1st
                        lastEvent.tappable = 1
                        eventBeforeLast.tappable = 1    #at least 2 notes in chord
                        if numChordNotes >= 3:  #is there a 3rd note in the same chord?
                            eventBeforeEventBeforeLast.tappable = 1
                            if numChordNotes == 4:  #is there a 4th note in the same chord?
                                eventBeforeEventBeforeEventBeforeLast.tappable = 1
                        note.tappable = 3

                #If current note is invalid for HOPO, and previous note was a HOPO section, then previous note is end of HOPO
                elif lastEvent.tappable > 0:
                    lastEvent.tappable = 3
            #current note valid
            elif note.tappable >= 0:
                #String of same notes can be followed by HOPO
                if note.tappable == 3:

                    #myfingershurt: the new after-chord HOPO special logic needs to also be applied here
                    if lastEvent.tappable == -5:  #special case, still can be HOPO start
                        lastEvent.tappable = 1
                    if lastEvent.tappable == -4:  #chord
                        thisNoteShouldStillBeAHopo = True
                        #determine the highest note in the chord:
                        topChordNote = lastEvent.number
                        if eventBeforeLast.number > topChordNote:
                            topChordNote = eventBeforeLast.number
                        numChordNotes = 2
                        #now to determine how many notes were in that chord:
                        if tickDeltaBeforeLast < self.chordFudge:  #is there a 3rd note in the same chord?
                            if eventBeforeEventBeforeLast.number > topChordNote:
                                topChordNote = eventBeforeEventBeforeLast.number
                            numChordNotes = 3
                            if tickDeltaBeforeTickDeltaBeforeLast < self.chordFudge:  #is there a 4th note in the same chord?
                                if eventBeforeEventBeforeEventBeforeLast.number > topChordNote:
                                    topChordNote = eventBeforeEventBeforeEventBeforeLast.number
                                numChordNotes = 4
                        if topChordNote == note.number:   #only if the note number matches the top chord note do we outlaw the HOPO.
                            thisNoteShouldStillBeAHopo = False
                        if thisNoteShouldStillBeAHopo:
                            #here, need to go back and mark all notes in this chord as tappable = 1 not just the last one.
                            #chord max of 4 frets (5 is just ridiculous) - so if "lastEvent" is the 4th, must go back and change 3rd, 2nd, and 1st
                            lastEvent.tappable = 1
                            eventBeforeLast.tappable = 1    #at least 2 notes in chord
                            if numChordNotes >= 3:  #is there a 3rd note in the same chord?
                                eventBeforeEventBeforeLast.tappable = 1
                                if numChordNotes == 4:  #is there a 4th note in the same chord?
                                    eventBeforeEventBeforeEventBeforeLast.tappable = 1
                        else:
                            note.tappable = -1

                    #This is the end of a valid HOPO section
                    if lastEvent.tappable == 1 or lastEvent.tappable == 2:
                        eventBeforeEventBeforeEventBeforeLast = eventBeforeLast
                        eventBeforeEventBeforeLast = eventBeforeLast
                        eventBeforeLast = lastEvent
                        lastEvent = note
                        lastTime = time
                        continue
                    if lastEvent.tappable == -2:
                        #If its the same note again it's invalid
                        if lastEvent.number == note.number:
                            note.tappable = -2
                        else:
                            lastEvent.tappable = 1
                    elif lastEvent.tappable == 0:
                        lastEvent.tappable = 1
                    #If last note was invalid or end of HOPO section, and current note is end, it is really not HOPO
                    elif lastEvent.tappable != 2 and lastEvent.tappable != 1:
                        note.tappable = 0
                    #If last event was invalid or end of HOPO section, current note is start of HOPO
                    else:
                        note.tappable = 1
                elif note.tappable == 2:
                    if lastEvent.tappable == -2:
                        note.tappable = 1
                    elif lastEvent.tappable == -1:
                        note.tappable = 0
                    elif lastEvent.tappable == 3:
                        lastEvent.tappable = 2



                elif note.tappable == 1:
                    if lastEvent.tappable == 2:
                        note.tappable = 0



                #myfingershurt: default case, tappable=0
                else:
                    if lastEvent.tappable == -5:  #special case, still can be HOPO start
                        lastEvent.tappable = 1
                    if lastEvent.tappable == -4:  #chord
                        thisNoteShouldStillBeAHopo = True
                        #determine the highest note in the chord:
                        topChordNote = lastEvent.number
                        if eventBeforeLast.number > topChordNote:
                            topChordNote = eventBeforeLast.number
                        numChordNotes = 2
                        #now to determine how many notes were in that chord:
                        if tickDeltaBeforeLast < self.chordFudge:  #is there a 3rd note in the same chord?
                            if eventBeforeEventBeforeLast.number > topChordNote:
                                topChordNote = eventBeforeEventBeforeLast.number
                            numChordNotes = 3
                            if tickDeltaBeforeTickDeltaBeforeLast < self.chordFudge:  #is there a 4th note in the same chord?
                                if eventBeforeEventBeforeEventBeforeLast.number > topChordNote:
                                    topChordNote = eventBeforeEventBeforeEventBeforeLast.number
                                numChordNotes = 4
                        if topChordNote == note.number:   #only if the note number matches the top chord note do we outlaw the HOPO.
                            thisNoteShouldStillBeAHopo = False
                        if thisNoteShouldStillBeAHopo:
                            #here, need to go back and mark all notes in this chord as tappable = 1 not just the last one.
                            #chord max of 4 frets (5 is just ridiculous) - so if "lastEvent" is the 4th, must go back and change 3rd, 2nd, and 1st
                            lastEvent.tappable = 1
                            eventBeforeLast.tappable = 1    #at least 2 notes in chord
                            if numChordNotes >= 3:  #is there a 3rd note in the same chord?
                                eventBeforeEventBeforeLast.tappable = 1
                                if numChordNotes == 4:  #is there a 4th note in the same chord?
                                    eventBeforeEventBeforeEventBeforeLast.tappable = 1
                        else:
                            note.tappable = -1

                    if lastEvent.tappable == -2 and tickDelta <= hopoDelta:  #same note
                        lastEvent.tappable = 1
                    if lastEvent.tappable == 3 and tickDelta <= hopoDelta:   #supposedly last of a HOPO
                        lastEvent.tappable = 2

                    if lastEvent.tappable != 2 and lastEvent.tappable != 1:
                        note.tappable = 1
                    else:
                        if note.tappable == 1:
                            note.tappable = 1
                        else:
                            note.tappable = 2


            #myfingershurt: to really check marking, need to track 4 notes into the past.
            eventBeforeEventBeforeEventBeforeLast = eventBeforeLast
            eventBeforeEventBeforeLast = eventBeforeLast
            eventBeforeLast = lastEvent
            lastEvent = note
            lastTime = time
        else:
            if note != None:
                #Handle last note
                #If it is the start of a HOPO, it's not really a HOPO
                if note.tappable == 1:
                    note.tappable = 0
                #If it is the middle of a HOPO, it's really the end of a HOPO
                elif note.tappable == 2:
                    #myfingershurt: here, need to check if the last note is a HOPO after chord and is being merged into the chord (which happens if too close to end of song)
                    if tickDelta < self.chordFudge:
                        note.tappable = -4
                    else:
                        note.tappable = 3
        self.marked = True


class Song(object):
    def __init__(self, engine, infoFileName, songTrackName, guitarTrackName, rhythmTrackName, noteFileName, scriptFileName = None, partlist = [parts[GUITAR_PART]], drumTrackName = None, crowdTrackName = None):
        self.engine        = engine

        self.logClassInits = self.engine.config.get("game", "log_class_inits")
        if self.logClassInits == 1:
            Log.debug("Song class init (song.py)...")

        self.info         = SongInfo(infoFileName)
        self.tracks = []
        for i in partlist:
            if i == parts[VOCAL_PART]:
                self.tracks.append([VocalTrack(self.engine)])
            else:
                self.tracks.append([NoteTrack(self.engine) for t in range(len(difficulties))])

        self.difficulty   = [difficulties[EXP_DIF] for i in partlist]
        self._playing     = False
        self.start        = 0.0
        self.noteFileName = noteFileName

        self.bpm          = DEFAULT_BPM     #MFH - enforcing a default / fallback tempo of 120 BPM

        self.period = 60000.0 / self.bpm    #MFH - enforcing a default / fallback tempo of 120 BPM

        self.readyToGo = False    #MFH - to prevent anything from happening until all prepration & initialization is complete!


        self.parts        = partlist
        self.delay        = self.engine.config.get("audio", "delay")
        self.delay        += self.info.delay
        self.missVolume   = self.engine.config.get("audio", "miss_volume")
        self.backVolume   = self.engine.config.get("audio", "songvol") #akedrou
        self.activeVolume = self.engine.config.get("audio", "guitarvol")

        self.hasMidiLyrics = False
        self.midiStyle = self.info.midiStyle

        self.earlyHitWindowSize = EARLY_HIT_WINDOW_HALF   #MFH - holds the detected early hit window size for the current song

        self.hasStarpowerPaths = False
        self.hasFreestyleMarkings = False

        #MFH - add a separate variable to house the special text event tracks:
        #MFH - special text-event tracks for the separated text-event list variable
        self.eventTracks       = [Track(self.engine) for t in range(0,5)]    #MFH - should result in eventTracks[0] through [4]

        self.midiEventTracks   = []
        self.activeAudioTracks = []
        for i in partlist:
            if i == parts[VOCAL_PART]:
                self.midiEventTracks.append([None])
            else:
                self.midiEventTracks.append([Track(self.engine) for t in range(len(difficulties))])
                if i == parts[GUITAR_PART] or i == parts[LEAD_PART] or i == parts[PRO_GUITAR_PART]:
                    self.activeAudioTracks.append(GUITAR_TRACK)
                elif i == parts[RHYTHM_PART] or i == parts[BASS_PART]:
                    self.activeAudioTracks.append(RHYTHM_TRACK)
                elif i == parts[DRUM_PART] or i == parts[PRO_DRUM_PART]:
                    self.activeAudioTracks.append(DRUM_TRACK)

        self.vocalEventTrack   = VocalTrack(self.engine)

        self.tempoEventTrack = TempoTrack(self.engine)   #MFH - need a separated Tempo/BPM track!

        self.breMarkerTime = None

        self.songTrack = None
        self.guitarTrack = None
        self.rhythmTrack = None

        #myfingershurt:
        self.drumTrack = None
        #akedrou
        self.crowdTrack = None

        try:
            if songTrackName:
                self.songTrack = Audio.StreamingSound(self.engine.audio.getChannel(0), songTrackName)
        except Exception, e:
            Log.warn("Unable to load song track: %s" % e)

        try:
            if guitarTrackName:
                self.guitarTrack = Audio.StreamingSound(self.engine.audio.getChannel(1), guitarTrackName)
        except Exception, e:
            Log.warn("Unable to load guitar track: %s" % e)

        try:
            if rhythmTrackName:
                self.rhythmTrack = Audio.StreamingSound(self.engine.audio.getChannel(2), rhythmTrackName)
        except Exception, e:
            Log.warn("Unable to load rhythm track: %s" % e)


        try:
            if drumTrackName:
                self.drumTrack = Audio.StreamingSound(self.engine.audio.getChannel(3), drumTrackName)
        except Exception, e:
            Log.warn("Unable to load drum track: %s" % e)

        try:
            if crowdTrackName:
                self.crowdTrack = Audio.StreamingSound(self.engine.audio.getChannel(4), crowdTrackName)
        except Exception, e:
            Log.warn("Unable to load crowd track: %s" % e)

        #MFH - single audio track song detection
        self.singleTrackSong = False
        if (self.songTrack == None) or (self.guitarTrack == None and self.rhythmTrack == None and self.drumTrack == None):
            if not (self.songTrack == None and self.guitarTrack == None and self.rhythmTrack == None and self.drumTrack == None):
                self.singleTrackSong = True
                self.missVolume = self.engine.config.get("audio", "single_track_miss_volume")   #MFH - force single-track miss volume setting instead
                Log.debug("Song with only a single audio track identified - single-track miss volume applied: " + str(self.missVolume))


        # load the notes
        if noteFileName:
            Log.debug("Retrieving notes from: " + noteFileName)
            midiIn = midi.MidiInFile(MidiReader(self), noteFileName)
            midiIn.read()

        # load the script
        if scriptFileName and os.path.isfile(scriptFileName):
            scriptReader = ScriptReader(self, open(scriptFileName))
            scriptReader.read()

        # set playback speed
        if self.engine.audioSpeedFactor != 1.0:
            self.setSpeed(self.engine.audioSpeedFactor)

        #self.tempoEventTrack.songLength =

        self.tempoEventTrack.markBars()

    @property
    def length(self):
        length = 0
        for t in self.tracks:
            for n in t:          #note/vocal tracks
                if n.length > length:
                    length += (n.length - length)
        length += 3000.0
        return length

    #myfingershurt: new function to re-retrieve the a/v delay setting so it can be changed in-game:
    def refreshAudioDelay(self):
        self.delay        = self.engine.config.get("audio", "delay")
        self.delay        += self.info.delay

    #myfingershurt: new function to refresh the miss volume after a pause
    def refreshVolumes(self):
        if self.singleTrackSong:
            self.missVolume = self.engine.config.get("audio", "single_track_miss_volume")   #MFH - force single-track miss volume setting instead
        else:
            self.missVolume   = self.engine.config.get("audio", "miss_volume")
        self.activeVolume   = self.engine.config.get("audio", "guitarvol")
        self.backVolume     = self.engine.config.get("audio", "songvol")


    def getCurrentTempo(self, pos):  #MFH
        return self.tempoEventTrack.getCurrentTempo(pos)

    def setBpm(self, bpm):
        self.bpm    = bpm
        self.period = 60000.0 / self.bpm

    def play(self, start = 0.0):
        self.start = start

        #RF-mod No longer needed?

        self.songTrack.setPosition(start / 1000.0)
        self.songTrack.play()
        if self.singleTrackSong:
            self.songTrack.setVolume(self.activeVolume)
        else:
            self.songTrack.setVolume(self.backVolume)

        if self.guitarTrack:
            assert start == 0.0
            self.guitarTrack.play()
        if self.rhythmTrack:
            assert start == 0.0
            self.rhythmTrack.play()
        #myfingershurt
        if self.drumTrack:
            assert start == 0.0
            self.drumTrack.play()
        if self.crowdTrack:
            assert start == 0.0
            self.crowdTrack.play()
        self._playing = True

    def pause(self):
        self.engine.audio.pause()

    def unpause(self):
        self.engine.audio.unpause()

    def setInstrumentVolume(self, volume, part):
        if self.singleTrackSong:
            self.setGuitarVolume(volume)
        elif part == parts[GUITAR_PART] or part == parts[PRO_GUITAR_PART]:
            self.setGuitarVolume(volume)
        elif part == parts[DRUM_PART] or part == parts[PRO_DRUM_PART]:
            self.setDrumVolume(volume)
        else:
            self.setRhythmVolume(volume)

    def setGuitarVolume(self, volume):
        if self.guitarTrack:
            if volume == 0:
                self.guitarTrack.setVolume(self.missVolume)
            elif volume == 1:
                if GUITAR_TRACK in self.activeAudioTracks or self.singleTrackSong:
                    self.guitarTrack.setVolume(self.activeVolume)
                else:
                    self.guitarTrack.setVolume(self.backVolume)
            else:
                self.guitarTrack.setVolume(volume)
        #This is only used if there is no guitar.ogg to lower the volume of song.ogg instead of muting this track
        # evilynux - It also falls on this with buggy pygame < 1.9 on 64bit CPUs.
        else:
            if volume == 0:
                self.songTrack.setVolume(self.missVolume)
            elif volume == 1:
                if GUITAR_TRACK in self.activeAudioTracks or self.singleTrackSong:
                    self.songTrack.setVolume(self.activeVolume)
                else:
                    self.songTrack.setVolume(self.backVolume)
            else:
                self.songTrack.setVolume(volume)

    def setRhythmVolume(self, volume):
        if self.rhythmTrack:
            if volume == 0:
                self.rhythmTrack.setVolume(self.missVolume)
            elif volume == 1:
                if RHYTHM_TRACK in self.activeAudioTracks:
                    self.rhythmTrack.setVolume(self.activeVolume)
                else:
                    self.rhythmTrack.setVolume(self.backVolume)
            else:
                self.rhythmTrack.setVolume(volume)

    def setDrumVolume(self, volume):
        if self.drumTrack:
            if volume == 0:
                self.drumTrack.setVolume(self.missVolume)
            elif volume == 1:
                if DRUM_TRACK in self.activeAudioTracks:
                    self.drumTrack.setVolume(self.activeVolume)
                else:
                    self.drumTrack.setVolume(self.backVolume)
            else:
                self.drumTrack.setVolume(volume)

    def setInstrumentPitch(self, semitones, part):
        if part == parts[GUITAR_PART]:
            if self.guitarTrack:
                self.guitarTrack.setPitchBendSemitones(semitones)
            else:
                self.songTrack.setPitchBendSemitones(semitones)
        elif part == parts[DRUM_PART]:
            pass
        else:
            if self.rhythmTrack:
                self.rhythmTrack.setPitchBendSemitones(semitones)

    def resetInstrumentPitch(self, part):
        self.setInstrumentPitch(0.0, part)

    def setBackgroundVolume(self, volume):
        if volume == 1:
            self.songTrack.setVolume(self.backVolume)
        else:
            self.songTrack.setVolume(volume)

    def setCrowdVolume(self, volume):
        if self.crowdTrack:
            self.crowdTrack.setVolume(volume)

    def setAllTrackVolumes(self, volume):
        self.setBackgroundVolume(volume)
        self.setDrumVolume(volume)
        self.setRhythmVolume(volume)
        self.setGuitarVolume(volume)
        self.setCrowdVolume(volume)

    def stop(self):
        for tracks in self.tracks:
            for track in tracks:
                track.reset()

        for tracks in self.midiEventTracks:
            for track in tracks:
                if track is not None:
                    track.reset()


        if self.songTrack:
            self.songTrack.stop()
        if self.guitarTrack:
            self.guitarTrack.stop()
        if self.rhythmTrack:
            self.rhythmTrack.stop()
        if self.drumTrack:
            self.drumTrack.stop()
        if self.crowdTrack:
            self.crowdTrack.stop()
        self._playing = False

    def setSpeed(self, speed):
        if self.songTrack:
            self.songTrack.setSpeed(speed)
        if self.guitarTrack:
            self.guitarTrack.setSpeed(speed)
        if self.rhythmTrack:
            self.rhythmTrack.setSpeed(speed)
        if self.drumTrack:
            self.drumTrack.setSpeed(speed)
        if self.crowdTrack:
            self.crowdTrack.setSpeed(speed)

    def fadeout(self, time):
        for tracks in self.tracks:
            for track in tracks:
                track.reset()

        if self.songTrack:
            self.songTrack.fadeout(time)
        if self.guitarTrack:
            self.guitarTrack.fadeout(time)
        if self.rhythmTrack:
            self.rhythmTrack.fadeout(time)
        if self.drumTrack:
            self.drumTrack.fadeout(time)
        if self.crowdTrack:
            self.crowdTrack.fadeout(time)
        self._playing = False

    def getPosition(self):
        if not self._playing:
            pos = 0.0
        else:
            pos = self.songTrack.getPosition() * 1000.0

        if pos < 0.0:
            pos = 0.0
        return pos - self.delay

    def isPlaying(self):
        return self._playing and self.songTrack.isPlaying()

    def getBeat(self):
        return self.getPosition() / self.period

    def update(self, ticks):
        pass

    def getTrack(self):
        return [self.tracks[i][self.difficulty[i].id] for i in range(len(self.difficulty))]

    def getIsSingleAudioTrack(self):
        return self.singleTrackSong

    track = property(getTrack)
    isSingleAudioTrack = property(getIsSingleAudioTrack)

    def getMidiEventTrack(self):   #MFH - for new special MIDI marker note track
        return [self.midiEventTracks[i][self.difficulty[i].id] for i in range(len(self.difficulty))]
    midiEventTrack = property(getMidiEventTrack)


#MFH - translating / marking the common MIDI notes:
noteMap = {     # difficulty, note
  0x60: (EXP_DIF, 0), #=========#0x60 = 96 = C 8
  0x61: (EXP_DIF, 1),           #0x61 = 97 = Db8
  0x62: (EXP_DIF, 2),           #0x62 = 98 = D 8
  0x63: (EXP_DIF, 3),           #0x63 = 99 = Eb8
  0x64: (EXP_DIF, 4),           #0x64 = 100= E 8
  0x54: (HAR_DIF, 0), #=========#0x54 = 84 = C 7
  0x55: (HAR_DIF, 1),           #0x55 = 85 = Db7
  0x56: (HAR_DIF, 2),           #0x56 = 86 = D 7
  0x57: (HAR_DIF, 3),           #0x57 = 87 = Eb7
  0x58: (HAR_DIF, 4),           #0x58 = 88 = E 7
  0x48: (MED_DIF, 0), #=========#0x48 = 72 = C 6
  0x49: (MED_DIF, 1),           #0x49 = 73 = Db6
  0x4a: (MED_DIF, 2),           #0x4a = 74 = D 6
  0x4b: (MED_DIF, 3),           #0x4b = 75 = Eb6
  0x4c: (MED_DIF, 4),           #0x4c = 76 = E 6
  0x3c: (EAS_DIF, 0), #=========#0x3c = 60 = C 5
  0x3d: (EAS_DIF, 1),           #0x3d = 61 = Db5
  0x3e: (EAS_DIF, 2),           #0x3e = 62 = D 5
  0x3f: (EAS_DIF, 3),           #0x3f = 63 = Eb5
  0x40: (EAS_DIF, 4),           #0x40 = 64 = E 5
}

realNoteMap = {       # difficulty, note
  0x60: (EXP_DIF, 0),
  0x61: (EXP_DIF, 1),
  0x62: (EXP_DIF, 2),
  0x63: (EXP_DIF, 3),
  0x64: (EXP_DIF, 4),
  0x65: (EXP_DIF, 5),
  0x48: (HAR_DIF, 0),
  0x49: (HAR_DIF, 1),
  0x4a: (HAR_DIF, 2),
  0x4b: (HAR_DIF, 3),
  0x4c: (HAR_DIF, 4),
  0x4d: (HAR_DIF, 5),
  0x30: (MED_DIF, 0),
  0x31: (MED_DIF, 1),
  0x32: (MED_DIF, 2),
  0x33: (MED_DIF, 3),
  0x34: (MED_DIF, 4),
  0x35: (MED_DIF, 5),
  0x18: (EAS_DIF, 0),
  0x19: (EAS_DIF, 1),
  0x1a: (EAS_DIF, 2),
  0x1b: (EAS_DIF, 3),
  0x1c: (EAS_DIF, 4),
  0x1d: (EAS_DIF, 5),
}


#MFH - special note numbers
starPowerMarkingNote = 103     #note 103 = G 8
overDriveMarkingNote = 116     #note 116 = G#9
hopoMarkingNotes = []
proHopoMarkingNotes = [0x1e, 0x36, 0x4e, 0x66]

freestyleMarkingNote = 124      #notes 120 - 124 = drum fills & BREs - always all 5 notes present


reverseNoteMap = dict([(v, k) for k, v in noteMap.items()])


class ScriptReader:
    def __init__(self, song, scriptFile):
        self.song = song
        self.file = scriptFile

        self.logClassInits = Config.get("game", "log_class_inits")
        if self.logClassInits == 1:
            Log.debug("ScriptReader class init (song.py)...")


    def read(self):
        for line in self.file:
            if line.startswith("#") or line.isspace(): continue
            time, length, type, data = re.split("[\t ]+", line.strip(), 3)
            time   = float(time)
            length = float(length)

            if type == "text":
                event = TextEvent(data, length)
            elif type == "pic":
                event = PictureEvent(data, length)
            else:
                continue

            self.song.eventTracks[TK_SCRIPT].addEvent(time, event)  #MFH - add an event to the script.txt track

class MidiReader(midi.MidiOutStream):
    def __init__(self, song):
        midi.MidiOutStream.__init__(self)
        self.song = song
        self.heldNotes = {}
        self.velocity  = {}
        self.ticksPerBeat = 480
        self.tempoMarkers = []
        self.partTrack = 0
        self.partnumber = -1

        self.vocalTrack = False
        self.useVocalTrack = False
        self.vocalOverlapCheck = []

        self.logClassInits = Config.get("game", "log_class_inits")
        if self.logClassInits == 1:
            Log.debug("MidiReader class init (song.py)...")

        self.logMarkerNotes = Config.get("game", "log_marker_notes")

        self.logTempoEvents = Config.get("log",   "log_tempo_events")

        self.guitarSoloIndex = 0
        self.guitarSoloActive = False
        self.guitarSoloSectionMarkers = False

    def addEvent(self, track, event, time = None):
        if self.partnumber == -1:
            #Looks like notes have started appearing before any part information. Lets assume its part0
            self.partnumber = self.song.parts[0]

        if (self.partnumber == None) and isinstance(event, Note):
            return True

        if time is None:
            time = self.abs_time()
        assert time >= 0

        if track is None:
            for t in self.song.tracks:
                for s in t:
                    s.addEvent(time, event)
        else:
            tracklist = [i for i,j in enumerate(self.song.parts) if self.partnumber == j]
            for i in tracklist:
                #Each track needs it's own copy of the event, otherwise they'll interfere
                eventcopy = event.copy()
                if track < len(self.song.tracks[i]):
                    self.song.tracks[i][track].addEvent(time, eventcopy)

    def addVocalEvent(self, event, time = None):
        if time is None:
            time = self.abs_time()
        assert time >= 0

        if not self.useVocalTrack:
            return True

        track = [i for i,j in enumerate(self.song.parts) if self.partnumber == j][0]
        if isinstance(event, VocalNote):
            self.song.track[track].minPitch = min(event.note, self.song.track[track].minPitch)
            self.song.track[track].maxPitch = max(event.note, self.song.track[track].maxPitch)
            self.song.track[track].allNotes[int(time)] = (time, event)
        elif isinstance(event, VocalPhrase):
            self.song.track[track].addEvent(time, event)

    def addVocalLyric(self, text):
        time = self.abs_time()
        assert time >= 0

        if not self.useVocalTrack:
            return True

        if self.partnumber == None:
            return False

        for i, j in enumerate(self.song.parts):
            if self.partnumber == j:
                track = i

        self.song.track[track].allWords[time] = text

    def addVocalStar(self, time):
        if time is None:
            time = self.abs_time()
        assert time >= 0

        if not self.useVocalTrack:
            return True

        track = [i for i,j in enumerate(self.song.parts) if self.partnumber == j][0]
        self.song.track[track].starTimes.append(time)

    def addTempoEvent(self, event, time = None):    #MFH - universal Tempo track handling
        if not isinstance(event, Tempo):
            return

        if time is None:
            time = self.abs_time()
        assert time >= 0

        #add tempo events to the universal tempo track
        self.song.tempoEventTrack.addEvent(time, event)
        if self.logTempoEvents == 1:
            Log.debug("Tempo event added to Tempo track: " + str(time) + " - " + str(event.bpm) + "BPM" )

    def addSpecialMidiEvent(self, track, event, time = None):    #MFH
        if self.partnumber == -1:
            #Looks like notes have started appearing before any part information. Lets assume its part0
            self.partnumber = self.song.parts[0]

        if (self.partnumber == None) and isinstance(event, MarkerNote):
            return True

        if time is None:
            time = self.abs_time()
        assert time >= 0

        if track is None:
            for t in self.song.midiEventTracks:
                for s in t:
                    s.addEvent(time, event)
        else:

            tracklist = [i for i,j in enumerate(self.song.parts) if self.partnumber == j]
            for i in tracklist:
                #Each track needs it's own copy of the event, otherwise they'll interfere
                eventcopy = event.copy()
                if track < len(self.song.midiEventTracks[i]):
                    self.song.midiEventTracks[i][track].addEvent(time, eventcopy)


    def abs_time(self):
        def ticksToBeats(ticks, bpm):
            return (60000.0 * ticks) / (bpm * self.ticksPerBeat)

        if self.song.bpm:
            currentTime = midi.MidiOutStream.abs_time(self)

            scaledTime      = 0.0
            tempoMarkerTime = 0.0
            currentBpm      = self.song.bpm
            for i, marker in enumerate(self.tempoMarkers):
                time, bpm = marker
                if time > currentTime:
                    break
                scaledTime += ticksToBeats(time - tempoMarkerTime, currentBpm)
                tempoMarkerTime, currentBpm = time, bpm
            return scaledTime + ticksToBeats(currentTime - tempoMarkerTime, currentBpm)
        return 0.0

    def header(self, format, nTracks, division):
        self.ticksPerBeat = division
        if nTracks == 2:
            self.partTrack = 1

    def tempo(self, value):
        bpm = 60.0 * 10.0**6 / value
        self.tempoMarkers.append((midi.MidiOutStream.abs_time(self), bpm))
        if not self.song.bpm:
            self.song.setBpm(bpm)
        self.addTempoEvent(Tempo(bpm))  #MFH

    def sequence_name(self, text):
        self.partnumber = None

        tempText = "Found sequence_name in MIDI: " + text + ", recognized as "
        tempText2 = ""

        for part in self.song.parts:
            if text in part.trackName:
                if (part.id == VOCAL_PART):
                    self.vocalTrack = True
                    self.useVocalTrack = True
                self.partnumber = part
                break    #should only have one instance of an instrument

        if text in parts[VOCAL_PART].trackName and parts[VOCAL_PART] not in self.song.parts:
            self.useVocalTrack = False

        self.guitarSoloIndex = 0
        self.guitarSoloActive = False

    def note_on(self, channel, note, velocity):
        if self.partnumber == None:
            return
        self.velocity[note] = velocity
        self.heldNotes[(self.get_current_track(), channel, note)] = self.abs_time()

    def note_off(self, channel, note, velocity):
        if self.partnumber == None:
            return
        try:
            startTime = self.heldNotes[(self.get_current_track(), channel, note)]
            endTime   = self.abs_time()
            del self.heldNotes[(self.get_current_track(), channel, note)]
            if self.vocalTrack:
                if note > 39 and note < 84:
                    self.addVocalEvent(VocalNote(note, endTime - startTime), time = startTime)
                elif note == 96: #tambourine
                    self.addVocalEvent(VocalNote(note, 1, True), time = startTime)
                elif note == 105 or note == 106:
                    if startTime not in self.vocalOverlapCheck:
                        self.addVocalEvent(VocalPhrase(endTime - startTime), time = startTime)
                        self.vocalOverlapCheck.append(startTime)
                elif note == overDriveMarkingNote:
                    self.addVocalStar(startTime)
                return
            if note in noteMap:
                track, number = noteMap[note]
                self.addEvent(track, Note(number, endTime - startTime, special = self.velocity[note] == 127), time = startTime)

            #MFH: use self.midiEventTracks to store all the special MIDI marker notes, keep the clutter out of the main notes lists
            #  also -- to make use of marker notes in real-time, must add a new attribute to MarkerNote class "endMarker"
            #     if this is == True, then the note is just an event to mark the end of the previous note (which has length and is used in other ways)

            elif note == overDriveMarkingNote:    #MFH
                self.song.hasStarpowerPaths = True
                self.earlyHitWindowSize = EARLY_HIT_WINDOW_NONE

                for diff in difficulties:
                    self.addSpecialMidiEvent(diff, MarkerNote(note, endTime - startTime), time = startTime)
                    self.addSpecialMidiEvent(diff, MarkerNote(note, 1, endMarker = True), time = endTime+1)   #ending marker note
                    if self.logMarkerNotes == 1:
                        Log.debug("RB Overdrive MarkerNote at %f added to part: %s and difficulty: %s" % ( startTime, self.partnumber, difficulties[diff] ) )

            elif note == starPowerMarkingNote:    #MFH
                self.song.hasStarpowerPaths = True
                for diff in difficulties:
                    self.addSpecialMidiEvent(diff, MarkerNote(note, endTime - startTime), time = startTime)
                    self.addSpecialMidiEvent(diff, MarkerNote(note, 1, endMarker = True), time = endTime+1)   #ending marker note
                    if self.logMarkerNotes == 1:
                        Log.debug("GH Starpower (or RB Solo) MarkerNote at %f added to part: %s and difficulty: %s" % ( startTime, self.partnumber, difficulties[diff] ) )

            elif note == freestyleMarkingNote:    #MFH - for drum fills and big rock endings
                self.song.hasFreestyleMarkings = True
                for diff in difficulties:
                    self.addSpecialMidiEvent(diff, MarkerNote(note, endTime - startTime), time = startTime)
                    if self.logMarkerNotes == 1:
                        Log.debug("RB freestyle section (drum fill or BRE) at %f added to part: %s and difficulty: %s" % ( startTime, self.partnumber, difficulties[diff] ) )
            else:
                pass
        except KeyError:
            Log.warn("MIDI note 0x%x on channel %d ending at %d was never started." % (note, channel, self.abs_time()))


    #MFH - OK - this needs to be optimized.
    #There should be a separate "Sections" track, and a separate "Lyrics" track created for their respective events
    #Then another separate "Text Events" track to put all the unused events, so they don't bog down the game when it looks through / filters / sorts these track event lists


    #myfingershurt: adding MIDI text event access
    #these events happen on their own track, and are processed after the note tracks.
    #just mark the guitar solo sections ahead of time
    #and then write an iteration routine to go through whatever track / difficulty is being played in GuitarScene
    #to find these markers and count the notes and add a new text event containing each solo's note count
    def text(self, text):
        if text == '[music_end]':
            time = self.abs_time()

        if text.find("GNMIDI") < 0:   #to filter out the midi class illegal usage / trial timeout messages
            #MFH - if sequence name is PART VOCALS then look for text event lyrics
            if self.vocalTrack:
                if text.find("[") < 0:    #not a marker
                    event = TextEvent(text, 400.0)
                    self.addVocalLyric(text)
                    self.song.hasMidiLyrics = True
                    self.song.eventTracks[TK_LYRICS].addEvent(self.abs_time(), event)  #MFH - add an event to the lyrics track

            else:



                unusedEvent = None
                event = None
                gSoloEvent = False
                #also convert all underscores to spaces so it look better
                text = text.replace("_"," ")
                if text.lower().find("section") >= 0:
                    self.guitarSoloSectionMarkers = True      #GH1 dont use section markers... GH2+ do
                    #strip unnecessary text / chars:
                    text = text.replace("section","")
                    text = text.replace("[","")
                    text = text.replace("]","")
                    #also convert "gtr" to "Guitar"
                    text = text.replace("gtr","Guitar")
                    event = TextEvent(text, 250.0)
                    if text.lower().find("big rock ending") >= 0:
                        curTime = self.abs_time()
                        Log.debug("Big Rock Ending section event marker found at " + str(curTime) )
                        self.song.breMarkerTime = curTime

                    if text.lower().find("solo") >= 0 and text.lower().find("drum") < 0 and text.lower().find("outro") < 0 and text.lower().find("organ") < 0 and text.lower().find("synth") < 0 and text.lower().find("bass") < 0 and text.lower().find("harmonica") < 0:
                        gSoloEvent = True
                        gSolo = True
                    elif text.lower().find("guitar") >= 0 and text.lower().find("lead") >= 0:    #Foreplay Long Time "[section_gtr_lead_1]"
                        gSoloEvent = True
                        gSolo = True
                    elif text.lower().find("guitar") >= 0 and text.lower().find("line") >= 0:   #support for REM Orange Crush style solos
                        gSoloEvent = True
                        gSolo = True
                    elif text.lower().find("guitar") >= 0 and text.lower().find("ostinato") >= 0:   #support for Pleasure solos "[section gtr_ostinato]"
                        gSoloEvent = True
                        gSolo = True
                    else: #this is the cue to end solos...
                        gSoloEvent = True
                        gSolo = False
                elif text.lower().find("solo") >= 0 and text.find("[") < 0 and text.lower().find("drum") < 0 and text.lower().find("map") < 0 and text.lower().find("play") < 0 and not self.guitarSoloSectionMarkers:
                    event = TextEvent(text, 250.0)
                    gSoloEvent = True
                    if text.lower().find("off") >= 0:
                        gSolo = False
                    else:
                        gSolo = True
                elif (text.lower().find("verse") >= 0 or text.lower().find("chorus") >= 0) and text.find("[") < 0 and not self.guitarSoloSectionMarkers:   #this is an alternate GH1-style solo end marker
                    event = TextEvent(text, 250.0)
                    gSoloEvent = True
                    gSolo = False
                elif text.lower().find("gtr") >= 0 and text.lower().find("off") >= 0 and text.find("[") < 0 and not self.guitarSoloSectionMarkers:   #this is an alternate GH1-style solo end marker
                    #also convert "gtr" to "Guitar"
                    text = text.replace("gtr","Guitar")
                    event = TextEvent(text, 100.0)
                    gSoloEvent = True
                    gSolo = False
                else:  #unused text event
                    unusedEvent = TextEvent(text, 100.0)
                #now, check for guitar solo status change:
                if gSoloEvent:
                    if gSolo:
                        if not self.guitarSoloActive:
                            self.guitarSoloActive = True
                            soloEvent = TextEvent("GSOLO ON", 250.0)
                            Log.debug("GSOLO ON event " + event.text + " found at time " + str(self.abs_time()) )
                            self.song.eventTracks[TK_GUITAR_SOLOS].addEvent(self.abs_time(), soloEvent)  #MFH - add an event to the guitar solos track
                    else: #this is the cue to end solos...
                        if self.guitarSoloActive:
                            #MFH - here, check to make sure we're not ending a guitar solo that has just started!!
                            curTime = self.abs_time()
                            if self.song.eventTracks[TK_GUITAR_SOLOS][-1][0] < curTime:
                                self.guitarSoloActive = False
                                soloEvent = TextEvent("GSOLO OFF", 250.0)
                                Log.debug("GSOLO OFF event " + event.text + " found at time " + str(curTime) )
                                self.guitarSoloIndex += 1
                                self.song.eventTracks[TK_GUITAR_SOLOS].addEvent(curTime, soloEvent)  #MFH - add an event to the guitar solos track

                if event:
                    curTime = self.abs_time()
                    if len(self.song.eventTracks[TK_SECTIONS]) <= 1:
                        self.song.eventTracks[TK_SECTIONS].addEvent(curTime, event)  #MFH - add an event to the sections track
                    elif len(self.song.eventTracks[TK_SECTIONS]) > 1:    #ensure it exists first
                        if self.song.eventTracks[TK_SECTIONS][-1][0] < curTime: #ensure we're not adding two consecutive sections to the same location!
                            self.song.eventTracks[TK_SECTIONS].addEvent(curTime, event)  #MFH - add an event to the sections track
                elif unusedEvent:
                    self.song.eventTracks[TK_UNUSED_TEXT].addEvent(self.abs_time(), unusedEvent)  #MFH - add an event to the unused text track

    #myfingershurt: adding MIDI lyric event access
    def lyric(self, text):
        if text.find("GNMIDI") < 0:   #to filter out the midi class illegal usage / trial timeout messages
            event = TextEvent(text, 400.0)
            self.addVocalLyric(text)
            self.song.hasMidiLyrics = True
            self.song.eventTracks[TK_LYRICS].addEvent(self.abs_time(), event)  #MFH - add an event to the lyrics track

class MidiSectionReader(midi.MidiOutStream):
    # We exit via this exception so that we don't need to read the whole file in
    class Done: pass

    def __init__(self):
        midi.MidiOutStream.__init__(self)
        self.difficulties = []

        self.logClassInits = Config.get("game", "log_class_inits")
        if self.logClassInits == 1:
            Log.debug("MidiSectionReader class init (song.py)...")

        #MFH: practice section support:
        self.ticksPerBeat = 480
        self.sections = []
        self.tempoMarkers = []
        self.guitarSoloSectionMarkers = False
        self.bpm = None

        self.noteCountSections = []
        self.nextSectionMinute = 0.25


    def header(self, format=0, nTracks=1, division=96):
        self.ticksPerBeat = division

    def abs_time(self):
        def ticksToBeats(ticks, bpm):
            return (60000.0 * ticks) / (bpm * self.ticksPerBeat)

        if self.bpm:
            currentTime = midi.MidiOutStream.abs_time(self)

            scaledTime      = 0.0
            tempoMarkerTime = 0.0
            currentBpm      = self.bpm
            for i, marker in enumerate(self.tempoMarkers):
                time, bpm = marker
                if time > currentTime:
                    break
                scaledTime += ticksToBeats(time - tempoMarkerTime, currentBpm)
                tempoMarkerTime, currentBpm = time, bpm
            return scaledTime + ticksToBeats(currentTime - tempoMarkerTime, currentBpm)
        return 0.0

    def tempo(self, value):
        self.bpm = 60.0 * 10.0**6 / value
        self.tempoMarkers.append((midi.MidiOutStream.abs_time(self), self.bpm))

    def note_on(self, channel, note, velocity):
        pos = float(midi.MidiOutStream.abs_time(self))
        if (pos / 60000) >= self.nextSectionMinute:
            text = "%d:%02d -> " % (pos / 60000, (pos % 60000) / 1000) + "Section " + str(round(self.nextSectionMinute,2))
            self.nextSectionMinute += 0.25

            self.noteCountSections.append([text,pos])

    def lyric(self, text):  #filter lyric events
        if text.find("GNMIDI") < 0:   #to filter out the midi class illegal usage / trial timeout messages
            text = ""

    #MFH - adding text event / section retrieval here
    #also must prevent "Done" flag setting so can read whole MIDI file, all text events
    def text(self, text):
        if text.find("GNMIDI") < 0:   #to filter out the midi class illegal usage / trial timeout messages
            pos = self.abs_time()
            text = text.replace("_"," ")
            if text.lower().find("section") >= 0:
                if not self.guitarSoloSectionMarkers:
                    self.guitarSoloSectionMarkers = True      #GH1 dont use section markers... GH2+ do
                    self.sections = []  #reset sections
                #strip unnecessary text / chars:
                text = text.replace("section","")
                text = text.replace("[","")
                text = text.replace("]","")
                #also convert "gtr" to "Guitar"
                text = text.replace("gtr","Guitar")

                text = "%d:%02d -> " % (pos / 60000, (pos % 60000) / 1000) + text
                self.sections.append([text,pos])


            elif text.lower().find("solo") >= 0 and text.find("[") < 0 and text.lower().find("drum") < 0 and text.lower().find("map") < 0 and text.lower().find("play") < 0 and not self.guitarSoloSectionMarkers:

                text = "%d:%02d -> " % (pos / 60000, (pos % 60000) / 1000) + text
                self.sections.append([text,pos])
            elif text.lower().find("verse") >= 0 and text.find("[") < 0 and not self.guitarSoloSectionMarkers:   #this is an alternate GH1-style solo end marker

                text = "%d:%02d -> " % (pos / 60000, (pos % 60000) / 1000) + text
                self.sections.append([text,pos])
            elif text.lower().find("gtr") >= 0 and text.lower().find("off") >= 0 and text.find("[") < 0 and not self.guitarSoloSectionMarkers:   #this is an alternate GH1-style solo end marker
                #also convert "gtr" to "Guitar"
                text = text.replace("gtr","Guitar")

                text = "%d:%02d -> " % (pos / 60000, (pos % 60000) / 1000) + text
                self.sections.append([text,pos])
            elif not self.guitarSoloSectionMarkers:   #General GH1-style sections.  Messy but effective.

                text = "%d:%02d -> " % (pos / 60000, (pos % 60000) / 1000) + text
                self.sections.append([text,pos])

            else:  #unused text event
                text = ""


class SongQueue:
    '''Stores a list of songs to be played.'''

    def __init__(self):
        self.songName = []
        self.library = []
        self.diffs = []
        self.parts = []
        self.totalSongName = []
        self.totalLibrary  = []
        self.scores = []

        self.logClassInits = Config.get("game", "log_class_inits")
        if self.logClassInits == 1:
            Log.debug("SongQueue class init (song.py)...")

    def __len__(self):
        return len(self.songName)

    def isLastSong(self, songName, library):
        if len(self.songName) == 0 or len(self.library) == 0:
            return False
        if songName == self.songName[-1] and library == self.library[-1]:
            return True
        return False

    def addSong(self, songName, library):
        # Adds a song to the SongQueue.
        self.songName.append(songName)
        self.library.append(library)

    def addSongCheckReady(self, songName, library):
        # Checks if a song should be added to the SongQueue. If the song is the same as the
        # previous, assume the player intended to start the game instead.
        # returns True if game should be started, and False if the song is added to the queue.
        # @param   songName   folder name of song to be queued.
        # @param   library    path from the default library to the song's parent folder.
        # @return  bool       True if game is ready; False if song is added to queue.
        if self.isLastSong(songName, library):
            return True
        else:
            self.addSong(songName, library)
            return False

    def setFullQueue(self):
        self.totalSongName = self.songName[:]
        self.totalLibrary  = self.library[:]

    def replayFullQueue(self):
        self.songName = self.totalSongName[:]
        self.library = self.totalLibrary[:]
        self.scores = []

    def getSong(self):
        if len(self.songName) == 0 or len(self.library) == 0:
            Log.warn("SongQueue.getSong: Empty queue get.")
            return False
        song = self.songName.pop(0)
        library = self.library.pop(0)
        return song, library

    def getRandomSong(self):
        if len(self.songName) == 0 or len(self.library) == 0:
            Log.warn("SongQueue.getRandomSong: Empty queue get.")
            return False
        n = random.randint(0,len(self.songName)-1)
        song = self.songName.pop(n)
        library = self.library.pop(n)
        return song, library

    def getParts(self):
        return self.parts

    def getDiffs(self):
        return self.diffs

    def addScores(self, scores):
        self.scores.append(scores)

    def reset(self):
        self.totalSongName = []
        self.totalLibrary  = []
        self.songName = []
        self.library = []
        self.diffs = []
        self.parts = []
        self.scores = []

class MidiPartsDiffReader(midi.MidiOutStream):

    def __init__(self, forceGuitar = False):
        midi.MidiOutStream.__init__(self)
        self.parts = []
        self.difficulties = {}
        self.currentPart = -1
        self.nextPart    = 0
        self.forceGuitar = forceGuitar
        self.firstTrack   = False
        self.notesFound   = [0, 0, 0, 0]
        self._drumFound   = False
        self._ODNoteFound = False
        self._SPNoteFound = False

        self.logClassInits = Config.get("game", "log_class_inits")
        if self.logClassInits == 1:
            Log.debug("MidiPartsDiffReader class init (song.py)...")

    def getMidiStyle(self):
        if self._ODNoteFound:
            Log.debug("MIDI Type identified as RB")
            return MIDI_TYPE_RB
        elif self._drumFound and self._SPNoteFound:
            Log.debug("MIDI Type identified as WT")
            return MIDI_TYPE_WT
        else:
            Log.debug("MIDI Type identified as GH")
            return MIDI_TYPE_GH
    midiStyle = property(getMidiStyle)

    def start_of_track(self, n_track=0):
        if self.forceGuitar:
            if not self.firstTrack:
                if not parts[GUITAR_PART] in self.parts:
                    part = parts[GUITAR_PART]
                    self.parts.append(part)
                    self.nextPart = None
                    self.currentPart = part.id
                    self.notesFound  = [0, 0, 0, 0]
                    self.difficulties[part.id] = []

                self.firstTrack = True
            else:
                Log.notice("This song has multiple tracks, none properly named. Behavior may be erratic.")

    def sequence_name(self, text):

        for part in parts.values():
            if text in part.trackName:
                if part not in self.parts:
                    if part.id == VOCAL_PART:
                        self.parts.append(part)
                        self.nextPart = None
                        self.currentPart = part.id
                        self.difficulties[part.id] = difficulties.values()
                    else:
                        self.nextPart = part
                        self.currentPart = self.nextPart.id
                        self.notesFound  = [0, 0, 0, 0]
                        if part.id == DRUM_PART or part.id == PRO_DRUM_PART:
                            self._drumFound  = True
                        Log.debug(tempText + tempText2)
                    return
        self.currentPart = -1

    def addPart(self):
        self.parts.append(self.nextPart)
        self.difficulties[self.nextPart.id] = []
        self.nextPart = None

    def note_on(self, channel, note, velocity):
        if self.currentPart == -1:
            return
        if note == overDriveMarkingNote:
            self._ODNoteFound = True
        elif note == starPowerMarkingNote:
            self._SPNoteFound = True
        try:
            try:
                if len(self.difficulties[self.currentPart]) == len(difficulties):
                    return
            except KeyError:
                pass
            track, number = noteMap[note]
            self.notesFound[track] += 1
            if self.notesFound[track] > 5:
                if self.nextPart is not None:
                    self.addPart()
                diff = difficulties[track]
                if not diff in self.difficulties[self.currentPart]:
                    self.difficulties[self.currentPart].append(diff)
        except KeyError:
            pass

def loadSong(engine, name, library = DEFAULT_LIBRARY, seekable = False, playbackOnly = False, notesOnly = False, part = [parts[GUITAR_PART]], practiceMode = False, practiceSpeed = .5):

    Log.debug("loadSong function call (song.py)...")
    crowdsEnabled = engine.config.get("audio", "enable_crowd_tracks")

    #RF-mod (not needed?)
    guitarFile = engine.resource.fileName(library, name, "guitar.ogg")
    songFile   = engine.resource.fileName(library, name, "song.ogg")
    rhythmFile = engine.resource.fileName(library, name, "rhythm.ogg")
    crowdFile  = engine.resource.fileName(library, name, "crowd.ogg")

    noteFile   = engine.resource.fileName(library, name, "notes.mid", writable = True)

    infoFile   = engine.resource.fileName(library, name, "song.ini", writable = True)
    scriptFile = engine.resource.fileName(library, name, "script.txt")
    previewFile = engine.resource.fileName(library, name, "preview.ogg")
    #myfingershurt:
    drumFile = engine.resource.fileName(library, name, "drums.ogg")


    if seekable:
        if os.path.isfile(guitarFile) and os.path.isfile(songFile):
            # TODO: perform mixing here
            songFile   = guitarFile
            guitarFile = None
            rhythmFile = ""
        else:
            songFile   = guitarFile
            guitarFile = None
            rhythmFile = ""
    if not os.path.isfile(songFile):
        songFile   = guitarFile
        guitarFile = None
    if not os.path.isfile(rhythmFile):
        rhythmFile = None
    if not os.path.isfile(drumFile):
        drumFile = None
    if not os.path.isfile(crowdFile):
        crowdFile = None
    if crowdsEnabled == 0:
        crowdFile = None


    if songFile != None and guitarFile != None:
        #check for the same file
        if hashlib.sha1(open(songFile, 'rb').read()).hexdigest() == hashlib.sha1(open(guitarFile, 'rb').read()).hexdigest():
            guitarFile = None



    if practiceMode:    #single track practice mode only!
        if (part[0] == parts[GUITAR_PART] or part[0] == parts[PRO_GUITAR_PART]) and guitarFile != None:
            songFile = guitarFile
        elif part[0] == parts[BASS_PART] and rhythmFile != None:
            songFile = rhythmFile
        elif (part[0] == parts[DRUM_PART] or part[0] == parts[PRO_DRUM_PART]) and drumFile != None:
            songFile = drumFile
        guitarFile = None
        rhythmFile = None
        drumFile = None
        crowdFile = None
        slowDownFactor = practiceSpeed
    else:
        slowDownFactor = engine.config.get("audio", "speed_factor")
    engine.audioSpeedFactor = slowDownFactor


    if playbackOnly:
        noteFile = None
        crowdFile = None
        if os.path.isfile(previewFile):
            songFile = previewFile
            guitarFile = None
            rhythmFile = None
            drumFile = None

    if notesOnly:
        songFile = None
        crowdFile = None
        guitarFile = None
        rhythmFile = None
        previewFile = None
        drumFile = None

    song       = Song(engine, infoFile, songFile, guitarFile, rhythmFile, noteFile, scriptFile, part, drumFile, crowdFile)
    return song

def loadSongInfo(engine, name, library = DEFAULT_LIBRARY):
    #RF-mod (not needed?)
    infoFile   = engine.resource.fileName(library, name, "song.ini", writable = True)
    return SongInfo(infoFile, library)

def getDefaultLibrary(engine):
    return LibraryInfo(DEFAULT_LIBRARY, engine.resource.fileName(DEFAULT_LIBRARY, "library.ini"))

def getAvailableLibraries(engine, library = DEFAULT_LIBRARY):
    Log.debug("Song.getAvailableLibraries function call...library = " + str(library) )
    # Search for libraries in both the read-write and read-only directories
    songRoots    = [engine.resource.fileName(library),
                    engine.resource.fileName(library, writable = True)]
    libraries    = []
    libraryRoots = []

    for songRoot in set(songRoots):
        if (os.path.exists(songRoot) == False):
            return libraries
        for libraryRoot in os.listdir(songRoot):
            if libraryRoot == ".svn":   #MFH - filter out the hidden SVN control folder!
                continue
            libraryRoot = os.path.join(songRoot, libraryRoot)
            if not os.path.isdir(libraryRoot):
                continue
            if os.path.isfile(os.path.join(libraryRoot, "notes.mid")):
                continue
            if os.path.isfile(os.path.join(libraryRoot, "notes-unedited.mid")):
                continue

            libName = library + os.path.join(libraryRoot.replace(songRoot, ""))

            libraries.append(LibraryInfo(libName, os.path.join(libraryRoot, "library.ini")))
            continue # why were these here? we must filter out empty libraries - coolguy567
                                #MFH - I'll tell you why -- so that empty ("tiered" / organizational) folders are displayed, granting access to songs in subfolders...

            dirs = os.listdir(libraryRoot)
            for name in dirs:
                if os.path.isfile(os.path.join(libraryRoot, name, "song.ini")):
                    if not libraryRoot in libraryRoots:
                        libName = library + os.path.join(libraryRoot.replace(songRoot, ""))
                        libraries.append(LibraryInfo(libName, os.path.join(libraryRoot, "library.ini")))
                        libraryRoots.append(libraryRoot)

    libraries.sort(lambda a, b: cmp(a.name.lower(), b.name.lower()))

    return libraries

def getAvailableSongs(engine, library = DEFAULT_LIBRARY, includeTutorials = False, progressCallback = lambda p: None):

    # Search for songs in both the read-write and read-only directories
    if library == None:
        return []

    songRoots = [engine.resource.fileName(library), engine.resource.fileName(library, writable = True)]

    names = []
    for songRoot in songRoots:
        if (os.path.exists(songRoot) == False):
            return []
        for name in os.listdir(songRoot):
            if not os.path.isfile(os.path.join(songRoot, name, "notes.mid")):
                continue
            elif not os.path.isfile(os.path.join(songRoot, name, "song.ini")) or name.startswith("."):
                continue
            if not name in names:
                names.append(name)
    songs = []
    for name in names:
        progressCallback(len(songs)/float(len(names)))
        songs.append(SongInfo(engine.resource.fileName(library, name, "song.ini", writable = True), library))

    songs = [song for song in songs if not song.artist == '=FOLDER=']
    songs.sort(lambda a, b: cmp(a.name.lower(), b.name.lower()))

    instrument = engine.config.get("game", "songlist_instrument")
    theInstrumentDiff = instrumentDiff[instrument]
    return songs

def getAvailableSongsAndTitles(engine, library = DEFAULT_LIBRARY, includeTutorials = False, progressCallback = lambda p: None):

    #NOTE: list-all mode and career modes are BROKEN as of now
    if library == None:
        return []

    items = getAvailableSongs(engine, library, includeTutorials, progressCallback=progressCallback)

    items.insert(0, RandomSongInfo())

    return items


def removeSongOrderPrefixFromName(name):
    return re.sub(r'^[0-9]+\. *', '', name)
