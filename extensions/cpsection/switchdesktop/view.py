# Copyright (C) 2009 One Laptop per Child
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
# Foundation, Inc., 51 Franklin St, Fifth Floor, Boston, MA  02110-1301 USA

import os
from gi.repository import Gtk
import gettext
import subprocess

from sugar3.graphics import style
from sugar3.graphics.icon import Icon

from jarabe.controlpanel.sectionview import SectionView
from jarabe.model.session import get_session_manager
from jarabe import config

_ = lambda msg: gettext.dgettext('olpc-switch-desktop', msg)

class SwitchDesktop(SectionView):
    def __init__(self, model, alerts):
        SectionView.__init__(self)
        self._model = model
        self._switch_button_handler = None
        self._undo_button_handler = None
        self._fix_unknown_button_handler = None

        self.set_border_width(style.DEFAULT_SPACING * 2)
        self.set_spacing(style.DEFAULT_SPACING)

        self._active_desktop_label = Gtk.Label()
        self.pack_start(self._active_desktop_label, False, False, 0)

        self._sugar_desc_label = Gtk.Label(label=
            _("Sugar is the graphical user interface that you are looking at. "
              "It is a learning environment designed for children."))
        self._sugar_desc_label.set_line_wrap(True)
        self._sugar_desc_label.set_justify(Gtk.Justification.FILL)
        self.pack_start(self._sugar_desc_label, False, False, 0)

        self._gnome_opt_label = Gtk.Label(label=
            _("As an alternative to Sugar, you can switch to the GNOME "
              "desktop environment by clicking the button below."))
        self._gnome_opt_label.set_line_wrap(True)
        self._gnome_opt_label.set_justify(Gtk.Justification.FILL)
        self.pack_start(self._gnome_opt_label, False, False, 0)

        label_text = _("Restart the graphical interface to complete the change to the "
            "GNOME desktop environment.\n\n"
            "Remember, you can return to Sugar later by opening the GNOME "
            "Applications menu and clicking <b>Switch to Sugar</b> under the "
            "<b>System Tools</b> sub-menu. Or, click the <b>Cancel "
            "changes</b> button below if you would like to continue using "
            "Sugar as your desktop environment.")


        self._switch_align = Gtk.Alignment.new(0.5, 0.5, 0, 0)
        self.pack_start(self._switch_align, True, True, 0)

        self._switch_button = Gtk.Button(_("Switch to GNOME"))
        self._switch_button.set_image(Icon(icon_name="module-switch-desktop"))
        self._switch_align.add(self._switch_button)
        self._switch_button.show()


        self._undo_align = Gtk.Alignment.new(0.5, 0.5, 0, 0)
        self.pack_start(self._undo_align, True, True, 0)

        hbox = Gtk.HButtonBox()
        hbox.set_layout(Gtk.ButtonBoxStyle.END)
        hbox.set_spacing(style.DEFAULT_SPACING)
        self._undo_align.add(hbox)
        hbox.show()

        self._undo_button = Gtk.Button(_("Cancel changes"))
        self._undo_button.set_image(Icon(icon_name="dialog-cancel"))
        hbox.add(self._undo_button)
        self._undo_button.show()

        self._unknown_align = Gtk.Alignment.new(0.5, 0.5, 0, 0)
        self.pack_start(self._unknown_align, True, True, 0)

        self._fix_unknown_button = Gtk.Button(_("Set Sugar as active desktop"))
        self._fix_unknown_button.set_image(Icon(icon_name="computer-xo"))
        self._unknown_align.add(self._fix_unknown_button)
        self._fix_unknown_button.show()

        self._return_label = Gtk.Label()
        self._return_label.set_markup(
            _("You can return to Sugar later, by clicking on the <b>Switch "
              "to Sugar</b> icon on the GNOME desktop. This is also available "
              "from the GNOME <b>Applications</b> menu."))
        self._return_label.set_line_wrap(True)
        self._return_label.set_justify(Gtk.Justification.FILL)
        self.pack_start(self._return_label, False, False, 0)

        self._img_table = Gtk.Table(rows=2, columns=2)
        self.pack_start(self._img_table, False, False, 0)

        img_path = os.path.join(config.ext_path, 'cpsection', 'switchdesktop')

        img = Gtk.Image.new_from_file(os.path.join(img_path, 'sugar.png'))
        self._img_table.attach(img, 0, 1, 0, 1)
        label = Gtk.Label(label="Sugar")
        self._img_table.attach(label, 0, 1, 1, 2)

        img = Gtk.Image.new_from_file(os.path.join(img_path, 'gnome.png'))
        self._img_table.attach(img, 1, 2, 0, 1)
        label = Gtk.Label(label="GNOME")
        self._img_table.attach(label, 1, 2, 1, 2)

        self.setup()
        self._update()

    def setup(self):
        self._switch_button_handler =  \
                self._switch_button.connect('clicked', self._switch_button_cb)
        self._undo_button_handler = \
                self._undo_button.connect('clicked', self._undo_button_cb)
        self._fix_unknown_button_handler = \
                self._fix_unknown_button.connect('clicked', self._undo_button_cb)
        # FIXME: disconnect anywhere?

    def undo(self):
        self._do_undo()
        self._update()

    def _update(self):
        active = self._model.get_active_desktop()
        self._active_desktop_label.set_markup("<big>" + _("Active desktop environment: ")
            + "<b>" + active + "</b></big>")
        self._active_desktop_label.show()
        
        sugar_active = active == "Sugar"
        gnome_active = active == "GNOME"
        unknown_active = active == "Unknown"

        self._sugar_desc_label.set_visible(sugar_active)
        self._gnome_opt_label.set_visible(sugar_active)
        self._switch_align.set_visible(sugar_active)
        self._return_label.set_visible(sugar_active)
        self._undo_align.set_visible(gnome_active)
        self._unknown_align.set_visible(unknown_active)

        self._img_table.show_all()

    def _do_undo(self):
        self._model.undo_switch()

    def _switch_button_cb(self, widget):
        self._model.switch_to_gnome()
        self._update()

    def _undo_button_cb(self, widget):
        self._do_undo()
        self._update()

