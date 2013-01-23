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
from gi.repository import GObject
from gettext import gettext as _

from sugar3.graphics import style
from sugar3.graphics import iconentry
from sugar3.graphics.icon import Icon

from jarabe.controlpanel.sectionview import SectionView
from jarabe.controlpanel.inlinealert import InlineAlert


class AddRemoveWidget(Gtk.HBox):

    def __init__(self, label, add_button_clicked_cb,
                 remove_button_clicked_cb, index):
        Gtk.Box.__init__(self)
        self.set_homogeneous(False)
        self.set_spacing(10)

        self._index = index
        self._add_button_added = False
        self._remove_button_added = False

        self._entry_box = Gtk.Entry()
        self._entry_box.set_text(label)
        self._entry_box.set_width_chars(40)
        self.pack_start(self._entry_box, False, False, 0)
        self._entry_box.show()

        add_icon = Icon(icon_name='list-add')
        self._add_button = Gtk.Button()
        self._add_button.set_image(add_icon)
        self._add_button.connect('clicked',
                                 add_button_clicked_cb,
                                 self)

        remove_icon = Icon(icon_name='list-remove')
        self._remove_button = Gtk.Button()
        self._remove_button.set_image(remove_icon)
        self._remove_button.connect('clicked',
                                    remove_button_clicked_cb,
                                    self)
        self.__add_add_button()
        self.__add_remove_button()

    def _get_index(self):
        return self._index

    def _set_index(self, value):
        self._index = value

    def _get_entry(self):
        return self._entry_box.get_text()

    def __add_add_button(self):
        self.pack_start(self._add_button, False, False, 0)
        self._add_button.show()
        self._add_button_added = True

    def _remove_remove_button_if_not_already(self):
        if self._remove_button_added:
            self.__remove_remove_button()

    def __remove_remove_button(self):
        self.remove(self._remove_button)
        self._remove_button_added = False

    def _add_remove_button_if_not_already(self):
        if not self._remove_button_added:
            self.__add_remove_button()

    def __add_remove_button(self):
        self.pack_start(self._remove_button, False, False, 0)
        self._remove_button.show()
        self._remove_button_added = True


class MultiWidget(Gtk.VBox):

    def __init__(self):
        Gtk.VBox.__init__(self)

    def _add_widget(self, label):
        new_widget = AddRemoveWidget(label,
                                     self.__add_button_clicked_cb,
                                     self.__remove_button_clicked_cb,
                                     len(self.get_children()))
        self.add(new_widget)
        new_widget.show()
        self.show()
        self._update_remove_button_statuses()

    def __add_button_clicked_cb(self, add_button,
                                      add_button_container):
        self._add_widget('')
        self._update_remove_button_statuses()

    def __remove_button_clicked_cb(self, remove_button,
                                   remove_button_container):
        for child in self.get_children():
            if child._get_index() > remove_button_container._get_index():
                child._set_index(child._get_index() - 1)

        self.remove(remove_button_container)
        self._update_remove_button_statuses()

    def _update_remove_button_statuses(self):
        children = self.get_children()

        # Now, if there is only one entry, remove-button
        # should not be shown.
        if len(children) == 1:
            children[0]._remove_remove_button_if_not_already()

        # Alternatively, if there are more than 1 entries,
        # remove-button should be shown for all.
        if len(children) > 1:
            for child in children:
                child._add_remove_button_if_not_already()


    def _get_entries(self):
        entries = []
        for child in self.get_children():
            entries.append(child._get_entry())

        return entries


class TimeZone(SectionView):
    def __init__(self, model, alerts):
        SectionView.__init__(self)

        self._model = model
        self.restart_alerts = alerts
        self._zone_sid = 0
        self._cursor_change_handler = None

        self.set_border_width(style.DEFAULT_SPACING * 2)
        self.set_spacing(style.DEFAULT_SPACING)

        self.connect('realize', self.__realize_cb)

        self._entry = iconentry.IconEntry()
        self._entry.set_icon_from_name(iconentry.ICON_ENTRY_PRIMARY,
                                 'system-search')
        self._entry.add_clear_button()
        self.pack_start(self._entry, False, False, 0)
        self._entry.show()

        self._scrolled_window = Gtk.ScrolledWindow()
        self._scrolled_window.set_policy(Gtk.PolicyType.NEVER,
                                         Gtk.PolicyType.AUTOMATIC)
        self._scrolled_window.set_shadow_type(Gtk.ShadowType.IN)

        self._store = Gtk.ListStore(GObject.TYPE_STRING)
        zones = model.read_all_timezones()
        for zone in zones:
            self._store.append([zone])

        self._treeview = Gtk.TreeView(self._store)
        self._treeview.set_search_entry(self._entry)
        self._treeview.set_search_equal_func(self._search, None)
        self._treeview.set_search_column(0)
        self._scrolled_window.add(self._treeview)
        self._treeview.show()

        self._timezone_column = Gtk.TreeViewColumn(_('Timezone'))
        self._cell = Gtk.CellRendererText()
        self._timezone_column.pack_start(self._cell, True)
        self._timezone_column.add_attribute(self._cell, 'text', 0)
        self._timezone_column.set_sort_column_id(0)
        self._treeview.append_column(self._timezone_column)

        self._container = Gtk.VBox()
        self._container.set_homogeneous(False)
        self._container.pack_start(self._scrolled_window, True, True, 0)
        self._container.set_spacing(style.DEFAULT_SPACING)
        self._container.show_all()
        self.pack_start(self._container, True, True, 0)

        self._zone_alert_box = Gtk.HBox(spacing=style.DEFAULT_SPACING)
        self._zone_alert = InlineAlert()
        self._zone_alert_box.pack_start(self._zone_alert, True, True, 0)
        if 'zone' in self.restart_alerts:
            self._zone_alert.props.msg = self.restart_msg
            self._zone_alert.show()

            # Not showing this, as this hides the selected timezone.
            # Instead, the alert will anyways be shown when user clicks
            # on "Ok".
            #self._zone_alert.show()
        self._zone_alert_box.show()

        self._ntp_ui_setup = False

        self.setup()

    def setup(self):
        zone = self._model.get_timezone()
        for row in self._store:
            if zone == row[0]:
                self._treeview.set_cursor(row.path, self._timezone_column,
                                          False)
                self._treeview.scroll_to_cell(row.path, self._timezone_column,
                                              True, 0.5, 0.5)
                break

        self.needs_restart = False
        self._cursor_change_handler = self._treeview.connect( \
                'cursor-changed', self.__zone_changed_cd)
        if self._model.is_ntp_servers_config_feature_available():
            self.setup_ui_for_ntp_server_config()

    def setup_ui_for_ntp_server_config(self):
        if self._ntp_ui_setup:
            return
        self._ntp_ui_setup = True

        self._ntp_scrolled_window = Gtk.ScrolledWindow()
        self._ntp_scrolled_window.set_policy(Gtk.PolicyType.NEVER,
                                             Gtk.PolicyType.AUTOMATIC)
        box_ntp_servers_config = Gtk.VBox()
        box_ntp_servers_config.set_spacing(style.DEFAULT_SPACING)

        separator_ntp_servers_config= Gtk.HSeparator()
        self._container.pack_start(separator_ntp_servers_config,
                                   False, False, 0)
        separator_ntp_servers_config.show()

        label_ntp_servers_config = Gtk.Label(_('NTP Servers Configuration'))
        label_ntp_servers_config.set_alignment(0, 0)
        self._container.pack_start(label_ntp_servers_config,
                                   False, False, 0)
        label_ntp_servers_config.show()

        self._widget_table = MultiWidget()
        box_ntp_servers_config.pack_start(self._widget_table, False, False, 0)
        box_ntp_servers_config.show_all()

        self._ntp_scrolled_window.add_with_viewport(box_ntp_servers_config)
        self._container.pack_start(self._ntp_scrolled_window, True, True, 0)
        self._ntp_scrolled_window.show_all()

        ntp_servers = self._model.get_ntp_servers()
        if len(ntp_servers) == 0:
            self._widget_table._add_widget('')
        else:
            for server in ntp_servers:
                self._widget_table._add_widget(server)

    def undo(self):
        self._treeview.disconnect(self._cursor_change_handler)
        self._model.undo()
        self._zone_alert.hide()

    def __realize_cb(self, widget):
        self._entry.grab_focus()

    def _search(self, model, column, key, iterator, data=None):
        value = model.get_value(iterator, column)
        if key.lower() in value.lower():
            return False
        return True

    def __zone_changed_cd(self, treeview, data=None):
        list_, row = treeview.get_selection().get_selected()
        if not row:
            return False
        if self._model.get_timezone() == self._store.get_value(row, 0):
            return False

        if self._zone_sid:
            GObject.source_remove(self._zone_sid)
        self._zone_sid = GObject.timeout_add(self._APPLY_TIMEOUT,
                                             self.__zone_timeout_cb, row)
        return True

    def __zone_timeout_cb(self, row):
        self._zone_sid = 0
        self._model.set_timezone(self._store.get_value(row, 0))
        self.restart_alerts.append('zone')
        self.needs_restart = True
        self._zone_alert.props.msg = self.restart_msg
        return False

    def perform_accept_actions(self):
        self._model.set_ntp_servers(self._widget_table._get_entries())
