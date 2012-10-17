# Copyright (C) 2007, One Laptop Per Child
# Copyright (C) 2009, Walter Bender
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

from gettext import gettext as _
from gettext import ngettext
import logging
from datetime import datetime, timedelta
import os
from gi.repository import GConf
import time

from gi.repository import GObject
from gi.repository import Gio
import glib
from gi.repository import Gtk
from gi.repository import Gdk

from sugar3.graphics.palette import Palette
from sugar3.graphics.toolbarbox import ToolbarBox
from sugar3.graphics.toolcombobox import ToolComboBox
from sugar3.graphics.toolbutton import ToolButton
from sugar3.graphics.toggletoolbutton import ToggleToolButton
from sugar3.graphics.combobox import ComboBox
from sugar3.graphics.menuitem import MenuItem
from sugar3.graphics.icon import Icon
from sugar3.graphics.xocolor import XoColor
from sugar3.graphics.alert import Alert
from sugar3.graphics import iconentry
from sugar3 import mime

from jarabe.model import bundleregistry
from jarabe.journal import misc
from jarabe.journal import model
from jarabe.journal.palettes import ClipboardMenu
from jarabe.journal.palettes import VolumeMenu
from jarabe.journal import journalwindow, palettes

COPY_MENU_HELPER = palettes.get_copy_menu_helper()

_AUTOSEARCH_TIMEOUT = 1000

_ACTION_ANYTIME = 0
_ACTION_TODAY = 1
_ACTION_SINCE_YESTERDAY = 2
_ACTION_PAST_WEEK = 3
_ACTION_PAST_MONTH = 4
_ACTION_PAST_YEAR = 5

_ACTION_ANYTHING = 0

_ACTION_EVERYBODY = 0
_ACTION_MY_FRIENDS = 1
_ACTION_MY_CLASS = 2


class MainToolbox(ToolbarBox):

    __gsignals__ = {
        'query-changed': (GObject.SignalFlags.RUN_FIRST, None,
                          ([object])),
        }

    def __init__(self):
        ToolbarBox.__init__(self)

        self._info_widget = MultiSelectEntriesInfoWidget()
        self.add(self._info_widget)
        self._info_widget.hide()

        self._mount_point = None

        self.search_entry = iconentry.IconEntry()
        self.search_entry.set_icon_from_name(iconentry.ICON_ENTRY_PRIMARY,
                                             'system-search')
        text = _('Search in %s') % _('Journal')
        self.search_entry.set_placeholder_text(text)
        self.search_entry.connect('activate', self._search_entry_activated_cb)
        self.search_entry.connect('changed', self._search_entry_changed_cb)
        self.search_entry.add_clear_button()
        self._autosearch_timer = None
        self._add_widget(self.search_entry, expand=True)

        self._favorite_button = ToggleToolButton('emblem-favorite')
        self._favorite_button.connect('toggled',
                                      self.__favorite_button_toggled_cb)
        self.toolbar.insert(self._favorite_button, -1)
        self._favorite_button.show()

        self._what_search_combo = ComboBox()
        self._what_combo_changed_sid = self._what_search_combo.connect(
                'changed', self._combo_changed_cb)
        tool_item = ToolComboBox(self._what_search_combo)
        self.toolbar.insert(tool_item, -1)
        tool_item.show()

        self._when_search_combo = self._get_when_search_combo()
        tool_item = ToolComboBox(self._when_search_combo)
        self.toolbar.insert(tool_item, -1)
        tool_item.show()

        self._sorting_button = SortingButton()
        self._sorting_button.connect('clicked',
                                     self.__sorting_button_clicked_cb)
        self.toolbar.insert(self._sorting_button, -1)
        self._sorting_button.connect('sort-property-changed',
                                     self.__sort_changed_cb)
        self._sorting_button.show()

        # TODO: enable it when the DS supports saving the buddies.
        #self._with_search_combo = self._get_with_search_combo()
        #tool_item = ToolComboBox(self._with_search_combo)
        #self.insert(tool_item, -1)
        #tool_item.show()

        self._query = self._build_query()

        self.refresh_filters()

    def update_progress(self, fraction):
        self._info_widget.update_progress(fraction)

    def hide_info_widget(self):
        self._info_widget.hide()

    def _get_when_search_combo(self):
        when_search = ComboBox()
        when_search.append_item(_ACTION_ANYTIME, _('Anytime'))
        when_search.append_separator()
        when_search.append_item(_ACTION_TODAY, _('Today'))
        when_search.append_item(_ACTION_SINCE_YESTERDAY,
                                      _('Since yesterday'))
        # TRANS: Filter entries modified during the last 7 days.
        when_search.append_item(_ACTION_PAST_WEEK, _('Past week'))
        # TRANS: Filter entries modified during the last 30 days.
        when_search.append_item(_ACTION_PAST_MONTH, _('Past month'))
        # TRANS: Filter entries modified during the last 356 days.
        when_search.append_item(_ACTION_PAST_YEAR, _('Past year'))
        when_search.set_active(0)
        when_search.connect('changed', self._combo_changed_cb)
        return when_search

    def _get_with_search_combo(self):
        with_search = ComboBox()
        with_search.append_item(_ACTION_EVERYBODY, _('Anyone'))
        with_search.append_separator()
        with_search.append_item(_ACTION_MY_FRIENDS, _('My friends'))
        with_search.append_item(_ACTION_MY_CLASS, _('My class'))
        with_search.append_separator()

        # TODO: Ask the model for buddies.
        with_search.append_item(3, 'Dan', 'theme:xo')

        with_search.set_active(0)
        with_search.connect('changed', self._combo_changed_cb)
        return with_search

    def _add_widget(self, widget, expand=False):
        tool_item = Gtk.ToolItem()
        tool_item.set_expand(expand)

        tool_item.add(widget)
        widget.show()

        self.toolbar.insert(tool_item, -1)
        tool_item.show()

    def _build_query(self):
        query = {}

        if self._mount_point:
            query['mountpoints'] = [self._mount_point]

        if self._favorite_button.props.active:
            query['keep'] = 1

        if self._what_search_combo.props.value:
            value = self._what_search_combo.props.value
            generic_type = mime.get_generic_type(value)
            if generic_type:
                mime_types = generic_type.mime_types
                query['mime_type'] = mime_types
            else:
                query['activity'] = self._what_search_combo.props.value

        if self._when_search_combo.props.value:
            date_from, date_to = self._get_date_range()
            query['timestamp'] = {'start': date_from, 'end': date_to}

        if self.search_entry.props.text:
            text = self.search_entry.props.text.strip()
            if text:
                query['query'] = text

        property_, order = self._sorting_button.get_current_sort()

        if order == Gtk.SortType.ASCENDING:
            sign = '+'
        else:
            sign = '-'
        query['order_by'] = [sign + property_]

        return query

    def _get_date_range(self):
        today_start = datetime.today().replace(hour=0, minute=0, second=0)
        right_now = datetime.today()
        if self._when_search_combo.props.value == _ACTION_TODAY:
            date_range = (today_start, right_now)
        elif self._when_search_combo.props.value == _ACTION_SINCE_YESTERDAY:
            date_range = (today_start - timedelta(1), right_now)
        elif self._when_search_combo.props.value == _ACTION_PAST_WEEK:
            date_range = (today_start - timedelta(7), right_now)
        elif self._when_search_combo.props.value == _ACTION_PAST_MONTH:
            date_range = (today_start - timedelta(30), right_now)
        elif self._when_search_combo.props.value == _ACTION_PAST_YEAR:
            date_range = (today_start - timedelta(356), right_now)

        return (time.mktime(date_range[0].timetuple()),
                time.mktime(date_range[1].timetuple()))

    def _combo_changed_cb(self, combo):
        self._update_if_needed()

    def __sort_changed_cb(self, button):
        self._update_if_needed()

    def __sorting_button_clicked_cb(self, button):
        self._sorting_button.palette.popup(immediate=True, state=1)

    def _update_if_needed(self):
        new_query = self._build_query()
        if self._query != new_query:
            self._query = new_query
            self.emit('query-changed', self._query)

    def _search_entry_activated_cb(self, search_entry):
        if self._autosearch_timer:
            GObject.source_remove(self._autosearch_timer)
        new_query = self._build_query()
        if self._query != new_query:
            self._query = new_query
            self.emit('query-changed', self._query)

    def _search_entry_changed_cb(self, search_entry):
        if not search_entry.props.text:
            search_entry.activate()
            return

        if self._autosearch_timer:
            GObject.source_remove(self._autosearch_timer)
        self._autosearch_timer = GObject.timeout_add(_AUTOSEARCH_TIMEOUT,
                                                     self._autosearch_timer_cb)

    def _autosearch_timer_cb(self):
        logging.debug('_autosearch_timer_cb')
        self._autosearch_timer = None
        self.search_entry.activate()
        return False

    def set_mount_point(self, mount_point):
        self._mount_point = mount_point
        new_query = self._build_query()
        if self._query != new_query:
            self._query = new_query
            self.emit('query-changed', self._query)

    def set_what_filter(self, what_filter):
        combo_model = self._what_search_combo.get_model()
        what_filter_index = -1
        for i in range(0, len(combo_model) - 1):
            if combo_model[i][0] == what_filter:
                what_filter_index = i
                break

        if what_filter_index == -1:
            logging.warning('what_filter %r not known', what_filter)
        else:
            self._what_search_combo.set_active(what_filter_index)

    def refresh_filters(self):
        current_value = self._what_search_combo.props.value
        current_value_index = 0

        self._what_search_combo.handler_block(self._what_combo_changed_sid)
        try:
            self._what_search_combo.remove_all()
            # TRANS: Item in a combo box that filters by entry type.
            self._what_search_combo.append_item(_ACTION_ANYTHING,
                                                _('Anything'))

            registry = bundleregistry.get_registry()
            appended_separator = False

            types = mime.get_all_generic_types()
            for generic_type in types:
                if not appended_separator:
                    self._what_search_combo.append_separator()
                    appended_separator = True
                self._what_search_combo.append_item(
                    generic_type.type_id, generic_type.name, generic_type.icon)
                if generic_type.type_id == current_value:
                    current_value_index = \
                            len(self._what_search_combo.get_model()) - 1

                self._what_search_combo.set_active(current_value_index)

            self._what_search_combo.append_separator()

            for service_name in model.get_unique_values('activity'):
                activity_info = registry.get_bundle(service_name)
                if activity_info is None:
                    continue

                if service_name == current_value:
                    combo_model = self._what_search_combo.get_model()
                    current_value_index = len(combo_model)

                # try activity-provided icon
                if os.path.exists(activity_info.get_icon()):
                    try:
                        self._what_search_combo.append_item(service_name,
                                activity_info.get_name(),
                                file_name=activity_info.get_icon())
                    except GObject.GError, exception:
                        logging.warning('Falling back to default icon for'
                                        ' "what" filter because %r (%r) has an'
                                        ' invalid icon: %s',
                                        activity_info.get_name(),
                                        str(service_name), exception)
                    else:
                        continue

                # fall back to generic icon
                self._what_search_combo.append_item(service_name,
                        activity_info.get_name(),
                        icon_name='application-octet-stream')

        finally:
            self._what_search_combo.handler_unblock(
                    self._what_combo_changed_sid)

    def __favorite_button_toggled_cb(self, favorite_button):
        self._update_if_needed()

    def clear_query(self):
        self.search_entry.props.text = ''
        self._what_search_combo.set_active(0)
        self._when_search_combo.set_active(0)
        self._favorite_button.props.active = False


class DetailToolbox(ToolbarBox):
    __gsignals__ = {
        'volume-error': (GObject.SignalFlags.RUN_FIRST, None,
                         ([str, str])),
        }

    def __init__(self):
        ToolbarBox.__init__(self)

        self._metadata = None
        self._temp_file_path = None

        self._resume = ToolButton('activity-start')
        self._resume.connect('clicked', self._resume_clicked_cb)
        self.toolbar.insert(self._resume, -1)
        self._resume.show()

        client = GConf.Client.get_default()
        color = XoColor(client.get_string('/desktop/sugar/user/color'))
        self._copy = ToolButton()
        icon = Icon(icon_name='edit-copy', xo_color=color)
        self._copy.set_icon_widget(icon)
        icon.show()
        self._copy.set_tooltip(_('Copy to'))
        self._copy.connect('clicked', self._copy_clicked_cb)
        self.toolbar.insert(self._copy, -1)
        self._copy.show()

        self._duplicate = ToolButton()
        icon = Icon(icon_name='edit-duplicate', xo_color=color)
        self._duplicate.set_icon_widget(icon)
        self._duplicate.set_tooltip(_('Duplicate'))
        self._duplicate.connect('clicked', self._duplicate_clicked_cb)
        self.toolbar.insert(self._duplicate, -1)

        separator = Gtk.SeparatorToolItem()
        self.toolbar.insert(separator, -1)
        separator.show()

        erase_button = ToolButton('list-remove')
        self._erase_button = erase_button
        erase_button.set_tooltip(_('Erase'))
        erase_button.connect('clicked', self._erase_button_clicked_cb)
        self.toolbar.insert(erase_button, -1)
        erase_button.show()

    def set_mount_point(self, mount_point):
        self._mount_point = mount_point
        self.set_sensitivity_of_icons()

    def get_mount_point(self):
        return self._mount_point

    def set_sensitivity_of_icons(self):
        mount_point = self.get_mount_point()
        if model.is_mount_point_for_locally_mounted_remote_share(mount_point):
            sensitivity = False
        else:
            sensitivity = True

        self._resume.set_sensitive(sensitivity)
        self._duplicate.set_sensitive(sensitivity)
        self._erase_button.set_sensitive(sensitivity)

    def set_metadata(self, metadata):
        self._metadata = metadata
        self._refresh_copy_palette()
        self._refresh_duplicate_palette()
        self._refresh_resume_palette()

    def _resume_clicked_cb(self, button):
        misc.resume(self._metadata)

    def _copy_clicked_cb(self, button):
        button.palette.popup(immediate=True, state=Palette.SECONDARY)

    def _duplicate_clicked_cb(self, button):
        file_path = model.get_file(self._metadata['uid'])
        try:
            model.copy(self._metadata, '/')
        except IOError, e:
            logging.exception('Error while copying the entry.')
            self.emit('volume-error',
                      _('Error while copying the entry. %s') % (e.strerror, ),
                      _('Error'))

    def _erase_button_clicked_cb(self, button):
        alert = Alert()
        erase_string = _('Erase')
        alert.props.title = erase_string
        alert.props.msg = _('Do you want to permanently erase \"%s\"?') \
            % self._metadata['title']
        icon = Icon(icon_name='dialog-cancel')
        alert.add_button(Gtk.ResponseType.CANCEL, _('Cancel'), icon)
        icon.show()
        ok_icon = Icon(icon_name='dialog-ok')
        alert.add_button(Gtk.ResponseType.OK, erase_string, ok_icon)
        ok_icon.show()
        alert.connect('response', self.__erase_alert_response_cb)
        journalwindow.get_journal_window().add_alert(alert)
        alert.show()

    def __erase_alert_response_cb(self, alert, response_id):
        journalwindow.get_journal_window().remove_alert(alert)
        if response_id is Gtk.ResponseType.OK:
            registry = bundleregistry.get_registry()
            bundle = misc.get_bundle(self._metadata)
            if bundle is not None and registry.is_installed(bundle):
                registry.uninstall(bundle)
            model.delete(self._metadata['uid'])

    def _resume_menu_item_activate_cb(self, menu_item, service_name):
        misc.resume(self._metadata, service_name)

    def _refresh_copy_palette(self):
        palette = self._copy.get_palette()

        for menu_item in palette.menu.get_children():
            palette.menu.remove(menu_item)
            menu_item.destroy()

        COPY_MENU_HELPER.insert_copy_to_menu_items(palette.menu,
                                                   [self._metadata],
                                                   show_editing_alert=False,
                                                   show_progress_info_alert=False,
                                                   batch_mode=False)

    def _refresh_duplicate_palette(self):
        color = misc.get_icon_color(self._metadata)
        self._copy.get_icon_widget().props.xo_color = color
        if self._metadata['mountpoint'] == '/':
            self._duplicate.show()
            icon = self._duplicate.get_icon_widget()
            icon.props.xo_color = color
            icon.show()
        else:
            self._duplicate.hide()

    def __volume_error_cb(self, menu_item, message, severity):
        self.emit('volume-error', message, severity)

    def _refresh_resume_palette(self):
        if self._metadata.get('activity_id', ''):
            # TRANS: Action label for resuming an activity.
            self._resume.set_tooltip(_('Resume'))
        else:
            # TRANS: Action label for starting an entry.
            self._resume.set_tooltip(_('Start'))

        palette = self._resume.get_palette()

        for menu_item in palette.menu.get_children():
            palette.menu.remove(menu_item)
            menu_item.destroy()

        for activity_info in misc.get_activities(self._metadata):
            menu_item = MenuItem(activity_info.get_name())
            menu_item.set_image(Icon(file=activity_info.get_icon(),
                                        icon_size=Gtk.IconSize.MENU))
            menu_item.connect('activate', self._resume_menu_item_activate_cb,
                                activity_info.get_bundle_id())
            palette.menu.append(menu_item)
            menu_item.show()


class EditToolbox(ToolbarBox):
    def __init__(self):
        ToolbarBox.__init__(self)

        self.toolbar.add(SelectNoneButton())
        self.toolbar.add(SelectAllButton())

        self.toolbar.add(Gtk.SeparatorToolItem())

        self.toolbar.add(BatchEraseButton())
        self.toolbar.add(BatchCopyButton())

        self.toolbar.add(Gtk.SeparatorToolItem())

        self._multi_select_info_widget = MultiSelectEntriesInfoWidget()
        self.toolbar.add(self._multi_select_info_widget)

        self.show_all()
        self.toolbar.show_all()

    def process_new_selected_entry_in_multi_select(self):
        GObject.idle_add(self._multi_select_info_widget.update_text,
                         '', '', True, True)

    def process_new_deselected_entry_in_multi_select(self):
        GObject.idle_add(self._multi_select_info_widget.update_text,
                         '', '', False, True)

    def display_running_status_in_multi_select(self, primary_info,
                                               secondary_info):
        GObject.idle_add(self._multi_select_info_widget.update_text,
                         primary_info, secondary_info,
                         None, None)

    def display_already_selected_entries_status(self):
        GObject.idle_add(self._multi_select_info_widget.update_text,
                         '', '', True, False)

    def set_total_number_of_entries(self, total):
        self._multi_select_info_widget.set_total_number_of_entries(total)

    def get_current_entry_number(self):
        return self._multi_select_info_widget.get_current_entry_number()

    def update_progress(self, fraction):
        self._multi_select_info_widget.update_progress(fraction)


class SelectNoneButton(ToolButton):
    def __init__(self):
        ToolButton.__init__(self, 'select-none')
        self.props.tooltip = _('Deselect all')

        self.connect('clicked', self.__do_deselect_all)

    def __do_deselect_all(self, widget_clicked):
        from jarabe.journal.journalactivity import get_journal
        journal = get_journal()

        journal.get_list_view()._selected_entries = 0
        journal.switch_to_editing_mode(False)
        journal.get_list_view().inhibit_refresh(False)
        journal.get_list_view().refresh()


class SelectAllButton(ToolButton, palettes.ActionItem):
    def __init__(self):
        ToolButton.__init__(self, 'select-all')
        palettes.ActionItem.__init__(self, '', [],
                                     show_editing_alert=False,
                                     show_progress_info_alert=False,
                                     batch_mode=True,
                                     auto_deselect_source_entries=True,
                                     need_to_popup_options=False,
                                     operate_on_deselected_entries=True,
                                     show_not_completed_ops_info=False)
        self.props.tooltip = _('Select all')

    def _get_actionable_signal(self):
        return 'clicked'

    def _get_editing_alert_operation(self):
        return _('Select all')

    def _get_info_alert_title(self):
        return _('Selecting')

    def _get_post_selection_alert_message_entries_len(self):
        return self._model_len

    def _get_post_selection_alert_message(self, entries_len):
        from jarabe.journal.journalactivity import get_journal
        journal = get_journal()

        return ngettext('You have selected %d entry.',
                        'You have selected %d entries.',
                         entries_len) % (entries_len,)

    def _operate(self, metadata):
        # Nothing specific needs to be done.
        # The checkboxes are unchecked as part of the toggling of any
        # operation that operates on selected entries.

        # This is sync-operation. Thus, call the callback.
        self._post_operate_per_metadata_per_action(metadata)


class BatchEraseButton(ToolButton, palettes.ActionItem):
    def __init__(self):
        ToolButton.__init__(self, 'edit-delete')
        palettes.ActionItem.__init__(self, '', [],
                                     show_editing_alert=True,
                                     show_progress_info_alert=True,
                                     batch_mode=True,
                                     auto_deselect_source_entries=True,
                                     need_to_popup_options=False,
                                     operate_on_deselected_entries=False,
                                     show_not_completed_ops_info=True)
        self.props.tooltip = _('Erase')

        # De-sensitize Batch-Erase button, for locally-mounted-remote-shares.
        from jarabe.journal.journalactivity import get_mount_point
        current_mount_point = get_mount_point()

        if model.is_mount_point_for_locally_mounted_remote_share(current_mount_point):
            self.set_sensitive(False)

    def _get_actionable_signal(self):
        return 'clicked'

    def _get_editing_alert_title(self):
        return _('Erase')

    def _get_editing_alert_message(self, entries_len):
        return ngettext('Do you want to erase %d entry?',
                        'Do you want to erase %d entries?',
                         entries_len) % (entries_len)

    def _get_editing_alert_operation(self):
        return _('Erase')

    def _get_info_alert_title(self):
        return _('Erasing')

    def _operate(self, metadata):
        model.delete(metadata['uid'])

        # This is sync-operation. Thus, call the callback.
        self._post_operate_per_metadata_per_action(metadata)


class BatchCopyButton(ToolButton, palettes.ActionItem):
    def __init__(self):
        ToolButton.__init__(self, 'edit-copy')
        palettes.ActionItem.__init__(self, '', [],
                                     show_editing_alert=True,
                                     show_progress_info_alert=True,
                                     batch_mode=True,
                                     auto_deselect_source_entries=False,
                                     need_to_popup_options=True,
                                     operate_on_deselected_entries=False,
                                     show_not_completed_ops_info=False)

        self.props.tooltip = _('Copy')

        self._metadata_list = None
        self._fill_and_pop_up_options(None)

    def _get_actionable_signal(self):
        return 'clicked'

    def _fill_and_pop_up_options(self, widget_clicked):
        for child in self.props.palette.menu.get_children():
            self.props.palette.menu.remove(child)

        COPY_MENU_HELPER.insert_copy_to_menu_items(self.props.palette.menu,
                                                   [],
                                                   show_editing_alert=True,
                                                   show_progress_info_alert=True,
                                                   batch_mode=True)
        if widget_clicked is not None:
            self.props.palette.popup(immediate=True, state=1)


class MultiSelectEntriesInfoWidget(Gtk.ToolItem):
    def __init__(self):
        Gtk.ToolItem.__init__(self)

        self._box = Gtk.VBox()
        self._selected_entries = 0

        self._label = Gtk.Label()
        self._box.pack_start(self._label, True, True, 0)

        self._progress_label = Gtk.Label()
        self._box.pack_start(self._progress_label, True, True, 0)

        self.add(self._box)

        self.show_all()
        self._box.show_all()
        self._progress_label.hide()

    def set_total_number_of_entries(self, total):
        self._total = total

    def update_progress(self, fraction):
        percent = '%.02f' % (fraction * 100)

        # TRANS: Do not translate %.02f
        text = '%.02f%% complete' % (fraction * 100)
        if (str(percent) != '100.00') and (str(percent).endswith('00')):
            self._progress_label.set_text(text)
            self._progress_label.show()
            self.show_all()
            Gdk.Window.process_all_updates()
        else:
            self._progress_label.hide()
            from jarabe.journal.journalactivity import get_journal
            if not get_journal().is_editing_mode_present():
                self.hide()

    def update_text(self, primary_text, secondary_text, special_action,
                    update_selected_entries):
        # If "special_action" is None,
        #       we need to display the info, conveyed by
        #       "primary_message" and "secondary_message"
        #
        # If "special_action" is True,
        #       a new entry has been selected.
        #
        # If "special_action" is False,
        #       an enrty has been deselected.
        if special_action == None:
            self._label.set_text(primary_text + secondary_text)
            self._label.show()
        else:
            if update_selected_entries:
                if special_action == True:
                    self._selected_entries = self._selected_entries + 1
                elif special_action == False:
                    self._selected_entries = self._selected_entries - 1

            # TRANS: Do not translate the two "%d".
            message = _('Selected %d of %d') % (self._selected_entries,
                                                self._total)

            # Only show the "selected x of y" for "Select All", or
            # "Deselect All", or if the user checked/unchecked a
            # checkbox.
            from jarabe.journal.palettes import get_current_action_item
            current_action_item = get_current_action_item()
            if current_action_item == None or \
               isinstance(current_action_item, SelectAllButton) or \
               isinstance(current_action_item, SelectNoneButton):
                   self._label.set_text(message)
                   self._label.show()

        Gdk.Window.process_all_updates()

    def get_current_entry_number(self):
        return self._selected_entries


class SortingButton(ToolButton):
    __gtype_name__ = 'JournalSortingButton'

    __gsignals__ = {
        'sort-property-changed': (GObject.SignalFlags.RUN_FIRST,
                                  None,
                                  ([])),
    }

    _SORT_OPTIONS = [
        ('timestamp', 'view-lastedit', _('Sort by date modified')),
        ('creation_time', 'view-created', _('Sort by date created')),
        ('filesize', 'view-size', _('Sort by size')),
    ]

    def __init__(self):
        ToolButton.__init__(self)

        self._property = 'timestamp'
        self._order = Gtk.SortType.ASCENDING

        self.props.tooltip = _('Sort view')
        self.props.icon_name = 'view-lastedit'

        for property_, icon, label in self._SORT_OPTIONS:
            button = MenuItem(icon_name=icon, text_label=label)
            button.connect('activate',
                           self.__sort_type_changed_cb,
                           property_,
                           icon)
            button.show()
            self.props.palette.menu.insert(button, -1)

    def __sort_type_changed_cb(self, widget, property_, icon_name):
        self._property = property_
        #FIXME: Implement sorting order
        self._order = Gtk.SortType.ASCENDING
        self.emit('sort-property-changed')

        self.props.icon_name = icon_name

    def get_current_sort(self):
        return (self._property, self._order)
