from gettext import gettext as _

import logging

from gi.repository import GObject
from gi.repository import Gtk
from gi.repository import GConf
import os

from sugar3.graphics.tray import TrayIcon
from sugar3.graphics.xocolor import XoColor
from sugar3.graphics.palette import Palette
from sugar3.graphics import style
from jarabe.frame.frameinvoker import FrameWidgetInvoker

import jarabe.view.virtualkeyboard
from jarabe.model import accessibility

class DeviceView(TrayIcon):

    FRAME_POSITION_RELATIVE = 500

    def __init__(self):
        icon_name = 'virtualkeyboard'

        client = GConf.Client.get_default()
        color = XoColor(client.get_string('/desktop/sugar/user/color'))
        TrayIcon.__init__(self, icon_name=icon_name, xo_color=color)
        self.set_palette_invoker(FrameWidgetInvoker(self))

    def create_palette(self):
        palette = VirtualkeyboardPalette(_('Teclado Virtual'))
        palette.set_group_id('frame')
        return palette

class VirtualkeyboardPalette(Palette):

    def __init__(self, primary_text):
        Palette.__init__(self, label=primary_text)

        self.connect('popup', self._popup_cb)
        self.connect('popdown', self._popdown_cb)

        self._popped_up = False

        self._open_item = Gtk.MenuItem(_('Open'))
        self._open_item.connect('activate', self._open_activate_cb)
        self.menu.append(self._open_item)
        self._open_item.show()

        self._close_item = Gtk.MenuItem(_('Close'))
        self._close_item.connect('activate', self._close_activate_cb)
        self.menu.append(self._close_item)
        self._close_item.show()

    def _popup_cb(self, gobject_ref):
        self._popped_up = True

    def _popdown_cb(self, gobject_ref):
        self._popped_up = False

    def _open_activate_cb(self, gobject_ref):
        self.v = jarabe.view.virtualkeyboard.Teclado()

    def _close_activate_cb(self, gobject_ref):
        try:
            self.v.close()
        except:
            pass

def setup(tray):
    try:
        keyboard = accessibility.Keyboard()
        if keyboard.get_virtualkeyboard():
            tray.add_device(DeviceView())
    except:
        logging.error('show virtual keyboard device icon')
