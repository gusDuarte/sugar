# Copyright (C) 2007, 2011, One Laptop Per Child
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
import statvfs
from gettext import gettext as _

from gi.repository import GObject
from gi.repository import Gio
from gi.repository import GLib
from gi.repository import Gtk
from gi.repository import Gdk
from gi.repository import GConf
import cPickle
import xapian
import simplejson
import tempfile
import shutil

from sugar3.graphics.radiotoolbutton import RadioToolButton
from sugar3.graphics.palette import Palette
from sugar3.graphics.xocolor import XoColor
from sugar3 import env

from jarabe.journal import model
from jarabe.view.palettes import JournalVolumePalette, RemoteSharePalette


_JOURNAL_0_METADATA_DIR = '.olpc.store'

SHARE_TYPE_PEER = 1
SHARE_TYPE_SCHOOL_SERVER = 2


def _get_id(document):
    """Get the ID for the document in the xapian database."""
    tl = document.termlist()
    try:
        term = tl.skip_to('Q').term
        if len(term) == 0 or term[0] != 'Q':
            return None
        return term[1:]
    except StopIteration:
        return None


def _convert_entries(root):
    """Convert entries written by the datastore version 0.

    The metadata and the preview will be written using the new
    scheme for writing Journal entries to removable storage
    devices.

    - entries that do not have an associated file are not
    converted.
    - if an entry has no title we set it to Untitled and rename
    the file accordingly, taking care of creating a unique
    filename

    """
    try:
        database = xapian.Database(os.path.join(root, _JOURNAL_0_METADATA_DIR,
                                                'index'))
    except xapian.DatabaseError:
        logging.exception('Convert DS-0 Journal entries: error reading db: %s',
                      os.path.join(root, _JOURNAL_0_METADATA_DIR, 'index'))
        return

    metadata_dir_path = os.path.join(root, model.JOURNAL_METADATA_DIR)
    if not os.path.exists(metadata_dir_path):
        try:
            os.mkdir(metadata_dir_path)
        except EnvironmentError:
            logging.error('Convert DS-0 Journal entries: '
                          'error creating the Journal metadata directory.')
            return

    for posting_item in database.postlist(''):
        try:
            document = database.get_document(posting_item.docid)
        except xapian.DocNotFoundError, e:
            logging.debug('Convert DS-0 Journal entries: error getting '
                          'document %s: %s', posting_item.docid, e)
            continue
        _convert_entry(root, document)


def _convert_entry(root, document):
    try:
        metadata_loaded = cPickle.loads(document.get_data())
    except cPickle.PickleError, e:
        logging.debug('Convert DS-0 Journal entries: '
                      'error converting metadata: %s', e)
        return

    if not ('activity_id' in metadata_loaded and
            'mime_type' in metadata_loaded and
            'title' in metadata_loaded):
        return

    metadata = {}

    uid = _get_id(document)
    if uid is None:
        return

    for key, value in metadata_loaded.items():
        metadata[str(key)] = str(value[0])

    if 'uid' not in metadata:
        metadata['uid'] = uid

    filename = metadata.pop('filename', None)
    if not filename:
        return
    if not os.path.exists(os.path.join(root, filename)):
        return

    if not metadata.get('title'):
        metadata['title'] = _('Untitled')
        fn = model.get_file_name(metadata['title'],
                                 metadata['mime_type'])
        new_filename = model.get_unique_file_name(root, fn)
        os.rename(os.path.join(root, filename),
                  os.path.join(root, new_filename))
        filename = new_filename

    preview_path = os.path.join(root, _JOURNAL_0_METADATA_DIR,
                                'preview', uid)
    if os.path.exists(preview_path):
        preview_fname = filename + '.preview'
        new_preview_path = os.path.join(root,
                                        model.JOURNAL_METADATA_DIR,
                                        preview_fname)
        if not os.path.exists(new_preview_path):
            shutil.copy(preview_path, new_preview_path)

    metadata_fname = filename + '.metadata'
    metadata_path = os.path.join(root, model.JOURNAL_METADATA_DIR,
                                 metadata_fname)
    if not os.path.exists(metadata_path):
        (fh, fn) = tempfile.mkstemp(dir=root)
        os.write(fh, simplejson.dumps(metadata))
        os.close(fh)
        os.rename(fn, metadata_path)

        logging.debug('Convert DS-0 Journal entries: entry converted: '
                      'file=%s metadata=%s',
                      os.path.join(root, filename), metadata)


class VolumesToolbar(Gtk.Toolbar):
    __gtype_name__ = 'VolumesToolbar'

    __gsignals__ = {
        'volume-changed': (GObject.SignalFlags.RUN_FIRST, None,
                           ([str])),
        'volume-error': (GObject.SignalFlags.RUN_FIRST, None,
                         ([str, str])),
    }

    def __init__(self):
        Gtk.Toolbar.__init__(self)
        self._mount_added_hid = None
        self._mount_removed_hid = None

        button = JournalButton()
        button.connect('toggled', self._button_toggled_cb)
        self.insert(button, 0)
        button.show()
        self._volume_buttons = [button]

        self.connect('destroy', self.__destroy_cb)

        GObject.idle_add(self._set_up_volumes)

    def __destroy_cb(self, widget):
        volume_monitor = Gio.VolumeMonitor.get()
        volume_monitor.disconnect(self._mount_added_hid)
        volume_monitor.disconnect(self._mount_removed_hid)

    def _set_up_volumes(self):
        self._set_up_documents_button()

        if model.is_peer_to_peer_sharing_available():
            self._set_up_local_shares_button()

        client = GConf.Client.get_default()
        color = XoColor(client.get_string('/desktop/sugar/user/color'))

        if model.is_school_server_present():
            self._add_remote_share_button(_('School-Server Shares'),
                                          model.SCHOOL_SERVER_IP_ADDRESS_OR_DNS_NAME,
                                          color, SHARE_TYPE_SCHOOL_SERVER)

        volume_monitor = Gio.VolumeMonitor.get()
        self._mount_added_hid = volume_monitor.connect('mount-added',
                                                       self.__mount_added_cb)
        self._mount_removed_hid = volume_monitor.connect('mount-removed',
            self.__mount_removed_cb)

        for mount in volume_monitor.get_mounts():
            self._add_button(mount)

    def _set_up_directory_button(self, dir_path, icon_name, label_text):
        if dir_path is not None:
            button = DirectoryButton(dir_path, icon_name)
            button.props.group = self._volume_buttons[0]
            label = GLib.markup_escape_text(label_text)
            button.set_palette(Palette(label))
            button.connect('toggled', self._button_toggled_cb)
            button.show()

            position = self.get_item_index(self._volume_buttons[-1]) + 1
            self.insert(button, position)
            self._volume_buttons.append(button)
            self.show()

    def _set_up_documents_button(self):
        documents_path = model.get_documents_path()
        self._set_up_directory_button(documents_path,
                                      'user-documents',
                                      _('Documents'))

    def _set_up_local_shares_button(self):
        local_shares_path = model.LOCAL_SHARES_MOUNT_POINT
        self._set_up_directory_button(local_shares_path,
                                      'emblem-neighborhood-shared',
                                      _('Local Shares'))

    def _add_remote_share_button(self, primary_text,
                                 ip_address_or_dns_name, color,
                                 share_type):
        button = RemoteSharesButton(primary_text, ip_address_or_dns_name,
                                    color, share_type)
        button._share_type = share_type
        button.props.group = self._volume_buttons[0]

        show_unmount_option = None
        if share_type == SHARE_TYPE_PEER:
            show_unmount_option = True
        else:
            show_unmount_option = False
        button.set_palette(RemoteSharePalette(primary_text,
                           ip_address_or_dns_name, button,
                           show_unmount_option))
        button.connect('toggled', self._button_toggled_cb)
        button.show()

        position = self.get_item_index(self._volume_buttons[-1]) + 1
        self.insert(button, position)
        self._volume_buttons.append(button)
        self.show()

        return button

    def __mount_added_cb(self, volume_monitor, mount):
        self._add_button(mount)

    def __mount_removed_cb(self, volume_monitor, mount):
        self._remove_button(mount)

    def _add_button(self, mount):
        logging.debug('VolumeToolbar._add_button: %r', mount.get_name())

        if os.path.exists(os.path.join(mount.get_root().get_path(),
                                       _JOURNAL_0_METADATA_DIR)):
            logging.debug('Convert DS-0 Journal entries: starting conversion')
            GObject.idle_add(_convert_entries, mount.get_root().get_path())

        button = VolumeButton(mount)
        button.props.group = self._volume_buttons[0]
        button.connect('toggled', self._button_toggled_cb)
        button.connect('volume-error', self.__volume_error_cb)
        position = self.get_item_index(self._volume_buttons[-1]) + 1
        self.insert(button, position)
        button.show()

        self._volume_buttons.append(button)

        if len(self.get_children()) > 1:
            self.show()

    def __volume_error_cb(self, button, strerror, severity):
        self.emit('volume-error', strerror, severity)

    def _button_toggled_cb(self, button, force_toggle=False):
        if button.props.active or force_toggle:
            button.set_active(True)
            from jarabe.journal.journalactivity import get_journal
            journal = get_journal()

            journal.hide_alert()
            journal.get_list_view()._selected_entries = 0
            journal.switch_to_editing_mode(False)
            journal.get_list_view().inhibit_refresh(False)

            self.emit('volume-changed', button.mount_point)

    def _unmount_activated_cb(self, menu_item, mount):
        logging.debug('VolumesToolbar._unmount_activated_cb: %r', mount)
        mount.unmount(self.__unmount_cb)

    def __unmount_cb(self, source, result):
        logging.debug('__unmount_cb %r %r', source, result)

    def _get_button_for_mount(self, mount):
        mount_point = mount.get_root().get_path()
        for button in self.get_children():
            if button.mount_point == mount_point:
                return button
        logging.error('Couldnt find button with mount_point %r', mount_point)
        return None

    def _get_button_for_mount_point(self, mount_point):
        for button in self.get_children():
            if button.mount_point == mount_point:
                return button
        logging.error('Couldnt find button with mount_point %r', mount_point)
        return None

    def _remove_button(self, mount):
        button = self._get_button_for_mount(mount)
        self._volume_buttons.remove(button)
        self.remove(button)
        self.get_children()[0].props.active = True

        if len(self.get_children()) < 2:
            self.hide()

    def _remove_remote_share_button(self, ip_address_or_dns_name):
        for button in self.get_children():
            if type(button) == RemoteSharesButton and \
                    button.mount_point == (model.WEBDAV_MOUNT_POINT + ip_address_or_dns_name):
                        self._volume_buttons.remove(button)
                        self.remove(button)

                        from jarabe.journal.webdavmanager import \
                                unmount_share_from_backend
                        unmount_share_from_backend(ip_address_or_dns_name)

                        self.get_children()[0].props.active = True

                        if len(self.get_children()) < 2:
                            self.hide()
                        break;

    def set_active_volume(self, mount):
        button = self._get_button_for_mount(mount)
        button.props.active = True

    def get_journal_button(self):
        return self._volume_buttons[0]

    def get_button_toggled_cb(self):
        return self._button_toggled_cb


class BaseButton(RadioToolButton):
    __gsignals__ = {
        'volume-error': (GObject.SignalFlags.RUN_FIRST, None,
                         ([str, str])),
    }

    def __init__(self, mount_point):
        RadioToolButton.__init__(self)

        self.mount_point = mount_point

        self.drag_dest_set(Gtk.DestDefaults.ALL,
                           [Gtk.TargetEntry.new('journal-object-id', 0, 0)],
                           Gdk.DragAction.COPY)
        self.connect('drag-data-received', self._drag_data_received_cb)

    def _drag_data_received_cb(self, widget, drag_context, x, y,
                               selection_data, info, timestamp):
        # Disallow copying to mounted-shares for peers.
        if (model.is_mount_point_for_locally_mounted_remote_share(self.mount_point)) and \
           (model.is_mount_point_for_peer_share(self.mount_point)):
            from jarabe.journal.journalactivity import get_journal

            journal = get_journal()
            journal._show_alert(_('Entries cannot be copied to Peer-Shares.'), _('Error'))
            return

        object_id = selection_data.get_data()
        metadata = model.get(object_id)

        from jarabe.journal.palettes import CopyMenu, get_copy_menu_helper
        copy_menu_helper = get_copy_menu_helper()

        dummy_copy_menu = CopyMenu()
        copy_menu_helper.insert_copy_to_menu_items(dummy_copy_menu,
                                                   [metadata],
                                                   False,
                                                   False,
                                                   False)

        # Now, activate the menuitem, whose mount-point matches the
        # mount-point of the button, upon whom the item has been
        # dragged.
        children_menu_items = dummy_copy_menu.get_children()
        for child in children_menu_items:
            if child.get_mount_point() == self.mount_point:
                child.activate()
                return


class VolumeButton(BaseButton):
    def __init__(self, mount):
        self._mount = mount
        mount_point = mount.get_root().get_path()
        BaseButton.__init__(self, mount_point)

        icon_name = None
        icon_theme = Gtk.IconTheme.get_default()
        for icon_name in mount.get_icon().props.names:
            icon_info = icon_theme.lookup_icon(icon_name,
                                               Gtk.IconSize.LARGE_TOOLBAR, 0)
            if icon_info is not None:
                break

        if icon_name is None:
            icon_name = 'drive'

        self.props.icon_name = icon_name

        # TODO: retrieve the colors from the owner of the device
        client = GConf.Client.get_default()
        color = XoColor(client.get_string('/desktop/sugar/user/color'))
        self.props.xo_color = color

    def create_palette(self):
        palette = JournalVolumePalette(self._mount)
        #palette.props.invoker = FrameWidgetInvoker(self)
        #palette.set_group_id('frame')
        return palette


class JournalButton(BaseButton):
    def __init__(self):
        BaseButton.__init__(self, mount_point='/')

        self.props.icon_name = 'activity-journal'

        client = GConf.Client.get_default()
        color = XoColor(client.get_string('/desktop/sugar/user/color'))
        self.props.xo_color = color

    def create_palette(self):
        palette = JournalButtonPalette(self)
        return palette


class JournalButtonPalette(Palette):

    def __init__(self, mount):
        Palette.__init__(self, GLib.markup_escape_text(_('Journal')))
        vbox = Gtk.VBox()
        self.set_content(vbox)
        vbox.show()

        self._progress_bar = Gtk.ProgressBar()
        vbox.add(self._progress_bar)
        self._progress_bar.show()

        self._free_space_label = Gtk.Label()
        self._free_space_label.set_alignment(0.5, 0.5)
        vbox.add(self._free_space_label)
        self._free_space_label.show()

        self.connect('popup', self.__popup_cb)

    def __popup_cb(self, palette):
        stat = os.statvfs(env.get_profile_path())
        free_space = stat[statvfs.F_BSIZE] * stat[statvfs.F_BAVAIL]
        total_space = stat[statvfs.F_BSIZE] * stat[statvfs.F_BLOCKS]

        fraction = (total_space - free_space) / float(total_space)
        self._progress_bar.props.fraction = fraction
        self._free_space_label.props.label = _('%(free_space)d MB Free') % \
                {'free_space': free_space / (1024 * 1024)}


class DirectoryButton(BaseButton):

    def __init__(self, dir_path, icon_name):
        BaseButton.__init__(self, mount_point=dir_path)
        self._mount = dir_path

        self.props.icon_name = icon_name

        client = GConf.Client.get_default()
        color = XoColor(client.get_string('/desktop/sugar/user/color'))
        self.props.xo_color = color


class RemoteSharesButton(BaseButton):

    def __init__(self, primary_text, ip_address_or_dns_name, color,
                 share_type):
        BaseButton.__init__(self, mount_point=(model.WEBDAV_MOUNT_POINT + ip_address_or_dns_name))

        self._primary_text = primary_text
        self._ip_address_or_dns_name = ip_address_or_dns_name

        if share_type == SHARE_TYPE_PEER:
            self.props.icon_name = 'emblem-neighborhood-shared'
        elif share_type == SHARE_TYPE_SCHOOL_SERVER:
            self.props.icon_name = 'school-server'
        self.props.xo_color = color

    def create_palette(self):
        palette = RemoteSharePalette(self._primary_text, self._ip_address_or_dns_name,
                                     self, True)
        return palette
