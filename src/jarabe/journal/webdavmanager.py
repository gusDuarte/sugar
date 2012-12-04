from gettext import gettext as _

from gi.repository import GObject

import logging
import os
import sys

import simplejson
import shutil

from webdav.Connection import AuthorizationError, WebdavError
from webdav.WebdavClient import CollectionStorer

def get_key_from_resource(resource):
    return resource.path

class WebDavUrlManager(GObject.GObject):
    """
    This class holds all data, relevant to a WebDavUrl.

    One thing must be noted, that a valid WebDavUrl is the one which
    may contain zero or more resources (files), or zero or more
    collections (directories).

    Thus, following are valid WebDavUrls ::

        dav://1.2.3.4/webdav
        dav://1.2.3.4/webdav/dir_1
        dav://1.2.3.4/webdav/dir_1/dir_2

    but following are not ::

        dav://1.2.3.4/webdav/a.txt
        dav://1.2.3.4/webdav/dir_1/b.jpg
        dav://1.2.3.4/webdab/dir_1/dir_2/c.avi
    """

    def __init__(self, WebDavUrl, username, password):
        self._WebDavUrl = WebDavUrl
        self._username = username
        self._password = password

    def _get_key_from_resource(self, resource):
        return resource.path.encode(sys.getfilesystemencoding())

    def _get_number_of_collections(self):
        return len(self._remote_webdav_share_collections)

    def _get_root(self):
        return self._root

    def _get_resources_dict(self):
        return self._remote_webdav_share_resources

    def _get_collections_dict(self):
        return self._remote_webdav_share_collections

    def _get_resource_by_key(self, key):
        if key in self._remote_webdav_share_resources.keys():
            return self._remote_webdav_share_resources[key]['resource']
        return None

    def _add_or_replace_resource_by_key(self, key, resource):
        self._remote_webdav_share_resources[key] = {}
        self._remote_webdav_share_resources[key]['resource'] = resource

    def _get_metadata_list(self):
        metadata_list = []
        for key in self._remote_webdav_share_resources.keys():
            metadata_list.append(self._remote_webdav_share_resources[key]['metadata'])
        return metadata_list

    def _get_live_properties(self, resource_key):
        resource_container = self._remote_webdav_share_resources[resource_key]
        return resource_container['webdav-properties']

    def _fetch_resources_and_collections(self):
        webdavConnection = CollectionStorer(self._WebDavUrl, validateResourceNames=False)
        self._root = webdavConnection

        authFailures = 0
        while authFailures < 2:
            try:
                self._remote_webdav_share_resources = {}
                self._remote_webdav_share_collections = {}

                try:
                    self._collection_contents = webdavConnection.getCollectionContents()
                    for resource, properties in self._collection_contents:
                        try:
                            key = self._get_key_from_resource(resource)
                            selected_dict = None

                            if properties.getResourceType() == 'resource':
                                selected_dict = self._remote_webdav_share_resources
                            else:
                                selected_dict = self._remote_webdav_share_collections

                            selected_dict[key] = {}
                            selected_dict[key]['resource'] = resource
                            selected_dict[key]['webdav-properties'] = properties
                        except UnicodeEncodeError:
                            print("Cannot encode resource path or properties.")

                    return True

                except WebdavError, e:
                    # Note that, we need to deal with all errors,
                    # except "AuthorizationError", as that is not
                    # really an error from our perspective.
                    if not type(e) == AuthorizationError:
                        from jarabe.journal.journalactivity import get_journal

                        from jarabe.journal.palettes import USER_FRIENDLY_GENERIC_WEBDAV_ERROR_MESSAGE
                        error_message = USER_FRIENDLY_GENERIC_WEBDAV_ERROR_MESSAGE
                        get_journal()._volume_error_cb(None, error_message,_('Error'))

                        # Re-raise this error.
                        # Note that since this is not an
                        # "AuthorizationError", this will not be caught
                        # by the outer except-block. Instead, it will
                        # navigate all the way back up, and will report
                        # the error in the enclosing except block.
                        raise e

                    else:
                    # If this indeed is an Authorization Error,
                    # re-raise it, so that it is caught by the outer
                    # "except" block.
                        raise e


            except AuthorizationError, e:
                if self._username is None or self._password is None:
                    raise Exception("WebDav username or password is None. Please specify appropriate values.")

                if e.authType == "Basic":
                    webdavConnection.connection.addBasicAuthorization(self._username, self._password)
                elif e.authType == "Digest":
                    info = parseDigestAuthInfo(e.authInfo)
                    webdavConnection.connection.addDigestAuthorization(self._username, self._password, realm=info["realm"], qop=info["qop"], nonce=info["nonce"])
                else:
                    raise
                authFailures += 1

        return False

webdav_manager = {}

def get_data_webdav_manager(ip_address_or_dns_name):
    return webdav_manager[ip_address_or_dns_name]['data']


def get_metadata_webdav_manager(ip_address_or_dns_name):
    return webdav_manager[ip_address_or_dns_name]['metadata']


def get_resource_by_resource_key(root_webdav, key):
    resources_dict = root_webdav._get_resources_dict()
    if key in resources_dict.keys():
        resource_dict = resources_dict[key]
        resource = resource_dict['resource']
        return resource
    return None


def add_resource_by_resource_key(root_webdav, key,
                                 content_file_path):
    root = root_webdav._get_root()

    resource = root.addResource(key)

    # Procure the resource-lock.
    lockToken = resource.lock('olpc')

    input_stream = open(content_file_path)

    # Now, upload the data; but it's necessary to enclose this in a
    # try-except-finally block here, since we need to close the
    # input-stream, whatever may happen.
    try:
        resource.uploadFile(input_stream, lockToken)
        root_webdav._add_or_replace_resource_by_key(key, resource)
    except Exception, e:
        logging.exception(e)
        resource.delete(lockToken)
        raise e
    else:
        resource.unlock(lockToken)
    finally:
        input_stream.close()


def get_remote_webdav_share_metadata(ip_address_or_dns_name):
    protocol = 'davs://'
    root_webdav_url = '/webdav'
    complete_root_url = protocol + ip_address_or_dns_name + root_webdav_url

    root_webdav = WebDavUrlManager(complete_root_url, 'test', 'olpc')
    if root_webdav._fetch_resources_and_collections() is False:
        # Return empty metadata list.
        return []

    # Keep reference to the "WebDavUrlManager", keyed by IP-Address.
    global webdav_manager
    webdav_manager[ip_address_or_dns_name] = {}
    webdav_manager[ip_address_or_dns_name]['data'] = root_webdav


    # Assert that the number of collections is only one at this url
    # (i.e. only ".Sugar-Metadata" is present).
    assert root_webdav._get_number_of_collections() == 1

    root_sugar_metadata_url = root_webdav_url + '/.Sugar-Metadata'

    complete_root_sugar_metadata_url = protocol + ip_address_or_dns_name + root_sugar_metadata_url
    root_webdav_sugar_metadata = WebDavUrlManager(complete_root_sugar_metadata_url, 'test', 'olpc')
    if root_webdav_sugar_metadata._fetch_resources_and_collections() is False:
        # Return empty metadata list.
        return []

    webdav_manager[ip_address_or_dns_name]['metadata'] = root_webdav_sugar_metadata

    # assert that the number of collections is zero at this url.
    assert root_webdav_sugar_metadata._get_number_of_collections() == 0

    # Now. associate sugar-metadata with each of the "root-webdav"
    # resource.
    root_webdav_resources = root_webdav._get_resources_dict()
    root_webdav_sugar_metadata_resources = root_webdav_sugar_metadata._get_resources_dict()

    # Prepare the metadata-download folder.
    downloaded_data_root_dir = '/tmp/' + ip_address_or_dns_name
    downloaded_metadata_file_dir = downloaded_data_root_dir + '/.Sugar-Metadata'
    if os.path.isdir(downloaded_data_root_dir):
        shutil.rmtree(downloaded_data_root_dir)
    os.makedirs(downloaded_metadata_file_dir)

    metadata_list = []

    # Note that the presence of a resource in the metadata directory,
    # is the only assurance of the entry (and its constituents) being
    # present in entirety. Thus, always proceed taking the metadata as
    # the "key".
    for root_webdav_sugar_metadata_resource_name in root_webdav_sugar_metadata_resources.keys():
        """
        root_webdav_sugar_metadata_resource_name is of the type ::

            /webdav/.Sugar-Metadata/a.txt.metadata, OR
            /webdav/.Sugar-Metadata/a.txt.preview
        """

        # If this is a "preview" resource, continue forward, as we only
        # want the metadata list. The "preview" resources are anyways
        # already present in the manager DS.
        if root_webdav_sugar_metadata_resource_name.endswith('.preview'):
            continue

        split_tokens_array = root_webdav_sugar_metadata_resource_name.split('/')

        # This will provide us with "a.txt.metadata"
        sugar_metadata_basename = split_tokens_array[len(split_tokens_array) - 1]

        # This will provide us with "a.txt"
        basename = sugar_metadata_basename[0:sugar_metadata_basename.index('.metadata')]

        downloaded_metadata_file_path = downloaded_metadata_file_dir + '/' + sugar_metadata_basename
        metadata_resource = \
                root_webdav_sugar_metadata._get_resource_by_key(root_webdav_sugar_metadata_resource_name)
        metadata_resource.downloadFile(downloaded_metadata_file_path)


        # We need to download the preview-file as well at this stage,
        # so that it can be shown in the expanded entry.
        downloaded_preview_file_path = downloaded_metadata_file_dir + \
                                       '/' + basename + '.preview'
        root_webdav_sugar_preview_resource_name = \
                root_webdav_sugar_metadata_resource_name[0:root_webdav_sugar_metadata_resource_name.index('.metadata')] + \
                '.preview'
        preview_resource = \
                root_webdav_sugar_metadata._get_resource_by_key(root_webdav_sugar_preview_resource_name)
        if preview_resource is not None:
            preview_resource.downloadFile(downloaded_preview_file_path)


        file_pointer = open(downloaded_metadata_file_path)
        metadata = eval(file_pointer.read())
        file_pointer.close()

        # Fill in the missing metadata properties.
        # Note that the file is not physically present.
        metadata['uid'] = downloaded_data_root_dir + '/' + basename
        metadata['creation_time'] = metadata['timestamp']

        # Now, write this to the metadata-file, so that
        # webdav-properties get gelled into sugar-metadata.
        file_pointer = open(downloaded_metadata_file_path, 'w')
        file_pointer.write(simplejson.dumps(metadata))
        file_pointer.close()

        metadata_list.append(metadata)

    return metadata_list


def is_remote_webdav_loaded(ip_address_or_dns_name):
    return ip_address_or_dns_name in webdav_manager.keys()


def unmount_share_from_backend(ip_address_or_dns_name):
    if ip_address_or_dns_name in webdav_manager.keys():
        del webdav_manager[ip_address_or_dns_name]
