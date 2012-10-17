# Copyright (C) 2007, 2008 One Laptop Per Child
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
#
# The timezone config is based on the system-config-date
# (http://fedoraproject.org/wiki/SystemConfig/date) tool.
# Parts of the code were reused.
#

import os
import logging

from gettext import gettext as _
from gi.repository import GConf

_zone_tab = '/usr/share/zoneinfo/zone.tab'
NTPDATE_PATH = '/usr/sbin/ntpdate'
NTP_SERVER_CONFIG_FILENAME = '/etc/ntp/step-tickers'

_logger = logging.getLogger('ControlPanel - TimeZone')


def is_ntp_servers_config_feature_available():
    return os.path.exists(NTPDATE_PATH)


def get_ntp_servers():
    servers = []

    # If the file does not exist, return.
    if not os.path.exists(NTP_SERVER_CONFIG_FILENAME):
        return servers

    f = open(NTP_SERVER_CONFIG_FILENAME, 'r')
    for server in f.readlines():
        servers.append(server.rstrip('\n'))
    f.close()

    return servers


def set_ntp_servers(servers):

    # First remove the old ssid-file, if it exists.
    if os.path.exists(NTP_SERVER_CONFIG_FILENAME):
        try:
            os.remove(NTP_SERVER_CONFIG_FILENAME)
        except:
            _logger.exception('Error removing file.')
            return

    # Do nothing and return, if the values-list is empty
    if len(servers) == 0:
        return

    # If we reach here, we have a non-empty ssid-values-list.
    f = open(NTP_SERVER_CONFIG_FILENAME, 'w')
    for server in servers:
        if len(server) > 0:
            f.write(server + '\n')
    f.close()


def _initialize():
    """Initialize the docstring of the set function"""
    if set_timezone.__doc__ is None:
        # when running under 'python -OO', all __doc__ fields are None,
        # so += would fail -- and this function would be unnecessary anyway.
        return
    timezones = read_all_timezones()
    for timezone in timezones:
        set_timezone.__doc__ += timezone + '\n'


def read_all_timezones(fn=_zone_tab):
    fd = open(fn, 'r')
    lines = fd.readlines()
    fd.close()
    timezones = []
    for line in lines:
        if line.startswith('#'):
            continue
        line = line.split()
        if len(line) > 1:
            timezones.append(line[2])
    timezones.sort()

    for offset in xrange(-12, 13):
        if offset < 0:
            tz = 'GMT%d' % offset
        elif offset > 0:
            tz = 'GMT+%d' % offset
        else:
            tz = 'GMT'
        timezones.append(tz)
    for offset in xrange(-12, 13):
        if offset < 0:
            tz = 'UTC%d' % offset
        elif offset > 0:
            tz = 'UTC+%d' % offset
        else:
            tz = 'UTC'
        timezones.append(tz)
    return timezones


def get_timezone():
    client = GConf.Client.get_default()
    return client.get_string('/desktop/sugar/date/timezone')


def print_timezone():
    print get_timezone()


def set_timezone(timezone):
    """Set the system timezone
    timezone : e.g. 'America/Los_Angeles'
    """
    timezones = read_all_timezones()
    if timezone in timezones:
        os.environ['TZ'] = timezone
        client = GConf.Client.get_default()
        client.set_string('/desktop/sugar/date/timezone', timezone)
    else:
        raise ValueError(_('Error timezone does not exist.'))
    return 1

# inilialize the docstrings for the timezone
_initialize()
