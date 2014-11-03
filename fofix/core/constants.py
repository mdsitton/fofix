#####################################################################
# Frets on Fire X (FoFiX)                                           #
# Copyright (C) 2011 FoFiX Team                                     #
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

# Horizontal alignments
LEFT   = 0
CENTER = 1
RIGHT  = 2

# Vertical alignments
TOP    = 0
MIDDLE = 1
BOTTOM = 2

# Stretching constants
FIT_WIDTH = 1
FIT_HEIGHT = 2
FULL_SCREEN = 3
KEEP_ASPECT = 4

# Screen sizing scalers
SCREEN_WIDTH = 640.0
SCREEN_HEIGHT = 480.0

EXP_DIF     = 0
HAR_DIF     = 1
MED_DIF     = 2
EAS_DIF     = 3

GUITAR_TRACK             = 0
RHYTHM_TRACK             = 1
DRUM_TRACK               = 2

GUITAR_PART             = 0
RHYTHM_PART             = 1
BASS_PART               = 2
LEAD_PART               = 3
DRUM_PART               = 4
VOCAL_PART              = 5
PRO_GUITAR_PART         = 6
PRO_DRUM_PART           = 7

#set of values that define as true when loading string values from a file
def isTrue(value):
    return value in ["1", "true", "yes", "on"]

