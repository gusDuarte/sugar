# Copyright (C) 2006-2007 Red Hat, Inc.
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 51 Franklin St, Fifth Floor, Boston, MA  02110-1301  USA

import logging
import os

from gi.repository import Gtk
from gi.repository import Gdk
from gi.repository import GObject

from sugar3.graphics import animator
from sugar3.graphics import style
from sugar3.graphics import palettegroup
from sugar3 import profile

from jarabe.frame.eventarea import EventArea
from jarabe.frame.activitiestray import ActivitiesTray
from jarabe.frame.zoomtoolbar import ZoomToolbar
from jarabe.frame.friendstray import FriendsTray
from jarabe.frame.devicestray import DevicesTray
from jarabe.frame.framewindow import FrameWindow
from jarabe.frame.clipboardpanelwindow import ClipboardPanelWindow
from jarabe.frame.notification import NotificationIcon, NotificationWindow
from jarabe.frame.notification import NotificationButton, HistoryPalette
from jarabe.model import notifications


TOP_RIGHT = 0
TOP_LEFT = 1
BOTTOM_RIGHT = 2
BOTTOM_LEFT = 3

_NOTIFICATION_DURATION = 5000

_DEFAULT_ICON = 'emblem-notification'


class _Animation(animator.Animation):
    def __init__(self, frame, end):
        start = frame.current_position
        animator.Animation.__init__(self, start, end)
        self._frame = frame

    def next_frame(self, current):
        self._frame.move(current)


class _KeyListener(object):
    def __init__(self, frame):
        self._frame = frame

    def key_press(self):
        if self._frame.visible:
            self._frame.hide()
        else:
            self._frame.show()


class Frame(object):
    def __init__(self):
        logging.debug('STARTUP: Loading the frame')

        self._palette_group = palettegroup.get_group('frame')

        self._left_panel = None
        self._right_panel = None
        self._top_panel = None
        self._bottom_panel = None

        self.current_position = 0.0
        self._animator = None

        self._event_area = EventArea()
        self._event_area.connect('enter', self._enter_corner_cb)
        self._event_area.show()

        self._activities_tray = None
        self._devices_tray = None
        self._friends_tray = None

        self._top_panel = self._create_top_panel()
        self._bottom_panel = self._create_bottom_panel()
        self._left_panel = self._create_left_panel()
        self._right_panel = self._create_right_panel()

        screen = Gdk.Screen.get_default()
        screen.connect('size-changed', self._size_changed_cb)

        self._key_listener = _KeyListener(self)

        self._notif_by_icon = {}
        self._notif_by_message = {}

        notification_service = notifications.get_service()
        notification_service.notification_received.connect(
                self.__notification_received_cb)
        notification_service.notification_cancelled.connect(
                self.__notification_cancelled_cb)

    def is_visible(self):
        return self.current_position != 0.0

    visible = property(is_visible, None)

    def hide(self):
        if not self.visible:
            return

        if self._animator:
            self._animator.stop()

        palettegroup.popdown_all()
        self._animator = animator.Animator(0.5)
        self._animator.add(_Animation(self, 0.0))
        self._animator.start()

    def show(self):
        if self.visible:
            return
        if self._animator:
            self._animator.stop()

        self._animator = animator.Animator(0.5)
        self._animator.add(_Animation(self, 1.0))
        self._animator.start()

    def move(self, pos):
        self.current_position = pos
        self._update_position()

    def _create_top_panel(self):
        panel = self._create_panel(Gtk.PositionType.TOP)

        zoom_toolbar = ZoomToolbar()
        panel.append(zoom_toolbar, expand=False)
        zoom_toolbar.show()
        zoom_toolbar.connect('level-clicked', self._level_clicked_cb)

        activities_tray = ActivitiesTray()
        panel.append(activities_tray)
        activities_tray.show()

        self._activities_tray = activities_tray

        return panel

    def _create_bottom_panel(self):
        panel = self._create_panel(Gtk.PositionType.BOTTOM)

        devices_tray = DevicesTray()
        panel.append(devices_tray)
        devices_tray.show()

        self._devices_tray = devices_tray

        return panel

    def _create_right_panel(self):
        panel = self._create_panel(Gtk.PositionType.RIGHT)

        tray = FriendsTray()
        panel.append(tray)
        tray.show()

        self._friends_tray = tray

        return panel

    def _create_left_panel(self):
        panel = ClipboardPanelWindow(self, Gtk.PositionType.LEFT)

        return panel

    def _create_panel(self, orientation):
        panel = FrameWindow(orientation)

        return panel

    def _move_panel(self, panel, pos, x1, y1, x2, y2):
        x = (x2 - x1) * pos + x1
        y = (y2 - y1) * pos + y1

        panel.move(int(x), int(y))

        # FIXME we should hide and show as necessary to free memory
        if not panel.props.visible:
            panel.show()

    def _level_clicked_cb(self, zoom_toolbar):
        self.hide()

    def _update_position(self):
        screen_h = Gdk.Screen.height()
        screen_w = Gdk.Screen.width()

        self._move_panel(self._top_panel, self.current_position,
                         0, - self._top_panel.size, 0, 0)

        self._move_panel(self._bottom_panel, self.current_position,
                         0, screen_h, 0, screen_h - self._bottom_panel.size)

        self._move_panel(self._left_panel, self.current_position,
                         - self._left_panel.size, 0, 0, 0)

        self._move_panel(self._right_panel, self.current_position,
                         screen_w, 0, screen_w - self._right_panel.size, 0)

    def _size_changed_cb(self, screen):
        self._update_position()

    def _enter_corner_cb(self, event_area):
        if self.visible:
            self.hide()
        else:
            self.show()

    def _create_notification_window(self, corner):
        window = NotificationWindow()

        screen = Gdk.Screen.get_default()
        if corner == Gtk.CornerType.TOP_LEFT:
            window.move(0, 0)
        elif corner == Gtk.CornerType.TOP_RIGHT:
            window.move(screen.get_width() - style.GRID_CELL_SIZE, 0)
        elif corner == Gtk.CornerType.BOTTOM_LEFT:
            window.move(0, screen.get_height() - style.GRID_CELL_SIZE)
        elif corner == Gtk.CornerType.BOTTOM_RIGHT:
            window.move(screen.get_width() - style.GRID_CELL_SIZE,
                        screen.get_height() - style.GRID_CELL_SIZE)
        else:
            raise ValueError('Inalid corner: %r' % corner)

        return window

    def _add_message_button(self, button, corner):
        if corner == Gtk.CornerType.BOTTOM_RIGHT:
            self._devices_tray.add_item(button)
        elif corner == Gtk.CornerType.TOP_RIGHT:
            self._friends_tray.add_item(button)
        else:
            self._activities_tray.add_item(button)

    def _remove_message_button(self, button, corner):
        if corner == Gtk.CornerType.BOTTOM_RIGHT:
            self._devices_tray.remove_item(button)
        elif corner == Gtk.CornerType.TOP_RIGHT:
            self._friends_tray.remove_item(button)
        else:
            self._activities_tray.remove_item(button)

    def _launch_notification_icon(self, icon_name, xo_color,
                                  position, duration):
        icon = NotificationIcon()
        icon.props.xo_color = xo_color

        if icon_name.startswith(os.sep):
            icon.props.icon_filename = icon_name
        else:
            icon.props.icon_name = icon_name

        self.add_notification(icon, position, duration)

    def notify_key_press(self):
        self._key_listener.key_press()

    def add_notification(self, icon, corner=Gtk.CornerType.TOP_LEFT,
                         duration=_NOTIFICATION_DURATION):

        if not isinstance(icon, NotificationIcon):
            raise TypeError('icon must be a NotificationIcon.')

        window = self._create_notification_window(corner)

        window.add(icon)
        icon.show()
        window.show()

        self._notif_by_icon[icon] = window

        GObject.timeout_add(duration,
                        lambda: self.remove_notification(icon))

    def remove_notification(self, icon):
        if icon not in self._notif_by_icon:
            logging.debug('icon %r not in list of notifications.', icon)
            return

        window = self._notif_by_icon[icon]
        window.destroy()
        del self._notif_by_icon[icon]

    def add_message(self, body, summary='', link=None, link_text=None, icon_name=_DEFAULT_ICON,
                    xo_color=None, corner=Gtk.CornerType.TOP_LEFT,
                    duration=_NOTIFICATION_DURATION):

        if xo_color is None:
            xo_color = profile.get_color()

        button = self._notif_by_message.get(corner, None)
        if button is None:
            button = NotificationButton(_DEFAULT_ICON, xo_color)
            button.show()
            self._add_message_button(button, corner)
            self._notif_by_message[corner] = button

        palette = button.get_palette()
        if palette is None:
            palette = HistoryPalette()
            palette.set_group_id('frame')
            palette.connect('clear-messages', self.remove_message, corner)
            palette.connect('notice-messages', button.stop_pulsing)
            button.set_palette(palette)

        button.start_pulsing()

        palette.push_message(body, summary, link, link_text, icon_name, xo_color)
        if not self.visible:
            self._launch_notification_icon(_DEFAULT_ICON, xo_color, corner, duration)

    def remove_message(self, palette, corner):
        if corner not in self._notif_by_message:
            logging.debug('Button %s is not active', str(corner))
            return

        button = self._notif_by_message[corner]
        self._remove_message_button(button, corner)
        del self._notif_by_message[corner]

    def __notification_received_cb(self, **kwargs):
        logging.debug('__notification_received_cb %r', kwargs)

        hints = kwargs['hints']

        icon_name = hints.get('x-sugar-icon-file-name', '')
        if not icon_name:
            icon_name = _DEFAULT_ICON

        icon_colors = hints.get('x-sugar-icon-colors', '')
        if not icon_colors:
            icon_colors = profile.get_color()

        duration = kwargs.get('expire_timeout', -1)
        if duration == -1:
            duration = _NOTIFICATION_DURATION

        category = hints.get('category', '')
        if category == 'device':
            position = Gtk.CornerType.BOTTOM_RIGHT
        elif category == 'presence':
            position = Gtk.CornerType.TOP_RIGHT
        else:
            position = Gtk.CornerType.TOP_LEFT

        summary = kwargs.get('summary', '')
        body = kwargs.get('body', '')

        if summary or body:
            self.add_message(body, summary, icon_name,
                            icon_colors, position, duration)
        else:
            self._launch_notification_icon(icon_name, icon_colors,
                                          position, duration)

    def __notification_cancelled_cb(self, **kwargs):
        # Do nothing for now. Our notification UI is so simple, there's no
        # point yet.
        pass

    def switch_to_journal_activity(self):
        self._activities_tray._show_journal_activity()
