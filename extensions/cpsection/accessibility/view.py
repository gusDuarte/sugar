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
from gettext import gettext as _

from sugar3.graphics import style

from jarabe.controlpanel.sectionview import SectionView
from jarabe.controlpanel.inlinealert import InlineAlert

class accessibility(SectionView):
    def __init__(self, model, alerts=None):
        SectionView.__init__(self)

        self._model = model
        self.restart_alerts = alerts
        self.set_border_width(style.DEFAULT_SPACING * 2)
        self.set_spacing(style.DEFAULT_SPACING)
        scrollwindow = Gtk.ScrolledWindow()
        scrollwindow.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
        self.pack_start(scrollwindow, True, True, 0)
        scrollwindow.show()

        self._vbox_section = Gtk.VBox()
        scrollwindow.add_with_viewport(self._vbox_section)
        self._vbox_section.show()

        self._zone_alert_box = Gtk.HBox(spacing=style.DEFAULT_SPACING)
        self.pack_start(self._zone_alert_box, False, False, 0)

        self._zone_alert = InlineAlert()
        self._zone_alert_box.pack_start(self._zone_alert, True, True, 0)
        if 'zone' in self.restart_alerts:
            self._zone_alert.props.msg = self.restart_msg
            self._zone_alert.show()
        self._zone_alert_box.show()

        self.needs_restart = False

        self._view_keyboard_options()
        self._view_screen_options()
        self._view_mouse_options()


    def _view_keyboard_options(self):
        separator_pm_keyboard = Gtk.HSeparator()
        self._vbox_section.pack_start(separator_pm_keyboard, False, False, 0)
        separator_pm_keyboard.show()

        label_pm_keyboard = Gtk.Label(_('Keyboard'))
        label_pm_keyboard.set_alignment(0, 0)
        self._vbox_section.pack_start(label_pm_keyboard, False, False, 0)
        label_pm_keyboard.show()

        self.box_pm_keyboard = Gtk.VBox()
        self.box_pm_keyboard.set_border_width(style.DEFAULT_SPACING * 2)
        self.box_pm_keyboard.set_spacing(style.DEFAULT_SPACING)

        self._view_mouse_keys()
        self._view_sticky_keys()
        self._view_bounce_keys()
        self._view_virtualkeyboard()

        self._vbox_section.pack_start(self.box_pm_keyboard, False, False, 0)
        self.box_pm_keyboard.show()

    def _view_screen_options(self):
        separator_pm_screen = Gtk.HSeparator()
        self._vbox_section.pack_start(separator_pm_screen, False, False, 0)
        separator_pm_screen.show()

        label_pm_screen = Gtk.Label(_('Screen'))
        label_pm_screen.set_alignment(0, 0)
        self._vbox_section.pack_start(label_pm_screen, False, False, 0)
        label_pm_screen.show()

        self.box_pm_screen = Gtk.VBox()
        self.box_pm_screen.set_border_width(style.DEFAULT_SPACING * 2)
        self.box_pm_screen.set_spacing(style.DEFAULT_SPACING)

        self._view_contrast()
        self._view_letters()

        self._vbox_section.pack_start(self.box_pm_screen, False, False, 0)
        self.box_pm_screen.show()

    def _view_mouse_options(self):
        separator_pm_mouse = Gtk.HSeparator()
        self._vbox_section.pack_start(separator_pm_mouse, False, False, 0)
        separator_pm_mouse.show()

        label_pm_mouse = Gtk.Label(_('Mouse'))
        label_pm_mouse.set_alignment(0, 0)
        self._vbox_section.pack_start(label_pm_mouse, False, False, 0)
        label_pm_mouse.show()

        self.box_pm_mouse = Gtk.VBox()
        self.box_pm_mouse.set_border_width(style.DEFAULT_SPACING * 2)
        self.box_pm_mouse.set_spacing(style.DEFAULT_SPACING)

        self._view_white_mouse()
        self._view_acceleration_mouse()

        self._vbox_section.pack_start(self.box_pm_mouse, False, False, 0)
        self.box_pm_mouse.show()

    def _set_mouse_keys(self, widget):
        state = widget.get_active()
        self._model.set_mouse_keys(state)

    def _set_sticky_keys(self, widget):
        state = widget.get_active()
        self._model.set_sticky_keys(state)

    def _set_bounce_keys(self, widget):
        state = widget.get_active()
        self._model.set_bounce_keys(state)
        self.needs_restart = True

    def _set_virtualkeyboard(self, widget):
        state = widget.get_active()
        self._model.set_virtualkeyboard(state)
        self.restart_alerts.append('zone')
        self.needs_restart = True
        self._zone_alert.props.msg = self.restart_msg
        self._zone_alert.show()

    def _set_contrast(self, widget):
        state = widget.get_active()
        self._model.set_contrast(state)
        self.restart_alerts.append('zone')
        self.needs_restart = True
        self._zone_alert.props.msg = self.restart_msg
        self._zone_alert.show()

    def _set_capital_letters(self, widget):
        state = widget.get_active()
        self._model.set_capital_letters(state)
        self.restart_alerts.append('zone')
        self.needs_restart = True
        self._zone_alert.props.msg = self.restart_msg
        self._zone_alert.show()

    def _set_white_mouse(self, widget):
        state = widget.get_active()
        self._model.set_white_mouse(state)
        self.restart_alerts.append('zone')
        self.needs_restart = True
        self._zone_alert.props.msg = self.restart_msg
        self._zone_alert.show()

    def cb_digits_scale_accel_mouse(self, adj):
        self._model.set_accel_mouse(adj.get_value())

    def undo(self):
        self._model.set_mouse_keys(self.init_state_mouse_keys)
        self._model.set_sticky_keys(self.init_state_sticky_keys)
        self._model.set_bounce_keys(self.init_state_bounce_keys)

        self._model.set_virtualkeyboard(self.init_state_virtualkeyboard)
        self.btn_virtualkeyboard.set_active(self.init_state_virtualkeyboard)

        self._model.set_contrast(self.init_state_contrast)
        self.btn_contrast.set_active(self.init_state_contrast)

        self._model.set_capital_letters(self.init_state_capital_letters)
        self.btn_capital_letters.set_active(self.init_state_capital_letters)

        self._model.set_white_mouse(self.init_state_white_mouse)
        self.btn_white_mouse.set_active(self.init_state_white_mouse)

        self.adj_accel_mouse.set_value(self.init_state_accel_mouse)

        self.needs_restart = False
        self._zone_alert.hide()

    def _view_mouse_keys(self):
        self.btn_mouse_keys = Gtk.CheckButton(_('Mouse Keys'))
        self._mouse_pm_change_handler = self.btn_mouse_keys.connect("toggled", self._set_mouse_keys)
        self.init_state_mouse_keys = self._model.get_mouse_keys()
        self.btn_mouse_keys.set_active(self.init_state_mouse_keys)
        self.box_pm_keyboard.pack_start(self.btn_mouse_keys, True, True, 2)
        self.btn_mouse_keys.show()

        lbl_mouse = Gtk.Label(_('Move the mouse pointer with keyboard number.'))
        lbl_mouse.set_alignment(0, 0)
        self.box_pm_keyboard.pack_start(lbl_mouse, True, True, 2)
        lbl_mouse.show()

    def _view_sticky_keys(self):
        self.btn_sticky_keys = Gtk.CheckButton(_('Sticky Keys'))
        self._sticky_pm_change_handler = self.btn_sticky_keys.connect("toggled", self._set_sticky_keys)
        self.init_state_sticky_keys = self._model.get_sticky_keys()
        self.btn_sticky_keys.set_active(self.init_state_sticky_keys)
        self.box_pm_keyboard.pack_start(self.btn_sticky_keys, True, True, 2)
        self.btn_sticky_keys.show()

        lbl_sticky = Gtk.Label(_('Instead of having to press two keys at once (such as CTRL + Q), you can press one key at a time.'))
        lbl_sticky.set_line_wrap(True)
        lbl_sticky.set_alignment(0, 0)
        self.box_pm_keyboard.pack_start(lbl_sticky, True, True, 2)
        lbl_sticky.show()

    def _view_bounce_keys(self):
        self.btn_bounce_keys = Gtk.CheckButton(_('Bounce Keys'))
        self._bounce_pm_change_handler = self.btn_bounce_keys.connect("toggled", self._set_bounce_keys)
        self.init_state_bounce_keys = self._model.get_bounce_keys()
        self.btn_bounce_keys.set_active(self.init_state_bounce_keys)
        self.box_pm_keyboard.pack_start(self.btn_bounce_keys, True, True, 2)
        self.btn_bounce_keys.show()

        lbl_bounce = Gtk.Label(_('Ignore rapid, repeated keypresses of the same key.'))
        lbl_bounce.set_alignment(0, 0)
        self.box_pm_keyboard.pack_start(lbl_bounce, True, True, 2)
        lbl_bounce.show()

    def _view_virtualkeyboard(self):
        self.btn_virtualkeyboard = Gtk.CheckButton(_('Virtual keyboard'))
        self._virtualkeyboard_pm_change_handler = self.btn_virtualkeyboard.connect("toggled", self._set_virtualkeyboard)
        self.init_state_virtualkeyboard = self._model.get_virtualkeyboard()
        if self.init_state_virtualkeyboard:
            self.btn_virtualkeyboard.handler_block(self._virtualkeyboard_pm_change_handler)
            self.btn_virtualkeyboard.set_active(True)
            self.btn_virtualkeyboard.handler_unblock(self._virtualkeyboard_pm_change_handler)
        else:
            self.btn_virtualkeyboard.set_active(False)
        self.box_pm_keyboard.pack_start(self.btn_virtualkeyboard, True, True, 2)
        self.btn_virtualkeyboard.show()

        lbl_virtualkeyboard = Gtk.Label(_('Show virtual keyboard on frame.'))
        lbl_virtualkeyboard.set_alignment(0, 0)
        self.box_pm_keyboard.pack_start(lbl_virtualkeyboard, True, True, 2)
        lbl_virtualkeyboard.show()

    def _view_contrast(self):
        self.btn_contrast = Gtk.CheckButton(_('Contrast'))
        self._contrast_pm_change_handler = self.btn_contrast.connect("toggled", self._set_contrast)
        self.init_state_contrast = self._model.get_contrast()
        if self.init_state_contrast:
            self.btn_contrast.handler_block(self._contrast_pm_change_handler)
            self.btn_contrast.set_active(True)
            self.btn_contrast.handler_unblock(self._contrast_pm_change_handler)
        else:
            self.btn_contrast.set_active(False)
        self.box_pm_screen.pack_start(self.btn_contrast, True, True, 2)
        self.btn_contrast.show()

        lbl_contrast = Gtk.Label(_('Enables the color contrast of the graphic interface.'))
        lbl_contrast.set_alignment(0, 0)
        self.box_pm_screen.pack_start(lbl_contrast, True, True, 2)
        lbl_contrast.show()

    def _view_letters(self):
        self.btn_capital_letters = Gtk.CheckButton(_('Capital letters'))
        self._capital_letters_pm_change_handler = self.btn_capital_letters.connect("toggled", self._set_capital_letters)
        self.init_state_capital_letters = self._model.get_capital_letters()
        if self.init_state_capital_letters:
            self.btn_capital_letters.handler_block(self._capital_letters_pm_change_handler)
            self.btn_capital_letters.set_active(True)
            self.btn_capital_letters.handler_unblock(self._capital_letters_pm_change_handler)
        else:
            self.btn_capital_letters.set_active(False)
        self.box_pm_screen.pack_start(self.btn_capital_letters, True, True, 2)
        self.btn_capital_letters.show()

        lbl_capital_letters = Gtk.Label(_('Shows capital letters in the user interface.'))
        lbl_capital_letters.set_alignment(0, 0)
        self.box_pm_screen.pack_start(lbl_capital_letters, True, True, 2)
        lbl_capital_letters.show()

    def _view_white_mouse(self):
        self.btn_white_mouse = Gtk.CheckButton(_('White Mouse'))
        self._white_mouse_pm_change_handler = self.btn_white_mouse.connect("toggled", self._set_white_mouse)
        self.init_state_white_mouse = self._model.get_white_mouse()
        if self.init_state_white_mouse:
            self.btn_white_mouse.handler_block(self._white_mouse_pm_change_handler)
            self.btn_white_mouse.set_active(True)
            self.btn_white_mouse.handler_unblock(self._white_mouse_pm_change_handler)
        else:
            self.btn_white_mouse.set_active(False)
        self.box_pm_mouse.pack_start(self.btn_white_mouse, True, True, 2)
        self.btn_white_mouse.show()

        lbl_white_mouse = Gtk.Label(_('Show the mouse cursor white.'))
        lbl_white_mouse.set_alignment(0, 0)
        self.box_pm_mouse.pack_start(lbl_white_mouse, True, True, 2)
        lbl_white_mouse.show()

    def _view_acceleration_mouse(self):
        box_accel_mouse = Gtk.HBox(False, 0)
        box_accel_mouse.set_border_width(0)
        lbl_accel_mouse = Gtk.Label(_('Acceleration: '))
        lbl_accel_mouse.show()
        box_accel_mouse.pack_start(lbl_accel_mouse, False, False, 0)

        self.init_state_accel_mouse = self._model.get_accel_mouse();
        self.adj_accel_mouse = Gtk.Adjustment(self.init_state_accel_mouse, 0.0, 5.0, 1.0, 1.0, 0.0)
        self.adj_accel_mouse.connect("value_changed", self.cb_digits_scale_accel_mouse)
        self.scale_accel_mouse = Gtk.HScale(adjustment=self.adj_accel_mouse)
        self.scale_accel_mouse.set_digits(0)
        self.scale_accel_mouse.show()

        box_accel_mouse.pack_start(self.scale_accel_mouse, True, True, 0)
        box_accel_mouse.show()

        self.box_pm_mouse.pack_start(box_accel_mouse, True, True, 2)

        desc_accel_mouse = Gtk.Label(_('Controller acceleration mouse.'))
        desc_accel_mouse.set_alignment(0, 0)
        self.box_pm_mouse.pack_start(desc_accel_mouse, True, True, 2)
        desc_accel_mouse.show()

    def setup(self):
        pass
