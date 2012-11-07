# Copyright (C) 2008 One Laptop Per Child
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

from gi.repository import GObject
from gi.repository import Gtk
from gi.repository import Gdk

import re
import os

from gettext import gettext as _

from sugar3.graphics import style
from sugar3.graphics.xocolor import XoColor
from sugar3.graphics.palette import Palette
from sugar3.graphics.palettemenuitem import PaletteMenuItem
from sugar3.graphics.toolbutton import ToolButton
from sugar3 import profile

from jarabe.frame.frameinvoker import FrameWidgetInvoker

from jarabe.view.pulsingicon import PulsingIcon

_PULSE_TIMEOUT = 3
_PULSE_COLOR = XoColor('%s,%s' % \
        (style.COLOR_BUTTON_GREY.get_svg(), style.COLOR_TRANSPARENT.get_svg()))
_BODY_FILTERS = "<img.*?/>"


def _create_pulsing_icon(icon_name, xo_color, timeout=None):
    icon = PulsingIcon(
            pixel_size=style.STANDARD_ICON_SIZE,
            pulse_color=_PULSE_COLOR,
            base_color=xo_color
            )

    if timeout is not None:
        icon.timeout = timeout

    if icon_name.startswith(os.sep):
        icon.props.file = icon_name
    else:
        icon.props.icon_name = icon_name

    return icon


class _HistoryIconWidget(Gtk.Alignment):
    __gtype_name__ = 'SugarHistoryIconWidget'

    def __init__(self, icon_name, xo_color):
        icon = _create_pulsing_icon(icon_name, xo_color, _PULSE_TIMEOUT)
        icon.props.pulsing = True

        Gtk.Alignment.__init__(self, xalign=0.5, yalign=0.0)
        self.props.top_padding = style.DEFAULT_PADDING
        self.set_size_request(
                style.GRID_CELL_SIZE - style.FOCUS_LINE_WIDTH * 2,
                style.GRID_CELL_SIZE - style.DEFAULT_PADDING)
        self.add(icon)


class _HistorySummaryWidget(Gtk.Alignment):
    __gtype_name__ = 'SugarHistorySummaryWidget'

    def __init__(self, summary):
        summary_label = Gtk.Label()
        summary_label.props.wrap = True
        summary_label.set_markup(
                '<b>%s</b>' % GObject.markup_escape_text(summary))

        Gtk.Alignment.__init__(self, xalign=0.0, yalign=1.0)
        self.props.right_padding = style.DEFAULT_SPACING
        self.add(summary_label)


class _HistoryBodyWidget(Gtk.Alignment):
    __gtype_name__ = 'SugarHistoryBodyWidget'
    def __init__(self, body):
        body_label = Gtk.Label()
        body_label.props.wrap = True
        body_label.set_markup(body)

        Gtk.Alignment.__init__(self, xalign=0, yalign=0.0)
        self.props.right_padding = style.DEFAULT_SPACING
        self.add(body_label)


class _MessagesHistoryBox(Gtk.VBox):
    __gtype_name__ = 'SugarMessagesHistoryBox'

    def __init__(self):
        Gtk.VBox.__init__(self)
        self._setup_links_style()

    def _setup_links_style(self):
        # XXX: find a better way to change style for upstream
        link_color = profile.get_color().get_fill_color()
        visited_link_color = profile.get_color().get_stroke_color()

        links_style='''
        style "label" {
          GtkLabel::link-color="%s"
          GtkLabel::visited-link-color="%s"
        }
        widget_class "*GtkLabel" style "label"
        ''' % (link_color, visited_link_color)
        Gtk.rc_parse_string(links_style)

    def push_message(self, body, summary, icon_name, xo_color):
        entry = Gtk.HBox()

        icon_widget = _HistoryIconWidget(icon_name, xo_color)
        entry.pack_start(icon_widget, False, False, 0)

        message = Gtk.VBox()
        message.props.border_width = style.DEFAULT_PADDING
        entry.pack_start(message, True, True, 0)

        if summary:
            summary_widget = _HistorySummaryWidget(summary)
            message.pack_start(summary_widget, False, False, 0)

        body = re.sub(_BODY_FILTERS, '', body)

        if body:
            body_widget = _HistoryBodyWidget(body)
            message.pack_start(body_widget, True, True, 0)

        entry.show_all()
        self.pack_start(entry, True, True, 0)
        self.reorder_child(entry, 0)

        self_width_ = self.props.width_request
        self_height = self.props.height_request
        if (self_height > Gdk.Screen.height() / 4 * 3) and \
                (len(self.get_children()) > 1):
            self.remove(self.get_children()[-1])

class HistoryPalette(Palette):
    __gtype_name__ = 'SugarHistoryPalette'

    __gsignals__ = {
        'clear-messages': (GObject.SignalFlags.RUN_FIRST, None, ([])),
        'notice-messages': (GObject.SignalFlags.RUN_FIRST, None, ([]))
    }

    def __init__(self):
        Palette.__init__(self)

        self._update_accept_focus()

        self._messages_box = _MessagesHistoryBox()
        self._messages_box.show()

        palette_box = self._palette_box
        primary_box = self._primary_box
        primary_box.hide()
        palette_box.add(self._messages_box)
        palette_box.reorder_child(self._messages_box, 0)

        clear_option = PaletteMenuItem(_('Clear history'), 'dialog-cancel')
        clear_option.connect('activate', self.__clear_messages_cb)
        clear_option.show()

        vbox = Gtk.VBox()
        self.set_content(vbox)
        vbox.show()

        vbox.add(clear_option)

        self.connect('popup', self.__notice_messages_cb)

    def __clear_messages_cb(self, clear_option):
        self.emit('clear-messages')

    def __notice_messages_cb(self, palette):
        self.emit('notice-messages')

    def push_message(self, body, summary, icon_name, xo_color):
        self._messages_box.push_message(body, summary, icon_name, xo_color)


class NotificationButton(ToolButton):

    def __init__(self, icon_name, xo_color):
        ToolButton.__init__(self)
        self._icon = _create_pulsing_icon(icon_name, xo_color)
        self.set_icon_widget(self._icon)
        self._icon.show()
        self.set_palette_invoker(FrameWidgetInvoker(self))

    def start_pulsing(self):
        self._icon.props.pulsing = True

    def stop_pulsing(self, widget):
        self._icon.props.pulsing = False


class NotificationIcon(Gtk.EventBox):
    __gtype_name__ = 'SugarNotificationIcon'

    __gproperties__ = {
        'xo-color': (object, None, None, GObject.PARAM_READWRITE),
        'icon-name': (str, None, None, None, GObject.PARAM_READWRITE),
        'icon-filename': (str, None, None, None, GObject.PARAM_READWRITE),
    }

    def __init__(self, **kwargs):
        self._icon = PulsingIcon(pixel_size=style.STANDARD_ICON_SIZE)
        Gtk.EventBox.__init__(self, **kwargs)
        self.props.visible_window = False
        self.set_app_paintable(True)

        color = Gdk.color_parse(style.COLOR_BLACK.get_html())
        self.modify_bg(Gtk.StateType.PRELIGHT, color)

        color = Gdk.color_parse(style.COLOR_BUTTON_GREY.get_html())
        self.modify_bg(Gtk.StateType.ACTIVE, color)

        self._icon.props.pulse_color = _PULSE_COLOR
        self._icon.props.timeout = _PULSE_TIMEOUT
        self.add(self._icon)
        self._icon.show()

        self.start_pulsing()

        self.set_size_request(style.GRID_CELL_SIZE, style.GRID_CELL_SIZE)

    def start_pulsing(self):
        self._icon.props.pulsing = True

    def do_set_property(self, pspec, value):
        if pspec.name == 'xo-color':
            if self._icon.props.base_color != value:
                self._icon.props.base_color = value
        elif pspec.name == 'icon-name':
            if self._icon.props.icon_name != value:
                self._icon.props.icon_name = value
        elif pspec.name == 'icon-filename':
            if self._icon.props.file != value:
                self._icon.props.file = value

    def do_get_property(self, pspec):
        if pspec.name == 'xo-color':
            return self._icon.props.base_color
        elif pspec.name == 'icon-name':
            return self._icon.props.icon_name
        elif pspec.name == 'icon-filename':
            return self._icon.props.file

    def _set_palette(self, palette):
        self._icon.palette = palette

    def _get_palette(self):
        return self._icon.palette

    palette = property(_get_palette, _set_palette)


class NotificationWindow(Gtk.Window):
    __gtype_name__ = 'SugarNotificationWindow'

    def __init__(self):
        Gtk.Window.__init__(self)

        self.set_decorated(False)
        self.set_resizable(False)
        self.connect('realize', self._realize_cb)

    def _realize_cb(self, widget):
        self.set_type_hint(Gdk.WindowTypeHint.DIALOG)
        self.get_window().set_accept_focus(False)

        color = Gdk.color_parse(style.COLOR_TOOLBAR_GREY.get_html())
        self.modify_bg(Gtk.StateType.NORMAL, color)
