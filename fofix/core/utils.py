#####################################################################
# Frets on Fire X (FoFiX)                                           #
# Copyright (C) 2014 FoFiX Team                                     #
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
'''
Short utility functions that 
'''

from fofix.core import constants as const

def hexToColor(color):
    '''Convert hexadecimal color string to tuple containing rgb or rgba values'''

    if not (isinstance(color, str) or isinstance(color, unicode)):
        raise TypeError('Invalid input type: {}'.format(type(color)))

    elif color[0] != '#':
        raise ValueError('Invalid color')

    else:
        color = color[1:]

        if len(color) < 4:
            colorData = [color[i]+color[i] for i in xrange(0, len(color))]
        else:
            colorData = [color[i:i+2] for i in xrange(0, len(color), 2)]

        rgbColor = tuple([int(i, 16) / 255.0 for i in colorData])

    return rgbColor


def colorToHex(color):
    '''Convert RGB/RGBA color tuple to hexadecimal format'''
    if not isinstance(color, tuple):
        raise TypeError

    colorData = [ "%02x" % int(c * 255) for c in color]
    return "#%s" % "".join(colorData)

def isTrue(value):
    '''Check Values that define true when loading string values from a file'''
    return value in ["1", "true", "yes", "on"]