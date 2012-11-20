# Copyright (C) 2008, OLPC
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

from gi.repository import Gtk
from gi.repository import Gdk
from gi.repository import GConf
from gi.repository import GObject
from gi.repository import Gio
from gi.repository import Pango
from gettext import gettext as _

import os
import subprocess
import logging

from sugar3.graphics import style

from jarabe.controlpanel.sectionview import SectionView
from jarabe.controlpanel.inlinealert import InlineAlert


CLASS = 'Network'
ICON = 'module-network'
TITLE = _('Network')

_APPLY_TIMEOUT = 3000
EXPLICIT_REBOOT_MESSAGE = _('Please restart your computer for changes to take effect.')

# Please refer ::
# http://developer.gnome.org/ProxyConfiguration/

GSETTINGS_PROXY       = Gio.Settings.new('org.gnome.system.proxy')
GSETTINGS_PROXY_FTP   = Gio.Settings.new('org.gnome.system.proxy.ftp')
GSETTINGS_PROXY_HTTP  = Gio.Settings.new('org.gnome.system.proxy.http')
GSETTINGS_PROXY_HTTPS = Gio.Settings.new('org.gnome.system.proxy.https')
GSETTINGS_PROXY_SOCKS = Gio.Settings.new('org.gnome.system.proxy.socks')


client = GConf.Client.get_default()


class GConfMixin(object):
    """Mix-in class for GTK widgets backed by GConf"""
    def __init__(self, gconf_key, gsettings_dconf, dconf_key, widget=None, signal='changed'):
        self._timeout_id = None
        self._gconf_key = gconf_key
        self._gsettings_dconf = gsettings_dconf
        self._dconf_key = dconf_key
        self._notify_id = client.notify_add(gconf_key, self.__gconf_notify_cb, None)
        initial_value = self._get_gconf_value()
        self._undo_value = initial_value
        self.set_value_from_gconf(initial_value)
        widget = widget or self
        widget.connect(signal, self.__changed_cb)

    def undo(self):
        """Revert to original value if modified"""
        if not self.changed:
            return
        logging.debug('Reverting %r to %r', self._gconf_key, self._undo_value)
        self._set_gconf_value(self._undo_value)

    def get_value_for_gconf(self):
        """
        Return the current value of the widget in a format suitable for GConf

        MUST be implemented by subclasses.
        """
        raise NotImplementedError()

    def set_value_from_gconf(self, value):
        """
        Set the current value of the widget based on a value from GConf
        MUST be implemented by subclasses.
        """
        raise NotImplementedError()

    def __changed_cb(self, widget):
        if self._timeout_id is not None:
            GObject.source_remove(self._timeout_id)
        self._timeout_id = GObject.timeout_add(_APPLY_TIMEOUT, self._commit,
                                               widget)

    def __gconf_notify_cb(self, client, transaction_id_, entry, user_data_):
        new_value = _gconf_value_to_python(entry.value)
        self.set_value_from_gconf(new_value)

    def _commit(self, widget):
        new_value = self.get_value_for_gconf()
        logging.debug('Setting %r to %r', self._gconf_key, new_value)

        widget.handler_block_by_func(self.__changed_cb)
        try:
            self._set_gconf_value(new_value)
        finally:
            widget.handler_unblock_by_func(self.__changed_cb)

    def _set_gconf_value(self, new_value):
        gconf_type = client.get(self._gconf_key).type
        if gconf_type == GConf.ValueType.STRING:
            client.set_string(self._gconf_key, new_value)
            self._gsettings_dconf.set_string(self._dconf_key, new_value)
        elif gconf_type == GConf.ValueType.INT:
            client.set_int(self._gconf_key, new_value)
            self._gsettings_dconf.set_int(self._dconf_key, new_value)
        elif gconf_type == GConf.ValueType.FLOAT:
            client.set_float(self._gconf_key, new_value)
            self._gsettings_dconf.set_double(self._dconf_key, new_value)
        elif gconf_type == GConf.ValueType.BOOL:
            client.set_bool(self._gconf_key, new_value)
            self._gsettings_dconf.set_boolean(self._dconf_key, new_value)
        elif gconf_type == GConf.ValueType.LIST:
            import traceback
            list_type = client.get(self._gconf_key).get_list_type()

            # Persisting the value of a "LIST" via shell, unless and
            # until http://bugs.sugarlabs.org/ticket/3926 gets solved.
            commit_list = []
            for value in new_value:
                translated_value = value.translate(None, "' ")
                commit_list.append(translated_value)

            environment = os.environ.copy()
            try:
                process = subprocess.Popen(['gconftool-2 '
                                            '--type list '
                                            '--list-type string '
                                            '--set %s \'%s\'' % (self._gconf_key,
                                                                 commit_list)],
                                            stdout=subprocess.PIPE,
                                            env=environment,
                                            shell=True)
                process.wait()

                self._gsettings_dconf.set_strv(self._dconf_key, new_value)
            except Exception, e:
                logging.exception(e)
            #client.set_list(self._gconf_key, list_type, new_value)
        else:
            raise TypeError('Cannot store %r in GConf' % (new_value, ))

    def _get_gconf_value(self):
        return _gconf_value_to_python(client.get(self._gconf_key))

    def changed(self):
        return self._undo_value != self.get_value_for_gconf()


class GConfEntry(Gtk.Entry, GConfMixin):
    """Text entry backed by GConf

    It is the callers responsibility to call GConfClient.add_dir() for the
    GConf directory containing the key.
    """

    def __init__(self, gconf_key, gsettings_dconf, dconf_key):
        Gtk.Entry.__init__(self)
        GConfMixin.__init__(self, gconf_key, gsettings_dconf, dconf_key)

    def get_value_for_gconf(self):
        return self.props.text

    def set_value_from_gconf(self, value):
        self.props.text = value


class GConfIntegerSpinButton(Gtk.SpinButton, GConfMixin):
    """Integer SpinButton backed by GConf
    It is the callers responsibility to call GConfClient.add_dir() for the
    GConf directory containing the key.
    """

    def __init__(self, gconf_key, gsettings_dconf, dconf_key, adjustment, climb_rate=0):
        Gtk.SpinButton.__init__(self, adjustment=adjustment, climb_rate=climb_rate)
        GConfMixin.__init__(self, gconf_key, gsettings_dconf, dconf_key)

    def get_value_for_gconf(self):
        return self.get_value_as_int()

    def set_value_from_gconf(self, value):
        self.set_value(value)


class GConfStringListEntry(GConfEntry):
    """Text entry backed by a GConf list of strings"""

    def __init__(self, gconf_key, gsettings_dconf, dconf_key, separator=','):
        self._separator = separator
        GConfEntry.__init__(self, gconf_key, gsettings_dconf, dconf_key)

    def get_value_for_gconf(self):
        entries = self.props.text.split(self._separator)
        return [entry for entry in entries if entry]

    def set_value_from_gconf(self, value):
        self.props.text = self._separator.join(value)


class SettingBox(Gtk.HBox):
    """
    Base class for "lines" on the screen representing configuration settings
    """

    def __init__(self, name, size_group=None):
        Gtk.HBox.__init__(self, spacing=style.DEFAULT_SPACING)
        self.label = Gtk.Label(name)
        self.label.modify_fg(Gtk.StateType.NORMAL,
                             style.COLOR_SELECTION_GREY.get_gdk_color())
        self.label.set_alignment(1, 0.5)
        self.label.show()
        self.pack_start(self.label, False, False, 0)

        if size_group is not None:
            size_group.add_widget(self.label)


class GConfStringSettingBox(SettingBox):
    """A configuration line for a GConf string setting"""

    def __init__(self, name, gconf_key, gsettings_dconf, dconf_key, size_group=None):
        SettingBox.__init__(self, name, size_group=size_group)
        self.string_entry = GConfEntry(gconf_key, gsettings_dconf, dconf_key)
        self.string_entry.show()
        self.pack_start(self.string_entry, True, True, 0)

    def undo(self):
        """Revert to original value if modified"""
        self.string_entry.undo()

    @property
    def changed(self):
        return self.string_entry.changed


class GConfPasswordSettingBox(GConfStringSettingBox):
    """A configuration line for a GConf password setting"""

    def __init__(self, name, gconf_key, gsettings_dconf, dconf_key, size_group=None):
        GConfStringSettingBox.__init__(self, name, gconf_key,
                                       gsettings_dconf, dconf_key, size_group)
        self.string_entry.set_visibility(False)


class GConfHostListSettingBox(GConfStringSettingBox):
    """A configuration line for a host list GConf setting"""

    def __init__(self, name, gconf_key, gsettings_dconf, dconf_key, size_group=None):
        SettingBox.__init__(self, name, size_group=size_group)
        self.hosts_entry = GConfStringListEntry(gconf_key,
                                                gsettings_dconf, dconf_key)
        self.hosts_entry.show()
        self.pack_start(self.hosts_entry, True, True, 0)

    def undo(self):
        """Revert to original value if modified"""
        self.hosts_entry.undo()

    @property
    def changed(self):
        return self.hosts_entry.changed

class GConfHostPortSettingBox(SettingBox):
    """A configuration line for a combined host name and port GConf setting"""

    def __init__(self, name, host_key, port_key, gsettings_dconf,
                 dconf_host_key, dconf_port_key, size_group=None):
        SettingBox.__init__(self, name, size_group=size_group)
        self.host_name_entry = GConfEntry(host_key, gsettings_dconf,
                                          dconf_host_key)
        self.host_name_entry.show()
        self.pack_start(self.host_name_entry, True, True, 0)

        # port number 0 means n/a
        adjustment = Gtk.Adjustment(0, 0, 65535, 1, 10)
        self.port_spin_button = GConfIntegerSpinButton(port_key,
                                                       gsettings_dconf,
                                                       dconf_port_key,
                                                       adjustment,
                                                       climb_rate=0.1)
        self.port_spin_button.show()
        self.pack_start(self.port_spin_button, False, False, 0)

    def undo(self):
        """Revert to original values if modified"""
        self.host_name_entry.undo()
        self.port_spin_button.undo()

    @property
    def changed(self):
        return self.host_name_entry.changed or self.port_spin_button.changed


class ExclusiveOptionSetsBox(Gtk.VBox):
    """
    Container for sets of different settings selected by a top-level setting
    Renders the top level setting as a ComboBox. Only the currently
    active set is shown on screen.
    """
    def __init__(self, top_name, option_sets, size_group=None):
        """Initialize an ExclusiveOptionSetsBox instance

        Arguments:

        top_name -- text label used for the top-level selection
        option_sets -- list of tuples containing text label and GTK
                       widget to display for each of the option sets
        size_group -- optional gtk.SizeGroup to use for the top-level label
        """
        Gtk.VBox.__init__(self, spacing=style.DEFAULT_SPACING)
        self.label_size_group = size_group
        top_box = Gtk.HBox(spacing=style.DEFAULT_SPACING)
        top_box.show()
        top_label = Gtk.Label(top_name)
        top_label.modify_fg(Gtk.StateType.NORMAL,
                            style.COLOR_SELECTION_GREY.get_gdk_color())
        top_label.set_alignment(1, 0.5)
        top_label.show()
        self.label_size_group.add_widget(top_label)
        top_box.pack_start(top_label, False, False, 0)

        model = Gtk.ListStore(GObject.TYPE_STRING, GObject.TYPE_OBJECT)
        self._top_combo_box = Gtk.ComboBox(model=model)
        self._top_combo_box.connect('changed', self.__combo_changed_cb)
        self._top_combo_box.show()

        cell_renderer = Gtk.CellRendererText()
        cell_renderer.props.ellipsize = Pango.EllipsizeMode.MIDDLE
        cell_renderer.props.ellipsize_set = True
        self._top_combo_box.pack_start(cell_renderer, True)
        self._top_combo_box.add_attribute(cell_renderer, 'text', 0)
        top_box.pack_start(self._top_combo_box, True, True, 0)
        self.pack_start(top_box, False, False, 0)

        self._settings_box = Gtk.VBox()
        self._settings_box.show()
        self.pack_start(self._settings_box, False, False, 0)

        for name, box in option_sets:
            model.append((name, box))

    def __combo_changed_cb(self, combobox):
        giter = combobox.get_active_iter()
        new_box = combobox.get_model().get(giter, 1)[0]
        current_box = self._settings_box.get_children()
        if current_box:
            self._settings_box.remove(current_box[0])

        self._settings_box.add(new_box)
        new_box.show()


class GConfExclusiveOptionSetsBox(ExclusiveOptionSetsBox, GConfMixin):
    """
    Container for sets of GConf settings based on a top-level setting
    """

    def __init__(self, top_name, top_gconf_key, gsettings_dconf,
                 dconf_key, option_sets, size_group=None):
        """Initialize a GConfExclusiveOptionSetsBox instance

        Arguments:

        top_name -- text label used for the top-level selection
        top_gconf_key -- key for the GConf entry to use for the
                         top-level selection
        option_sets -- list of tuples containing text label, matching
                       GConf value as well as the GTK widget to display
                       for each of the option sets
        size_group -- optional gtk.SizeGroup to use for the top-level label
        """
        display_sets = [(name, widget) for name, value, widget in option_sets]
        self._top_mapping = dict([(name, value)
                                  for name, value, widget in option_sets])
        ExclusiveOptionSetsBox.__init__(self, top_name, display_sets,
                                        size_group=size_group)
        GConfMixin.__init__(self, top_gconf_key, gsettings_dconf,
                            dconf_key, self._top_combo_box)

    def get_value_for_gconf(self):
        giter = self._top_combo_box.get_active_iter()
        if giter is None:
            return None
        name = self._top_combo_box.get_model().get(giter, 0)[0]
        return self._top_mapping[name]

    def set_value_from_gconf(self, value):
        for idx, (name, widget_) in enumerate(self._top_combo_box.get_model()):
            if self._top_mapping[name] == value:
                self._top_combo_box.set_active(idx)
                return

        raise ValueError('Invalid value %r' % (value, ))


class OptionalSettingsBox(Gtk.VBox):
    """
    Container for settings (de)activated by a top-level setting

    Renders the top level setting as a CheckButton. The settings are only
    shown on screen if the top-level setting is enabled.
    """
    def __init__(self, top_name, options):
        """Initialize an OptionalSettingsBox instance
        Arguments:

        top_name -- text label used for the top-level selection
        options -- list of GTK widgets to display for each of the options
        """
        Gtk.VBox.__init__(self, spacing=style.DEFAULT_SPACING)
        self._top_check_button = Gtk.CheckButton()
        self._top_check_button.props.label = top_name
        self._top_check_button.connect('toggled', self.__button_changed_cb)
        self._top_check_button.show()
        self.pack_start(self._top_check_button, True, True, 0)
        self._settings_box = Gtk.VBox(spacing=style.DEFAULT_SPACING)
        for box in options:
            self._settings_box.pack_start(box, True, True, 0)

    def __button_changed_cb(self, check_button):
        if check_button.get_active():
            self._settings_box.show()
        else:
            self._settings_box.hide()


class GConfOptionalSettingsBox(OptionalSettingsBox, GConfMixin):
    """
    Container for GConf settings (de)activated by a top-level setting
    """
    def __init__(self, top_name, top_gconf_key, gsettings_dconf,
                 dconf_key, options):
        """Initialize a GConfExclusiveOptionSetsBox instance
        Arguments:

        top_name -- text label used for the top-level selection
        top_gconf_key -- key for the GConf entry to use for the
                         top-level selection
        options -- list of  GTK widgets to display for each of the options
        """
        OptionalSettingsBox.__init__(self, top_name, options)
        GConfMixin.__init__(self, top_gconf_key, gsettings_dconf,
                            dconf_key, self._top_check_button,
                            signal='toggled')

    def get_value_for_gconf(self):
        return self._top_check_button.get_active()

    def set_value_from_gconf(self, value):
        self._top_check_button.set_active(value)
        self.pack_start(self._settings_box, False, False, 0)


class Network(SectionView):
    def __init__(self, model, alerts):
        SectionView.__init__(self)

        self._model = model
        self.restart_alerts = alerts
        self._jabber_sid = 0
        self._jabber_valid = True
        self._radio_valid = True
        self._jabber_change_handler = None
        self._radio_change_handler = None
        self._network_configuration_reset_handler = None
        self._undo_objects = []

        client.add_dir('/system/http_proxy', GConf.ClientPreloadType.PRELOAD_ONELEVEL)
        client.add_dir('/system/proxy', GConf.ClientPreloadType.PRELOAD_ONELEVEL)

        self.set_border_width(style.DEFAULT_SPACING * 2)
        self.set_spacing(style.DEFAULT_SPACING)
        group = Gtk.SizeGroup(Gtk.SizeGroupMode.HORIZONTAL)

        self._radio_alert_box = Gtk.HBox(spacing=style.DEFAULT_SPACING)
        self._jabber_alert_box = Gtk.HBox(spacing=style.DEFAULT_SPACING)
        self._nm_connection_editor_alert_box = Gtk.HBox(spacing=style.DEFAULT_SPACING)

        scrolled = Gtk.ScrolledWindow()
        scrolled.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        self.add(scrolled)
        scrolled.show()

        workspace = Gtk.VBox()
        scrolled.add_with_viewport(workspace)
        workspace.show()

        separator_wireless = Gtk.HSeparator()
        workspace.pack_start(separator_wireless, False, True, 0)
        separator_wireless.show()

        label_wireless = Gtk.Label(label=_('Wireless'))
        label_wireless.set_alignment(0, 0)
        workspace.pack_start(label_wireless, False, True, 0)
        label_wireless.show()
        box_wireless = Gtk.VBox()
        box_wireless.set_border_width(style.DEFAULT_SPACING * 2)
        box_wireless.set_spacing(style.DEFAULT_SPACING)

        radio_info = Gtk.Label(label=_('Turn off the wireless radio to save battery'
                                 ' life'))
        radio_info.set_alignment(0, 0)
        radio_info.set_line_wrap(True)
        radio_info.show()
        box_wireless.pack_start(radio_info, False, True, 0)

        box_radio = Gtk.HBox(spacing=style.DEFAULT_SPACING)
        self._button = Gtk.CheckButton()
        self._button.set_alignment(0, 0)
        box_radio.pack_start(self._button, False, True, 0)
        self._button.show()

        label_radio = Gtk.Label(label=_('Radio'))
        label_radio.set_alignment(0, 0.5)
        box_radio.pack_start(label_radio, False, True, 0)
        label_radio.show()

        box_wireless.pack_start(box_radio, False, True, 0)
        box_radio.show()

        self._radio_alert = InlineAlert()
        self._radio_alert_box.pack_start(self._radio_alert, False, True, 0)
        box_radio.pack_end(self._radio_alert_box, False, True, 0)
        self._radio_alert_box.show()
        if 'radio' in self.restart_alerts:
            self._radio_alert.props.msg = self.restart_msg
            self._radio_alert.show()

        history_info = Gtk.Label(label=_('Discard network history if you have'
                                   ' trouble connecting to the network'))
        history_info.set_alignment(0, 0)
        history_info.set_line_wrap(True)
        history_info.show()
        box_wireless.pack_start(history_info, False, True, 0)

        box_clear_history = Gtk.HBox(spacing=style.DEFAULT_SPACING)
        self._clear_history_button = Gtk.Button()
        self._clear_history_button.set_label(_('Discard network history'))
        box_clear_history.pack_start(self._clear_history_button, False, True, 0)
        if not self._model.have_networks():
            self._clear_history_button.set_sensitive(False)
        self._clear_history_button.show()
        box_wireless.pack_start(box_clear_history, False, True, 0)
        box_clear_history.show()

        workspace.pack_start(box_wireless, False, True, 0)
        box_wireless.show()

        separator_mesh = Gtk.HSeparator()
        workspace.pack_start(separator_mesh, False, False, 0)
        separator_mesh.show()

        label_mesh = Gtk.Label(label=_('Collaboration'))
        label_mesh.set_alignment(0, 0)
        workspace.pack_start(label_mesh, False, True, 0)
        label_mesh.show()
        box_mesh = Gtk.VBox()
        box_mesh.set_border_width(style.DEFAULT_SPACING * 2)
        box_mesh.set_spacing(style.DEFAULT_SPACING)

        server_info = Gtk.Label(_("The server is the equivalent of what"
                                  " room you are in; people on the same server"
                                  " will be able to see each other, even when"
                                  " they aren't on the same network."))
        server_info.set_alignment(0, 0)
        server_info.set_line_wrap(True)
        box_mesh.pack_start(server_info, False, True, 0)
        server_info.show()

        box_server = Gtk.HBox(spacing=style.DEFAULT_SPACING)
        label_server = Gtk.Label(label=_('Server:'))
        label_server.set_alignment(1, 0.5)
        label_server.modify_fg(Gtk.StateType.NORMAL,
                               style.COLOR_SELECTION_GREY.get_gdk_color())
        box_server.pack_start(label_server, False, True, 0)
        group.add_widget(label_server)
        label_server.show()
        self._entry = Gtk.Entry()
        self._entry.set_alignment(0)
        self._entry.set_size_request(int(Gdk.Screen.width() / 3), -1)
        box_server.pack_start(self._entry, False, True, 0)
        self._entry.show()
        box_mesh.pack_start(box_server, False, True, 0)
        box_server.show()

        self._jabber_alert = InlineAlert()
        label_jabber_error = Gtk.Label()
        group.add_widget(label_jabber_error)
        self._jabber_alert_box.pack_start(label_jabber_error, False, True, 0)
        label_jabber_error.show()
        self._jabber_alert_box.pack_start(self._jabber_alert, False, True, 0)
        box_mesh.pack_end(self._jabber_alert_box, False, True, 0)
        self._jabber_alert_box.show()
        if 'jabber' in self.restart_alerts:
            self._jabber_alert.props.msg = self.restart_msg
            self._jabber_alert.show()

        workspace.pack_start(box_mesh, False, True, 0)
        box_mesh.show()

        proxy_separator = Gtk.HSeparator()
        workspace.pack_start(proxy_separator, False, False, 0)
        proxy_separator.show()

        self._add_proxy_section(workspace)

        if client.get_bool('/desktop/sugar/extensions/network/show_nm_connection_editor') is True:
            box_nm_connection_editor = self.add_nm_connection_editor_launcher(workspace)

        self.setup()

    def add_nm_connection_editor_launcher(self, workspace):
        separator_nm_connection_editor = Gtk.HSeparator()
        workspace.pack_start(separator_nm_connection_editor, False, True, 0)
        separator_nm_connection_editor.show()

        label_nm_connection_editor = Gtk.Label(_('Advanced Network Settings'))
        label_nm_connection_editor.set_alignment(0, 0)
        workspace.pack_start(label_nm_connection_editor, False, True, 0)
        label_nm_connection_editor.show()

        box_nm_connection_editor = Gtk.VBox()
        box_nm_connection_editor.set_border_width(style.DEFAULT_SPACING * 2)
        box_nm_connection_editor.set_spacing(style.DEFAULT_SPACING)

        info = Gtk.Label(_("For more specific network settings, use "
                              "the NetworkManager Connection Editor."))

        info.set_alignment(0, 0)
        info.set_line_wrap(True)
        box_nm_connection_editor.pack_start(info, False, True, 0)

        self._nm_connection_editor_alert = InlineAlert()
        self._nm_connection_editor_alert.props.msg = EXPLICIT_REBOOT_MESSAGE
        self._nm_connection_editor_alert_box.pack_start(self._nm_connection_editor_alert,
                False, True, 0)
        box_nm_connection_editor.pack_end(self._nm_connection_editor_alert_box,
                False, True, 0)
        self._nm_connection_editor_alert_box.show()
        self._nm_connection_editor_alert.show()

        launch_button = Gtk.Button()
        launch_button.set_alignment(0, 0)
        launch_button.set_label(_('Launch'))
        launch_button.connect('clicked', self.__launch_button_clicked_cb)
        box_launch_button = Gtk.HBox()
        box_launch_button.set_homogeneous(False)
        box_launch_button.pack_start(launch_button, False, True, 0)
        box_launch_button.show_all()

        box_nm_connection_editor.pack_start(box_launch_button, False, True, 0)
        workspace.pack_start(box_nm_connection_editor, False, True, 0)
        box_nm_connection_editor.show_all()


    def _add_proxy_section(self, workspace):
        proxy_title = Gtk.Label(_('Proxy'))
        proxy_title.set_alignment(0, 0)
        proxy_title.show()
        workspace.pack_start(proxy_title, False, False, 0)

        proxy_box = Gtk.VBox()
        proxy_box.set_border_width(style.DEFAULT_SPACING * 2)
        proxy_box.set_spacing(style.DEFAULT_SPACING)
        proxy_box.show()

        workspace.pack_start(proxy_box, True, True, 0)

        size_group = Gtk.SizeGroup(Gtk.SizeGroupMode.HORIZONTAL)

        automatic_proxy_box = Gtk.VBox()
        automatic_proxy_box.set_spacing(style.DEFAULT_SPACING)

        url_box = GConfStringSettingBox(_('Configuration URL:'),
                                        '/system/proxy/autoconfig_url',
                                        GSETTINGS_PROXY,
                                        'autoconfig-url',
                                        size_group)
        url_box.show()
        automatic_proxy_box.pack_start(url_box, True, True, 0)
        self._undo_objects.append(url_box)

        wpad_help_text = _('Web Proxy Autodiscovery (WPAD) is used when a'
                           ' Configuration URL is not provided. This is not'
                           ' recommended for untrusted public networks.')
        automatic_proxy_help = Gtk.Label(wpad_help_text)
        automatic_proxy_help.set_alignment(0, 0)
        automatic_proxy_help.set_line_wrap(True)
        automatic_proxy_help.show()
        automatic_proxy_box.pack_start(automatic_proxy_help, True, True, 0)

        manual_proxy_box = Gtk.VBox()
        manual_proxy_box.set_spacing(style.DEFAULT_SPACING)

        http_box = GConfHostPortSettingBox(_('HTTP Proxy:'),
                                           '/system/http_proxy/host',
                                           '/system/http_proxy/port',
                                            GSETTINGS_PROXY_HTTP,
                                            'host',
                                            'port',
                                           size_group)
        http_box.show()
        manual_proxy_box.pack_start(http_box, True, True, 0)
        self._undo_objects.append(http_box)

        user_name_box = GConfStringSettingBox(_('Username:'),
            '/system/http_proxy/authentication_user',
            GSETTINGS_PROXY_HTTP, 'authentication-user', size_group)
        user_name_box.show()
        self._undo_objects.append(user_name_box)

        password_box = GConfPasswordSettingBox(_('Password:'),
            '/system/http_proxy/authentication_password',
            GSETTINGS_PROXY_HTTP, 'authentication-password', size_group)
        password_box.show()
        self._undo_objects.append(password_box)

        auth_box = GConfOptionalSettingsBox(_('Use authentication'),
            '/system/http_proxy/use_authentication',
            GSETTINGS_PROXY_HTTP,
            'use-authentication',
            [user_name_box, password_box])
        auth_box.show()
        manual_proxy_box.pack_start(auth_box, True, True, 0)
        self._undo_objects.append(auth_box)

        https_box = GConfHostPortSettingBox(_('HTTPS Proxy:'),
                                            '/system/proxy/secure_host',
                                            '/system/proxy/secure_port',
                                            GSETTINGS_PROXY_HTTPS,
                                            'host',
                                            'port',
                                            size_group)
        https_box.show()
        manual_proxy_box.pack_start(https_box, True, True, 0)
        self._undo_objects.append(https_box)

        ftp_box = GConfHostPortSettingBox(_('FTP Proxy:'),
                                          '/system/proxy/ftp_host',
                                          '/system/proxy/ftp_port',
                                          GSETTINGS_PROXY_FTP,
                                          'host',
                                          'port',
                                          size_group)
        ftp_box.show()
        manual_proxy_box.pack_start(ftp_box, True, True, 0)
        self._undo_objects.append(ftp_box)

        socks_box = GConfHostPortSettingBox(_('SOCKS Proxy:'),
                                            '/system/proxy/socks_host',
                                            '/system/proxy/socks_port',
                                            GSETTINGS_PROXY_SOCKS,
                                            'host',
                                            'port',
                                            size_group)
        socks_box.show()
        manual_proxy_box.pack_start(socks_box, True, True, 0)
        self._undo_objects.append(socks_box)

        option_sets = [('None', 'none', Gtk.VBox()),
                       ('Automatic', 'auto', automatic_proxy_box),
                       ('Manual', 'manual', manual_proxy_box)]
        option_sets_box = GConfExclusiveOptionSetsBox(_('Method:'),
                                                      '/system/proxy/mode',
                                                      GSETTINGS_PROXY,
                                                      'mode',
                                                      option_sets, size_group)
        option_sets_box.show()
        proxy_box.pack_start(option_sets_box, False, False, 0)
        self._undo_objects.append(option_sets_box)

        no_proxy_box = GConfHostListSettingBox(_('Ignored Hosts'),
            '/system/http_proxy/ignore_hosts', GSETTINGS_PROXY,
            'ignore-hosts', size_group)
        no_proxy_box.show()
        proxy_box.pack_start(no_proxy_box, False, False, 0)
        self._undo_objects.append(no_proxy_box)

    def setup(self):
        self._entry.set_text(self._model.get_jabber())
        try:
            radio_state = self._model.get_radio()
        except self._model.ReadError, detail:
            self._radio_alert.props.msg = detail
            self._radio_alert.show()
        else:
            self._button.set_active(radio_state)

        self._jabber_valid = True
        self._radio_valid = True
        self.needs_restart = False
        self._radio_change_handler = self._button.connect( \
                'toggled', self.__radio_toggled_cb)
        self._jabber_change_handler = self._entry.connect( \
                'changed', self.__jabber_changed_cb)
        self._network_configuration_reset_handler =  \
                self._clear_history_button.connect( \
                        'clicked', self.__network_configuration_reset_cb)

    def undo(self):
        self._button.disconnect(self._radio_change_handler)
        self._entry.disconnect(self._jabber_change_handler)
        self._model.undo()
        self._jabber_alert.hide()
        self._radio_alert.hide()
        for setting in self._undo_objects:
            setting.undo()

    # pylint: disable=E0202
    @property
    def needs_restart(self):
        # Some parts of Sugar as well as many non-Gnome applications
        # use environment variables rather than gconf for proxy
        # settings, so we need to restart for the changes to take
        # _full_ effect.
        for setting in self._undo_objects:
            if setting.changed:
                return True

        return False

    # pylint: disable=E0102,E1101
    @needs_restart.setter
    def needs_restart(self, value):
        # needs_restart is a property (i.e. gets calculated) in this Control
        # Panel, but SectionView.__init__() wants to initialise it to False,
        # so we need to provide a (fake) setter.
        pass

    def _validate(self):
        if self._jabber_valid and self._radio_valid:
            self.props.is_valid = True
        else:
            self.props.is_valid = False

    def __radio_toggled_cb(self, widget, data=None):
        radio_state = widget.get_active()
        try:
            self._model.set_radio(radio_state)
        except self._model.ReadError, detail:
            self._radio_alert.props.msg = detail
            self._radio_valid = False
        else:
            self._radio_valid = True
            if self._model.have_networks():
                self._clear_history_button.set_sensitive(True)

        self._validate()
        return False

    def __jabber_changed_cb(self, widget, data=None):
        if self._jabber_sid:
            GObject.source_remove(self._jabber_sid)
        self._jabber_sid = GObject.timeout_add(_APPLY_TIMEOUT,
                                               self.__jabber_timeout_cb,
                                               widget)

    def __jabber_timeout_cb(self, widget):
        self._jabber_sid = 0
        if widget.get_text() == self._model.get_jabber:
            return
        try:
            self._model.set_jabber(widget.get_text())
        except self._model.ReadError, detail:
            self._jabber_alert.props.msg = detail
            self._jabber_valid = False
            self._jabber_alert.show()
            self.restart_alerts.append('jabber')
        else:
            self._jabber_valid = True
            self._jabber_alert.hide()

        for setting in self._undo_objects:
            setting.undo()

        self._validate()
        return False

    def __network_configuration_reset_cb(self, widget):
        # FIXME: takes effect immediately, not after CP is closed with
        # confirmation button
        self._model.clear_networks()
        if not self._model.have_networks():
            self._clear_history_button.set_sensitive(False)

    def __launch_button_clicked_cb(self, launch_button):
        self._model.launch_nm_connection_editor()


def _gconf_value_to_python(gconf_value):
    if gconf_value.type == GConf.ValueType.STRING:
        return gconf_value.get_string()
    elif gconf_value.type == GConf.ValueType.INT:
        return gconf_value.get_int()
    elif gconf_value.type == GConf.ValueType.FLOAT:
        return gconf_value.get_float()
    elif gconf_value.type == GConf.ValueType.BOOL:
        return gconf_value.get_bool()
    elif gconf_value.type == GConf.ValueType.LIST:
        return [_gconf_value_to_python(entry)
                for entry in gconf_value.get_list()]
    else:
        raise TypeError("Don't know how to handle GConf value"
                        " type %r" % (gconf_value.type, ))
