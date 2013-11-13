# Copyright (C) 2007-2011, One Laptop per Child
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
import stat
import errno
import subprocess
from datetime import datetime
import time
import shutil
import tempfile
from stat import S_IFLNK, S_IFMT, S_IFDIR, S_IFREG
import re
from operator import itemgetter
import simplejson
from gettext import gettext as _

from gi.repository import GObject
import dbus
from gi.repository import Gio
from gi.repository import GConf

from gi.repository import SugarExt

from sugar3 import dispatch
from sugar3 import mime
from sugar3 import util

from jarabe.journal import webdavmanager


DS_DBUS_SERVICE = 'org.laptop.sugar.DataStore'
DS_DBUS_INTERFACE = 'org.laptop.sugar.DataStore'
DS_DBUS_PATH = '/org/laptop/sugar/DataStore'

# Properties the journal cares about.
PROPERTIES = ['activity', 'activity_id', 'buddies', 'bundle_id',
              'creation_time', 'filesize', 'icon-color', 'keep', 'mime_type',
              'mountpoint', 'mtime', 'progress', 'timestamp', 'title', 'uid']

MIN_PAGES_TO_CACHE = 3
MAX_PAGES_TO_CACHE = 5

WEBDAV_MOUNT_POINT   = '/tmp/'
LOCAL_SHARES_MOUNT_POINT = '/var/www/web1/web/'

JOURNAL_METADATA_DIR = '.Sugar-Metadata'

LIST_VIEW = 1
DETAIL_VIEW = 2

_datastore = None
created = dispatch.Signal()
updated = dispatch.Signal()
deleted = dispatch.Signal()


SCHOOL_SERVER_IP_ADDRESS_OR_DNS_NAME_PATH = \
        '/desktop/sugar/network/school_server_ip_address_or_dns_name'
IS_PEER_TO_PEER_SHARING_AVAILABLE_PATH    = \
        '/desktop/sugar/network/is_peer_to_peer_sharing_available'

client = GConf.Client.get_default()
SCHOOL_SERVER_IP_ADDRESS_OR_DNS_NAME = client.get_string(SCHOOL_SERVER_IP_ADDRESS_OR_DNS_NAME_PATH) or ''
IS_PEER_TO_PEER_SHARING_AVAILABLE    = client.get_bool(IS_PEER_TO_PEER_SHARING_AVAILABLE_PATH)



def is_school_server_present():
    return not (SCHOOL_SERVER_IP_ADDRESS_OR_DNS_NAME is '')


def is_peer_to_peer_sharing_available():
    return IS_PEER_TO_PEER_SHARING_AVAILABLE == True


def _get_mount_point(path):
    dir_path = os.path.dirname(path)
    while dir_path:
        if os.path.ismount(dir_path):
            return dir_path
        else:
            dir_path = dir_path.rsplit(os.sep, 1)[0]
    return None


def _check_remote_sharing_mount_point(mount_point, share_type):
    from jarabe.journal.journalactivity import get_journal

    mount_point_button = get_journal().get_volumes_toolbar()._get_button_for_mount_point(mount_point)
    if mount_point_button._share_type == share_type:
        return True
    return False


def is_mount_point_for_school_server(mount_point):
    from jarabe.journal.volumestoolbar import SHARE_TYPE_SCHOOL_SERVER
    return _check_remote_sharing_mount_point(mount_point, SHARE_TYPE_SCHOOL_SERVER)


def is_mount_point_for_peer_share(mount_point):
    from jarabe.journal.volumestoolbar import SHARE_TYPE_PEER
    return _check_remote_sharing_mount_point(mount_point, SHARE_TYPE_PEER)

def mount_point_button_exists(mount_point):
    from jarabe.journal.journalactivity import get_journal

    mount_point_button = get_journal().get_volumes_toolbar()._get_button_for_mount_point(mount_point)
    return mount_point_button is not None

def is_current_mount_point_for_remote_share(view_type):
    from jarabe.journal.journalactivity import get_journal, get_mount_point
    if view_type == LIST_VIEW:
        current_mount_point = get_mount_point()
    elif view_type == DETAIL_VIEW:
        current_mount_point = get_journal().get_detail_toolbox().get_mount_point()

    if is_mount_point_for_locally_mounted_remote_share(current_mount_point):
        return True
    return False


def extract_ip_address_or_dns_name_from_locally_mounted_remote_share_path(path):
    """
    Path is of type ::

        /tmp/1.2.3.4/webdav/a.txt; OR
        /tmp/this.is.dns.name/a.txt
    """
    return path.split('/')[2]


def is_mount_point_for_locally_mounted_remote_share(mount_point):
    """
    The mount-point can be either of the ip-Address, or the DNS name.
    More importantly, whatever the "name" be, it does NOT have a
    forward-slash.
    """
    return mount_point.find(WEBDAV_MOUNT_POINT) == 0


class _Cache(object):

    __gtype_name__ = 'model_Cache'

    def __init__(self, entries=None):
        self._array = []
        if entries is not None:
            self.append_all(entries)

    def prepend_all(self, entries):
        self._array[0:0] = entries

    def append_all(self, entries):
        self._array += entries

    def __len__(self):
        return len(self._array)

    def __getitem__(self, key):
        return self._array[key]

    def __delitem__(self, key):
        del self._array[key]


class BaseResultSet(object):
    """Encapsulates the result of a query
    """

    def __init__(self, query, page_size):
        self._total_count = -1
        self._position = -1
        self._query = query
        self._page_size = page_size

        self._offset = 0
        self._cache = _Cache()

        self.ready = dispatch.Signal()
        self.progress = dispatch.Signal()

    def setup(self):
        self.ready.send(self)

    def stop(self):
        pass

    def get_length(self):
        if self._total_count == -1:
            query = self._query.copy()
            query['limit'] = self._page_size * MIN_PAGES_TO_CACHE
            entries, self._total_count = self.find(query)
            self._cache.append_all(entries)
            self._offset = 0
        return self._total_count

    length = property(get_length)

    def find(self, query):
        raise NotImplementedError()

    def seek(self, position):
        self._position = position

    def read(self):
        if self._position == -1:
            self.seek(0)

        if self._position < self._offset:
            remaining_forward_entries = 0
        else:
            remaining_forward_entries = self._offset + len(self._cache) - \
                                        self._position

        if self._position > self._offset + len(self._cache):
            remaining_backwards_entries = 0
        else:
            remaining_backwards_entries = self._position - self._offset

        last_cached_entry = self._offset + len(self._cache)

        if remaining_forward_entries <= 0 and remaining_backwards_entries <= 0:

            # Total cache miss: remake it
            limit = self._page_size * MIN_PAGES_TO_CACHE
            offset = max(0, self._position - limit / 2)
            logging.debug('remaking cache, offset: %r limit: %r', offset,
                limit)
            query = self._query.copy()
            query['limit'] = limit
            query['offset'] = offset
            entries, self._total_count = self.find(query)

            del self._cache[:]
            self._cache.append_all(entries)
            self._offset = offset

        elif (remaining_forward_entries <= 0 and
              remaining_backwards_entries > 0):

            # Add one page to the end of cache
            logging.debug('appending one more page, offset: %r',
                last_cached_entry)
            query = self._query.copy()
            query['limit'] = self._page_size
            query['offset'] = last_cached_entry
            entries, self._total_count = self.find(query)

            # update cache
            self._cache.append_all(entries)

            # apply the cache limit
            cache_limit = self._page_size * MAX_PAGES_TO_CACHE
            objects_excess = len(self._cache) - cache_limit
            if objects_excess > 0:
                self._offset += objects_excess
                del self._cache[:objects_excess]

        elif remaining_forward_entries > 0 and \
                remaining_backwards_entries <= 0 and self._offset > 0:

            # Add one page to the beginning of cache
            limit = min(self._offset, self._page_size)
            self._offset = max(0, self._offset - limit)

            logging.debug('prepending one more page, offset: %r limit: %r',
                self._offset, limit)
            query = self._query.copy()
            query['limit'] = limit
            query['offset'] = self._offset
            entries, self._total_count = self.find(query)

            # update cache
            self._cache.prepend_all(entries)

            # apply the cache limit
            cache_limit = self._page_size * MAX_PAGES_TO_CACHE
            objects_excess = len(self._cache) - cache_limit
            if objects_excess > 0:
                del self._cache[-objects_excess:]

        return self._cache[self._position - self._offset]

    def is_favorite_compatible(self, metadata):
        if self._favorite == '0':
            return True

        return ((metadata is not None) and \
                ('keep' in metadata.keys()) and \
                (str(metadata['keep']) == '1'))


class DatastoreResultSet(BaseResultSet):
    """Encapsulates the result of a query on the datastore
    """
    def __init__(self, query, page_size):

        if query.get('query', '') and not query['query'].startswith('"'):
            query_text = ''
            words = query['query'].split(' ')
            for word in words:
                if word:
                    if query_text:
                        query_text += ' '
                    query_text += word + '*'

            query['query'] = query_text

        BaseResultSet.__init__(self, query, page_size)

    def find(self, query):
        entries, total_count = _get_datastore().find(query, PROPERTIES,
                                                     byte_arrays=True)

        for entry in entries:
            entry['mountpoint'] = '/'

        return entries, total_count


class InplaceResultSet(BaseResultSet):
    """Encapsulates the result of a query on a mount point
    """
    def __init__(self, query, page_size, mount_point):
        BaseResultSet.__init__(self, query, page_size)
        self._mount_point = mount_point
        self._file_list = None
        self._pending_directories = []
        self._visited_directories = []
        self._pending_files = []
        self._stopped = False

        query_text = query.get('query', '')
        if query_text.startswith('"') and query_text.endswith('"'):
            self._regex = re.compile('*%s*' % query_text.strip(['"']))
        elif query_text:
            expression = ''
            for word in query_text.split(' '):
                expression += '(?=.*%s.*)' % word
            self._regex = re.compile(expression, re.IGNORECASE)
        else:
            self._regex = None

        if query.get('timestamp', ''):
            self._date_start = int(query['timestamp']['start'])
            self._date_end = int(query['timestamp']['end'])
        else:
            self._date_start = None
            self._date_end = None

        self._mime_types = query.get('mime_type', [])

        self._sort = query.get('order_by', ['+timestamp'])[0]

        self._favorite = str(query.get('keep', 0))

    def setup(self):
        self._file_list = []
        self._pending_directories = [self._mount_point]
        self._visited_directories = []
        self._pending_files = []
        GObject.idle_add(self._scan)

    def stop(self):
        self._stopped = True

    def setup_ready(self):
        if self._sort[1:] == 'filesize':
            keygetter = itemgetter(3)
        else:
            # timestamp
            keygetter = itemgetter(2)
        self._file_list.sort(lambda a, b: cmp(b, a),
                             key=keygetter,
                             reverse=(self._sort[0] == '-'))
        self.ready.send(self)

    def find(self, query):
        if self._file_list is None:
            raise ValueError('Need to call setup() first')

        if self._stopped:
            raise ValueError('InplaceResultSet already stopped')

        t = time.time()

        offset = int(query.get('offset', 0))
        limit = int(query.get('limit', len(self._file_list)))
        total_count = len(self._file_list)

        files = self._file_list[offset:offset + limit]

        entries = []
        for file_path, stat, mtime_, size_, metadata in files:
            if metadata is None:
                metadata = _get_file_metadata(file_path, stat)
            metadata['mountpoint'] = self._mount_point
            entries.append(metadata)

        logging.debug('InplaceResultSet.find took %f s.', time.time() - t)

        return entries, total_count

    def _scan(self):
        if self._stopped:
            return False

        self.progress.send(self)

        if self._pending_files:
            self._scan_a_file()
            return True

        if self._pending_directories:
            self._scan_a_directory()
            return True

        self.setup_ready()
        self._visited_directories = []
        return False

    def _scan_a_file(self):
        full_path = self._pending_files.pop(0)
        metadata = None

        try:
            stat = os.lstat(full_path)
        except OSError, e:
            if e.errno != errno.ENOENT:
                logging.exception(
                    'Error reading metadata of file %r', full_path)
            return

        if S_IFMT(stat.st_mode) == S_IFLNK:
            try:
                link = os.readlink(full_path)
            except OSError, e:
                logging.exception(
                    'Error reading target of link %r', full_path)
                return

            if not os.path.abspath(link).startswith(self._mount_point):
                return

            try:
                stat = os.stat(full_path)

            except OSError, e:
                if e.errno != errno.ENOENT:
                    logging.exception(
                        'Error reading metadata of linked file %r', full_path)
                return

        if S_IFMT(stat.st_mode) == S_IFDIR:
            id_tuple = stat.st_ino, stat.st_dev
            if not id_tuple in self._visited_directories:
                self._visited_directories.append(id_tuple)
                self._pending_directories.append(full_path)
            return

        if S_IFMT(stat.st_mode) != S_IFREG:
            return

        metadata = _get_file_metadata(full_path, stat,
                                      fetch_preview=False)

        if not self.is_favorite_compatible(metadata):
            return
        if self._regex is not None and \
                not self._regex.match(full_path):
            if not metadata:
                return
            add_to_list = False
            for f in ['fulltext', 'title',
                      'description', 'tags']:
                if f in metadata and \
                        self._regex.match(metadata[f]):
                    add_to_list = True
                    break
            if not add_to_list:
                return

        if self._date_start is not None and stat.st_mtime < self._date_start:
            return

        if self._date_end is not None and stat.st_mtime > self._date_end:
            return

        if self._mime_types:
            mime_type, uncertain_result_ = \
                    Gio.content_type_guess(filename=full_path, data=None)
            if mime_type not in self._mime_types:
                return

        file_info = (full_path, stat, int(stat.st_mtime), stat.st_size,
                     metadata)
        self._file_list.append(file_info)

        return

    def _scan_a_directory(self):
        dir_path = self._pending_directories.pop(0)

        try:
            entries = os.listdir(dir_path)
        except OSError, e:
            if e.errno != errno.EACCES:
                logging.exception('Error reading directory %r', dir_path)
            return

        for entry in entries:
            if entry.startswith('.'):
                continue
            self._pending_files.append(dir_path + '/' + entry)
        return


class RemoteShareResultSet(BaseResultSet):
    def __init__(self, ip_address_or_dns_name, query):
        self._ip_address_or_dns_name = ip_address_or_dns_name
        self._file_list = []

        self.ready = dispatch.Signal()
        self.progress = dispatch.Signal()

        # First time, query is none.
        if query is None:
            return

        query_text = query.get('query', '')
        if query_text.startswith('"') and query_text.endswith('"'):
            self._regex = re.compile('*%s*' % query_text.strip(['"']))
        elif query_text:
            expression = ''
            for word in query_text.split(' '):
                expression += '(?=.*%s.*)' % word
            self._regex = re.compile(expression, re.IGNORECASE)
        else:
            self._regex = None

        if query.get('timestamp', ''):
            self._date_start = int(query['timestamp']['start'])
            self._date_end = int(query['timestamp']['end'])
        else:
            self._date_start = None
            self._date_end = None

        self._mime_types = query.get('mime_type', [])

        self._sort = query.get('order_by', ['+timestamp'])[0]

        self._favorite = str(query.get('keep', 0))

    def setup(self):
        try:
            metadata_list_complete = webdavmanager.get_remote_webdav_share_metadata(self._ip_address_or_dns_name)
        except Exception, e:
            metadata_list_complete = []

        for metadata in metadata_list_complete:

            if not self.is_favorite_compatible(metadata):
                continue

            add_to_list = False
            if self._regex is not None:
                for f in ['fulltext', 'title',
                          'description', 'tags']:
                    if f in metadata and \
                            self._regex.match(metadata[f]):
                        add_to_list = True
                        break
            else:
                add_to_list = True
            if not add_to_list:
                continue

            add_to_list = False
            if self._date_start is not None:
                if metadata['timestamp'] > self._date_start:
                    add_to_list = True
            else:
                add_to_list = True
            if not add_to_list:
                continue

            add_to_list = False
            if self._date_end is not None:
                if metadata['timestamp'] < self._date_end:
                    add_to_list = True
            else:
                add_to_list = True
            if not add_to_list:
                continue

            add_to_list = False
            if self._mime_types:
                mime_type = metadata['mime_type']
                if mime_type in self._mime_types:
                    add_to_list = True
            else:
                add_to_list = True
            if not add_to_list:
                continue

            # If control reaches here, the current metadata has passed
            # out all filter-tests.
            file_info = (metadata['timestamp'],
                         metadata['creation_time'],
                         metadata['filesize'],
                         metadata)
            self._file_list.append(file_info)

        if self._sort[1:] == 'filesize':
            keygetter = itemgetter(2)
        elif self._sort[1:] == 'creation_time':
            keygetter = itemgetter(1)
        else:
            # timestamp
            keygetter = itemgetter(0)

        self._file_list.sort(lambda a, b: cmp(b, a),
                             key=keygetter,
                             reverse=(self._sort[0] == '-'))

        self.ready.send(self)

    def get_length(self):
        return len(self._file_list)

    length = property(get_length)

    def seek(self, position):
        self._position = position

    def read(self):
        modified_timestamp, creation_timestamp, filesize, metadata =  self._file_list[self._position]
        return  metadata

    def stop(self):
        self._stopped = True


def _get_file_metadata(path, stat, fetch_preview=True):
    """Return the metadata from the corresponding file.

    Reads the metadata stored in the json file or create the
    metadata based on the file properties.

    """
    filename = os.path.basename(path)
    dir_path = os.path.dirname(path)
    metadata = _get_file_metadata_from_json(dir_path, filename, fetch_preview)
    if metadata:
        if 'filesize' not in metadata:
            if stat is not None:
                metadata['filesize'] = stat.st_size
        return metadata

    if stat is None:
        raise ValueError('File does not exist')

    mime_type, uncertain_result_ = Gio.content_type_guess(filename=path,
                                                          data=None)
    return {'uid': path,
            'title': os.path.basename(path),
            'timestamp': stat.st_mtime,
            'filesize': stat.st_size,
            'mime_type': mime_type,
            'activity': '',
            'activity_id': '',
            'icon-color': '#000000,#ffffff',
            'description': path}


def _get_file_metadata_from_json(dir_path, filename, fetch_preview):
    """Read the metadata from the json file and the preview
    stored on the external device.

    If the metadata is corrupted we do remove it and the preview as well.

    """

    # In case of nested mount-points, (eg. ~/Documents/in1/in2/in3.txt),
    # "dir_path = ~/Documents/in1/in2"; while
    # "metadata_dir_path = ~/Documents".
    from jarabe.journal.journalactivity import get_mount_point
    metadata_dir_path = get_mount_point()

    metadata = None
    metadata_path = os.path.join(metadata_dir_path, JOURNAL_METADATA_DIR,
                                 filename + '.metadata')
    preview_path = os.path.join(metadata_dir_path, JOURNAL_METADATA_DIR,
                                filename + '.preview')

    if not os.path.exists(metadata_path):
        return None

    try:
        metadata = simplejson.load(open(metadata_path))
    except (ValueError, EnvironmentError):
        os.unlink(metadata_path)
        if os.path.exists(preview_path):
            os.unlink(preview_path)
        logging.error('Could not read metadata for file %r on '
                      'external device.', filename)
        return None
    else:
        metadata['uid'] = os.path.join(dir_path, filename)

    if not fetch_preview:
        if 'preview' in metadata:
            del(metadata['preview'])
    else:
        if os.path.exists(preview_path):
            try:
                metadata['preview'] = dbus.ByteArray(open(preview_path).read())
            except EnvironmentError:
                logging.debug('Could not read preview for file %r on '
                              'external device.', filename)

    return metadata


def _get_datastore():
    global _datastore
    if _datastore is None:
        bus = dbus.SessionBus()
        remote_object = bus.get_object(DS_DBUS_SERVICE, DS_DBUS_PATH)
        _datastore = dbus.Interface(remote_object, DS_DBUS_INTERFACE)

        _datastore.connect_to_signal('Created', _datastore_created_cb)
        _datastore.connect_to_signal('Updated', _datastore_updated_cb)
        _datastore.connect_to_signal('Deleted', _datastore_deleted_cb)

    return _datastore


def _datastore_created_cb(object_id):
    created.send(None, object_id=object_id)


def _datastore_updated_cb(object_id):
    updated.send(None, object_id=object_id)


def _datastore_deleted_cb(object_id):
    deleted.send(None, object_id=object_id)


def find(query_, page_size):
    """Returns a ResultSet
    """
    query = query_.copy()

    mount_points = query.pop('mountpoints', ['/'])
    if mount_points is None or len(mount_points) != 1:
        raise ValueError('Exactly one mount point must be specified')

    if mount_points[0] == '/':
        return DatastoreResultSet(query, page_size)
    elif is_mount_point_for_locally_mounted_remote_share(mount_points[0]):
        ip_address = extract_ip_address_or_dns_name_from_locally_mounted_remote_share_path(mount_points[0])
        return RemoteShareResultSet(ip_address, query)
    else:
        return InplaceResultSet(query, page_size, mount_points[0])


def _get_mount_point(path):
    dir_path = os.path.dirname(path)
    while dir_path:
        if os.path.ismount(dir_path):
            return dir_path
        else:
            dir_path = dir_path.rsplit(os.sep, 1)[0]
    return None


def get(object_id):
    """Returns the metadata for an object
    """
    if (object_id[0] == '/'):
        if os.path.exists(object_id):
            stat = os.stat(object_id)
        else:
            stat = None

        metadata = _get_file_metadata(object_id, stat)
        metadata['mountpoint'] = _get_mount_point(object_id)
    else:
        metadata = _get_datastore().get_properties(object_id, byte_arrays=True)
        metadata['mountpoint'] = '/'
    return metadata


def get_file(object_id):
    """Returns the file for an object
    """
    if os.path.exists(object_id):
        logging.debug('get_file asked for file with path %r', object_id)
        return object_id
    else:
        logging.debug('get_file asked for entry with id %r', object_id)
        file_path = _get_datastore().get_filename(object_id)
        if file_path:
            return util.TempFilePath(file_path)
        else:
            return None


def get_file_size(object_id):
    """Return the file size for an object
    """
    logging.debug('get_file_size %r', object_id)
    if os.path.exists(object_id):
        return os.stat(object_id).st_size

    file_path = _get_datastore().get_filename(object_id)
    if file_path:
        size = os.stat(file_path).st_size
        os.remove(file_path)
        return size

    return 0


def get_unique_values(key):
    """Returns a list with the different values a property has taken
    """
    empty_dict = dbus.Dictionary({}, signature='ss')
    return _get_datastore().get_uniquevaluesfor(key, empty_dict)


def delete(object_id):
    """Removes an object from persistent storage
    """
    if not os.path.exists(object_id):
        _get_datastore().delete(object_id)
    else:
        os.unlink(object_id)
        dir_path = os.path.dirname(object_id)
        filename = os.path.basename(object_id)
        old_files = [os.path.join(dir_path, JOURNAL_METADATA_DIR,
                                  filename + '.metadata'),
                     os.path.join(dir_path, JOURNAL_METADATA_DIR,
                                  filename + '.preview')]
        for old_file in old_files:
            if os.path.exists(old_file):
                try:
                    os.unlink(old_file)
                except EnvironmentError:
                    logging.error('Could not remove metadata=%s '
                                  'for file=%s', old_file, filename)
        deleted.send(None, object_id=object_id)


def copy(metadata, mount_point):
    """Copies an object to another mount point
    """
    # In all cases (except one), "copy" means the actual duplication of
    # the content.
    # Only in case of remote downloading, the content is first copied
    # to "/tmp" folder. In those cases, copying would refer to a mere
    # renaming.
    transfer_ownership = False

    from jarabe.journal.journalactivity import get_mount_point
    current_mount_point = get_mount_point()

    if is_mount_point_for_locally_mounted_remote_share(current_mount_point):
        transfer_ownership = True

    metadata = get(metadata['uid'])

    if mount_point == '/' and metadata['icon-color'] == '#000000,#ffffff':
        client = GConf.Client.get_default()
        metadata['icon-color'] = client.get_string('/desktop/sugar/user/color')
    file_path = get_file(metadata['uid'])
    if file_path is None:
        file_path = ''

    metadata['mountpoint'] = mount_point
    del metadata['uid']

    return write(metadata, file_path, transfer_ownership=transfer_ownership)


def write(metadata, file_path='', update_mtime=True, transfer_ownership=True):
    """Creates or updates an entry for that id
    """
    logging.debug('model.write %r %r %r', metadata.get('uid', ''), file_path,
        update_mtime)
    if update_mtime:
        metadata['mtime'] = datetime.now().isoformat()
        metadata['timestamp'] = int(time.time())

    if metadata.get('mountpoint', '/') == '/':
        if metadata.get('uid', ''):
            object_id = _get_datastore().update(metadata['uid'],
                                                 dbus.Dictionary(metadata),
                                                 file_path,
                                                 transfer_ownership)
        else:
            object_id = _get_datastore().create(dbus.Dictionary(metadata),
                                                 file_path,
                                                 transfer_ownership)
    elif metadata.get('mountpoint', '/') == (WEBDAV_MOUNT_POINT + SCHOOL_SERVER_IP_ADDRESS_OR_DNS_NAME):
        filename = get_file_name(metadata['title'], metadata['mime_type'])
        metadata['title'] = filename

        ip_address_or_dns_name = SCHOOL_SERVER_IP_ADDRESS_OR_DNS_NAME
        webdavmanager.get_remote_webdav_share_metadata(ip_address_or_dns_name)

        data_webdav_manager = \
                webdavmanager.get_data_webdav_manager(ip_address_or_dns_name)
        metadata_webdav_manager = \
                webdavmanager.get_metadata_webdav_manager(ip_address_or_dns_name)


        # If we get a resource by this name, there is already an entry
        # on the server with this name; we do not want to do any
        # overwrites.
        data_resource = webdavmanager.get_resource_by_resource_key(data_webdav_manager,
                '/webdav/' + filename)
        metadata_resource = webdavmanager.get_resource_by_resource_key(metadata_webdav_manager,
                '/webdav/.Sugar-Metadata/' + filename + '.metadata')
        if (data_resource is not None) or (metadata_resource is not None):
            raise Exception(_('Entry already present on the server with '
                              'this name. Try again after renaming.'))

        # No entry for this name present.
        # So, first write the metadata- and preview-file to temporary
        # locations.
        metadata_file_path, preview_file_path = \
                _write_metadata_and_preview_files_and_return_file_paths(metadata,
                                                                        filename)

        # Finally,
        # Upload the data file.
        webdavmanager.add_resource_by_resource_key(data_webdav_manager,
                                                   filename,
                                                   file_path)

        # Upload the preview file.
        if preview_file_path is not None:
            webdavmanager.add_resource_by_resource_key(metadata_webdav_manager,
                                                       filename + '.preview',
                                                       preview_file_path)

        # Upload the metadata file.
        #
        # Note that this needs to be the last step. If there was any
        # error uploading the data- or the preview-file, control would
        # not reach here.
        #
        # In other words, the control reaches here only if the data-
        # and the preview- files have been uploaded. Finally, IF this
        # file is successfully uploaded, we have the guarantee that all
        # files for a particular journal entry are in place.
        webdavmanager.add_resource_by_resource_key(metadata_webdav_manager,
                                                   filename + '.metadata',
                                                   metadata_file_path)


        object_id = 'doesn\'t matter'

    else:
        object_id = _write_entry_on_external_device(metadata,
                                                    file_path,
                                                    transfer_ownership)

    return object_id


def make_file_fully_permissible(file_path):
    fd = os.open(file_path, os.O_RDONLY)
    os.fchmod(fd, stat.S_IRWXU | stat.S_IRWXG |stat.S_IRWXO)
    os.close(fd)


def _rename_entry_on_external_device(file_path, destination_path):
    """Rename an entry with the associated metadata on an external device."""
    old_file_path = file_path
    if old_file_path != destination_path:
        # Strangely, "os.rename" works fine on sugar-jhbuild, but fails
        # on XOs, wih the OSError 13 ("invalid cross-device link"). So,
        # using the system call "mv".
        os.system('mv "%s" "%s"' % (file_path, destination_path))
        make_file_fully_permissible(destination_path)


        # In renaming, we want to delete the metadata-, and preview-
        # files of the current mount-point, and not the destination
        # mount-point.
        # But we also need to ensure that the directory of
        # 'old_file_path' and 'destination_path' are not same.
        if os.path.dirname(old_file_path) == os.path.dirname(destination_path):
            return

        from jarabe.journal.journalactivity import get_mount_point

        # Also, as a special case, the metadata- and preview-files of
        # the remote-shares must never be deleted. For them, only the
        # data-file needs to be moved.
        if is_mount_point_for_locally_mounted_remote_share(get_mount_point()):
            return


        source_metadata_dir_path = get_mount_point() + '/.Sugar-Metadata'

        old_fname = os.path.basename(file_path)
        old_files = [os.path.join(source_metadata_dir_path,
                                  old_fname + '.metadata'),
                     os.path.join(source_metadata_dir_path,
                                  old_fname + '.preview')]
        for ofile in old_files:
            if os.path.exists(ofile):
                try:
                    os.unlink(ofile)
                except EnvironmentError:
                    logging.error('Could not remove metadata=%s '
                                  'for file=%s', ofile, old_fname)


def _write_metadata_and_preview_files_and_return_file_paths(metadata,
                                                            file_name):
    metadata_copy = metadata.copy()
    metadata_copy.pop('mountpoint', None)
    metadata_copy.pop('uid', None)


    # For copying to School-Server, we need to retain this  property.
    # Else wise, I have no idea why this property is being removed !!
    if (is_mount_point_for_locally_mounted_remote_share(metadata.get('mountpoint', '/')) == False) and \
       (metadata.get('mountpoint', '/') != LOCAL_SHARES_MOUNT_POINT):
        metadata_copy.pop('filesize', None)

    # For journal case, there is the special treatment.
    if metadata.get('mountpoint', '/') == '/':
        if metadata.get('uid', ''):
            object_id = _get_datastore().update(metadata['uid'],
                                                dbus.Dictionary(metadata),
                                                '',
                                                False)
        else:
            object_id = _get_datastore().create(dbus.Dictionary(metadata),
                                                '',
                                                False)
        return


    metadata_dir_path = os.path.join(metadata['mountpoint'],
                                     JOURNAL_METADATA_DIR)
    if not os.path.exists(metadata_dir_path):
        os.mkdir(metadata_dir_path)

    # Set the HIDDEN attrib even when the metadata directory already
    # exists for backward compatibility; but don't set it in ~/Documents
    if not metadata['mountpoint'] == get_documents_path():
        if not SugarExt.fat_set_hidden_attrib(metadata_dir_path):
            logging.error('Could not set hidden attribute on %s' %
                          (metadata_dir_path))

    preview = None
    if 'preview' in metadata_copy:
        preview = metadata_copy['preview']
        preview_fname = file_name + '.preview'
        metadata_copy.pop('preview', None)

    try:
        metadata_json = simplejson.dumps(metadata_copy)
    except (UnicodeDecodeError, EnvironmentError):
        logging.error('Could not convert metadata to json.')
    else:
        (fh, fn) = tempfile.mkstemp(dir=metadata['mountpoint'])
        os.write(fh, metadata_json)
        os.close(fh)
        os.rename(fn, os.path.join(metadata_dir_path, file_name + '.metadata'))

        if preview:
            (fh, fn) = tempfile.mkstemp(dir=metadata['mountpoint'])
            os.write(fh, preview)
            os.close(fh)
            os.rename(fn, os.path.join(metadata_dir_path, preview_fname))

    metadata_destination_path = os.path.join(metadata_dir_path, file_name + '.metadata')
    make_file_fully_permissible(metadata_destination_path)
    if preview:
        preview_destination_path =  os.path.join(metadata_dir_path, preview_fname)
        make_file_fully_permissible(preview_destination_path)
    else:
        preview_destination_path = None

    return (metadata_destination_path, preview_destination_path)


def update_only_metadata_and_preview_files_and_return_file_paths(metadata):
    file_name = metadata['title']
    _write_metadata_and_preview_files_and_return_file_paths(metadata,
                                                            file_name)


def _write_entry_on_external_device(metadata, file_path,
                                    transfer_ownership):
    """Create and update an entry copied from the
    DS to an external storage device.

    Besides copying the associated file a file for the preview
    and one for the metadata are stored in the hidden directory
    .Sugar-Metadata.

    This function handles renames of an entry on the
    external device and avoids name collisions. Renames are
    handled failsafe.

    """
    if 'uid' in metadata and os.path.exists(metadata['uid']):
        file_path = metadata['uid']

    if not file_path or not os.path.exists(file_path):
        raise ValueError('Entries without a file cannot be copied to '
                         'removable devices')

    if not metadata.get('title'):
        metadata['title'] = _('Untitled')
    file_name = get_file_name(metadata['title'], metadata['mime_type'])

    destination_path = os.path.join(metadata['mountpoint'], file_name)
    if destination_path != file_path:
        file_name = get_unique_file_name(metadata['mountpoint'], file_name)
        destination_path = os.path.join(metadata['mountpoint'], file_name)
        metadata['title'] = file_name

    _write_metadata_and_preview_files_and_return_file_paths(metadata,
                                                            file_name)

    if (os.path.dirname(destination_path) == os.path.dirname(file_path)) or \
       (transfer_ownership == True):
        _rename_entry_on_external_device(file_path, destination_path)
    else:
        shutil.copy(file_path, destination_path)
        make_file_fully_permissible(destination_path)

    object_id = destination_path
    created.send(None, object_id=object_id)

    return object_id


def get_file_name(title, mime_type):
    file_name = title

    # Invalid characters in VFAT filenames. From
    # http://en.wikipedia.org/wiki/File_Allocation_Table
    invalid_chars = ['/', '\\', ':', '*', '?', '"', '<', '>', '|', '\x7F']
    invalid_chars.extend([chr(x) for x in range(0, 32)])
    for char in invalid_chars:
        file_name = file_name.replace(char, '_')

    extension = mime.get_primary_extension(mime_type)
    if extension is not None and extension:
        extension = '.' + extension
        if not file_name.endswith(extension):
            file_name += extension

    return file_name


def get_unique_file_name(mount_point, file_name):
    if os.path.exists(os.path.join(mount_point, file_name)):
        i = 1
        name, extension = os.path.splitext(file_name)
        while len(file_name) <= 255:
            file_name = name + '_' + str(i) + extension
            if not os.path.exists(os.path.join(mount_point, file_name)):
                break
            i += 1

    return file_name


def is_editable(metadata):
    if metadata.get('mountpoint', '/') == '/':
        return True
    else:
        # sl#3605: Instead of relying on mountpoint property being
        #          present in the metadata, use journalactivity api.
        #          This would work seamlessly, as "Details View' is
        #          called, upon an entry in the context of a singular
        #          mount-point.
        from jarabe.journal.journalactivity import get_mount_point
        mount_point = get_mount_point()

        if is_mount_point_for_locally_mounted_remote_share(mount_point):
            return False
        return os.access(mount_point, os.W_OK)


def get_documents_path():
    """Gets the path of the DOCUMENTS folder

    If xdg-user-dir can not find the DOCUMENTS folder it returns
    $HOME, which we omit. xdg-user-dir handles localization
    (i.e. translation) of the filenames.

    Returns: Path to $HOME/DOCUMENTS or None if an error occurs
    """
    try:
        pipe = subprocess.Popen(['xdg-user-dir', 'DOCUMENTS'],
                                stdout=subprocess.PIPE)
        documents_path = os.path.normpath(pipe.communicate()[0].strip())
        if os.path.exists(documents_path) and \
                os.environ.get('HOME') != documents_path:
            return documents_path
    except OSError, exception:
        if exception.errno != errno.ENOENT:
            logging.exception('Could not run xdg-user-dir')
    return None
