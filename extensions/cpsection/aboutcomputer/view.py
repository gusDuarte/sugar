# coding=utf-8
# Copyright (C) 2008, OLPC
# Copyright (C) 2009 Simon Schampijer
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

from gettext import gettext as _

from gi.repository import Gtk
from gi.repository import Gdk

from sugar3.graphics import style

from jarabe.controlpanel.sectionview import SectionView
from jarabe.view.buddymenu import get_control_panel


class AboutComputer(SectionView):
    def __init__(self, model, alerts=None):
        SectionView.__init__(self)
        get_control_panel()._section_toolbar.cancel_button.hide()

        self._model = model

        self.set_border_width(style.DEFAULT_SPACING * 2)
        self.set_spacing(style.DEFAULT_SPACING)

        self._group = Gtk.SizeGroup(Gtk.SizeGroupMode.HORIZONTAL)

        scrollwindow = Gtk.ScrolledWindow()
        scrollwindow.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        self.pack_start(scrollwindow, True, True, 0)
        scrollwindow.show()

        self._vbox = Gtk.VBox()
        scrollwindow.add_with_viewport(self._vbox)
        self._vbox.show()

        self._setup_identity()

        self._setup_software()
        self._setup_copyright()

    def _setup_identity(self):
        separator_identity = Gtk.HSeparator()
        self._vbox.pack_start(separator_identity, False, True, 0)
        separator_identity.show()

        label_identity = Gtk.Label(label=_('Identity'))
        label_identity.set_alignment(0, 0)
        self._vbox.pack_start(label_identity, False, True, 0)
        label_identity.show()
        vbox_identity = Gtk.VBox()
        vbox_identity.set_border_width(style.DEFAULT_SPACING * 2)
        vbox_identity.set_spacing(style.DEFAULT_SPACING)

        self._setup_component_if_applicable(None,
                                            _('Model:'),
                                            self._model.get_model_laptop,
                                            vbox_identity)

        self._setup_component_if_applicable(None,
                                            _('Serial Number:'),
                                            self._model.get_serial_number,
                                            vbox_identity)

        self._setup_component_if_applicable('/desktop/sugar/extensions/aboutcomputer/display_lease',
                                            _('Lease:'),
                                            self._model.get_lease_days,
                                            vbox_identity)

        self._vbox.pack_start(vbox_identity, False, True, 0)
        vbox_identity.show()

    def _is_feature_to_be_shown(slf, gconf_key):
        if gconf_key is None:
            return True

        from gi.repository import GConf
        client = GConf.Client.get_default()

        return client.get_bool(gconf_key) is True

    def _setup_component_if_applicable(self, gconf_key, key, value_func, packer):
        if not self._is_feature_to_be_shown(gconf_key):
            return

        # Now that we do need to show, fetch the value.
        print value_func
        value = value_func()

        box = Gtk.HBox(spacing=style.DEFAULT_SPACING)
        key_label = Gtk.Label(label=key)
        key_label.set_alignment(1, 0)
        key_label.modify_fg(Gtk.StateType.NORMAL,
                            style.COLOR_SELECTION_GREY.get_gdk_color())
        box.pack_start(key_label, False, True, 0)
        self._group.add_widget(key_label)
        key_label.show()
        value_label = Gtk.Label(label=value)
        value_label.set_alignment(0, 0)
        box.pack_start(value_label, False, True, 0)
        value_label.show()
        packer.pack_start(box, False, True, 0)
        box.show()

    def _setup_software(self):
        separator_software = Gtk.HSeparator()
        self._vbox.pack_start(separator_software, False, True, 0)
        separator_software.show()

        label_software = Gtk.Label(label=_('Software'))
        label_software.set_alignment(0, 0)
        self._vbox.pack_start(label_software, False, True, 0)
        label_software.show()
        box_software = Gtk.VBox()
        box_software.set_border_width(style.DEFAULT_SPACING * 2)
        box_software.set_spacing(style.DEFAULT_SPACING)

        self._setup_component_if_applicable(None,
                                            _('Build:'),
                                            self._model.get_build_number,
                                            box_software)

        self._setup_component_if_applicable(None,
                                            _('Sugar:'),
                                            self._model.get_sugar_version,
                                            box_software)

        self._setup_component_if_applicable(None,
                                            _('Firmware:'),
                                            self._model.get_firmware_number,
                                            box_software)

        self._setup_component_if_applicable('/desktop/sugar/extensions/aboutcomputer/display_wireless_firmware',
                                            _('Wireless Firmware:'),
                                            self._model.get_wireless_firmware,
                                            box_software)

        self._setup_component_if_applicable('/desktop/sugar/extensions/aboutcomputer/display_plazo',
                                            _('Plazo:'),
                                            self._model.get_plazo,
                                            box_software)

        self._setup_component_if_applicable('/desktop/sugar/extensions/aboutcomputer/display_version_de_actual',
                                            _('Versión de Actualización:'),
                                            self._model.get_act,
                                            box_software)

        self._setup_component_if_applicable(None,
                                            _('Last Updated On:'),
                                            self._model.get_last_updated_on_field,
                                            box_software)

        self._vbox.pack_start(box_software, False, True, 0)
        box_software.show()

    def _setup_copyright(self):
        separator_copyright = Gtk.HSeparator()
        self._vbox.pack_start(separator_copyright, False, True, 0)
        separator_copyright.show()

        label_copyright = Gtk.Label(label=_('Copyright and License'))
        label_copyright.set_alignment(0, 0)
        self._vbox.pack_start(label_copyright, False, True, 0)
        label_copyright.show()
        vbox_copyright = Gtk.VBox()
        vbox_copyright.set_border_width(style.DEFAULT_SPACING * 2)
        vbox_copyright.set_spacing(style.DEFAULT_SPACING)

        copyright_text = '© 2006-2013 One Laptop per Child Association Inc,' \
                         ' Sugar Labs Inc, Red Hat Inc, Collabora Ltd and' \
                         ' Contributors.'
        label_copyright = Gtk.Label(label=copyright_text)
        label_copyright.set_alignment(0, 0)
        label_copyright.set_size_request(Gdk.Screen.width() / 2, -1)
        label_copyright.set_line_wrap(True)
        label_copyright.show()
        vbox_copyright.pack_start(label_copyright, False, True, 0)

        # TRANS: The word "Sugar" should not be translated.
        info_text = _('Sugar is the graphical user interface that you are'
                      ' looking at. Sugar is free software, covered by the'
                      ' GNU General Public License, and you are welcome to'
                      ' change it and/or distribute copies of it under'
                      ' certain conditions described therein.')
        label_info = Gtk.Label(label=info_text)
        label_info.set_alignment(0, 0)
        label_info.set_line_wrap(True)
        label_info.set_size_request(Gdk.Screen.width() / 2, -1)
        label_info.show()
        vbox_copyright.pack_start(label_info, False, True, 0)

        from gi.repository import GConf
        client = GConf.Client.get_default()
        if client.get_bool('/desktop/sugar/extensions/aboutcomputer/show_additional_au_copyright') is True:
            fonts_text = _('School Fonts © 2011 Free for use as part of'
                           ' the One Laptop per Child and Sugar projects.'
                           ' For any other use, visit: http://www.schoolfonts.com.au/')
            label_fonts = Gtk.Label(label=fonts_text)
            label_fonts.set_alignment(0, 0)
            label_fonts.set_line_wrap(True)
            label_fonts.set_size_request(Gdk.Screen.width() / 2, -1)
            label_fonts.show()
            vbox_copyright.pack_start(label_fonts, False, True, 0)

        expander = Gtk.Expander(label=_('Full license:'))
        expander.connect('notify::expanded', self.license_expander_cb)
        expander.show()
        vbox_copyright.pack_start(expander, True, True, 0)

        self._vbox.pack_start(vbox_copyright, True, True, 0)
        vbox_copyright.show()

    def license_expander_cb(self, expander, param_spec):
        # load/destroy the license viewer on-demand, to avoid storing the
        # GPL in memory at all times
        if expander.get_expanded():
            view_license = Gtk.TextView()
            view_license.set_editable(False)
            view_license.get_buffer().set_text(self._model.get_license())
            view_license.show()
            expander.add(view_license)
        else:
            expander.get_child().destroy()

    def perform_accept_actions(self):
        get_control_panel()._section_toolbar.cancel_button.show()
