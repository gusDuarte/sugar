# Copyright (C) 2010 Plan Ceibal
#
# Author: Esteban Arias <earias@plan.ceibal.edu.uy>
# Contact information: comunidad@plan.ceibal.edu.uy
# Plan Ceibal http://www.ceibal.edu.uy
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

from jarabe.model import accessibility

keyboard = accessibility.Keyboard()
screen = accessibility.Screen()
mouse = accessibility.Mouse()

KEYWORDS = ['mouse_keys', 'sticky_keys', 'bounce_keys', 'contrast', 'white_mouse', 'accel_mouse', 'capital_letters']

def get_mouse_keys():
    return keyboard.get_mouse_keys()

def set_mouse_keys(activar):
    keyboard.set_mouse_keys(activar)

def print_mouse_keys():
    print str(get_mouse_keys())

def get_sticky_keys():
    return keyboard.get_sticky_keys()

def set_sticky_keys(activar):
    keyboard.set_sticky_keys(activar)

def print_sticky_keys():
    print str(get_sticky_keys())

def get_bounce_keys():
    return keyboard.get_bounce_keys()

def set_bounce_keys(activar):
    keyboard.set_bounce_keys(activar)

def print_bounce_keys():
    print str(get_bounce_keys())

def get_contrast():
    return screen.get_contrast()

def set_contrast(activar):
    screen.set_contrast(activar)

def print_contrast():
    print str(get_contrast())

def get_capital_letters():
    return screen.get_capital_letters()

def set_capital_letters(activar):
    screen.set_capital_letters(activar)

def print_capital_letters():
    print str(get_capital_letters())

def get_white_mouse():
    return mouse.get_white_mouse()

def set_white_mouse(activar):
    mouse.set_white_mouse(activar)

def print_white_mouse():
    print str(get_white_mouse())

def get_accel_mouse():
	return mouse.get_accel_mouse()

def set_accel_mouse(valor):
	mouse.set_accel_mouse(valor)

def print_accel_mouse():
    print str(get_accel_mouse())
