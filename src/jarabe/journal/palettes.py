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

from gettext import gettext as _
from gettext import ngettext
import logging
import os

from gi.repository import GObject
from gi.repository import Gtk
from gi.repository import Gdk
from gi.repository import GConf
from gi.repository import Gio
from gi.repository import GLib

from sugar3.graphics import style
from sugar3.graphics.palette import Palette
from sugar3.graphics.menuitem import MenuItem
from sugar3.graphics.icon import Icon
from sugar3.graphics.xocolor import XoColor
from sugar3.graphics.alert import Alert
from sugar3 import mime

from jarabe.model import friends
from jarabe.model import filetransfer
from jarabe.model import mimeregistry
from jarabe.journal import misc
from jarabe.journal import model
from jarabe.journal import journalwindow
from jarabe.journal import webdavmanager
from jarabe.journal.journalwindow import freeze_ui,           \
                                         unfreeze_ui,         \
                                         show_normal_cursor,  \
                                         show_waiting_cursor

from webdav.Connection import WebdavError


friends_model = friends.get_model()

_copy_menu_helper = None
_current_action_item = None

USER_FRIENDLY_GENERIC_WEBDAV_ERROR_MESSAGE = _('Cannot perform request. Connection failed.')


class PassphraseDialog(Gtk.Dialog):
    def __init__(self, callback, metadata):
        Gtk.Dialog.__init__(self, flags=Gtk.DialogFlags.MODAL)
        self._callback = callback
        self._metadata = metadata
        self.set_title(_('Passphrase required'))

        # TRANS: Please do not translate the '%s'.
        label_text = _('Please enter the passphrase for "%s"' % metadata['title'])
        label = Gtk.Label(label_text)
        self.vbox.pack_start(label, True, True, 0)

        self.add_buttons(Gtk.STOCK_OK, Gtk.ResponseType.OK)
        self.set_default_response(Gtk.ResponseType.OK)
        self.add_key_entry()

        self.connect('response', self._key_dialog_response_cb)
        self.show_all()

    def add_key_entry(self):
        self._entry = Gtk.Entry()
        self._entry.connect('activate', self._entry_activate_cb)
        self.vbox.pack_start(self._entry, True, True, 0)
        self.vbox.set_spacing(6)
        self.vbox.show_all()

        self._entry.grab_focus()

    def _entry_activate_cb(self, entry):
        self.response(Gtk.ResponseType.OK)

    def get_response_object(self):
        return self._response

    def _key_dialog_response_cb(self, widget, response_id):
        self.hide()
        GObject.idle_add(self._callback, self._metadata,
                         self._entry.get_text())


class ObjectPalette(Palette):

    __gtype_name__ = 'ObjectPalette'

    __gsignals__ = {
        'detail-clicked': (GObject.SignalFlags.RUN_FIRST, None,
                           ([str])),
        'volume-error': (GObject.SignalFlags.RUN_FIRST, None,
                         ([str, str])),
    }

    def __init__(self, metadata, detail=False):

        self._metadata = metadata

        activity_icon = Icon(icon_size=Gtk.IconSize.LARGE_TOOLBAR)
        activity_icon.props.file = misc.get_icon_name(metadata)
        color = misc.get_icon_color(metadata)
        activity_icon.props.xo_color = color

        if 'title' in metadata:
            title = GObject.markup_escape_text(metadata['title'])
        else:
            title = GLib.markup_escape_text(_('Untitled'))

        Palette.__init__(self, primary_text=title,
                         icon=activity_icon)

        from jarabe.journal.journalactivity import get_mount_point
        current_mount_point = get_mount_point()

        if misc.get_activities(metadata) or misc.is_bundle(metadata):
            if metadata.get('activity_id', ''):
                resume_label = _('Resume')
                resume_with_label = _('Resume with')
            else:
                resume_label = _('Start')
                resume_with_label = _('Start with')
            menu_item = MenuItem(resume_label, 'activity-start')
            menu_item.connect('activate', self.__start_activate_cb)
            if model.is_mount_point_for_locally_mounted_remote_share(current_mount_point):
                menu_item.set_sensitive(False)
            self.menu.append(menu_item)
            menu_item.show()

            menu_item = MenuItem(resume_with_label, 'activity-start')
            if model.is_mount_point_for_locally_mounted_remote_share(current_mount_point):
                menu_item.set_sensitive(False)
            self.menu.append(menu_item)
            menu_item.show()
            start_with_menu = StartWithMenu(self._metadata)
            menu_item.set_submenu(start_with_menu)

        else:
            menu_item = MenuItem(_('No activity to start entry'))
            menu_item.set_sensitive(False)
            self.menu.append(menu_item)
            menu_item.show()

        menu_item = MenuItem(_('Copy to'))
        icon = Icon(icon_name='edit-copy', xo_color=color,
                    icon_size=Gtk.IconSize.MENU)
        menu_item.set_image(icon)
        self.menu.append(menu_item)
        menu_item.show()
        copy_menu = CopyMenu(metadata)
        copy_menu_helper = get_copy_menu_helper()

        metadata_list = []
        metadata_list.append(metadata)
        copy_menu_helper.insert_copy_to_menu_items(copy_menu,
                                                   metadata_list,
                                                   False,
                                                   False,
                                                   False)
        copy_menu.connect('volume-error', self.__volume_error_cb)
        menu_item.set_submenu(copy_menu)

        if self._metadata['mountpoint'] == '/':
            menu_item = MenuItem(_('Duplicate'))
            icon = Icon(icon_name='edit-duplicate', xo_color=color,
                        icon_size=Gtk.IconSize.MENU)
            menu_item.set_image(icon)
            menu_item.connect('activate', self.__duplicate_activate_cb)
            self.menu.append(menu_item)
            menu_item.show()

        menu_item = MenuItem(_('Send to'), 'document-send')
        if model.is_mount_point_for_locally_mounted_remote_share(current_mount_point):
            menu_item.set_sensitive(False)
        self.menu.append(menu_item)
        menu_item.show()

        friends_menu = FriendsMenu()
        friends_menu.connect('friend-selected', self.__friend_selected_cb)
        menu_item.set_submenu(friends_menu)

        if detail == True:
            menu_item = MenuItem(_('View Details'), 'go-right')
            menu_item.connect('activate', self.__detail_activate_cb)
            self.menu.append(menu_item)
            menu_item.show()

        menu_item = MenuItem(_('Erase'), 'list-remove')
        menu_item.connect('activate', self.__erase_activate_cb)
        if model.is_mount_point_for_locally_mounted_remote_share(current_mount_point):
            menu_item.set_sensitive(False)
        self.menu.append(menu_item)
        menu_item.show()

    def __start_activate_cb(self, menu_item):
        misc.resume(self._metadata)

    def __duplicate_activate_cb(self, menu_item):
        file_path = model.get_file(self._metadata['uid'])
        try:
            model.copy(self._metadata, '/')
        except IOError, e:
            logging.exception('Error while copying the entry. %s', e.strerror)
            self.emit('volume-error',
                      _('Error while copying the entry. %s') % e.strerror,
                      _('Error'))

    def __erase_activate_cb(self, menu_item):
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
            model.delete(self._metadata['uid'])

    def __detail_activate_cb(self, menu_item):
        self.emit('detail-clicked', self._metadata['uid'])

    def __volume_error_cb(self, menu_item, message, severity):
        self.emit('volume-error', message, severity)

    def __friend_selected_cb(self, menu_item, buddy):
        logging.debug('__friend_selected_cb')
        file_name = model.get_file(self._metadata['uid'])

        if not file_name or not os.path.exists(file_name):
            logging.warn('Entries without a file cannot be sent.')
            self.emit('volume-error',
                      _('Entries without a file cannot be sent.'),
                      _('Warning'))
            return

        title = str(self._metadata['title'])
        description = str(self._metadata.get('description', ''))
        mime_type = str(self._metadata['mime_type'])

        if not mime_type:
            mime_type = mime.get_for_file(file_name)

        filetransfer.start_transfer(buddy, file_name, title, description,
                                    mime_type)


class CopyMenu(Gtk.Menu):
    __gtype_name__ = 'JournalCopyMenu'

    __gsignals__ = {
        'volume-error': (GObject.SignalFlags.RUN_FIRST, None,
                        ([str, str])),
    }

    def __init__(self, metadata):
        Gtk.Menu.__init__(self)


class ActionItem(GObject.GObject):
    """
    This class implements the course of actions that happens when clicking
    upon an Action-Item (eg. Batch-Copy-Toolbar-button;
                             Actual-Batch-Copy-To-Journal-button;
                             Actual-Batch-Copy-To-Documents-button;
                             Actual-Batch-Copy-To-Mounted-Drive-button;
                             Actual-Batch-Copy-To-Clipboard-button;
                             Single-Copy-To-Journal-button;
                             Single-Copy-To-Documents-button;
                             Single-Copy-To-Mounted-Drive-button;
                             Single-Copy-To-Clipboard-button;
                             Batch-Erase-Button;
                             Select-None-Toolbar-button;
                             Select-All-Toolbar-button
    """
    __gtype_name__ = 'JournalActionItem'

    def __init__(self, label, metadata_list, show_editing_alert,
                 show_progress_info_alert, batch_mode,
                 auto_deselect_source_entries,
                 need_to_popup_options,
                 operate_on_deselected_entries,
                 show_not_completed_ops_info):
        GObject.GObject.__init__(self)

        self._label = label

        # Make a copy.
        self._immutable_metadata_list = []
        for metadata in metadata_list:
            self._immutable_metadata_list.append(metadata)

        self._metadata_list = metadata_list
        self._show_progress_info_alert = show_progress_info_alert
        self._batch_mode = batch_mode
        self._auto_deselect_source_entries = \
                auto_deselect_source_entries
        self._need_to_popup_options = \
                need_to_popup_options
        self._operate_on_deselected_entries = \
                operate_on_deselected_entries
        self._show_not_completed_ops_info = \
                show_not_completed_ops_info

        actionable_signal = self._get_actionable_signal()

        if need_to_popup_options:
            self.connect(actionable_signal, self._pre_fill_and_pop_up_options)
        else:
            if show_editing_alert:
                self.connect(actionable_signal, self._show_editing_alert)
            else:
                self.connect(actionable_signal,
                             self._pre_operate_per_action,
                             Gtk.ResponseType.OK)

    def _get_actionable_signal(self):
        """
        Some widgets like 'buttons' have 'clicked' as actionable signal;
        some like 'menuitems' have 'activate' as actionable signal.
        """

        raise NotImplementedError

    def _pre_fill_and_pop_up_options(self, widget_clicked):
        self._set_current_action_item_widget()
        self._fill_and_pop_up_options(widget_clicked)

    def _fill_and_pop_up_options(self, widget_clicked):
        """
        Eg. Batch-Copy-Toolbar-button does not do anything by itself
        useful; but rather pops-up the actual 'copy-to' options.
        """

        raise NotImplementedError

    def _show_editing_alert(self, widget_clicked):
        """
        Upon clicking the actual operation button (eg.
        Batch-Erase-Button and Batch-Copy-To-Clipboard button; BUT NOT
        Batch-Copy-Toolbar-button, since it does not do anything
        actually useful, but only pops-up the actual 'copy-to' options.
        """

        freeze_ui()
        GObject.idle_add(self.__show_editing_alert_after_freezing_ui,
                         widget_clicked)

    def __show_editing_alert_after_freezing_ui(self, widget_clicked):
        self._set_current_action_item_widget()

        alert_parameters = self._get_editing_alert_parameters()
        title = alert_parameters[0]
        message = alert_parameters[1]
        operation = alert_parameters[2]

        from jarabe.journal.journalactivity import get_journal
        get_journal().update_confirmation_alert(title, message,
                                                self._pre_operate_per_action,
                                                None)

    def _get_editing_alert_parameters(self):
        """
        Get the alert parameters for widgets that can show editing
        alert.
        """

        self._metadata_list = self._get_metadata_list()
        entries_len = len(self._metadata_list)

        title = self._get_editing_alert_title()
        message = self._get_editing_alert_message(entries_len)
        operation = self._get_editing_alert_operation()

        return (title, message, operation)

    def _get_list_model_len(self):
        """
        Get the total length of the model under view.
        """

        from jarabe.journal.journalactivity import get_journal
        journal = get_journal()

        return len(journal.get_list_view().get_model())

    def _get_metadata_list(self):
        """
        For batch-mode, get the metadata list, according to button-type.
        For eg, Select-All-Toolbar-button operates on non-selected entries;
        while othere operate on selected-entries.

        For single-mode, simply copy from the
        "immutable_metadata_list".
        """

        if self._batch_mode:
            from jarabe.journal.journalactivity import get_journal
            journal = get_journal()

            if self._operate_on_deselected_entries:
                metadata_list = journal.get_metadata_list(False)
            else:
                metadata_list = journal.get_metadata_list(True)

            # Make a backup copy, of this metadata_list.
            self._immutable_metadata_list = []
            for metadata in metadata_list:
                self._immutable_metadata_list.append(metadata)

            return metadata_list
        else:
            metadata_list = []
            for metadata in self._immutable_metadata_list:
                metadata_list.append(metadata)
            return metadata_list

    def _get_editing_alert_title(self):
        raise NotImplementedError

    def _get_editing_alert_message(self, entries_len):
        raise NotImplementedError

    def _get_editing_alert_operation(self):
        raise NotImplementedError

    def _is_metadata_list_empty(self):
        return (self._metadata_list is None) or \
                (len(self._metadata_list) == 0)

    def _set_current_action_item_widget(self):
        """
        Only set this, if this widget achieves some effective action.
        """
        if not self._need_to_popup_options:
            global _current_action_item
            _current_action_item = self

    def _pre_operate_per_action(self, obj, response_id):
        """
        This is the stage, just before the FIRST metadata gets into its
        processing cycle.
        """
        freeze_ui()
        GObject.idle_add(self._pre_operate_per_action_after_done_ui_freezing,
                         obj, response_id)

    def _pre_operate_per_action_after_done_ui_freezing(self, obj,
                                                       response_id):
        self._set_current_action_item_widget()

        self._continue_operation = True

        # If the user chose to cancel the operation from the onset,
        # simply proceeed to the last.
        if response_id == Gtk.ResponseType.CANCEL:
            unfreeze_ui()

            self._cancel_further_batch_operation_items()
            self._post_operate_per_action()
            return

        self._skip_all = False

        # Also, get the initial length of the model.
        self._model_len = self._get_list_model_len()

        # Speed Optimisation:
        # ===================
        # If the metadata-list is empty, fetch it;
        # else we have already fetched it, when we showed the
        # "editing-alert".
        if len(self._metadata_list) == 0:
            self._metadata_list = self._get_metadata_list()

        # Set the initial length of metadata-list.
        self._metadata_list_initial_len = len(self._metadata_list)

        self._metadata_processed = 0

        # Next, proceed with the metadata
        self._pre_operate_per_metadata_per_action()

    def _pre_operate_per_metadata_per_action(self):
        """
        This is the stage, just before EVERY metadata gets into doing
        its actual work.
        """

        show_waiting_cursor()
        GObject.idle_add(self.__pre_operate_per_metadata_per_action_after_freezing_ui)

    def __pre_operate_per_metadata_per_action_after_freezing_ui(self):
        from jarabe.journal.journalactivity import get_journal

        # If there is still some metadata left, proceed with the
        # metadata operation.
        # Else, proceed to post-operations.
        if len(self._metadata_list) > 0:
            metadata = self._metadata_list.pop(0)

            # If info-alert needs to be shown, show the alert, and
            # arrange for actual operation.
            # Else, proceed to actual operation directly.
            if self._show_progress_info_alert:
                current_len = len(self._metadata_list)

                # TRANS: Do not translate the two %d, and the %s.
                info_alert_message = _(' %d of %d : %s') % (
                        self._metadata_list_initial_len - current_len,
                        self._metadata_list_initial_len, metadata['title'])

                get_journal().update_info_alert(self._get_info_alert_title(),
                                                info_alert_message)

            # Call the core-function !!
            GObject.idle_add(self._operate_per_metadata_per_action, metadata)
        else:
            self._post_operate_per_action()

    def _get_info_alert_title(self):
        raise NotImplementedError

    def _operate_per_metadata_per_action(self, metadata):
        """
        This is just a code-convenient-function, which allows
        runtime-overriding. It just delegates to the actual
        "self._operate" method, the actual which is determined at
        runtime.
        """

        if self._continue_operation is False:
            # Jump directly to the post-operation
            self._post_operate_per_metadata_per_action(metadata)
        else:
            # Pass the callback for the post-operation-for-metadata. This
            # will ensure that async-operations on the metadata are taken
            # care of.
            if self._operate(metadata) is False:
                return
            else:
                self._metadata_processed = self._metadata_processed + 1

    def _operate(self, metadata):
        """
        Actual, core, productive stage for EVERY metadata.
        """

        raise NotImplementedError

    def _post_operate_per_metadata_per_action(self, metadata,
                                              response_id=None):
        """
        This is the stage, just after EVERY metadata has been
        processed.
        """
        self._hide_info_widget_for_single_mode()

        # Toggle the corresponding checkbox - but only for batch-mode.
        if self._batch_mode and self._auto_deselect_source_entries:
            from jarabe.journal.journalactivity import get_journal
            list_view = get_journal().get_list_view()

            list_view.do_ui_select_change(metadata)
            list_view.do_backend_select_change(metadata)

        # Call the next ...
        self._pre_operate_per_metadata_per_action()

    def _post_operate_per_action(self):
        """
        This is the stage, just after the LAST metadata has been
        processed.
        """

        from jarabe.journal.journalactivity import get_journal
        journal = get_journal()
        journal_toolbar_box = journal.get_toolbar_box()

        if self._batch_mode and (not self._auto_deselect_source_entries):
            journal_toolbar_box.display_already_selected_entries_status()

        self._process_switching_mode(None, False)

        unfreeze_ui()

        # Set the "_current_action_item" to None.
        global _current_action_item
        _current_action_item = None

    def _process_switching_mode(self, metadata, ok_clicked=False):
        from jarabe.journal.journalactivity import get_journal
        journal = get_journal()

        # Necessary to do this, when the alert needs to be hidden,
        # WITHOUT user-intervention.
        journal.hide_alert()

    def _refresh(self):
        from jarabe.journal.journalactivity import get_journal
        get_journal().get_list_view().refresh()

    def _handle_single_mode_notification(self, message, severity):
        from jarabe.journal.journalactivity import get_journal
        journal = get_journal()

        journal._show_alert(message, severity)
        self._hide_info_widget_for_single_mode()

    def _hide_info_widget_for_single_mode(self):
        if (not self._batch_mode):
            from jarabe.journal.journalactivity import get_journal
            journal = get_journal()

            journal.get_toolbar_box().hide_info_widget()

    def _unhide_info_widget_for_single_mode(self):
        if not self._batch_mode:
            from jarabe.journal.journalactivity import get_journal
            get_journal().update_progress(0)

    def _handle_error_alert(self, error_message, metadata):
        """
        This handles any error scenarios. Examples are of entries that
        display the message "Entries without a file cannot be copied."
        This is kind of controller-functionl the model-function is
        "self._set_error_info_alert".
        """

        if self._skip_all:
            self._post_operate_per_metadata_per_action(metadata)
        else:
            self._set_error_info_alert(error_message, metadata)

    def _set_error_info_alert(self, error_message, metadata):
        """
        This method displays the error alert.
        """

        current_len = len(self._metadata_list)

        # Only show the alert, if allowed to.
        if self._show_not_completed_ops_info:
            from jarabe.journal.journalactivity import get_journal
            get_journal().update_confirmation_alert(_('Error'),
                                             error_message,
                                             self._process_error_skipping,
                                             metadata)
        else:
            self._process_error_skipping(metadata, gtk.RESPONSE_OK)

    def _process_error_skipping(self, metadata, response_id):
        # This sets up the decision, as to whether continue operations
        # with the rest of the metadata.
        if response_id == Gtk.ResponseType.CANCEL:
            self._cancel_further_batch_operation_items()

        self._post_operate_per_metadata_per_action(metadata)

    def _cancel_further_batch_operation_items(self):
        self._continue_operation = False

        # Optimization:
        # Clear the metadata-list as well.
        # This would prevent the unnecessary traversing of the
        # remaining checkboxes-corresponding-to-remaining-metadata (of
        # course without doing any effective action).
        self._metadata_list = []

    def _file_path_valid(self, metadata):
        from jarabe.journal.journalactivity import get_mount_point
        current_mount_point = get_mount_point()

        # Now, for locally mounted remote-shares, download the file.
        # Note that, always download the file, to avoid the problems
        # of stale-cache.
        if model.is_mount_point_for_locally_mounted_remote_share(current_mount_point):
            file_path = metadata['uid']
            filename = os.path.basename(file_path)
            ip_address_or_dns_name = \
                    model.extract_ip_address_or_dns_name_from_locally_mounted_remote_share_path(file_path)

            data_webdav_manager = \
                    webdavmanager.get_data_webdav_manager(ip_address_or_dns_name)
            metadata_webdav_manager = \
                    webdavmanager.get_metadata_webdav_manager(ip_address_or_dns_name)

            # Download the preview file, if it exists.
            preview_resource = \
                    webdavmanager.get_resource_by_resource_key(metadata_webdav_manager,
                            '/webdav/.Sugar-Metadata/' + filename + '.preview')
            preview_path = os.path.dirname(file_path) + '/.Sugar-Metadata/'+ filename + '.preview'

            if preview_resource is not None:
                try:
                    preview_resource.downloadFile(preview_path,
                                                  show_progress=False,
                                                  filesize=0)
                except (WebdavError, socket.error), e:
                    error_message = USER_FRIENDLY_GENERIC_WEBDAV_ERROR_MESSAGE
                    logging.warn(error_message)
                    if self._batch_mode:
                        self._handle_error_alert(error_message, metadata)
                    else:
                        self._handle_single_mode_notification(error_message,
                                                              _('Error'))
                    return False

            # If we manage to reach here, download the data file.
            data_resource = \
                    webdavmanager.get_resource_by_resource_key(data_webdav_manager,
                                                               '/webdav/'+ filename)
            try:
                data_resource.downloadFile(metadata['uid'],
                                           show_progress=True,
                                           filesize=int(metadata['filesize']))
                return True
            except (WebdavError, socket.error), e:
                # Delete the downloaded preview file, if it exists.
                if os.path.exists(preview_path):
                    os.unlink(preview_path)

                error_message = USER_FRIENDLY_GENERIC_WEBDAV_ERROR_MESSAGE
                logging.warn(error_message)
                if self._batch_mode:
                    self._handle_error_alert(error_message, metadata)
                else:
                    self._handle_single_mode_notification(error_message,
                            _('Error'))
                return False

        file_path = model.get_file(metadata['uid'])
        if not file_path or not os.path.exists(file_path):
            logging.warn('Entries without a file cannot be copied.')
            error_message =  _('Entries without a file cannot be copied.')
            if self._batch_mode:
                self._handle_error_alert(error_message, metadata)
            else:
                self._handle_single_mode_notification(error_message, _('Warning'))
            return False
        else:
            return True

    def _metadata_copy_valid(self, metadata, mount_point):
        self._set_bundle_installation_allowed(False)

        try:
            model.copy(metadata, mount_point)
            return True
        except Exception, e:
            logging.exception(e)
            error_message = _('Error while copying the entry. %s') % e
            if self._batch_mode:
                self._handle_error_alert(error_message, metadata)
            else:
                self._handle_single_mode_notification(error_message, _('Error'))
            return False
        finally:
            self._set_bundle_installation_allowed(True)

    def _metadata_write_valid(self, metadata):
        operation = self._get_info_alert_title()
        self._set_bundle_installation_allowed(False)

        try:
            model.update_only_metadata_and_preview_files_and_return_file_paths(metadata)
            return True
        except Exception, e:
            logging.exception('Error while writing the metadata. %s', e)
            error_message = _('Error occurred while %s : %s.') % \
                    (operation, e,)
            if self._batch_mode:
                self._handle_error_alert(error_message, metadata)
            else:
                self._handle_single_mode_notification(error_message, _('Error'))
            return False
        finally:
            self._set_bundle_installation_allowed(True)

    def _set_bundle_installation_allowed(self, allowed):
        """
        This method serves only as a "delegating" method.
        This has been done to aid easy configurability.
        """
        from jarabe.journal.journalactivity import get_journal
        journal = get_journal()

        if self._batch_mode:
            journal.set_bundle_installation_allowed(allowed)

    def get_number_of_entries_to_operate_upon(self):
        return len(self._immutable_metadata_list)


class BaseCopyMenuItem(MenuItem, ActionItem):
    __gtype_name__ = 'JournalBaseCopyMenuItem'

    __gsignals__ = {
            'volume-error': (GObject.SignalFlags.RUN_FIRST,
                             None, ([str, str])),
            }

    def __init__(self, metadata_list, label, show_editing_alert,
                 show_progress_info_alert, batch_mode, mount_point):
        MenuItem.__init__(self, label)
        ActionItem.__init__(self, label, metadata_list, show_editing_alert,
                            show_progress_info_alert, batch_mode,
                            auto_deselect_source_entries=False,
                            need_to_popup_options=False,
                            operate_on_deselected_entries=False,
                            show_not_completed_ops_info=True)
        self._mount_point = mount_point

    def get_mount_point(self):
        return self._mount_point

    def _get_actionable_signal(self):
        return 'activate'

    def _get_editing_alert_title(self):
        return _('Copy')

    def _get_editing_alert_message(self, entries_len):
        return ngettext('Do you want to copy %d entry to %s?',
                        'Do you want to copy %d entries to %s?',
                        entries_len) % (entries_len, self._label)

    def _get_editing_alert_operation(self):
        return _('Copy')

    def _get_info_alert_title(self):
        return _('Copying')

    def _operate(self, metadata):
        from jarabe.journal.journalactivity import get_mount_point
        if(model.is_mount_point_for_locally_mounted_remote_share(get_mount_point())) \
                and (model.is_mount_point_for_school_server(get_mount_point()) == True):
            PassphraseDialog(self._proceed_after_receiving_passphrase, metadata)
        else:
            self._proceed_with_copy(metadata)

    def _proceed_after_receiving_passphrase(self, metadata, passphrase):
        if metadata['passphrase'] != passphrase:
            error_message = _('Passphrase does not match.')
            if self._batch_mode:
                self._handle_error_alert(error_message, metadata)
            else:
                self._handle_single_mode_notification(error_message, _('Error'))
            return False
        else:
            self._unhide_info_widget_for_single_mode()
            GObject.idle_add(self._proceed_with_copy, metadata)

    def _proceed_with_copy(self, metadata):
        return NotImplementedError

    def _post_successful_copy(self, metadata, response_id=None):
         from jarabe.journal.journalactivity import get_journal, \
                                                    get_mount_point

         if model.is_mount_point_for_locally_mounted_remote_share(get_mount_point()):
             successful_downloading_message = None

             if model.is_mount_point_for_school_server(get_mount_point()) == True:
                 # TRANS: Do not translate the %s.
                 successful_downloading_message = \
                         _('Your file "%s" was correctly downloaded from the School Server.') % metadata['title']
             else:
                 # TRANS: Do not translate the %s.
                 successful_downloading_message = \
                         _('Your file "%s" was correctly downloaded from the Peer.') % metadata['title']

             from jarabe.journal.journalactivity import get_journal
             get_journal().update_error_alert(self._get_editing_alert_title(),
                                              successful_downloading_message,
                                              self._post_operate_per_metadata_per_action,
                                              metadata)
         else:
             self._post_operate_per_metadata_per_action(metadata)


class VolumeMenu(BaseCopyMenuItem):
    def __init__(self, metadata_list, label, mount_point,
                 show_editing_alert, show_progress_info_alert,
                 batch_mode):
        BaseCopyMenuItem.__init__(self, metadata_list, label,
                                  show_editing_alert,
                                  show_progress_info_alert, batch_mode,
                                  mount_point)

    def _proceed_with_copy(self, metadata):
        if not self._file_path_valid(metadata):
            return False

        if not self._metadata_copy_valid(metadata, self._mount_point):
            return False

        # This is sync-operation. Thus, call the callback.
        self._post_successful_copy(metadata)


class ClipboardMenu(BaseCopyMenuItem):
    def __init__(self, metadata_list, show_editing_alert,
                 show_progress_info_alert, batch_mode):
        BaseCopyMenuItem.__init__(self, metadata_list, _('Clipboard'),
                                  show_editing_alert,
                                  show_progress_info_alert,
                                  batch_mode, None)
        self._temp_file_path_list = []

    def _proceed_with_copy(self, metadata):
        if not self._file_path_valid(metadata):
            return False

        clipboard = Gtk.Clipboard.get(Gdk.SELECTION_CLIPBOARD)
        clipboard.set_with_data([Gtk.TargetEntry.new('text/uri-list', 0, 0)],
                                self.__clipboard_get_func_cb,
                                self.__clipboard_clear_func_cb,
                                metadata)

    def __clipboard_get_func_cb(self, clipboard, selection_data, info,
                                metadata):
        # Get hold of a reference so the temp file doesn't get deleted
        self._temp_file_path = model.get_file(metadata['uid'])
        logging.debug('__clipboard_get_func_cb %r', self._temp_file_path)
        selection_data.set_uris(['file://' + self._temp_file_path])

    def __clipboard_clear_func_cb(self, clipboard, metadata):
        # Release and delete the temp file
        self._temp_file_path = None

        # This is async-operation; and this is the ending point.
        self._post_successful_copy(metadata)


class DocumentsMenu(BaseCopyMenuItem):
    def __init__(self, metadata_list, show_editing_alert,
                 show_progress_info_alert, batch_mode):
        BaseCopyMenuItem.__init__(self, metadata_list, _('Documents'),
                                  show_editing_alert,
                                  show_progress_info_alert,
                                  batch_mode,
                                  model.get_documents_path())

    def _proceed_with_copy(self, metadata):
        if not self._file_path_valid(metadata):
            return False

        if not self._metadata_copy_valid(metadata,
                                         model.get_documents_path()):
            return False

        # This is sync-operation. Call the post-operation now.
        self._post_successful_copy(metadata)


class LocalSharesMenu(BaseCopyMenuItem):
    def __init__(self, metadata_list, show_editing_alert,
                 show_progress_info_alert, batch_mode):
        BaseCopyMenuItem.__init__(self, metadata_list, _('Local Shares'),
                                  show_editing_alert,
                                  show_progress_info_alert,
                                  batch_mode,
                                  model.LOCAL_SHARES_MOUNT_POINT)

    def _proceed_with_copy(self, metadata):
        if not self._file_path_valid(metadata):
            return False

        # Attach the filesize.
        file_path = model.get_file(metadata['uid'])
        metadata['filesize'] = os.stat(file_path).st_size

        # Attach the current mount-point.
        from jarabe.journal.journalactivity import get_mount_point
        metadata['mountpoint'] = get_mount_point()

        if not self._metadata_write_valid(metadata):
            return False

        if not self._metadata_copy_valid(metadata,
                                        model.LOCAL_SHARES_MOUNT_POINT):
            return False

        # This is sync-operation. Call the post-operation now.
        self._post_successful_copy(metadata)


class SchoolServerMenu(BaseCopyMenuItem):
    def __init__(self, metadata_list, show_editing_alert,
                 show_progress_info_alert, batch_mode):
        BaseCopyMenuItem.__init__(self, metadata_list, _('School Server'),
                                  show_editing_alert,
                                  show_progress_info_alert,
                                  batch_mode,
                                  model.WEBDAV_MOUNT_POINT + model.SCHOOL_SERVER_IP_ADDRESS_OR_DNS_NAME)

    def _operate(self, metadata):
        if not self._file_path_valid(metadata):
            return False

        # If the entry is copyable, proceed with asking the
        # upload-passphrase.
        PassphraseDialog(self._proceed_after_receiving_passphrase, metadata)

    def _proceed_after_receiving_passphrase(self, metadata, passphrase):
        self._unhide_info_widget_for_single_mode()
        GObject.idle_add(self._proceed_with_uploading, metadata,
                         passphrase)

    def _proceed_with_uploading(self, metadata, passphrase):
        #
        # Attach the passphrase.
        metadata['passphrase'] = passphrase

        # Attach the filesize.
        file_path = model.get_file(metadata['uid'])
        metadata['filesize'] = os.stat(file_path).st_size

        # Attach the current mount-point.
        from jarabe.journal.journalactivity import get_mount_point, \
                                                   get_journal
        metadata['mountpoint'] = get_mount_point()

        # Attach the info of the uploader.
        from jarabe.model.buddy import get_owner_instance
        metadata['uploader-nick'] = get_owner_instance().props.nick
        metadata['uploader-serial'] = misc.get_xo_serial()

        if not self._metadata_write_valid(metadata):
            return False

        if not self._metadata_copy_valid(metadata,
                                         model.WEBDAV_MOUNT_POINT + model.SCHOOL_SERVER_IP_ADDRESS_OR_DNS_NAME):
            return False

        client = GConf.Client.get_default()
        validity_of_uploaded_file_in_days = \
                client.get_int('/desktop/sugar/network/validity_of_uploaded_file_in_days')

        # TRANS: Do not translate the %d and %s.
        successful_uploading_message = \
                _('Your file "%s" was correctly uploaded to the School Server.\n'
                  'The file will be available in the school server '
                  'for %d days.') % (metadata['title'], validity_of_uploaded_file_in_days)
        get_journal().update_error_alert(self._get_editing_alert_title(),
                                         successful_uploading_message,
                                         self._post_successful_copy,
                                         metadata)


class FriendsMenu(Gtk.Menu):
    __gtype_name__ = 'JournalFriendsMenu'

    __gsignals__ = {
        'friend-selected': (GObject.SignalFlags.RUN_FIRST, None,
                            ([object])),
    }

    def __init__(self):
        Gtk.Menu.__init__(self)

        if filetransfer.file_transfer_available():
            friends_model = friends.get_model()
            for friend in friends_model:
                if friend.is_present():
                    menu_item = MenuItem(text_label=friend.get_nick(),
                                         icon_name='computer-xo',
                                         xo_color=friend.get_color())
                    menu_item.connect('activate', self.__item_activate_cb,
                                      friend)
                    self.append(menu_item)
                    menu_item.show()

            if not self.get_children():
                menu_item = MenuItem(_('No friends present'))
                menu_item.set_sensitive(False)
                self.append(menu_item)
                menu_item.show()
        else:
            menu_item = MenuItem(_('No valid connection found'))
            menu_item.set_sensitive(False)
            self.append(menu_item)
            menu_item.show()

    def __item_activate_cb(self, menu_item, friend):
        self.emit('friend-selected', friend)


class StartWithMenu(Gtk.Menu):
    __gtype_name__ = 'JournalStartWithMenu'

    def __init__(self, metadata):
        Gtk.Menu.__init__(self)

        self._metadata = metadata

        for activity_info in misc.get_activities(metadata):
            menu_item = MenuItem(activity_info.get_name())
            menu_item.set_image(Icon(file=activity_info.get_icon(),
                                     icon_size=Gtk.IconSize.MENU))
            menu_item.connect('activate', self.__item_activate_cb,
                              activity_info.get_bundle_id())
            self.append(menu_item)
            menu_item.show()

        if not self.get_children():
            if metadata.get('activity_id', ''):
                resume_label = _('No activity to resume entry')
            else:
                resume_label = _('No activity to start entry')
            menu_item = MenuItem(resume_label)
            menu_item.set_sensitive(False)
            self.append(menu_item)
            menu_item.show()

    def __item_activate_cb(self, menu_item, service_name):
        mime_type = self._metadata.get('mime_type', '')
        if mime_type:
            mime_registry = mimeregistry.get_registry()
            mime_registry.set_default_activity(mime_type, service_name)
        misc.resume(self._metadata, service_name)


class BuddyPalette(Palette):
    def __init__(self, buddy):
        self._buddy = buddy

        nick, colors = buddy
        buddy_icon = Icon(icon_name='computer-xo',
                          icon_size=style.STANDARD_ICON_SIZE,
                          xo_color=XoColor(colors))

        Palette.__init__(self, primary_text=GLib.markup_escape_text(nick),
                         icon=buddy_icon)

        # TODO: Support actions on buddies, like make friend, invite, etc.


class CopyMenuHelper(Gtk.Menu):
    __gtype_name__ = 'JournalCopyMenuHelper'

    __gsignals__ = {
            'volume-error': (GObject.SignalFlags.RUN_FIRST,
                             None, ([str, str])),
            }

    def insert_copy_to_menu_items(self, menu, metadata_list,
                                  show_editing_alert,
                                  show_progress_info_alert,
                                  batch_mode):
        self._metadata_list = metadata_list

        clipboard_menu = ClipboardMenu(metadata_list,
                                       show_editing_alert,
                                       show_progress_info_alert,
                                       batch_mode)
        clipboard_menu.set_image(Icon(icon_name='toolbar-edit',
                                      icon_size=Gtk.IconSize.MENU))
        clipboard_menu.connect('volume-error', self.__volume_error_cb)
        menu.append(clipboard_menu)
        clipboard_menu.show()

        from jarabe.journal.journalactivity import get_mount_point

        if get_mount_point() != model.get_documents_path():
            documents_menu = DocumentsMenu(metadata_list,
                                           show_editing_alert,
                                           show_progress_info_alert,
                                           batch_mode)
            documents_menu.set_image(Icon(icon_name='user-documents',
                                          icon_size=Gtk.IconSize.MENU))
            documents_menu.connect('volume-error', self.__volume_error_cb)
            menu.append(documents_menu)
            documents_menu.show()

        if (model.is_school_server_present()) and \
           (not model.is_mount_point_for_locally_mounted_remote_share(get_mount_point())):
            documents_menu = SchoolServerMenu(metadata_list,
                                           show_editing_alert,
                                           show_progress_info_alert,
                                           batch_mode)
            documents_menu.set_image(Icon(icon_name='school-server',
                                          icon_size=Gtk.IconSize.MENU))
            documents_menu.connect('volume-error', self.__volume_error_cb)
            menu.append(documents_menu)
            documents_menu.show()

        if (model.is_peer_to_peer_sharing_available()) and \
           (get_mount_point() != model.LOCAL_SHARES_MOUNT_POINT):
            local_shares_menu = LocalSharesMenu(metadata_list,
                                                show_editing_alert,
                                                show_progress_info_alert,
                                                batch_mode)
            local_shares_menu.set_image(Icon(icon_name='emblem-neighborhood-shared',
                                        icon_size=Gtk.IconSize.MENU))
            local_shares_menu.connect('volume-error', self.__volume_error_cb)
            menu.append(local_shares_menu)
            local_shares_menu.show()

        if get_mount_point() != '/':
            client = GConf.Client.get_default()
            color = XoColor(client.get_string('/desktop/sugar/user/color'))
            journal_menu = VolumeMenu(metadata_list, _('Journal'), '/',
                                      show_editing_alert,
                                      show_progress_info_alert,
                                      batch_mode)
            journal_menu.set_image(Icon(icon_name='activity-journal',
                                        xo_color=color,
                                        icon_size=Gtk.IconSize.MENU))
            journal_menu.connect('volume-error', self.__volume_error_cb)
            menu.append(journal_menu)
            journal_menu.show()

        volume_monitor = Gio.VolumeMonitor.get()
        icon_theme = Gtk.IconTheme.get_default()
        for mount in volume_monitor.get_mounts():
            if get_mount_point() == mount.get_root().get_path():
                continue

            volume_menu = VolumeMenu(metadata_list, mount.get_name(),
                                     mount.get_root().get_path(),
                                     show_editing_alert,
                                     show_progress_info_alert,
                                     batch_mode)
            for name in mount.get_icon().props.names:
                if icon_theme.has_icon(name):
                    volume_menu.set_image(Icon(icon_name=name,
                                               icon_size=Gtk.IconSize.MENU))
                    break

            volume_menu.connect('volume-error', self.__volume_error_cb)
            menu.insert(volume_menu, -1)
            volume_menu.show()

    def __volume_error_cb(self, menu_item, message, severity):
        from jarabe.journal.journalactivity import get_journal
        journal = get_journal()
        journal._volume_error_cb(menu_item, message, severity)


def get_copy_menu_helper():
    global _copy_menu_helper
    if _copy_menu_helper is None:
        _copy_menu_helper = CopyMenuHelper()
    return _copy_menu_helper


def get_current_action_item():
    return _current_action_item
