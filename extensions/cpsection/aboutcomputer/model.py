# Copyright (C) 2008 One Laptop Per Child
# Copyright (C) 2010 Plan Ceibal <comunidad@plan.ceibal.edu.uy>
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
#

import os
import logging
import re
import ConfigParser
import time
import subprocess
from gettext import gettext as _
import errno
from datetime import datetime

import dbus

from jarabe import config


_NM_SERVICE = 'org.freedesktop.NetworkManager'
_NM_PATH = '/org/freedesktop/NetworkManager'
_NM_IFACE = 'org.freedesktop.NetworkManager'
_NM_DEVICE_IFACE = 'org.freedesktop.NetworkManager.Device'
_NM_DEVICE_TYPE_WIFI = 2

_OFW_TREE = '/ofw'
_PROC_TREE = '/proc/device-tree'
_DMI_DIRECTORY = '/sys/class/dmi/id'
_SN = 'serial-number'
_MODEL = 'openprom/model'

_XO_1_0_LEASE_PATH = '/security/lease.sig'
_XO_1_5_LEASE_PATH = '/bootpart/boot/security/lease.sig'

_logger = logging.getLogger('ControlPanel - AboutComputer')
_not_available = _('Not available')


def get_aboutcomputer():
    msg = 'Serial Number: %s \nBuild Number: %s \nFirmware Number: %s \n' \
            % (get_serial_number(), get_build_number(), get_firmware_number())
    return msg


def print_aboutcomputer():
    print get_aboutcomputer()


def _get_lease_path():
    if os.path.exists(_XO_1_0_LEASE_PATH):
        return _XO_1_0_LEASE_PATH
    elif os.path.exists(_XO_1_5_LEASE_PATH):
        return _XO_1_5_LEASE_PATH
    else:
        return ''


def get_lease_days():
    lease_file = _read_file(_get_lease_path())
    if lease_file is None:
        return _not_available

    encoded_date = str(str.split(lease_file)[3])
    expiry_date = datetime.strptime(encoded_date
            , '%Y%m%dT%H%M%SZ')
    current_date = datetime.today()
    days_remaining = (expiry_date - current_date).days

    # TRANS: Do not translate %s
    str_days_remaining = _('%s days remaining' % str(days_remaining))
    return str_days_remaining


def get_serial_number():
    serial_no = None
    if os.path.exists(os.path.join(_OFW_TREE, _SN)):
        serial_no = _read_file(os.path.join(_OFW_TREE, _SN))
    elif os.path.exists(os.path.join(_PROC_TREE, _SN)):
        serial_no = _read_file(os.path.join(_PROC_TREE, _SN))
    if serial_no is None:
        serial_no = _not_available
    return serial_no


def print_serial_number():
    serial_no = get_serial_number()
    if serial_no is None:
        serial_no = _not_available
    print serial_no


def get_build_number():
    if os.path.isfile('/boot/olpc_build'):
        build_no = _read_file('/boot/olpc_build')
    elif os.path.isfile('/bootpart/olpc_build'):
        build_no = _read_file('/bootpart/olpc_build')

    if build_no is None:
        build_no = _read_file('/etc/redhat-release')

    if build_no is None:
        try:
            popen = subprocess.Popen(['lsb_release', '-ds'],
                                     stdout=subprocess.PIPE)
        except OSError, e:
            if e.errno != errno.ENOENT:
                raise
        else:
            build_no, stderr_ = popen.communicate()

    if build_no is None or not build_no:
        build_no = _not_available

    return build_no


def print_build_number():
    print get_build_number()


def get_model_laptop():
    from ceibal import laptop

    model_laptop = laptops.get_model_laptop()
    if model_laptop is None or not model_laptop:
        model_laptop = _not_available
    return model_laptop


def _parse_firmware_number(firmware_no):
    if firmware_no is None:
        firmware_no = _not_available
    else:
        # try to extract Open Firmware version from OLPC style version
        # string, e.g. "CL2   Q4B11  Q4B"
        if firmware_no.startswith('CL'):
            firmware_no = firmware_no[6:13]
    return firmware_no


def get_firmware_number():
    firmware_no = None
    if os.path.exists(os.path.join(_OFW_TREE, _MODEL)):
        firmware_no = _read_file(os.path.join(_OFW_TREE, _MODEL))
        firmware_no = _parse_firmware_number(firmware_no)
    elif os.path.exists(os.path.join(_PROC_TREE, _MODEL)):
        firmware_no = _read_file(os.path.join(_PROC_TREE, _MODEL))
        firmware_no = _parse_firmware_number(firmware_no)
    elif os.path.exists(os.path.join(_DMI_DIRECTORY, 'bios_version')):
        firmware_no = _read_file(os.path.join(_DMI_DIRECTORY, 'bios_version'))
        if firmware_no is None:
            firmware_no = _not_available
    return firmware_no


def print_firmware_number():
    print get_firmware_number()


def _get_wireless_interfaces():
    try:
        bus = dbus.SystemBus()
        manager_object = bus.get_object(_NM_SERVICE, _NM_PATH)
        network_manager = dbus.Interface(manager_object, _NM_IFACE)
    except dbus.DBusException:
        _logger.warning('Cannot connect to NetworkManager, falling back to'
                        ' static list of devices')
        return ['wlan0', 'eth0']

    interfaces = []
    for device_path in network_manager.GetDevices():
        device_object = bus.get_object(_NM_SERVICE, device_path)
        properties = dbus.Interface(device_object,
                                    'org.freedesktop.DBus.Properties')
        device_type = properties.Get(_NM_DEVICE_IFACE, 'DeviceType')
        if device_type != _NM_DEVICE_TYPE_WIFI:
            continue

        interfaces.append(properties.Get(_NM_DEVICE_IFACE, 'Interface'))

    return interfaces


def get_wireless_firmware():
    environment = os.environ.copy()
    environment['PATH'] = '%s:/usr/sbin' % (environment['PATH'], )
    firmware_info = {}
    for interface in _get_wireless_interfaces():
        try:
            output = subprocess.Popen(['ethtool', '-i', interface],
                                      stdout=subprocess.PIPE,
                                      env=environment).stdout.readlines()
        except OSError:
            _logger.exception('Error running ethtool for %r', interface)
            continue

        try:
            version = ([line for line in output
                        if line.startswith('firmware')][0].split()[1])
        except IndexError:
            _logger.exception('Error parsing ethtool output for %r',
                              interface)
            continue

        firmware_info[interface] = version

    if not firmware_info:
        return _not_available

    if len(firmware_info) == 1:
        return firmware_info.values()[0]

    return ', '.join(['%(interface)s: %(version)s' %
                      {'interface': interface, 'version': version}
                      for interface, version in firmware_info.items()])


def print_wireless_firmware():
    print get_wireless_firmware()


def _read_file(path):
    if os.access(path, os.R_OK) == 0:
        return None

    fd = open(path, 'r')
    value = fd.read()
    fd.close()
    if value:
        value = value.strip('\n')
        return value
    else:
        _logger.debug('No information in file or directory: %s', path)
        return None


def get_license():
    license_file = os.path.join(config.data_path, 'GPLv2')
    lang = os.environ['LANG']
    if lang.endswith('UTF-8'):
        lang = lang[:-6]

    try_file = license_file + '.' + lang
    if os.path.isfile(try_file):
        license_file = try_file
    else:
        try_file = license_file + '.' + lang.split('_')[0]
        if os.path.isfile(try_file):
            license_file = try_file

    try:
        fd = open(license_file)
        # remove 0x0c page breaks which can't be rendered in text views
        license_text = fd.read().replace('\x0c', '')
        fd.close()
    except IOError:
        license_text = _not_available
    return license_text


def get_last_updated_on_field():

    # Get the number of UNIX seconds of the last update date.
    last_update_unix_seconds = {}
    try:
        last_update_unix_seconds = int(os.stat('/var/lib/rpm/Packages').st_mtime)
    except:
        msg_str = _('Information not available.')
        _logger.exception(msg_str)
        return msg_str


    NO_UPDATE_MESSAGE = _('No update yet!')


    # Check once again that 'last_update_unix_seconds' is not empty.
    # You never know !
    if not last_update_unix_seconds:
        return NO_UPDATE_MESSAGE

    if int(last_update_unix_seconds) == 1194004800:
        return NO_UPDATE_MESSAGE


    # If we reached here, we have the last-update-time, but it's in
    # timestamp format.
    # Using python-subprocess-module (no shell involved), to convert
    # it into readable date-format; the hack being used (after
    # removing '-u' option) is the first one mentioned at :
    # http://www.commandlinefu.com/commands/view/3719/convert-unix-timestamp-to-date
    environment = os.environ.copy()
    environment['PATH'] = '%s:/usr/sbin' % (environment['PATH'], )

    last_update_readable_format = {}
    try:
        last_update_readable_format = \
                 subprocess.Popen(['date', '-d',
                                   '1970-01-01 + ' +
                                   str(last_update_unix_seconds) +
                                   ' seconds'],
                                   stdout=subprocess.PIPE,
                                   env=environment).stdout.readlines()[0]
    except:
        msg_str = _('Information not available.')
        _logger.exception(msg_str)
        return msg_str

    if not last_update_readable_format:
        return _('Information not available.')

    # Everything should be fine (hopefully :-) )
    return last_update_readable_format


def get_sugar_version():
    return config.version


def get_plazo():
    from ceibal import env
    path_plazo = env.get_security_root()
    try:
        plazo = _read_file(os.path.join(path_plazo, "blacklist")).split("\n")[0].strip()
        plazo = time.strftime( "%d-%m-%Y",time.strptime(plazo,'%Y%m%d'))
    except:
        plazo = _not_available

    return plazo

def get_act():
    from ceibal import env
    path_act = env.get_updates_root()
    parser = ConfigParser.ConfigParser()
    salida = parser.read(os.path.join(path_act, "mi_version"))
    if salida == []:
        version = _not_available
    else:
        version = ''
        for seccion in parser.sections():
            version = "%s%s: %s\n" %(version,seccion,parser.get(seccion,'version'))
    return version
