# Copyright (C) 2009 Paraguay Educa, Martin Abente
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
# Foundation, Inc., 51 Franklin St, Fifth Floor, Boston, MA  02110-1301  US

import logging

import dbus
from gi.repository import Gtk
from gi.repository import GConf

import os
import locale
import logging

from xml.etree.cElementTree import ElementTree
from gettext import gettext as _

from jarabe.model import network


from cpsection.modemconfiguration.config import PROVIDERS_PATH, \
                                                PROVIDERS_FORMAT_SUPPORTED, \
                                                COUNTRY_CODES_PATH


def get_connection():
    return network.find_gsm_connection()


def get_modem_settings(callback):
    modem_settings = {}
    connection = get_connection()
    if not connection:
        return modem_settings

    settings = connection.get_settings('gsm')
    for setting in ('username', 'number', 'apn'):
        modem_settings[setting] = settings.get(setting, '')

    # use mutable container for nested function control variable
    secrets_call_done = [False]

    def _secrets_cb(secrets):
        secrets_call_done[0] = True
        if not secrets or not 'gsm' in secrets:
            return

        gsm_secrets = secrets['gsm']
        modem_settings['password'] = gsm_secrets.get('password', '')
        modem_settings['pin'] = gsm_secrets.get('pin', '')

        # sl#3800: We return the settings, via the "_secrets_cb()
        #          method", instead of busy-waiting.
        callback(modem_settings)

    def _secrets_err_cb(err):
        secrets_call_done[0] = True
        if isinstance(err, dbus.exceptions.DBusException) and \
                err.get_dbus_name() == network.NM_AGENT_MANAGER_ERR_NO_SECRETS:
            logging.debug('No GSM secrets present')
        else:
            logging.error('Error retrieving GSM secrets: %s', err)

    # must be called asynchronously as this re-enters the GTK main loop
    #
    # sl#3800: We return the settings, via the "_secrets_cb()" method,
    #          instead of busy-waiting.
    connection.get_secrets('gsm', _secrets_cb, _secrets_err_cb)


def _set_or_clear(_dict, key, value):
    """Update a dictionary value for a specific key. If value is None or
    zero-length, but the key is present in the dictionary, delete that
    dictionary entry."""
    if value:
        _dict[key] = value
        return

    if key in _dict:
        del _dict[key]


def set_modem_settings(modem_settings):
    username = modem_settings.get('username', '')
    password = modem_settings.get('password', '')
    number = modem_settings.get('number', '')
    apn = modem_settings.get('apn', '')
    pin = modem_settings.get('pin', '')

    connection = get_connection()
    if not connection:
        network.create_gsm_connection(username, password, number, apn, pin)
        return

    settings = connection.get_settings()
    gsm_settings = settings['gsm']
    _set_or_clear(gsm_settings, 'username', username)
    _set_or_clear(gsm_settings, 'password', password)
    _set_or_clear(gsm_settings, 'number', number)
    _set_or_clear(gsm_settings, 'apn', apn)
    _set_or_clear(gsm_settings, 'pin', pin)
    connection.update_settings(settings)


def has_providers_db():
    if not os.path.isfile(COUNTRY_CODES_PATH):
        logging.debug("Mobile broadband provider database: Country " \
                          "codes path %s not found.", COUNTRY_CODES_PATH)
        return False
    try:
        tree = ElementTree(file=PROVIDERS_PATH)
    except (IOError, SyntaxError), e:
        logging.debug("Mobile broadband provider database: Could not read " \
                          "provider information %s error=%s", PROVIDERS_PATH)
        return False
    else:
        elem = tree.getroot()
        if elem is None or elem.get('format') != PROVIDERS_FORMAT_SUPPORTED:
            logging.debug("Mobile broadband provider database: Could not " \
                          "read provider information. %s is wrong format.",
                          elem.get('format'))
            return False
        return True


class CountryListStore(Gtk.ListStore):
    COUNTRY_CODE = locale.getdefaultlocale()[0][3:5].lower()

    def __init__(self):
        Gtk.ListStore.__init__(self, str, object)
        codes = {}
        with open(COUNTRY_CODES_PATH) as codes_file:
            for line in codes_file:
                if line.startswith('#'):
                    continue
                code, name = line.split('\t')[:2]
                codes[code.lower()] = name.strip()
        etree = ElementTree(file=PROVIDERS_PATH).getroot()
        self._country_idx = None
        i = 0

        # This dictionary wil store the values, with "country-name" as
        # the key, and "country-code" as the value.
        temp_dict = {}

        for elem in etree.findall('.//country'):
            code = elem.attrib['code']
            if code == self.COUNTRY_CODE:
                self._country_idx = i
            else:
                i += 1
            if code in codes:
                temp_dict[codes[code]] = elem
            else:
                temp_dict[code] = elem

        # Now, sort the list by country-names.
        country_name_keys = temp_dict.keys()
        country_name_keys.sort()

        for country_name in country_name_keys:
            self.append((country_name, temp_dict[country_name]))

    def get_row_providers(self, row):
        return self[row][1]

    def guess_country_row(self):
        if self._country_idx is not None:
            return self._country_idx
        else:
            return 0

    def search_index_by_code(self, code):
        for index in range(0, len(self)):
            if self[index][0] == code:
                return index
        return -1


class ProviderListStore(Gtk.ListStore):
    def __init__(self, elem):
        Gtk.ListStore.__init__(self, str, object)
        for provider_elem in elem.findall('.//provider'):
            apns = provider_elem.findall('.//apn')
            if not apns:
                # Skip carriers with CDMA entries only
                continue
            self.append((provider_elem.find('.//name').text, apns))

    def get_row_plans(self, row):
        return self[row][1]

    def guess_providers_row(self):
        # Simply return the first entry as the default.
        return 0

    def search_index_by_code(self, code):
        for index in range(0, len(self)):
            if self[index][0] == code:
                return index
        return -1


class PlanListStore(Gtk.ListStore):
    LANG_NS_ATTR = '{http://www.w3.org/XML/1998/namespace}lang'
    LANG = locale.getdefaultlocale()[0][:2]
    DEFAULT_NUMBER = '*99#'

    def __init__(self, elems):
        Gtk.ListStore.__init__(self, str, object)
        for apn_elem in elems:
            plan = {}
            names = apn_elem.findall('.//name')
            if names:
                for name in names:
                    if name.get(self.LANG_NS_ATTR) is None:
                        # serviceproviders.xml default value
                        plan['name'] = name.text
                    elif name.get(self.LANG_NS_ATTR) == self.LANG:
                        # Great! We found a name value for our locale!
                        plan['name'] = name.text
                        break
            else:
                plan['name'] = _('Default')
            plan['apn'] = apn_elem.get('value')
            user = apn_elem.find('.//username')
            if user is not None:
                plan['username'] = user.text
            else:
                plan['username'] = ''
            passwd = apn_elem.find('.//password')
            if passwd is not None:
                plan['password'] = passwd.text
            else:
                plan['password'] = ''

            plan['number'] = self.DEFAULT_NUMBER

            self.append((plan['name'], plan))

    def get_row_plan(self, row):
        return self[row][1]

    def guess_plan_row(self):
        # Simply return the first entry as the default.
        return 0

    def search_index_by_code(self, code):
        for index in range(0, len(self)):
            if self[index][0] == code:
                return index
        return -1


def get_gconf_setting_string(gconf_key):
    client = GConf.Client.get_default()
    return client.get_string(gconf_key) or ''

def set_gconf_setting_string(gconf_key, gconf_setting_string_value):
    client = GConf.Client.get_default()
    client.set_string(gconf_key, gconf_setting_string_value)
