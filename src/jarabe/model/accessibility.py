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

from gi.repository import Gtk
from gi.repository import GConf
import subprocess

class Keyboard:

    def get_mouse_keys(self):
        client = GConf.Client.get_default()
        return client.get_bool("/desktop/sugar/accessibility/keyboard/mousekeys_enable")

    def set_mouse_keys(self, activar):
        client = GConf.Client.get_default()
        client.set_bool("/desktop/sugar/accessibility/keyboard/mousekeys_enable", activar)
        self.run_config_keyboard()

    def get_sticky_keys(self):
        client = GConf.Client.get_default()
        return client.get_bool("/desktop/sugar/accessibility/keyboard/stickykeys_enable")

    def set_sticky_keys(self, activar):
        client = GConf.Client.get_default()
        client.set_bool("/desktop/sugar/accessibility/keyboard/stickykeys_enable", activar)
        self.run_config_keyboard()

    def get_bounce_keys(self):
        client = GConf.Client.get_default()
        return client.get_bool("/desktop/sugar/accessibility/keyboard/bouncekeys_enable")

    def set_bounce_keys(self, activar):
        client = GConf.Client.get_default()
        client.set_bool("/desktop/sugar/accessibility/keyboard/bouncekeys_enable", activar)

    def get_virtualkeyboard(self):
        client = GConf.Client.get_default()
        return client.get_bool("/desktop/sugar/accessibility/keyboard/virtualkeyboard_enable")

    def set_virtualkeyboard(self, activar):
        client = GConf.Client.get_default()
        client.set_bool("/desktop/sugar/accessibility/keyboard/virtualkeyboard_enable", activar)
        self.run_config_keyboard()

    def run_config_keyboard(self):
        cmd = ['ax']
        if self.get_sticky_keys():
            cmd.append('+stickykeys')
        else:
            cmd.append('-stickykeys')
        if self.get_bounce_keys():
            cmd.append('+bouncekeys')
        else:
            cmd.append('-bouncekeys')
        if self.get_mouse_keys():
            cmd += ['+mousekeys', 'mousemaxspeed', '3000', 'mousetimetomax', '1000', '-timeout', '-repeatkeys']
        else:
            cmd += ['-mousekeys', 'mousemaxspeed', '3000', 'mousetimetomax', '1000', '+timeout', '+repeatkeys']
        subprocess.call(cmd)

class Screen:

    DEFAULT_THEME = "sugar"
    DEFAULT_FONT_SIZE = 7
    DEFAULT_FONT_FACE = "Sans Serif"
    CONTRAST_THEME = "sugar-contrast"
    CONTRAST_FONT_SIZE = 9.5
    CAPITAL_LETTERS_FONT_FACE = "Oracle"

    def get_contrast(self):
        client = GConf.Client.get_default()
        value = client.get_string("/desktop/sugar/interface/gtk_theme")
        return value==self.CONTRAST_THEME

    def set_contrast(self, activar):
        client = GConf.Client.get_default()
        if (activar):
            client.set_string("/desktop/sugar/interface/gtk_theme", self.CONTRAST_THEME)
            client.set_float('/desktop/sugar/font/default_size', self.CONTRAST_FONT_SIZE)
        else:
            client.set_string("/desktop/sugar/interface/gtk_theme", self.DEFAULT_THEME)
            client.set_float('/desktop/sugar/font/default_size', self.DEFAULT_FONT_SIZE)

    def get_capital_letters(self):
        client = GConf.Client.get_default()
        value = client.get_string("/desktop/sugar/font/default_face")
        return value==self.CAPITAL_LETTERS_FONT_FACE

    def set_capital_letters(self, activar):
        client = GConf.Client.get_default()
        if (activar):
            client.set_string('/desktop/sugar/font/default_face', self.CAPITAL_LETTERS_FONT_FACE)
            client.set_float('/desktop/sugar/font/default_size', self.CONTRAST_FONT_SIZE)
        else:
            client.set_string('/desktop/sugar/font/default_face', self.DEFAULT_FONT_FACE)
            client.set_float('/desktop/sugar/font/default_size', self.DEFAULT_FONT_SIZE)


class Mouse:

    WHITE_CURSOR_THEME="FlatbedCursors.White.Huge"
    DEFAULT_CURSOR_THEME="sugar"
    DEFAULT_ACCEL_MOUSE=3

    def get_white_mouse(self):
        client = GConf.Client.get_default()
        value = client.get_string("/desktop/sugar/peripherals/mouse/cursor_theme")
        return value==self.WHITE_CURSOR_THEME

    def set_white_mouse(self, activar):
        client = GConf.Client.get_default()
        if (activar):
            client.set_string("/desktop/sugar/peripherals/mouse/cursor_theme", self.WHITE_CURSOR_THEME)
        else:
            client.set_string("/desktop/sugar/peripherals/mouse/cursor_theme", self.DEFAULT_CURSOR_THEME)

    def _set_white_mouse_setting(self):
        cursor_theme = self.DEFAULT_CURSOR_THEME
        if (self.get_white_mouse()):
            cursor_theme = self.WHITE_CURSOR_THEME
        settings = Gtk.Settings.get_default()
        settings.set_property("gtk-cursor-theme-name", "%s" % (cursor_theme))

    def get_accel_mouse(self):
        client = GConf.Client.get_default()
        value = client.get_float("/desktop/sugar/peripherals/mouse/motion_acceleration")
        return value

    def set_accel_mouse(self, value):
        client = GConf.Client.get_default()
        client.set_float("/desktop/sugar/peripherals/mouse/motion_acceleration", value)
        self.run_config_mouse()

    def _set_accel_mouse_setting(self):
        cmd = ['xset', 'm' , str(self.get_accel_mouse())]
        subprocess.call(cmd)

    def run_config_mouse(self):
        self._set_accel_mouse_setting()
        self._set_white_mouse_setting()

class AccessibilityManager:
    def setup_accessibility(self):
        client = GConf.Client.get_default()
        is_accessibility = client.dir_exists("/desktop/sugar/accessibility")
        mouse = Mouse()
        if is_accessibility:
            keyboard = Keyboard()
            keyboard.run_config_keyboard()
            mouse.run_config_mouse()
        else:
            mouse.set_accel_mouse(mouse.DEFAULT_ACCEL_MOUSE)
            mouse.set_white_mouse(False)
            mouse._set_accel_mouse_setting()
