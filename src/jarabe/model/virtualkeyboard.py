#!/usr/bin/env python
# -*- coding: UTF-8 -*-
# VirtualKeyboard
# Copyright (C) 2010 Plan Ceibal
# pykey - http://shallowsky.com/software/crikey
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

import subprocess
import sys, os
import time
import Xlib.display
import Xlib.X
import Xlib.XK
import Xlib.protocol.event

class Teclado:
    special_X_keysyms = {
        ' ' : "space",
        '\t' : "Tab",
        '\n' : "Return",
        '\r' : "BackSpace",
        '\e' : "Escape",
        '!' : "exclam",
        '#' : "numbersign",
        '%' : "percent",
        '$' : "dollar",
        '&' : "ampersand",
        '"' : "quotedbl",
        '\'' : "apostrophe",
        '(' : "parenleft",
        ')' : "parenright",
        '*' : "asterisk",
        '=' : "equal",
        '+' : "plus",
        ',' : "comma",
        '-' : "minus",
        '.' : "period",
        '/' : "slash",
        ':' : "colon",
        ';' : "semicolon",
        '<' : "less",
        '>' : "greater",
        '?' : "question",
        '@' : "at",
        '[' : "bracketleft",
        ']' : "bracketright",
        '\\' : "backslash",
        '^' : "asciicircum",
        '_' : "underscore",
        '`' : "grave",
        '{' : "braceleft",
        '|' : "bar",
        '}' : "braceright",
        '~' : "asciitilde",
        'ñ' : "ntilde",
        'Ñ' : "Ntilde"
    };

    def __init__(self):
        self.display = Xlib.display.Display()
        self.window = self.display.get_input_focus()._data["focus"];

    def get_keysym(self, ch) :
        keysym = Xlib.XK.string_to_keysym(ch)
        if keysym == 0:
            keysym = Xlib.XK.string_to_keysym(self.special_X_keysyms[ch])
        return keysym

    def is_shifted(self, ch) :
        if ch.isupper() :
            return True
        if "/=~!@#$%^&()_*{}|:;\">?Ñ".find(ch) >= 0 :
            return True
        return False

    def char_to_keycode(self, ch) :
        keysym = self.get_keysym(ch)
        keycode = self.display.keysym_to_keycode(keysym)
        if keycode == 0 :
            print "Sorry, can't map", ch

        if (self.is_shifted(ch)) :
            shift_mask = Xlib.X.ShiftMask
        else :
            shift_mask = 0

        return keycode, shift_mask


    def send_string(self, ch):
        keycode, shift_mask = self.char_to_keycode(ch)
        self.escribir(keycode, shift_mask)

    def escribir(self, keycode, shift_mask):
        event = Xlib.protocol.event.KeyPress(
            time = int(time.time()),
            root = self.display.screen().root,
            window = self.window,
            same_screen = 0, child = Xlib.X.NONE,
            root_x = 0, root_y = 0, event_x = 0, event_y = 0,
            state = shift_mask,
            detail = keycode
            )
        self.window.send_event(event, propagate = True)
        event = Xlib.protocol.event.KeyRelease(
            time = int(time.time()),
            root = self.display.screen().root,
            window = self.window,
            same_screen = 0, child = Xlib.X.NONE,
            root_x = 0, root_y = 0, event_x = 0, event_y = 0,
            state = shift_mask,
            detail = keycode
            )
        self.window.send_event(event, propagate = True)


    def escribir_txt(self, txt):
        self.display = Xlib.display.Display()
        self.window = self.display.get_input_focus()._data["focus"];

        if (txt == "ü"):
            self.escribir(34, 1)
            self.send_string("u")
        elif (txt == "Ü"):
            self.escribir(34, 1)
            self.send_string("U")
        elif (txt == "|"):
            self.escribir(10, Xlib.X.Mod5Mask)
        elif (txt == "@"):
            self.escribir(11, Xlib.X.Mod5Mask)
        elif (txt == "#"):
            self.escribir(12, Xlib.X.Mod5Mask)
        elif (txt == "º"):
            self.escribir(49, 0)
        elif (txt == "ª"):
            self.escribir(49, 1)
        elif (txt == "'"):
            self.escribir(20, 0)
        elif (txt == "¿"):
            self.escribir(21, 1)
        elif (txt == "¡"):
            self.escribir(21, 0)
        elif (txt == "'"):
            self.escribir(34, 0)
        elif (self.tieneTilde(txt)):
            self.escribir(34, 0)
            self.escribirVocal(txt)
        else:
            self.send_string(txt)

        self.display.sync()

    def tieneTilde(self, txt):
        return "ÁÉÍÓÚáéíóú".find(txt) >= 0

    def escribirVocal(self, txt):
        if txt=="Á": self.send_string("A")
        if txt=="É": self.send_string("E")
        if txt=="Í": self.send_string("I")
        if txt=="Ó": self.send_string("O")
        if txt=="Ú": self.send_string("U")
        if txt=="á": self.send_string("a")
        if txt=="é": self.send_string("e")
        if txt=="í": self.send_string("i")
        if txt=="ó": self.send_string("o")
        if txt=="ú": self.send_string("u")

    def hablar(self, texto, s):
        subprocess.call(["espeak","-w", "temp.wav","-p", "30", "-s", s, "-v", "spanish", texto], stdout=subprocess.PIPE)
        subprocess.call(["aplay", "temp.wav"], stdout=subprocess.PIPE)
